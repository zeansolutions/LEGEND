# -*- coding: utf-8 -*-
"""
🪐 LEGEND Cognitive Engine
Includes:
1. Arabic Light Stemmer & Normalization
2. Relation-Agnostic Inference Engine & Property Inheritance
3. Active Curiosity Engine & Mystery Score Calculator
4. Semantic Sleep & Consolidation Cycle (Linguistic Discovery, Strengthening, Pruning, Dream Walks, Hygiene)
"""

import sqlite3
import json
import time
import random
import networkx as nx
from typing import List, Dict, Any, Tuple, Set

# =====================================================================
# 1. Arabic Light Stemmer & Normalization
# =====================================================================

from core_utils import normalize_arabic, stem_arabic, char_similarity
import core_utils


# =====================================================================
# 2. Relation-Agnostic Inference Engine
# =====================================================================

class CognitiveInferenceEngine:
    """
    Relation-agnostic inference engine.
    Applies logic propagation rules across all custom predicates and 
    implements complete property inheritance for taxonomic structures.
    """
    def __init__(self, prototype):
        self.proto = prototype

    def run_inference(self, logs: List[str] = None) -> List[Tuple[str, str, str, float]]:
        """
        Executes both:
        1. Relation-Agnostic Transitive Chaining (for all custom chainable relationships)
        2. Property Inheritance (inheriting properties/edges from taxonomic ancestors)
        Saves inferred relations to the database.
        """
        if logs is None:
            logs = []

        if getattr(self.proto, "strict_mode", False):
            logs.append("🔒 [Strict Facts Mode]: Inference suspended to prevent probabilistic reasoning.")
            return []

        inferred_triples = []
        graph = self.proto.sandbox_graph if self.proto.in_sandbox else self.proto.graph

        # Structural relations that should NOT be transitively chained
        non_chainable_relations = {"is_a", "جزء_من_حدث", "مرادف_لـ", "يماثل", "عكس"}

        # Gather all unique relations present in the graph
        relations = set()
        for u, v, d in graph.edges(data=True):
            r = d.get("relation")
            if r and r not in non_chainable_relations:
                relations.add(r)

        # ---------------------------------------------------------
        # Phase 1: Relation-Agnostic Transitive Chaining
        # ---------------------------------------------------------
        # For each relation R, if A -> R -> B and B -> R -> C => A -> R -> C
        for rel in relations:
            # Build adjacency dictionary for this specific relation
            adj = {}
            for u, v, d in graph.edges(data=True):
                if d.get("relation") == rel:
                    adj.setdefault(u, []).append((v, d.get("confidence", 1.0)))

            for start_node in adj:
                visited = {}
                self._dfs_transitive(start_node, adj, visited, 1.0, 0, max_depth=3)
                
                for target_node, confidence in visited.items():
                    if target_node == start_node:
                        continue
                    # Skip if direct relation already exists
                    if graph.has_edge(start_node, target_node) and graph[start_node][target_node].get("relation") == rel:
                        continue
                        
                    # Save inferred relation
                    # Confidence decays: c1 * c2 * ... * 0.90
                    final_conf = confidence * 0.90
                    self.proto.save_triple_to_db(start_node, rel, target_node, confidence=final_conf)
                    inferred_triples.append((start_node, rel, target_node, final_conf))
                    logs.append(f"🧠 [Free Transitive Inference]: Inferred ({start_node} ➔ {rel} ➔ {target_node}) with confidence {final_conf:.2f}")

        # ---------------------------------------------------------
        # Phase 2: Property Inheritance
        # ---------------------------------------------------------
        # If A is_a B (transitively via taxonomy), then A inherits all properties/relations of B (except taxonomic ones)
        is_a_chains = self._get_transitive_is_a_chains(graph)
        taxonomic_rels = {"is a", "is_a", "هي نوع من", "مثال علي", "مثال عليها", "هو من فئه", "تكون من نوع", "تصنف علي انها", "تصنف بانها", "ينتمي الي", "من فئه"}
        
        for child, ancestors in is_a_chains.items():
            for parent in ancestors:
                # Find all outgoing relations of parent
                for _, target, d in graph.out_edges(parent, data=True):
                    pred = d.get("relation")
                    norm_pred = normalize_arabic(pred) if isinstance(pred, str) else ""
                    
                    if pred == "is_a" or norm_pred in taxonomic_rels or pred in non_chainable_relations:
                        continue
                    
                    # Skip if child already has this direct relation
                    if graph.has_edge(child, target) and graph[child][target].get("relation") == pred:
                        continue
                        
                    parent_conf = d.get("confidence", 1.0)
                    inherited_conf = parent_conf * 0.92
                    
                    self.proto.save_triple_to_db(child, pred, target, confidence=inherited_conf)
                    inferred_triples.append((child, pred, target, inherited_conf))
                    logs.append(f"🧬 [Property Inheritance]: Node ({child}) inherited relation ({pred} ➔ {target}) from ancestor category ({parent}) with confidence {inherited_conf:.2f}")

        if inferred_triples:
            self.proto.load_graph_from_db() # Reload into NetworkX
            
        return inferred_triples

    def _dfs_transitive(self, current: str, adj: Dict[str, List[Tuple[str, float]]], visited: Dict[str, float], current_conf: float, depth: int, max_depth: int):
        if depth >= max_depth:
            return
        for neighbor, edge_conf in adj.get(current, []):
            new_conf = current_conf * edge_conf
            if neighbor not in visited or new_conf > visited[neighbor]:
                visited[neighbor] = new_conf
                self._dfs_transitive(neighbor, adj, visited, new_conf, depth + 1, max_depth)

    def _get_transitive_is_a_chains(self, graph: nx.DiGraph) -> Dict[str, Set[str]]:
        """Computes all transitive ancestors for each node in the graph via 'is_a' and Arabic taxonomic relations."""
        chains = {}
        taxonomic_rels = {"is a", "is_a", "هي نوع من", "مثال علي", "مثال عليها", "هو من فئه", "تكون من نوع", "تصنف علي انها", "تصنف بانها", "ينتمي الي", "من فئه"}
        
        for node in graph.nodes():
            ancestors = set()
            queue = [node]
            visited = set()
            while queue:
                curr = queue.pop(0)
                if curr in visited:
                    continue
                visited.add(curr)
                
                # Outgoing taxonomy edges
                parents = []
                for u, v, d in graph.out_edges(curr, data=True):
                    rel = d.get("relation", "")
                    norm_rel = normalize_arabic(rel) if isinstance(rel, str) else ""
                    if rel == "is_a" or norm_rel in taxonomic_rels:
                        parents.append(v)
                
                for p in parents:
                    if p not in ancestors and p != node:
                        ancestors.add(p)
                        queue.append(p)
            if ancestors:
                chains[node] = ancestors
        return chains

