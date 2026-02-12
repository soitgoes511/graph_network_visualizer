import math
import re
from collections import Counter
from typing import Dict, Iterable, List

import spacy

TARGET_ENTITY_LABELS = {"PERSON", "ORG", "GPE", "EVENT", "LOC", "PRODUCT", "WORK_OF_ART"}
SUBJECT_DEPS = {"nsubj", "nsubjpass", "csubj", "agent"}
OBJECT_DEPS = {"dobj", "obj", "pobj", "dative", "attr", "oprd"}

MAX_DOC_CHARS = 200_000
MAX_SENTENCES = 1_600
MAX_ENTITIES_PER_SENTENCE = 10
MAX_CO_OCCURRENCE_PAIRS_PER_SENTENCE = 45
MAX_VERB_PAIRS_PER_SENTENCE = 36
MAX_RELATIONS = 8_000
MAX_EVIDENCE_SENTENCES = 4

# Load the language model.
# Make sure "python -m spacy download en_core_web_sm" has been run.
try:
    nlp = spacy.load("en_core_web_sm")
    nlp.max_length = 3_000_000
except OSError:
    print("Spacy model 'en_core_web_sm' not found. Please run 'python -m spacy download en_core_web_sm'")
    nlp = None


def _clean_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "unknown"


def _normalize_entity_key(text: str) -> str:
    normalized = _clean_whitespace(text).lower()
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _sanitize_relation(token_lemma: str) -> str:
    cleaned = re.sub(r"[^a-z0-9_]+", "_", token_lemma.lower()).strip("_")
    return cleaned or "related_to"


def _trim_sentence(text: str, limit: int = 260) -> str:
    sentence = _clean_whitespace(text)
    if len(sentence) <= limit:
        return sentence
    return sentence[: limit - 3].rstrip() + "..."


def _entity_ids_in_subtree(token, token_entity_map: List[str], subtree_cache: Dict[int, tuple]):
    cached = subtree_cache.get(token.i)
    if cached is not None:
        return cached

    seen = set()
    entities = []
    for subtree_token in token.subtree:
        entity_id = token_entity_map[subtree_token.i]
        if not entity_id or entity_id in seen:
            continue

        seen.add(entity_id)
        entities.append(entity_id)

        if len(entities) >= MAX_ENTITIES_PER_SENTENCE:
            break

    cached_entities = tuple(entities)
    subtree_cache[token.i] = cached_entities
    return cached_entities


def _build_concepts(doc, top_n_concepts: int):
    noun_counts = Counter()

    for token in doc:
        if (
            token.pos_ in {"NOUN", "PROPN"}
            and token.is_alpha
            and not token.is_stop
            and not token.is_punct
            and len(token.text) > 2
        ):
            noun_counts[token.lemma_.lower()] += 1

    total_noun_mentions = max(sum(noun_counts.values()), 1)
    concepts = []

    for noun, count in noun_counts.most_common(top_n_concepts):
        concepts.append(
            {
                "id": f"concept:{_slugify(noun)}",
                "text": noun,
                "type": "concept",
                "count": count,
                "relevance": round(count / total_noun_mentions, 4),
            }
        )

    return concepts


def _extract_entities(doc):
    entity_records = {}
    token_entity_map = [None] * len(doc)

    for ent in doc.ents:
        if ent.label_ not in TARGET_ENTITY_LABELS:
            continue

        original_text = _clean_whitespace(ent.text)
        if len(original_text) < 3:
            continue

        normalized_key = _normalize_entity_key(original_text)
        if len(normalized_key) < 2:
            continue

        entity_id = f"entity:{_slugify(normalized_key)}"
        record = entity_records.get(entity_id)
        if not record:
            record = {
                "id": entity_id,
                "text": original_text,
                "type": ent.label_,
                "count": 0,
                "aliases": set(),
            }
            entity_records[entity_id] = record

        if len(original_text) > len(record["text"]):
            record["text"] = original_text
        record["count"] += 1
        record["aliases"].add(original_text)

        for token_index in range(ent.start, ent.end):
            token_entity_map[token_index] = entity_id

    entities = []
    for record in sorted(entity_records.values(), key=lambda item: item["count"], reverse=True):
        entities.append(
            {
                "id": record["id"],
                "text": record["text"],
                "type": record["type"],
                "count": record["count"],
                "aliases": sorted(record["aliases"])[:6],
                "confidence": round(min(0.99, 0.5 + 0.12 * math.log1p(record["count"])), 3),
            }
        )

    return entities, token_entity_map


