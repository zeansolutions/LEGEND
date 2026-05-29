# -*- coding: utf-8 -*-
"""
🪐 LEGEND Core Utilities Module (core_utils.py)
Provides unified, thread-safe, and highly optimized common features.
1. Thread-safe SQLite Connection Manager
2. Unified Arabic normalization and stemming utilities
3. Resilient LLM API caller with fallbacks and local GGUF loading
4. Semantic Web Exporter (RDF/OWL, JSON-LD, SPARQL structures)
5. Wikidata Entity Enrichment Client
6. Lite Lexical & Semantic Jaccard-vector search
7. Temporal Filtering logic helper
"""

import os
import re
import sys
import json
import time
import sqlite3
import requests
import networkx as nx
from typing import List, Dict, Any, Tuple, Set, Optional
from contextlib import contextmanager

# =====================================================================
# 1. Thread-Safe SQLite Connection Context Manager
# =====================================================================


@contextmanager
def get_db(db_path: str):
    """
    Thread-safe context manager to handle SQLite connections securely.
    Ensures rollback on error, commit on success, and proper connection closing.
    """
    conn = sqlite3.connect(db_path, timeout=30.0)
    # Enable WAL mode for better concurrency and write speed
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
    except sqlite3.OperationalError:
        pass

    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


# =====================================================================
# 2. Unified Arabic Normalization & Stemming Utilities
# =====================================================================


def normalize_arabic(text: str, remove_separators: bool = False) -> str:
    """
    Unified Arabic text normalization.
    Diacritics removal, unifying hamzas, alif layenas, and tah marbutas.
    Optionally removes underscores and hyphens.
    """
    if not text or not isinstance(text, str):
        return ""

    # Remove diacritics (harakaat)
    diacritics = [
        "\u064b",
        "\u064c",
        "\u064d",
        "\u064e",
        "\u064f",
        "\u0650",
        "\u0651",
        "\u0652",  # Standard tashkeel
        "\u0670",  # Dagger alif
    ]
    for d in diacritics:
        text = text.replace(d, "")

    # Normalize Alifs / Hamzas
    text = re.sub(r"[أإآإ]", "ا", text)

    # Normalize Teh Marbuta/Heh
    text = text.replace("ة", "ه")

    # Normalize Alef Layena / Ya'
    text = text.replace("ى", "ي")

    if remove_separators:
        text = text.replace("_", " ").replace("-", " ")

    # Strip double spaces and surrounding spaces
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def stem_arabic(word: str) -> Set[str]:
    """
    Arabic Morphological Stemmer (Light Stemmer).
    Returns candidate stems for a given word by stripping common prefixes/suffixes.
    """
    word = normalize_arabic(word, remove_separators=True)
    if not word or len(word) < 2:
        return {word} if word else set()

    candidates = {word}

    # 1. Definite articles and prefixes
    article_prefixes = ["وال", "بال", "كال", "فال", "لل", "ال"]
    current = word
    for prefix in article_prefixes:
        if current.startswith(prefix) and len(current) > len(prefix) + 1:
            stripped = current[len(prefix) :]
            candidates.add(stripped)
            current = stripped
            break

    # 2. Preposition/conjunction prefixes
    simple_prefixes = ["و", "ب", "ل", "ف", "ك", "س", "ا", "ت", "ي", "ن"]
    for base in list(candidates):
        for p in simple_prefixes:
            if base.startswith(p) and len(base) > 2:
                candidates.add(base[len(p) :])

    # 3. Imperfect tense prefixes
    verb_prefixes = ["يت", "تت", "نت", "ات", "است"]
    for base in list(candidates):
        for vp in verb_prefixes:
            if base.startswith(vp) and len(base) > len(vp) + 1:
                candidates.add(base[len(vp) :])

    # 4. Suffixes
    suffixes = [
        "ات",
        "ون",
        "ين",
        "ها",
        "هم",
        "همس",
        "همش",
        "هن",
        "تم",
        "تن",
        "نا",
        "وا",
        "ته",
        "يه",
        "ني",
        "كم",
        "ك",
        "ه",
        "ي",
        "ت",
    ]
    for base in list(candidates):
        for s in suffixes:
            if base.endswith(s) and len(base) > len(s) + 1:
                candidates.add(base[: -len(s)])

    # 5. Remove teh marbuta/heh at the end (only for words > 3 characters)
    for base in list(candidates):
        if base.endswith("ه") and len(base) > 3:
            candidates.add(base[:-1])

    return {c for c in candidates if len(c) >= 2}