# =====================================================================
# 3. Active Curiosity Engine
# =====================================================================

class CognitiveCuriosityEngine:
    """
    Curiosity Engine.
    Discovers knowledge gaps, orphan nodes, and vague concepts.
    Calculates a "mystery score" and generates Arabic questions.
    """
    def __init__(self, prototype):
        self.proto = prototype

    def calculate_mystery_score(self, concept: str) -> int:
        """
        Calculates the "mystery score" of a concept from 0 (fully understood) to 100 (unknown).
        """
        graph = self.proto.sandbox_graph if self.proto.in_sandbox else self.proto.graph
        if not graph.has_node(concept):
            return 100

        relations = []
        for u, v, d in graph.edges(concept, data=True):
            relations.append(d)
        for u, v, d in graph.in_edges(concept, data=True):
            relations.append(d)

        if not relations:
            return 100

        # Knowledge dimensions checks
        has_taxonomy = any(r.get("relation") == "is_a" for r in relations)
        has_properties = any(r.get("relation") in ("لون", "شكل", "ملمس", "حجم", "وزن", "طبيعه", "حاله") for r in relations)
        has_actions = any(r.get("relation") in ("يفعل", "يسبب", "يؤدي_إلى", "ينتج_عنه", "يقوم_بـ") for r in relations)
        
        score = 100
        if has_taxonomy:
            score -= 25
        if has_properties:
            score -= 25
        if has_actions:
            score -= 20
            
        # Degree factor (more connections, less mystery)
        deg = graph.degree(concept)
        score -= min(deg * 8, 30)
        
        return max(0, score)

    def find_knowledge_gaps(self) -> List[Dict[str, Any]]:
        """Scans the ontology and identifies nodes with high mystery scores."""
        graph = self.proto.sandbox_graph if self.proto.in_sandbox else self.proto.graph
        gaps = []
        
        for node in graph.nodes():
            # Skip structural/internal tags
            if str(node).startswith("ST_") or str(node).startswith("event_"):
                continue
                
            mystery = self.calculate_mystery_score(node)
            if mystery > 30: # Anything above 30 indicates a gap
                # Check outgoing properties
                has_taxonomy = any(d.get("relation") == "is_a" for u, v, d in graph.out_edges(node, data=True))
                has_properties = any(d.get("relation") in ("لون", "شكل", "ملمس", "حجم", "وزن") for u, v, d in graph.out_edges(node, data=True))
                
                gaps.append({
                    "concept": node,
                    "mystery_score": mystery,
                    "missing_taxonomy": not has_taxonomy,
                    "missing_properties": not has_properties,
                    "connections": graph.degree(node)
                })
                
        gaps.sort(key=lambda x: x["mystery_score"], reverse=True)
        return gaps

    def generate_questions(self, limit: int = 5, lang: str = "ar") -> List[Dict[str, Any]]:
        """Generates natural questions based on mapped knowledge gaps."""
        gaps = self.find_knowledge_gaps()
        questions = []
        
        # Translation dictionaries for curiosity questions
        templates = {
            "ar": {
                "taxonomy": "ما هو '{concept}' بالظبط؟ هو نوع من ماذا؟ (مثال: {concept} هو نوع من المعادن)",
                "property": "ما هي صفات '{concept}'؟ كيف يبدو لونه أو شكله أو ملمسه؟",
                "action": "ما هي سلوكيات أو أفعال '{concept}'؟ ماذا يفعل أو يسبّب في العادة؟"
            },
            "en": {
                "taxonomy": "What exactly is '{concept}'? What is it a type of? (Example: {concept} is a type of Mineral)",
                "property": "What are the properties of '{concept}'? How does it look, feel, or weigh?",
                "action": "What are the behaviors or actions of '{concept}'? What does it usually do or cause?"
            },
            "zh": {
                "taxonomy": "“{concept}”到底是什么？它是一种什么类型的实体？（例如：{concept} 是一种矿物）",
                "property": "“{concept}”的属性是什么？它的颜色、形状或质地是怎样的？",
                "action": "“{concept}”的行为或动作是什么？它通常会做什么或导致什么？"
            },
            "fr": {
                "taxonomy": "Qu'est-ce que '{concept}' exactement ? De quel type s'agit-il ? (Exemple : {concept} est un type de Minéral)",
                "property": "Quelles sont les propriétés de '{concept}' ? À quoi ressemble-t-il, quelle est sa texture ou sa couleur ?",
                "action": "Quels sont les comportements ou les actions de '{concept}' ? Que fait-il ou cause-t-il généralement ?"
            },
            "es": {
                "taxonomy": "¿Qué es exactamente '{concept}'? ¿De qué tipo es? (Ejemplo: {concept} es un tipo de Mineral)",
                "property": "¿Cuáles son las propiedades de '{concept}'? ¿Cómo se ve, se siente o qué color tiene?",
                "action": "¿Cuáles son los comportamientos o acciones de '{concept}'? ¿Qué hace o causa habitualmente?"
            },
            "tr": {
                "taxonomy": "'{concept}' tam olarak nedir? Ne tür bir şeydir? (Örnek: {concept} bir tür Mineraldir)",
                "property": "'{concept}' özellikleri nelerdir? Rengi, şekli veya dokusu nasıldır?",
                "action": "'{concept}' davranışları veya eylemleri nelerdir? Genellikle ne yapar veya neye neden olur?"
            },
            "de": {
                "taxonomy": "Was genau ist '{concept}'? Was für eine Art ist es? (Beispiel: {concept} ist eine Art von Mineral)",
                "property": "Was sind die Eigenschaften von '{concept}'? Wie sieht es aus, wie fühlt es sich an oder welche Farbe hat es?",
                "action": "Was sind die Verhaltensweisen oder Handlungen von '{concept}'? Was tut oder verursacht es normalerweise?"
            },
            "ru": {
                "taxonomy": "Что именно представляет собой '{concept}'? К какому типу относится? (Пример: {concept} — это тип минерала)",
                "property": "Каковы свойства '{concept}'? Как он выглядит, каков на ощупь или цвет?",
                "action": "Каковы действия или поведение '{concept}'? Что он обычно делает или вызывает?"
            },
            "pt": {
                "taxonomy": "O que exatamente é '{concept}'? De que tipo é? (Exemplo: {concept} é um tipo de Mineral)",
                "property": "Quais são as propriedades de '{concept}'? Como se parece, qual a textura ou cor?",
                "action": "Quais são os comportamentos ou ações de '{concept}'? O que geralmente faz ou causa?"
            },
            "ja": {
                "taxonomy": "「{concept}」とは正確には何ですか？何の一種ですか？（例：{concept}は鉱物の一種です）",
                "property": "「{concept}」の属性は何ですか？どのような色、形、または感触ですか？",
                "action": "「{concept}」の行動や作用は何ですか？通常何をしますか、または何を引き起こしますか？"
            },
            "ko": {
                "taxonomy": "'{concept}'은(는) 정확히 무엇입니까? 어떤 종류입니까? (예: {concept}은(는) 일종의 광물입니다)",
                "property": "'{concept}'의 속성은 무엇입니까? 색상, 모양 또는 질감은 어떻습니까?",
                "action": "'{concept}'의 행동이나 작용은 무엇입니까? 주로 무엇을 하거나 무엇을 유발합니까?"
            }
        }
        
        t = templates.get(lang, templates["en"])
        
        for gap in gaps[:limit]:
            concept = gap["concept"]
            mystery = gap["mystery_score"]
            
            if gap["missing_taxonomy"]:
                questions.append({
                    "concept": concept,
                    "type": "taxonomy",
                    "mystery_score": mystery,
                    "question": t["taxonomy"].format(concept=concept)
                })
            elif gap["missing_properties"]:
                questions.append({
                    "concept": concept,
                    "type": "property",
                    "mystery_score": mystery,
                    "question": t["property"].format(concept=concept)
                })
            else:
                questions.append({
                    "concept": concept,
                    "type": "action",
                    "mystery_score": mystery,
                    "question": t["action"].format(concept=concept)
                })
                
        return questions