def _register_relation(
    relation_map,
    source,
    target,
    relation_type,
    weight=1.0,
    confidence=0.5,
    evidence=None,
    predicate=None,
):
    if not source or not target or source == target:
        return

    key = (source, target, relation_type, predicate or "")
    relation = relation_map.get(key)
    if not relation:
        if len(relation_map) >= MAX_RELATIONS:
            return

        relation = {
            "source": source,
            "target": target,
            "relation_type": relation_type,
            "predicate": predicate,
            "weight": 0.0,
            "confidence": confidence,
            "evidence_sentences": [],
        }
        relation_map[key] = relation

    relation["weight"] += float(weight)
    relation["confidence"] = max(relation["confidence"], float(confidence))

    if evidence:
        evidence_text = _trim_sentence(evidence)
        evidence_sentences = relation["evidence_sentences"]
        if (
            evidence_text
            and evidence_text not in evidence_sentences
            and len(evidence_sentences) < MAX_EVIDENCE_SENTENCES
        ):
            evidence_sentences.append(evidence_text)


def _extract_relationships(doc, token_entity_map: List[str]):
    relation_map = {}
    subtree_cache = {}

    for sentence_index, sentence in enumerate(doc.sents):
        if sentence_index >= MAX_SENTENCES:
            break

        evidence_text = _trim_sentence(sentence.text)
        sentence_entities = []
        seen_sentence_entities = set()

        for ent in sentence.ents:
            entity_id = token_entity_map[ent.start]
            if not entity_id or entity_id in seen_sentence_entities:
                continue

            seen_sentence_entities.add(entity_id)
            sentence_entities.append(entity_id)

            if len(sentence_entities) >= MAX_ENTITIES_PER_SENTENCE:
                break

        if len(sentence_entities) >= 2:
            pair_count = 0
            for left_index, left in enumerate(sentence_entities[:-1]):
                for right in sentence_entities[left_index + 1 :]:
                    _register_relation(
                        relation_map,
                        left,
                        right,
                        "CO_OCCURS_IN_SENTENCE",
                        weight=1.0,
                        confidence=0.45,
                        evidence=evidence_text,
                    )
                    pair_count += 1
                    if pair_count >= MAX_CO_OCCURRENCE_PAIRS_PER_SENTENCE:
                        break
                if pair_count >= MAX_CO_OCCURRENCE_PAIRS_PER_SENTENCE:
                    break

        for token in sentence:
            if token.pos_ != "VERB":
                continue

            subject_entities = set()
            object_entities = set()

            for child in token.children:
                if child.dep_ in SUBJECT_DEPS:
                    subject_entities.update(_entity_ids_in_subtree(child, token_entity_map, subtree_cache))
                elif child.dep_ in OBJECT_DEPS:
                    object_entities.update(_entity_ids_in_subtree(child, token_entity_map, subtree_cache))

            if not subject_entities or not object_entities:
                continue

            predicate = _sanitize_relation(token.lemma_)
            relation_type = f"VERB:{predicate.upper()}"
            pair_count = 0

            for subject in sorted(subject_entities):
                for obj in sorted(object_entities):
                    _register_relation(
                        relation_map,
                        subject,
                        obj,
                        relation_type,
                        weight=1.0,
                        confidence=0.62,
                        evidence=evidence_text,
                        predicate=predicate,
                    )
                    pair_count += 1
                    if pair_count >= MAX_VERB_PAIRS_PER_SENTENCE:
                        break
                if pair_count >= MAX_VERB_PAIRS_PER_SENTENCE:
                    break

    relationships = []
    for relation in sorted(relation_map.values(), key=lambda item: item["weight"], reverse=True):
        evidence_sentences = relation.pop("evidence_sentences", [])
        relation["weight"] = round(relation["weight"], 3)
        relation["confidence"] = round(min(1.0, max(0.05, relation["confidence"])), 3)
        relation["evidence_sentences"] = evidence_sentences
        relation["evidence_sentence"] = evidence_sentences[0] if evidence_sentences else ""
        relationships.append(relation)

    return relationships


def _analyze_doc(doc, top_n_concepts: int):
    concepts = _build_concepts(doc, top_n_concepts)
    entities, token_entity_map = _extract_entities(doc)
    relationships = _extract_relationships(doc, token_entity_map)
    return {"concepts": concepts, "entities": entities, "relationships": relationships}


def process_text(text: str, top_n_concepts: int = 12):
    """
    Analyze text and return concepts, normalized entities, and inferred relationships.
    """
    if not nlp or not text:
        return {"concepts": [], "entities": [], "relationships": []}

    doc = nlp(text[:MAX_DOC_CHARS])
    return _analyze_doc(doc, top_n_concepts)


def process_texts(texts: Iterable[str], top_n_concepts: int = 12, batch_size: int = 3):
    if not texts:
        return []

    prepared_texts = [str(text or "")[:MAX_DOC_CHARS] for text in texts]
    if not nlp:
        return [{"concepts": [], "entities": [], "relationships": []} for _ in prepared_texts]

    results = []
    for raw_text, doc in zip(prepared_texts, nlp.pipe(prepared_texts, batch_size=max(1, batch_size))):
        if not raw_text.strip():
            results.append({"concepts": [], "entities": [], "relationships": []})
            continue

        try:
            results.append(_analyze_doc(doc, top_n_concepts))
        except Exception:
            results.append({"concepts": [], "entities": [], "relationships": []})

    return results
