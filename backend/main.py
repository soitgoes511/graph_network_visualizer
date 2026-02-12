import asyncio
import json
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from graph_builder import build_graph_from_data
from nlp_processor import process_text, process_texts
from parser import parse_docx, parse_pdf
from scraper import scrape_url

SAVE_FILE_PATH = "saved_graph.json"

SUM_FIELDS = {"count", "mention_count", "source_count"}
MAX_FIELDS = {"val", "confidence", "degree_centrality", "betweenness", "pagerank", "relevance"}
LIST_MERGE_FIELDS = {"aliases", "source_docs", "evidence_sentences"}

DEFAULT_NODE_LIMIT = 700
DEFAULT_LINK_LIMIT = 2600
LOAD_MORE_NODE_STEP = 500
LOAD_MORE_LINK_STEP = 2200
MAX_NODE_LIMIT = 7000
MAX_LINK_LIMIT = 40000
GRAPH_CACHE_MAX_ITEMS = 4

NODE_TYPE_PRIORITY = {
    "file": 7.0,
    "web": 7.0,
    "PERSON": 6.2,
    "ORG": 5.8,
    "GPE": 5.4,
    "EVENT": 5.1,
    "LOC": 4.9,
    "PRODUCT": 4.6,
    "WORK_OF_ART": 4.5,
    "concept": 3.4,
    "external": 2.8,
}

RELATION_PRIORITY = {
    "VERB:": 1.6,
    "MENTIONS_ENTITY": 1.35,
    "MENTIONS_CONCEPT": 1.2,
    "CO_OCCURS_IN_SENTENCE": 1.0,
    "LINKS_TO_EXTERNAL": 0.65,
}

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections[:]:
            try:
                await connection.send_text(message)
            except Exception:
                self.disconnect(connection)


