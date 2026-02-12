import spacy
from collections import Counter
import string

# Load the language model
# Make sure "python -m spacy download en_core_web_sm" has been run
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("Spacy model 'en_core_web_sm' not found. Please run 'python -m spacy download en_core_web_sm'")
    nlp = None

def process_text(text: str, top_n_concepts: int = 5):
    """
    Analyzes text to extract key concepts (frequent nouns) and named entities.
    
    Args:
        text (str): The text content to analyze.
        top_n_concepts (int): Number of top frequent nouns to return as concepts.
        
    Returns:
        dict: {
            "concepts": [{"text": str, "type": "concept", "count": int}, ...],
            "entities": [{"text": str, "type": str (e.g. PER, ORG, GPE)}, ...]
        }
    """
    if not nlp or not text:
        return {"concepts": [], "entities": []}

    # Increase max length for large documents if necessary
    nlp.max_length = 2000000 
    
    doc = nlp(text[:100000]) # Limit processing to first 100k chars for performance

    # 1. Extract Concepts (Frequent Nouns/Propn)
    # Filter for Nouns and Proper Nouns, exclude stop words and punctuation
    nouns = [
        token.lemma_.lower() 
        for token in doc 
        if token.pos_ in ["NOUN", "PROPN"] 
        and not token.is_stop 
        and not token.is_punct
        and len(token.text) > 2
    ]
    
    # Calculate frequency
    noun_counts = Counter(nouns)
    
    # Get top N concepts
    concepts = []
    for noun, count in noun_counts.most_common(top_n_concepts):
        concepts.append({
            "text": noun, # Use lemma
            "type": "concept",
            "count": count
        })

    # 2. Extract Named Entities
    # Filter for specific entity types we care about
    # PERSON: People, including fictional.
    # ORG: Companies, agencies, institutions, etc.
    # GPE: Countries, cities, states.
    # EVENT: Named hurricanes, battles, wars, sports events, etc.
    target_ent_labels = ["PERSON", "ORG", "GPE", "EVENT", "LOC", "PRODUCT", "WORK_OF_ART"]
    
    entities = []
    seen_entities = set()
    
    for ent in doc.ents:
        if ent.label_ in target_ent_labels:
            # Clean entity text
            ent_text = ent.text.strip()
            # Avoid duplicates and very short entities
            if ent_text.lower() not in seen_entities and len(ent_text) > 2:
                entities.append({
                    "text": ent_text,
                    "type": ent.label_
                })
                seen_entities.add(ent_text.lower())
    
    return {
        "concepts": concepts,
        "entities": entities
    }