def char_similarity(s1: str, s2: str) -> float:
    """Calculates character-level Jaccard similarity between two strings."""
    n1 = normalize_arabic(s1, remove_separators=True)
    n2 = normalize_arabic(s2, remove_separators=True)
    if not n1 and not n2:
        return 1.0
    if not n1 or not n2:
        return 0.0
    set1 = set(n1)
    set2 = set(n2)
    intersection = set1.intersection(set2)
    union = set1.union(set2)
    return len(intersection) / len(union) if union else 0.0


def strip_arabic_affixes(w: str) -> Set[str]:
    """Lightweight compatibility wrapper for engine's strip_affixes methods."""
    return stem_arabic(w)


# =====================================================================
# 3. Resilient LLM API Caller with Fallbacks and Local Inference
# =====================================================================

_local_llm = None
_local_llm_path = None


def get_local_llm(model_name: str) -> Any:
    """Loads or retrieves the local Llama model via llama-cpp-python in a memory-efficient manner."""
    global _local_llm, _local_llm_path

    # Calculate path relative to project folder
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # If currently in a subdirectory (like cli), adjust
    if os.path.basename(os.path.dirname(os.path.abspath(__file__))) == "legend-v4":
        base_dir = os.path.dirname(os.path.abspath(__file__))

    model_path = os.path.join(base_dir, "models", model_name)
    if not os.path.exists(model_path):
        # Check standard paths
        alternate_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "models", model_name
        )
        if os.path.exists(alternate_path):
            model_path = alternate_path

    if _local_llm is None or _local_llm_path != model_path:
        from llama_cpp import Llama

        _local_llm = None  # Force garbage collection
        _local_llm = Llama(
            model_path=model_path,
            n_gpu_layers=-1,  # Auto use GPU if available
            n_ctx=4096,
            n_threads=4,
            verbose=False,
        )
        _local_llm_path = model_path
    return _local_llm