manager = ConnectionManager()
graph_cache: Dict[str, Dict[str, Any]] = {}
graph_cache_order: List[str] = []


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _compact_text(value: str, limit: int = 280) -> str:
    compact = " ".join((value or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def _merge_unique_list(existing: Any, new_values: Any, limit: int = 8) -> List[str]:
    merged = []
    seen = set()

    for value in list(existing or []) + list(new_values or []):
        if value is None:
            continue
        item = str(value).strip()
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
        if len(merged) >= limit:
            break

    return merged


def _sanitize_limit(raw_value: Any, default: int, minimum: int, maximum: int) -> int:
    parsed = int(_safe_float(raw_value, default))
    return max(minimum, min(maximum, parsed))


def _node_interest_score(node: Dict[str, Any], degree_hint: float) -> float:
    node_type = str(node.get("type", "unknown"))
    base = NODE_TYPE_PRIORITY.get(node_type, NODE_TYPE_PRIORITY.get(node_type.upper(), 2.6))
    count_score = min(16.0, _safe_float(node.get("count", 0), 0.0) * 0.22)
    confidence_score = _safe_float(node.get("confidence", 0.0), 0.0) * 1.8
    value_score = min(12.0, _safe_float(node.get("val", 0.0), 0.0) * 0.18)
    connectivity_score = min(12.0, degree_hint * 0.14)
    return base + count_score + confidence_score + value_score + connectivity_score


def _link_interest_score(link: Dict[str, Any]) -> float:
    relation_type = str(link.get("relation_type", "RELATED_TO"))
    relation_boost = 1.0
    for relation_prefix, boost in RELATION_PRIORITY.items():
        if relation_type.startswith(relation_prefix):
            relation_boost = boost
            break

    weight = max(0.1, _safe_float(link.get("weight", 1.0), 1.0))
    confidence = max(0.05, _safe_float(link.get("confidence", 0.5), 0.5))
    occurrences = max(1.0, _safe_float(link.get("occurrences", 1), 1))
    return (weight * 0.95 + occurrences * 0.55 + confidence * 1.6) * relation_boost


def _store_graph_cache_entry(nodes: List[Dict[str, Any]], links: List[Dict[str, Any]], pinned_ids: List[str]) -> str:
    query_id = uuid4().hex
    graph_cache[query_id] = {
        "nodes": nodes,
        "links": links,
        "pinned_ids": pinned_ids,
    }
    graph_cache_order.append(query_id)

    while len(graph_cache_order) > GRAPH_CACHE_MAX_ITEMS:
        oldest_key = graph_cache_order.pop(0)
        graph_cache.pop(oldest_key, None)

    return query_id


def _select_graph_subset(
    all_nodes: List[Dict[str, Any]],
    all_links: List[Dict[str, Any]],
    pinned_ids: List[str],
    node_limit: int,
    link_limit: int,
):
    node_by_id: Dict[str, Dict[str, Any]] = {}
    for node in all_nodes:
        node_id = node.get("id")
        if node_id and node_id not in node_by_id:
            node_by_id[node_id] = node

    if not node_by_id:
        return [], [], {"visible_nodes": 0, "visible_links": 0, "total_nodes": 0, "total_links": 0, "truncated": False}

    safe_node_limit = max(len(pinned_ids), _sanitize_limit(node_limit, DEFAULT_NODE_LIMIT, 120, MAX_NODE_LIMIT))
    safe_link_limit = _sanitize_limit(link_limit, DEFAULT_LINK_LIMIT, 200, MAX_LINK_LIMIT)

    degree_hint: Dict[str, float] = {}
    for link in all_links:
        source = link.get("source")
        target = link.get("target")
        if not source or not target:
            continue

        weighted = max(0.1, _safe_float(link.get("weight", 1.0), 1.0))
        degree_hint[source] = degree_hint.get(source, 0.0) + weighted
        degree_hint[target] = degree_hint.get(target, 0.0) + weighted

    selected_ids: List[str] = []
    selected_id_set = set()

    for pinned_id in pinned_ids:
        if pinned_id in node_by_id and pinned_id not in selected_id_set:
            selected_ids.append(pinned_id)
            selected_id_set.add(pinned_id)

    ranked_node_ids = sorted(
        (node_id for node_id in node_by_id if node_id not in selected_id_set),
        key=lambda node_id: _node_interest_score(node_by_id[node_id], degree_hint.get(node_id, 0.0)),
        reverse=True,
    )

    for node_id in ranked_node_ids:
        if len(selected_ids) >= safe_node_limit:
            break
        selected_ids.append(node_id)
        selected_id_set.add(node_id)

    subset_links = []
    for link in all_links:
        source = link.get("source")
        target = link.get("target")
        if source in selected_id_set and target in selected_id_set:
            subset_links.append(link)

    if len(subset_links) > safe_link_limit:
        subset_links = sorted(subset_links, key=_link_interest_score, reverse=True)[:safe_link_limit]

    connected_node_ids = set(pinned_ids)
    for link in subset_links:
        connected_node_ids.add(link.get("source"))
        connected_node_ids.add(link.get("target"))

    subset_nodes = [node_by_id[node_id] for node_id in selected_ids if node_id in connected_node_ids and node_id in node_by_id]
    if not subset_nodes:
        subset_nodes = [node_by_id[node_id] for node_id in selected_ids if node_id in node_by_id]

    summary = {
        "visible_nodes": len(subset_nodes),
        "visible_links": len(subset_links),
        "total_nodes": len(node_by_id),
        "total_links": len(all_links),
        "node_limit": safe_node_limit,
        "link_limit": safe_link_limit,
        "truncated": len(subset_nodes) < len(node_by_id) or len(subset_links) < len(all_links),
    }
    return subset_nodes, subset_links, summary


def _upsert_node(node_index: Dict[str, Dict[str, Any]], node: Dict[str, Any]):
    node_id = node.get("id")
    if not node_id:
        return

    normalized = dict(node)
    normalized.setdefault("title", str(node_id))
    normalized.setdefault("type", "unknown")

    for key in LIST_MERGE_FIELDS:
        if isinstance(normalized.get(key), set):
            normalized[key] = sorted(normalized[key])

    existing = node_index.get(node_id)
    if not existing:
        node_index[node_id] = normalized
        return

    for key, value in normalized.items():
        if value is None:
            continue

        if key in SUM_FIELDS and isinstance(value, (int, float)):
            existing[key] = round(_safe_float(existing.get(key), 0.0) + _safe_float(value, 0.0), 5)
        elif key in MAX_FIELDS and isinstance(value, (int, float)):
            existing[key] = max(_safe_float(existing.get(key), 0.0), _safe_float(value, 0.0))
        elif key in LIST_MERGE_FIELDS and isinstance(value, (list, set, tuple)):
            existing[key] = _merge_unique_list(existing.get(key), value)
        elif key in {"text", "full_text"} and isinstance(value, str):
            current_value = existing.get(key, "")
            if len(value) > len(current_value):
                existing[key] = value
        elif key == "title":
            current_title = str(existing.get("title", ""))
            if not current_title or current_title == str(node_id) or len(str(value)) > len(current_title):
                existing[key] = value
        else:
            current = existing.get(key)
            if key not in existing or current is None or current == "" or current == 0:
                existing[key] = value


def _register_link(link_index: Dict[Any, Dict[str, Any]], link: Dict[str, Any]):
    source = link.get("source")
    target = link.get("target")
    if not source or not target or source == target:
        return

    relation_type = link.get("relation_type", "RELATED_TO")
    predicate = (link.get("predicate") or "").strip()
    key = (source, target, relation_type, predicate)

    edge = link_index.get(key)
    if not edge:
        edge = {
            "source": source,
            "target": target,
            "relation_type": relation_type,
            "weight": 0.0,
            "confidence": _clamp(_safe_float(link.get("confidence", 0.5), 0.5), 0.01, 1.0),
            "occurrences": 0,
            "source_docs": [],
            "evidence_sentences": [],
        }
        if predicate:
            edge["predicate"] = predicate
        link_index[key] = edge

    edge["weight"] += max(0.1, _safe_float(link.get("weight", 1.0), 1.0))
    edge["occurrences"] += max(1, int(_safe_float(link.get("occurrences", 1), 1)))
    edge["confidence"] = max(edge["confidence"], _clamp(_safe_float(link.get("confidence", 0.5), 0.5), 0.01, 1.0))

    source_doc = str(link.get("source_doc", "")).strip()
    if source_doc:
        edge["source_docs"] = _merge_unique_list(edge.get("source_docs"), [source_doc], limit=10)

    anchor_text = _compact_text(str(link.get("anchor_text", "")).strip(), 180)
    if anchor_text and not edge.get("anchor_text"):
        edge["anchor_text"] = anchor_text

    raw_sentences = []
    evidence_sentence = _compact_text(str(link.get("evidence_sentence", "")).strip(), 320)
    if evidence_sentence:
        raw_sentences.append(evidence_sentence)

    for sentence in link.get("evidence_sentences", []) or []:
        compact = _compact_text(str(sentence), 320)
        if compact:
            raw_sentences.append(compact)

    if raw_sentences:
        edge["evidence_sentences"] = _merge_unique_list(edge.get("evidence_sentences"), raw_sentences, limit=6)


def _finalize_nodes(node_index: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    finalized = []
    for node in node_index.values():
        normalized = dict(node)

        if isinstance(normalized.get("full_text"), str):
            full_text = normalized.pop("full_text")
            normalized["text_length"] = len(full_text)
            normalized["text_preview"] = _compact_text(full_text, 400)

        if isinstance(normalized.get("text"), str):
            raw_text = normalized["text"]
            normalized["text_length"] = max(len(raw_text), int(normalized.get("text_length", 0)))
            normalized["text_preview"] = _compact_text(raw_text, 400)
            normalized["text"] = raw_text[:1200]

        if isinstance(normalized.get("aliases"), list):
            normalized["aliases"] = normalized["aliases"][:8]

        finalized.append(normalized)

    return finalized


def _finalize_links(link_index: Dict[Any, Dict[str, Any]]) -> List[Dict[str, Any]]:
    finalized = []
    for edge in link_index.values():
        normalized = dict(edge)
        normalized["weight"] = round(_safe_float(normalized.get("weight", 1.0), 1.0), 3)
        normalized["confidence"] = round(_clamp(_safe_float(normalized.get("confidence", 0.5), 0.5), 0.01, 1.0), 3)
        normalized["source_docs"] = list(normalized.get("source_docs", []))
        normalized["evidence_sentences"] = list(normalized.get("evidence_sentences", []))
        normalized["evidence_sentence"] = (
            normalized["evidence_sentences"][0]
            if normalized["evidence_sentences"]
            else str(normalized.get("anchor_text", ""))
        )
        finalized.append(normalized)

    return finalized


@app.get("/")
def read_root():
    return {"message": "Graph Network Visualizer API"}


@app.websocket("/ws/logs")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.post("/process")
async def process_data(
    urls: Optional[str] = Form(None),
    depth: int = Form(1),
    files: List[UploadFile] = File(None),
    node_limit: int = Form(DEFAULT_NODE_LIMIT),
    link_limit: int = Form(DEFAULT_LINK_LIMIT),
):
    loop = asyncio.get_running_loop()

    def log_callback(message: str):
        asyncio.run_coroutine_threadsafe(manager.broadcast(message), loop)

    log_callback("Starting data processing...")
    depth = max(1, min(depth, 4))

    node_index: Dict[str, Dict[str, Any]] = {}
    link_index: Dict[Any, Dict[str, Any]] = {}

    if urls:
        try:
            parsed_urls = json.loads(urls)
            if not isinstance(parsed_urls, list):
                raise ValueError("URLs payload must be a JSON array.")
        except Exception as error:
            log_callback(f"Invalid URL payload: {error}")
            parsed_urls = []

        for raw_url in parsed_urls:
            url = str(raw_url).strip()
            if not url.startswith("http"):
                continue

            try:
                log_callback(f"Queuing scrape for {url}...")
                scraped_data = await loop.run_in_executor(None, scrape_url, url, depth, log_callback)
                for node in scraped_data.get("nodes", []):
                    _upsert_node(node_index, node)
                for link in scraped_data.get("links", []):
                    _register_link(link_index, link)
            except Exception as error:
                log_callback(f"Error processing URL {url}: {error}")
                print(f"Error processing URL {url}: {error}")

    if files:
        for upload in files:
            try:
                log_callback(f"Reading file: {upload.filename}")
                content = await upload.read()
                if not content:
                    continue

                filename = upload.filename.lower()
                parsed_file = None
                if filename.endswith(".pdf"):
                    parsed_file = await loop.run_in_executor(None, parse_pdf, content, log_callback)
                elif filename.endswith(".docx"):
                    parsed_file = await loop.run_in_executor(None, parse_docx, content, log_callback)
                else:
                    log_callback(f"Skipping unsupported file type: {upload.filename}")
                    continue

                if not parsed_file:
                    continue

                file_text = parsed_file.get("text", "")
                file_node_id = f"file:{upload.filename}"
                _upsert_node(
                    node_index,
                    {
                        "id": file_node_id,
                        "title": upload.filename,
                        "type": "file",
                        "text": file_text[:1200],
                        "full_text": file_text,
                        "val": 10,
                    },
                )

                for link_url in parsed_file.get("links", []):
                    if not isinstance(link_url, str):
                        continue
                    normalized_url = link_url.strip()
                    if not normalized_url.startswith("http"):
                        continue

                    _upsert_node(
                        node_index,
                        {
                            "id": normalized_url,
                            "title": normalized_url,
                            "type": "external",
                            "val": 4,
                        },
                    )
                    _register_link(
                        link_index,
                        {
                            "source": file_node_id,
                            "target": normalized_url,
                            "relation_type": "LINKS_TO_EXTERNAL",
                            "weight": 1.0,
                            "confidence": 1.0,
                            "source_doc": upload.filename,
                            "evidence_sentence": "Hyperlink extracted from uploaded document.",
                        },
                    )
            except Exception as error:
                log_callback(f"Error processing file {upload.filename}: {error}")
                print(f"Error processing file {upload.filename}: {error}")

    log_callback("Running NLP analysis on content...")
    source_nodes = [
        node
        for node in list(node_index.values())
        if node.get("type") in {"web", "file"} and (node.get("full_text") or node.get("text"))
    ]

    analysis_by_source: Dict[str, Dict[str, Any]] = {}
    analysis_inputs = []

    for source_node in source_nodes:
        source_id = source_node["id"]
        text = source_node.get("full_text") or source_node.get("text")
        if not text:
            continue

        analysis_inputs.append((source_id, text))

    if analysis_inputs:
        source_ids = [item[0] for item in analysis_inputs]
        source_texts = [item[1] for item in analysis_inputs]

        try:
            log_callback(f"Analyzing {len(source_texts)} source document(s) with batched NLP...")
            batched_results = await loop.run_in_executor(None, process_texts, source_texts, 14)
            if len(batched_results) != len(source_ids):
                raise RuntimeError("Batched NLP returned mismatched result count.")

            analysis_by_source = {source_id: batched_results[index] for index, source_id in enumerate(source_ids)}
        except Exception as error:
            log_callback(f"Batched NLP failed ({error}). Falling back to per-source analysis.")
            for source_id, text in analysis_inputs:
                try:
                    analysis_by_source[source_id] = await loop.run_in_executor(None, process_text, text, 14)
                except Exception as nlp_error:
                    log_callback(f"NLP failed for {source_id}: {nlp_error}")

    for source_node in source_nodes:
        source_id = source_node["id"]
        analysis = analysis_by_source.get(source_id)
        if not analysis:
            continue

        try:
            concepts = analysis.get("concepts", [])
            entities = analysis.get("entities", [])
            relationships = analysis.get("relationships", [])
        except Exception:
            continue

        for concept in concepts:
            concept_id = concept.get("id")
            if not concept_id:
                continue

            _upsert_node(
                node_index,
                {
                    "id": concept_id,
                    "title": concept.get("text", concept_id),
                    "type": "concept",
                    "count": concept.get("count", 0),
                    "relevance": concept.get("relevance", 0.0),
                    "val": 2.0 + _safe_float(concept.get("count", 0), 0.0) * 0.5,
                },
            )
            _register_link(
                link_index,
                {
                    "source": source_id,
                    "target": concept_id,
                    "relation_type": "MENTIONS_CONCEPT",
                    "weight": max(1.0, _safe_float(concept.get("count", 1), 1)),
                    "confidence": _clamp(_safe_float(concept.get("relevance", 0.35), 0.35), 0.2, 1.0),
                    "source_doc": source_id,
                },
            )

        for entity in entities:
            entity_id = entity.get("id")
            if not entity_id:
                continue

            _upsert_node(
                node_index,
                {
                    "id": entity_id,
                    "title": entity.get("text", entity_id),
                    "type": entity.get("type", "ENTITY"),
                    "count": entity.get("count", 0),
                    "aliases": entity.get("aliases", []),
                    "confidence": entity.get("confidence", 0.5),
                    "val": 3.5 + min(6.0, _safe_float(entity.get("count", 0), 0.0)),
                },
            )
            _register_link(
                link_index,
                {
                    "source": source_id,
                    "target": entity_id,
                    "relation_type": "MENTIONS_ENTITY",
                    "weight": max(1.0, _safe_float(entity.get("count", 1), 1)),
                    "confidence": _clamp(_safe_float(entity.get("confidence", 0.5), 0.5), 0.2, 1.0),
                    "source_doc": source_id,
                },
            )

        for relation in relationships:
            source_entity = relation.get("source")
            target_entity = relation.get("target")
            if not source_entity or not target_entity:
                continue

            if source_entity not in node_index:
                _upsert_node(
                    node_index,
                    {
                        "id": source_entity,
                        "title": source_entity.split(":", 1)[-1].replace("_", " "),
                        "type": "ENTITY",
                    },
                )
            if target_entity not in node_index:
                _upsert_node(
                    node_index,
                    {
                        "id": target_entity,
                        "title": target_entity.split(":", 1)[-1].replace("_", " "),
                        "type": "ENTITY",
                    },
                )

            _register_link(
                link_index,
                {
                    "source": source_entity,
                    "target": target_entity,
                    "relation_type": relation.get("relation_type", "RELATED_TO"),
                    "predicate": relation.get("predicate"),
                    "weight": max(0.5, _safe_float(relation.get("weight", 1.0), 1.0)),
                    "confidence": _clamp(_safe_float(relation.get("confidence", 0.5), 0.5), 0.05, 1.0),
                    "evidence_sentence": relation.get("evidence_sentence", ""),
                    "evidence_sentences": relation.get("evidence_sentences", []),
                    "source_doc": source_id,
                },
            )

    all_nodes = _finalize_nodes(node_index)
    all_links = _finalize_links(link_index)

    pinned_ids = [node["id"] for node in all_nodes if node.get("id") and node.get("type") in {"web", "file"}]
    safe_node_limit = _sanitize_limit(node_limit, DEFAULT_NODE_LIMIT, 120, MAX_NODE_LIMIT)
    safe_link_limit = _sanitize_limit(link_limit, DEFAULT_LINK_LIMIT, 200, MAX_LINK_LIMIT)

    query_id = _store_graph_cache_entry(all_nodes, all_links, pinned_ids)
    preview_nodes, preview_links, preview_summary = _select_graph_subset(
        all_nodes,
        all_links,
        pinned_ids,
        safe_node_limit,
        safe_link_limit,
    )

    log_callback(
        "Building graph network preview "
        f"({len(preview_nodes)} nodes / {len(preview_links)} links from {len(all_nodes)} / {len(all_links)})..."
    )
    graph_data = await loop.run_in_executor(None, build_graph_from_data, preview_nodes, preview_links)
    graph_data["meta"] = {
        "query_id": query_id,
        **preview_summary,
        "load_more_node_step": LOAD_MORE_NODE_STEP,
        "load_more_link_step": LOAD_MORE_LINK_STEP,
    }
    log_callback(
        "Processing complete. Showing "
        f"{preview_summary['visible_nodes']} of {preview_summary['total_nodes']} nodes and "
        f"{preview_summary['visible_links']} of {preview_summary['total_links']} links."
    )
    return graph_data


class GraphData(BaseModel):
    nodes: List[dict]
    links: List[dict]
    insights: Optional[dict] = None
    meta: Optional[dict] = None


class GraphViewRequest(BaseModel):
    query_id: str
    node_limit: Optional[int] = None
    link_limit: Optional[int] = None


@app.post("/graph_view")
async def graph_view(data: GraphViewRequest):
    cached_graph = graph_cache.get(data.query_id)
    if not cached_graph:
        raise HTTPException(status_code=404, detail="Graph cache expired. Please run processing again.")

    safe_node_limit = _sanitize_limit(data.node_limit, DEFAULT_NODE_LIMIT, 120, MAX_NODE_LIMIT)
    safe_link_limit = _sanitize_limit(data.link_limit, DEFAULT_LINK_LIMIT, 200, MAX_LINK_LIMIT)

    preview_nodes, preview_links, preview_summary = _select_graph_subset(
        cached_graph.get("nodes", []),
        cached_graph.get("links", []),
        cached_graph.get("pinned_ids", []),
        safe_node_limit,
        safe_link_limit,
    )

    loop = asyncio.get_running_loop()
    graph_data = await loop.run_in_executor(None, build_graph_from_data, preview_nodes, preview_links)
    graph_data["meta"] = {
        "query_id": data.query_id,
        **preview_summary,
        "load_more_node_step": LOAD_MORE_NODE_STEP,
        "load_more_link_step": LOAD_MORE_LINK_STEP,
    }
    return graph_data


@app.post("/save_graph")
async def save_graph(data: GraphData):
    try:
        with open(SAVE_FILE_PATH, "w", encoding="utf-8") as file_obj:
            json.dump(data.model_dump(), file_obj, ensure_ascii=False)
        return {"message": "Graph saved successfully"}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.get("/load_graph")
async def load_graph():
    try:
        with open(SAVE_FILE_PATH, "r", encoding="utf-8") as file_obj:
            data = json.load(file_obj)
        return data
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="No saved graph found")
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))