# =====================================================================
# 4. Semantic Sleep & Consolidation Cycle
# =====================================================================

class CognitiveSleepCycle:
    """
    Sleep Cycle & Consolidation Manager.
    Performs vector/character grouping, edge strengthening, random walk dreaming,
    and cognitive noise cleaning to maintain ontology integrity.
    """
    def __init__(self, prototype):
        self.proto = prototype

    def run_sleep_cycle(self) -> Dict[str, Any]:
        """
        Runs the full 5-stage Semantic Sleep Cycle.
        Returns a dictionary of execution statistics.
        """
        stats = {
            "synonyms_linked": 0,
            "edges_strengthened": 0,
            "edges_pruned": 0,
            "dream_discoveries": 0,
            "noise_nodes_cleaned": 0,
            "new_inferences": 0
        }

        # ---------------------------------------------------------
        # Phase 1: Linguistic Synonym Discovery & Grouping
        # ---------------------------------------------------------
        stats["synonyms_linked"] = self._consolidate_linguistic_synonyms()

        # ---------------------------------------------------------
        # Phase 2: Edge Strengthening
        # ---------------------------------------------------------
        stats["edges_strengthened"] = self._strengthen_edges()

        # ---------------------------------------------------------
        # Phase 3: Semantic Edge Pruning
        # ---------------------------------------------------------
        stats["edges_pruned"] = self._prune_weak_edges(min_confidence=0.50)

        # ---------------------------------------------------------
        # Phase 4: Dream Walks (Associative Dreaming)
        # ---------------------------------------------------------
        stats["dream_discoveries"] = self._dream_walks()

        # ---------------------------------------------------------
        # Phase 5: Dynamic Inferences Refresh
        # ---------------------------------------------------------
        engine = CognitiveInferenceEngine(self.proto)
        inferred = engine.run_inference()
        stats["new_inferences"] = len(inferred)

        # ---------------------------------------------------------
        # Phase 6: Cognitive Hygiene
        # ---------------------------------------------------------
        stats["noise_nodes_cleaned"] = self._cognitive_hygiene()

        # Sync changes to RAM
        self.proto.load_graph_from_db()
        return stats

    def _consolidate_linguistic_synonyms(self) -> int:
        """
        Discovers words that are morphological or character variations of each other.
        Links them via 'مرادف_لـ' (SYNONYM_OF) edges.
        """
        graph = self.proto.sandbox_graph if self.proto.in_sandbox else self.proto.graph
        nodes = list(graph.nodes())
        linked = 0
        
        processed = set()
        
        for i in range(len(nodes)):
            node_A = nodes[i]
            # Skip structural tags
            if str(node_A).startswith("ST_") or str(node_A).startswith("event_") or len(str(node_A)) < 3:
                continue
                
            for j in range(i + 1, len(nodes)):
                node_B = nodes[j]
                if str(node_B).startswith("ST_") or str(node_B).startswith("event_") or len(str(node_B)) < 3:
                    continue
                    
                pair = tuple(sorted([node_A, node_B]))
                if pair in processed:
                    continue
                processed.add(pair)
                
                # Check normalized equivalence or Jaccard similarity or light stem overlap
                norm_A = normalize_arabic(node_A)
                norm_B = normalize_arabic(node_B)
                
                is_synonym = False
                if norm_A == norm_B:
                    is_synonym = True
                else:
                    # Stems overlap
                    stems_A = stem_arabic(node_A)
                    stems_B = stem_arabic(node_B)
                    overlap = stems_A & stems_B
                    if overlap and len(max(overlap, key=len)) >= 3:
                        is_synonym = True
                    elif char_similarity(node_A, node_B) >= 0.88:
                        is_synonym = True
                        
                if is_synonym:
                    # Link them as synonyms in BOTH directions if not already linked
                    if not (graph.has_edge(node_A, node_B) and graph[node_A][node_B].get("relation") == "مرادف_لـ"):
                        self.proto.save_triple_to_db(node_A, "مرادف_لـ", node_B, confidence=0.95)
                        self.proto.save_triple_to_db(node_B, "مرادف_لـ", node_A, confidence=0.95)
                        linked += 1
                        
        return linked

    def _strengthen_edges(self) -> int:
        """
        Strengthens existing relations based on co-occurrence in parent nodes.
        If A and B share multiple neighbors, their direct edges are reinforced.
        """
        graph = self.proto.sandbox_graph if self.proto.in_sandbox else self.proto.graph
        strengthened = 0
        
        for u, v, d in list(graph.edges(data=True)):
            # Skip is_a and structural links
            rel = d.get("relation")
            if rel in ("is_a", "مرادف_لـ"):
                continue
                
            # Find shared parent/successor structures (triangles)
            successors_u = set(graph.successors(u))
            successors_v = set(graph.successors(v))
            shared = successors_u & successors_v
            
            if shared:
                # Add co-occurrence boost
                boost = len(shared) * 0.05
                current_conf = d.get("confidence", 1.0)
                new_conf = min(1.0, current_conf + boost)
                
                if new_conf > current_conf:
                    # Update DB
                    self.proto.save_triple_to_db(u, rel, v, confidence=new_conf)
                    strengthened += 1
                    
        return strengthened

    def _prune_weak_edges(self, min_confidence: float = 0.50) -> int:
        """
        Prunes edges that have confidence below min_confidence.
        Safety guard: Only prunes if BOTH nodes remain connected to the graph.
        """
        graph = self.proto.sandbox_graph if self.proto.in_sandbox else self.proto.graph
        pruned = 0
        
        for u, v, d in list(graph.edges(data=True)):
            conf = d.get("confidence", 1.0)
            if conf < min_confidence:
                # Safety check: do not orphan nodes
                if graph.degree(u) > 1 and graph.degree(v) > 1:
                    # Delete triple
                    self.proto.delete_triple(u, d.get("relation"), v)
                    pruned += 1
                    
        return pruned

    def _dream_walks(self, num_walks: int = 15, walk_length: int = 3) -> int:
        """
        Performs weighted random walks ("Dreams") across the ontology network.
        If two non-directly connected nodes share a property at the end of a walk,
        a weak association link 'يماثل' (resembles) is recorded at low confidence.
        """
        graph = self.proto.sandbox_graph if self.proto.in_sandbox else self.proto.graph
        nodes = list(graph.nodes())
        if len(nodes) < 5:
            return 0
            
        discoveries = 0
        
        for _ in range(num_walks):
            start = random.choice(nodes)
            if str(start).startswith("ST_") or str(start).startswith("event_"):
                continue
                
            curr = start
            path = [curr]
            
            for _ in range(walk_length):
                neighbors = list(graph.successors(curr)) + list(graph.predecessors(curr))
                if not neighbors:
                    break
                next_node = random.choice(neighbors)
                if next_node in path:
                    break
                path.append(next_node)
                curr = next_node
                
            if len(path) >= 3:
                end = path[-1]
                if start != end and not graph.has_edge(start, end):
                    # Check if they share any outgoing property relation
                    props_start = {d.get("relation"): v for _, v, d in graph.out_edges(start, data=True) if d.get("relation") != "is_a"}
                    props_end = {d.get("relation"): v for _, v, d in graph.out_edges(end, data=True) if d.get("relation") != "is_a"}
                    
                    shared_props = set(props_start.keys()) & set(props_end.keys())
                    match = False
                    for p in shared_props:
                        if props_start[p] == props_end[p]:
                            match = True
                            break
                            
                    if match:
                        # Record a dream walk associative similarity link
                        self.proto.save_triple_to_db(start, "يماثل", end, confidence=0.35)
                        discoveries += 1
                        
        return discoveries

    def _cognitive_hygiene(self) -> int:
        """
        Identifies and removes phonetic noise blacklisted words (e.g. تششش، أوأو)
        or completely isolated short nodes, protecting structural purity.
        """
        graph = self.proto.sandbox_graph if self.proto.in_sandbox else self.proto.graph
        nodes = list(graph.nodes())
        cleaned = 0
        
        phonetic_blacklist = {"تششش", "تشش", "أوأو", "همهم", "صفير", "رنين", "هدير", "ألو", "ممم", "هممم"}
        
        for node in nodes:
            # Check blacklist or isolated status
            is_noise = False
            if normalize_arabic(node) in phonetic_blacklist:
                is_noise = True
            elif len(normalize_arabic(node)) <= 2 and graph.degree(node) <= 1:
                # Short nodes with 0 or 1 connection
                is_noise = True
                
            if is_noise:
                # Remove node and its database representations
                self.proto.delete_node(node)
                cleaned += 1
                
        return cleaned