def call_llm_api(
    provider: str,
    api_key: str,
    model: str,
    prompt: str,
    logs: Optional[List[str]] = None,
) -> str:
    """
    Consolidated, thread-safe, and resilient LLM connector supporting Google Gemini,
    Groq, OpenRouter, and Local GGUF engines. Features exponential backoff & fallbacks.
    """
    if logs is None:
        logs = []

    max_retries = 3
    backoff = 1.5

    for attempt in range(max_retries):
        try:
            prov_clean = provider.strip().lower()
            if prov_clean == "google":
                logs.append(
                    f"🔄 [Google API]: Connecting using model '{model}' (Attempt {attempt + 1}/{max_retries})..."
                )
                import google.generativeai as genai

                genai.configure(api_key=api_key)
                m = genai.GenerativeModel(model)
                response = m.generate_content(
                    prompt,
                    generation_config={
                        "max_output_tokens": 8192,
                        "temperature": 0.1,
                    },
                )
                return response.text.strip()

            elif prov_clean == "local":
                logs.append(
                    f"🔄 [Local Engine]: Initializing CPU/GPU local GGUF model '{model}'..."
                )
                llm = get_local_llm(model)
                response = llm.create_chat_completion(
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=4096,
                    temperature=0.1,
                )
                return response["choices"][0]["message"]["content"].strip()

            else:
                if prov_clean == "groq":
                    url = "https://api.groq.com/openai/v1/chat/completions"
                elif prov_clean == "openrouter":
                    url = "https://openrouter.ai/api/v1/chat/completions"
                else:
                    raise ValueError(f"Unsupported LLM provider: {provider}")

                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }
                if prov_clean == "openrouter":
                    headers["HTTP-Referer"] = "http://localhost:8000"
                    headers["X-Title"] = "LEGEND Neuro-Symbolic Agent"

                data = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 4096,
                }

                logs.append(
                    f"🔄 [{provider.upper()} API]: Calling chat completions for model '{model}'..."
                )
                response = requests.post(url, headers=headers, json=data, timeout=45)
                response.raise_for_status()
                res_json = response.json()
                return res_json["choices"][0]["message"]["content"].strip()

        except Exception as e:
            logs.append(f"⚠️ Connection attempt {attempt + 1} failed: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(backoff)
                backoff *= 2.0
            else:
                # Handle Google fallback chain specifically
                if prov_clean == "google" and "gemma" in model.lower():
                    sibling = (
                        "gemma-2-27b-it" if "27b" not in model else "gemini-1.5-flash"
                    )
                    logs.append(f"⚠️ Falling back to sibling model '{sibling}'...")
                    try:
                        import google.generativeai as genai

                        genai.configure(api_key=api_key)
                        m = genai.GenerativeModel(sibling)
                        response = m.generate_content(prompt)
                        return response.text.strip()
                    except Exception as e2:
                        logs.append(f"⚠️ Sibling model fallback failed: {str(e2)}")

                # Final failover to stable flash model
                if prov_clean == "google":
                    logs.append(
                        "⚠️ Attempting final emergency fallback to 'gemini-2.5-flash'..."
                    )
                    try:
                        import google.generativeai as genai

                        genai.configure(api_key=api_key)
                        m = genai.GenerativeModel("gemini-2.5-flash")
                        response = m.generate_content(prompt)
                        return response.text.strip()
                    except Exception as e3:
                        raise RuntimeError(
                            f"All primary & fallback LLM connection attempts failed: {str(e3)}"
                        )
                raise e


# =====================================================================
# 4. Semantic Web Exporter (RDF/OWL & JSON-LD Exporters)
# =====================================================================


def export_to_rdf(graph: nx.DiGraph, format: str = "xml") -> str:
    """
    Generates a formal, semantic web-compatible representation of the knowledge graph.
    Outputs RDF/XML or Turtle (TTL) syntax.
    """
    output = []
    if format == "xml":
        # Generate clean RDF/XML
        output.append('<?xml version="1.0" encoding="utf-8"?>')
        output.append(
            '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        )
        output.append('         xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"')
        output.append('         xmlns:legend="http://legend.ai/ontology#">')

        # Write classes (concepts)
        for node, data in graph.nodes(data=True):
            if data.get("type") == "concept":
                super_type = data.get("super_type")
                output.append(
                    f'  <rdfs:Class rdf:about="http://legend.ai/ontology#{node}">'
                )
                output.append(f'    <rdfs:label xml:lang="ar">{node}</rdfs:label>')
                if super_type:
                    output.append(
                        f'    <rdfs:subClassOf rdf:resource="http://legend.ai/ontology#{super_type}"/>'
                    )
                output.append("  </rdfs:Class>")

        # Write properties and triples (relations)
        for u, v, data in graph.edges(data=True):
            pred = data.get("relation", "relatedTo")
            conf = data.get("confidence", 1.0)
            val = data.get("emotional_valence", 0.0)

            output.append(
                f'  <rdf:Description rdf:about="http://legend.ai/ontology#{u}">'
            )
            output.append(
                f'    <legend:{pred} rdf:resource="http://legend.ai/ontology#{v}"/>'
            )
            output.append(
                f'    <legend:confidence rdf:datatype="http://www.w3.org/2001/XMLSchema#double">{conf}</legend:confidence>'
            )
            output.append(
                f'    <legend:valence rdf:datatype="http://www.w3.org/2001/XMLSchema#double">{val}</legend:valence>'
            )
            output.append("  </rdf:Description>")

        output.append("</rdf:RDF>")
        return "\n".join(output)

    elif format == "turtle":
        # Generate clean Turtle format
        output.append("@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .")
        output.append("@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .")
        output.append("@prefix legend: <http://legend.ai/ontology#> .")
        output.append("")

        # Write classes
        for node, data in graph.nodes(data=True):
            if data.get("type") == "concept":
                output.append(f"legend:{node} a rdfs:Class ;")
                output.append(f'    rdfs:label "{node}"@ar .')
                super_type = data.get("super_type")
                if super_type:
                    output.append(
                        f"legend:{node} rdfs:subClassOf legend:{super_type} ."
                    )
                output.append("")

        # Write relations
        for u, v, data in graph.edges(data=True):
            pred = data.get("relation", "relatedTo")
            conf = data.get("confidence", 1.0)
            output.append(f"legend:{u} legend:{pred} legend:{v} ;")
            output.append(f"    legend:confidence {conf} .")
            output.append("")

        return "\n".join(output)

    return ""


def export_to_json_ld(graph: nx.DiGraph) -> str:
    """Exports the graph in high-fidelity JSON-LD context for modern search engine crawls."""
    context = {
        "@context": {
            "legend": "http://legend.ai/ontology#",
            "name": "http://www.w3.org/2000/01/rdf-schema#label",
            "is_a": {
                "@id": "http://www.w3.org/2000/01/rdf-schema#subClassOf",
                "@type": "@id",
            },
            "relation": "http://legend.ai/ontology#relation",
            "confidence": "http://legend.ai/ontology#confidence",
        },
        "@graph": [],
    }

    for node, data in graph.nodes(data=True):
        node_obj = {
            "@id": f"legend:{node}",
            "name": node,
            "@type": "legend:Concept"
            if data.get("type") == "concept"
            else "legend:Instance",
        }
        super_type = data.get("super_type")
        if super_type:
            node_obj["is_a"] = f"legend:{super_type}"
        context["@graph"].append(node_obj)

    for u, v, data in graph.edges(data=True):
        rel = data.get("relation", "relatedTo")
        context["@graph"].append(
            {
                "@id": f"legend:{u}",
                f"legend:{rel}": {"@id": f"legend:{v}"},
                "legend:confidence": data.get("confidence", 1.0),
            }
        )

    return json.dumps(context, ensure_ascii=False, indent=2)


# =====================================================================
# 5. Wikidata Entity Enrichment Client
# =====================================================================


def enrich_concept_from_wikidata(concept_name: str) -> Dict[str, Any]:
    """
    Enriches local Arabic concepts using real-time Wikidata lookup.
    Fetches aliases, English mappings, descriptions, and parent concepts.
    """
    url = "https://www.wikidata.org/w/api.php"
    params = {
        "action": "wbsearchentities",
        "format": "json",
        "language": "ar",
        "search": concept_name,
        "limit": 1,
    }
    try:
        res = requests.get(url, params=params, timeout=10.0)
        if res.status_code == 200:
            data = res.json()
            if data.get("search"):
                match = data["search"][0]
                q_id = match["id"]
                desc = match.get("description", "")
                label = match.get("label", "")

                # Fetch detailed properties
                detail_params = {
                    "action": "wbgetentities",
                    "ids": q_id,
                    "format": "json",
                    "languages": "ar|en",
                }
                detail_res = requests.get(url, params=detail_params, timeout=10.0)
                aliases_list = []
                en_label = ""
                if detail_res.status_code == 200:
                    details = detail_res.json()
                    entity = details.get("entities", {}).get(q_id, {})

                    # Extract aliases
                    aliases = entity.get("aliases", {}).get("ar", [])
                    aliases_list = [a["value"] for a in aliases]

                    # Extract English label
                    en_label = entity.get("labels", {}).get("en", {}).get("value", "")

                return {
                    "qid": q_id,
                    "arabic_label": label,
                    "english_label": en_label,
                    "description": desc,
                    "aliases": aliases_list,
                    "success": True,
                }
    except Exception as e:
        return {"success": False, "error": str(e)}
    return {"success": False, "error": "No matching entity found in Wikidata"}


# =====================================================================
# 6. Lite Semantic Jaccard-Vector Similarity Search
# =====================================================================


def search_similar_nodes(
    graph: nx.DiGraph, query: str, threshold: float = 0.3
) -> List[Tuple[str, float]]:
    """
    Performs high-speed character Jaccard-vector similarity search over graph nodes.
    Solves word-variation issues without neural network dependencies.
    """
    normalized_query = normalize_arabic(query, remove_separators=True)
    query_stems = stem_arabic(query)

    results = []
    for node in graph.nodes:
        normalized_node = normalize_arabic(node, remove_separators=True)
        node_stems = stem_arabic(node)

        # 1. Calculate Jaccard similarity of characters
        jaccard_score = char_similarity(normalized_query, normalized_node)

        # 2. Check stem overlap ratio
        stem_intersection = query_stems.intersection(node_stems)
        stem_union = query_stems.union(node_stems)
        stem_score = len(stem_intersection) / len(stem_union) if stem_union else 0.0

        # 3. Hybrid scoring
        final_score = (jaccard_score * 0.4) + (stem_score * 0.6)

        # Direct substring boost
        if normalized_query in normalized_node or normalized_node in normalized_query:
            final_score = max(final_score, 0.85)

        if final_score >= threshold:
            results.append((node, round(final_score, 3)))

    # Sort by descending similarity score
    results.sort(key=lambda x: x[1], reverse=True)
    return results


# =====================================================================
# 7. Temporal Filtering Helper
# =====================================================================


def filter_triples_by_time(triples: List[Tuple], year: int) -> List[Tuple]:
    """
    Filters logic triples based on their active temporal window.
    Supports queries like: 'What was true in 2020?'
    """
    filtered = []
    for item in triples:
        # Expected tuple structure: (subject, predicate, object, valid_from, valid_to, confidence)
        if len(item) >= 5:
            subj, pred, obj, valid_from, valid_to = item[:5]

            # If no temporal bounds defined, treat as universally true
            is_valid = True
            if valid_from is not None and year < valid_from:
                is_valid = False
            if valid_to is not None and year > valid_to:
                is_valid = False

            if is_valid:
                filtered.append(item)
        else:
            # Fallback if no temporal info exists
            filtered.append(item)
    return filtered
