# -*- coding: utf-8 -*-
"""
engine.py - Clean, Headless Arabic Neuro-Symbolic Reasoning Engine.
De-coupled from all GUI dependencies, serving as a clean Python API package.
"""

import json
import os
import sys
import re
import sqlite3
import networkx as nx
import time
import requests
from typing import List, Dict, Any, Tuple, Optional

# Add parent directory to sys.path to import core_utils
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core_utils import normalize_arabic, call_llm_api, get_local_llm
import core_utils



class ArabicReasoningEngine:
    """Headless, high-performance Arabic Neuro-Symbolic reasoning engine."""
    
    def __init__(self, db_filename: str = "ontology.db"):
        self.db_path = db_filename
        self.graph = nx.DiGraph()
        self.last_relations = []
        self.in_sandbox = False
        self.sandbox_graph = None
        self.strict_mode = False
        self.init_database()
        self.load_graph_from_db()

    def init_database(self):
        """Initialize or upgrade SQLite schemas for high-speed indexing."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS concepts (
                    name TEXT PRIMARY KEY,
                    super_type TEXT,
                    properties TEXT,
                    confidence REAL DEFAULT 1.0,
                    emotional_valence REAL DEFAULT 0.0,
                    created_at INTEGER
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS triples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject TEXT,
                    predicate TEXT,
                    object TEXT,
                    valid_from INTEGER,
                    valid_to INTEGER,
                    confidence REAL DEFAULT 1.0,
                    emotional_valence REAL DEFAULT 0.0,
                    created_at INTEGER,
                    UNIQUE(subject, predicate, object)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rule_name TEXT UNIQUE,
                    antecedents TEXT,
                    consequent TEXT,
                    confidence REAL DEFAULT 1.0,
                    is_active INTEGER DEFAULT 1
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS procedural_steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    procedure_name TEXT,
                    step_number INTEGER,
                    step_description TEXT
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_triples_sub_pred ON triples(subject, predicate)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_triples_obj ON triples(object)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_concepts_super ON concepts(super_type)")
            
            # Prevent schema upgrade issues on older databases
            schema_updates = [
                ("triples", "valid_from", "INTEGER"),
                ("triples", "valid_to", "INTEGER"),
                ("triples", "confidence", "REAL DEFAULT 1.0"),
                ("triples", "emotional_valence", "REAL DEFAULT 0.0"),
                ("triples", "created_at", "INTEGER"),
                ("triples", "inferred", "INTEGER DEFAULT 0"),
                ("concepts", "confidence", "REAL DEFAULT 1.0"),
                ("concepts", "emotional_valence", "REAL DEFAULT 0.0"),
                ("concepts", "created_at", "INTEGER")
            ]
            for table, col, col_type in schema_updates:
                try:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
                except sqlite3.OperationalError:
                    pass  # Column already exists
                    
            conn.commit()
            conn.close()
            
            # Automatically populate default logic rules if table is empty
            self.init_default_rules()
        except Exception as e:
            print(f" ⚠️ [SQLite Initialisation Error]: {e}")

    def init_default_rules(self):
        """Populate initial transitivity and logical reasoning rules in SQLite."""
        default_rules = [
            {
                "rule_name": "transitive_is_a",
                "antecedents": json.dumps([["?x", "is_a", "?y"], ["?y", "is_a", "?z"]], ensure_ascii=False),
                "consequent": json.dumps(["?x", "is_a", "?z"], ensure_ascii=False),
                "confidence": 1.0
            },
            {
                "rule_name": "transitive_lives_in",
                "antecedents": json.dumps([["?x", "يعيش_في", "?y"], ["?y", "جزء_من", "?z"]], ensure_ascii=False),
                "consequent": json.dumps(["?x", "يعيش_في", "?z"], ensure_ascii=False),
                "confidence": 0.95
            },
            {
                "rule_name": "transitive_works_in",
                "antecedents": json.dumps([["?x", "يعمل_في", "?y"], ["?y", "جزء_من", "?z"]], ensure_ascii=False),
                "consequent": json.dumps(["?x", "يعمل_في", "?z"], ensure_ascii=False),
                "confidence": 0.95
            },
            {
                "rule_name": "transitive_causation",
                "antecedents": json.dumps([["?x", "يؤدي_إلى", "?y"], ["?y", "يؤدي_إلى", "?z"]], ensure_ascii=False),
                "consequent": json.dumps(["?x", "يؤدي_إلى", "?z"], ensure_ascii=False),
                "confidence": 0.90
            }
        ]
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            for r in default_rules:
                cursor.execute("""
                    INSERT OR IGNORE INTO rules (rule_name, antecedents, consequent, confidence, is_active)
                    VALUES (?, ?, ?, ?, 1)
                """, (r["rule_name"], r["antecedents"], r["consequent"], r["confidence"]))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"⚠️ Failed to init default rules: {e}")

    def load_graph_from_db(self):
        """Populate the NetworkX graph from SQLite for blistering fast reasoning in RAM."""
        try:
            self.graph.clear()
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Load Concepts
            cursor.execute("SELECT name, super_type, properties, confidence, emotional_valence, created_at FROM concepts")
            concept_rows = cursor.fetchall()
            for name, super_type, props_json, confidence, emotional_valence, created_at in concept_rows:
                confidence = confidence if confidence is not None else 1.0
                emotional_valence = emotional_valence if emotional_valence is not None else 0.0
                props = json.loads(props_json) if props_json else []
                self.graph.add_node(name, type="concept", super_type=super_type, properties=props, 
                                    confidence=confidence, emotional_valence=emotional_valence, created_at=created_at)
                if super_type:
                    self.graph.add_edge(name, super_type, relation="is_a", confidence=1.0, emotional_valence=0.0, created_at=created_at)
            
            # Load Triples
            try:
                cursor.execute("SELECT subject, predicate, object, valid_from, valid_to, confidence, emotional_valence, created_at, inferred FROM triples")
                rows = cursor.fetchall()
            except sqlite3.OperationalError:
                cursor.execute("SELECT subject, predicate, object, valid_from, valid_to, confidence, emotional_valence, created_at FROM triples")
                rows = [r + (0,) for r in cursor.fetchall()]
                
            for subj, pred, obj, valid_from, valid_to, confidence, emotional_valence, created_at, inferred in rows:
                confidence = confidence if confidence is not None else 1.0
                emotional_valence = emotional_valence if emotional_valence is not None else 0.0
                inferred = inferred if inferred is not None else 0
                if not self.graph.has_node(subj):
                    self.graph.add_node(subj, type="instance")
                if not self.graph.has_node(obj):
                    self.graph.add_node(obj, type="instance")
                self.graph.add_edge(subj, obj, relation=pred, valid_from=valid_from, valid_to=valid_to, 
                                    confidence=confidence, emotional_valence=emotional_valence, created_at=created_at, inferred=inferred)
                
            conn.close()
        except Exception as e:
            print(f" ⚠️ [RAM In-Memory Graph Sync Failed]: {e}")

    def save_concept_to_db(self, name: str, super_type: str, properties: list = [], confidence: float = 1.0, emotional_valence: float = 0.0):
        name = normalize_arabic(name)
        super_type = normalize_arabic(super_type) if super_type else super_type
        confidence = confidence if confidence is not None else 1.0
            
        graph_to_use = self.sandbox_graph if self.in_sandbox else self.graph
        graph_to_use.add_node(name, type="concept", super_type=super_type, properties=properties, confidence=confidence, emotional_valence=emotional_valence, created_at=int(time.time()))
        if super_type:
            graph_to_use.add_edge(name, super_type, relation="is_a", confidence=1.0, emotional_valence=0.0, created_at=int(time.time()))
            
        if self.in_sandbox:
            return
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO concepts (name, super_type, properties, confidence, emotional_valence, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, super_type, json.dumps(properties, ensure_ascii=False), confidence, emotional_valence, int(time.time())))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f" ⚠️ Failed to save concept '{name}': {e}")

    def save_triple_to_db(self, subj: str, pred: str, obj: str, valid_from: int = None, valid_to: int = None, confidence: float = 1.0, emotional_valence: float = 0.0, inferred: int = 0):
        subj = normalize_arabic(subj)
        pred = normalize_arabic(pred)
        obj = normalize_arabic(obj)
        confidence = confidence if confidence is not None else 1.0
            
        graph_to_use = self.sandbox_graph if self.in_sandbox else self.graph
        
        if not graph_to_use.has_node(subj):
            graph_to_use.add_node(subj, type="instance")
        if not graph_to_use.has_node(obj):
            graph_to_use.add_node(obj, type="instance")
        graph_to_use.add_edge(subj, obj, relation=pred, valid_from=valid_from, valid_to=valid_to, confidence=confidence, emotional_valence=emotional_valence, created_at=int(time.time()), inferred=inferred)
        
        if self.in_sandbox:
            return
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO triples (subject, predicate, object, valid_from, valid_to, confidence, emotional_valence, created_at, inferred)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (subj, pred, obj, valid_from, valid_to, confidence, emotional_valence, int(time.time()), inferred))
            conn.commit()
            conn.close()
        except sqlite3.OperationalError:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO triples (subject, predicate, object, valid_from, valid_to, confidence, emotional_valence, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (subj, pred, obj, valid_from, valid_to, confidence, emotional_valence, int(time.time())))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f" ⚠️ Failed to save relation ({subj} ➔ {pred} ➔ {obj}): {e}")
        except Exception as e:
            print(f" ⚠️ Failed to save relation ({subj} ➔ {pred} ➔ {obj}): {e}")

    def delete_triple(self, subj: str, pred: str, obj: str) -> bool:
        """Permanently delete a triple from database and network graph."""
        subj = normalize_arabic(subj)
        pred = normalize_arabic(pred)
        obj = normalize_arabic(obj)
        
        graph_to_use = self.sandbox_graph if self.in_sandbox else self.graph
        if graph_to_use.has_edge(subj, obj) and graph_to_use[subj][obj].get("relation") == pred:
            graph_to_use.remove_edge(subj, obj)
            
        if self.in_sandbox:
            return True
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM triples WHERE subject=? AND predicate=? AND object=?", (subj, pred, obj))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"⚠️ Error deleting triple ({subj} ➔ {pred} ➔ {obj}): {e}")
            return False

    def get_all_triples(self) -> List[Tuple[str, str, str, Optional[int], Optional[int], float]]:
        """Fetch all factual triples registered in the DB."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT subject, predicate, object, valid_from, valid_to, confidence FROM triples")
            rows = cursor.fetchall()
            conn.close()
            return rows
        except Exception as e:
            print(f"⚠️ Failed to fetch triples: {e}")
            return []

    def clear_all_data(self) -> bool:
        """Reset ontology database and clear network memory completely."""
        if self.in_sandbox:
            if self.sandbox_graph:
                self.sandbox_graph.clear()
            return True
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM concepts")
            cursor.execute("DELETE FROM triples")
            cursor.execute("DELETE FROM rules")
            cursor.execute("DELETE FROM procedural_steps")
            conn.commit()
            conn.close()
            
            self.graph.clear()
            self.init_default_rules()
            return True
        except Exception as e:
            print(f"⚠️ Failed to clear memory: {e}")
            return False

    def delete_relation(self, subject: str, predicate: str, object_node: str) -> bool:
        """Delete specific semantic relation."""
        active_graph = self.sandbox_graph if self.in_sandbox else self.graph
        if active_graph.has_edge(subject, object_node) and active_graph.get_edge_data(subject, object_node).get('relation') == predicate:
            active_graph.remove_edge(subject, object_node)
                
        if self.in_sandbox:
            return True
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM triples WHERE subject=? AND predicate=? AND object=?", (subject, predicate, object_node))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"⚠️ Failed to delete relation: {e}")
            return False

    def delete_node(self, node_name: str) -> bool:
        """Delete concept completely with all its connected associations."""
        active_graph = self.sandbox_graph if self.in_sandbox else self.graph
        if active_graph.has_node(node_name):
            active_graph.remove_node(node_name)
            
        if self.in_sandbox:
            return True
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM concepts WHERE name=?", (node_name,))
            cursor.execute("DELETE FROM triples WHERE subject=? OR object=?", (node_name, node_name))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"⚠️ Failed to delete node: {e}")
            return False

    def gather_db_statistics(self) -> Dict[str, Any]:
        """Gather database statistics and metrics."""
        active_graph = self.sandbox_graph if self.in_sandbox else self.graph
        total_concepts = active_graph.number_of_nodes()
        total_triples = active_graph.number_of_edges()
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM concepts")
            total_concepts = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM triples")
            total_triples = cursor.fetchone()[0]
        except Exception:
            pass
            
        total_instances = len([n for n, d in active_graph.nodes(data=True) if d.get("type") == "instance"])
        
        max_depth = 0
        try:
            is_a_graph = nx.DiGraph()
            for u, v, d in active_graph.edges(data=True):
                if d.get("relation") == "is_a":
                    is_a_graph.add_edge(u, v)
            if is_a_graph.number_of_nodes() > 0:
                max_depth = nx.dag_longest_path_length(is_a_graph)
        except Exception:
            pass
            
        db_size_kb = 0.0
        try:
            if os.path.exists(self.db_path):
                db_size_kb = round(os.path.getsize(self.db_path) / 1024, 2)
        except Exception:
            pass
            
        top_connected = []
        try:
            degrees = dict(active_graph.degree())
            top_connected = sorted(degrees.items(), key=lambda x: x[1], reverse=True)[:5]
        except Exception:
            pass
            
        top_predicates = []
        try:
            cursor.execute("SELECT predicate, COUNT(*) as c FROM triples GROUP BY predicate ORDER BY c DESC LIMIT 5")
            top_predicates = cursor.fetchall()
            conn.close()
        except Exception:
            pass
                
        return {
            "total_concepts": total_concepts,
            "total_triples": total_triples,
            "total_instances": total_instances,
            "max_depth": max_depth,
            "db_size_kb": db_size_kb,
            "top_connected": top_connected,
            "top_predicates": top_predicates
        }

    def clean_and_extract_json(self, text: str) -> str:
        """Robust parser to extract JSON blocks from conversational LLM output."""
        if not text:
            return "{}"
        text = text.strip()
        
        # Strip markdown syntax wraps
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        text = text.strip()
        
        # Locate bounds
        first_brace = text.find('{')
        first_bracket = text.find('[')
        
        start_char = '{'
        first_idx = first_brace
        if first_bracket != -1 and (first_brace == -1 or first_bracket < first_brace):
            start_char = '['
            first_idx = first_bracket
            
        if first_idx == -1:
            return text
            
        end_char = '}' if start_char == '{' else ']'
        brace_indices = [i for i, char in enumerate(text) if char == end_char]
        if not brace_indices:
            return text
            
        # Try decoding window ranges backwards
        for idx in reversed(brace_indices):
            if idx > first_idx:
                candidate = text[first_idx:idx+1]
                # Fix trailing comma issues inside JSON arrays/objects
                candidate_clean = re.sub(r',\s*([\]}])', r'\1', candidate)
                try:
                    json.loads(candidate_clean)
                    return candidate_clean
                except Exception:
                    continue
                    
        last_brace = text.rfind(end_char)
        if last_brace > first_idx:
            candidate = text[first_idx:last_brace+1]
            return re.sub(r',\s*([\]}])', r'\1', candidate)
            
        return text

    def parse_sentence_with_llm(self, sentence: str, provider: str, api_key: str, model: str, logs: Optional[List[str]] = None) -> Dict[str, Any]:
        """Convert conversational Arabic natural language into entities, structured relations, and modal features."""
        if logs is None:
            logs = []
            
        prompt = f"""
أنت المحلل الدلالي العصبي (Semantic Parser) لنظام ذكي هجين.
مهمتك هي تحليل الجملة العربية (العامية أو الفصيحة) واستخراج الكيانات، العلاقات، وترجمة الكنايات العامية إلى مفاهيم مجردة، بالإضافة إلى البعد الزمني للعلاقات إن وجد (مثل سنة محددة أو عام معين) ومعامل الثقة/اليقين (Confidence Score) في كل كيان وعلاقة مستخرجة.

الجملة المراد تحليلها: "{sentence}"

قم بصياغة المخرجات بصيغة JSON نظيفة تحتوي على المفاتيح التالية:
1. "entities": قائمة بالكيانات المستخرجة وتصنيفها ونوعها التجريدي، وحقل "confidence" (كعدد عشري بين 0.0 و 1.0 بناءً على مدى صراحة ووضوح ذكر الكيان في السياق).
2. "relations": قائمة بالعلاقات بصيغة ثلاثية تحتوي على فاعل (subject)، علاقة (relation)، مفعول (object)، وحقلين اختياريين للزمن: "valid_from" (السنة كعدد صحيح مثل 2020) و "valid_to" (السنة كعدد صحيح مثل 2024)، وحقل "confidence" (كعدد عشري بين 0.0 و 1.0 بناءً على سياق الجملة).
   💡 تنبيه هام جداً: للأفعال اللازمة (التي لا تتطلب مفعولاً به صريحاً مثل 'تنام'، 'تتنفس'، 'يجري'، 'يضحك') أو الصفات والحالات، يجب صياغتها كعلاقة ثلاثية دلالية بوضع الكيان كفاعل (subject)، والحدث أو الفعل كعلاقة (relation)، ومفعول تجريدي مشتق من الفعل (object) (مثال: 'القطة تنام' ➔ subject: 'القطة'، relation: 'تنام'، object: 'النوم' أو 'حالة النوم')، وذلك لضمان تخزين وحفظ الحقيقة بالكامل في قاعدة البيانات الدلالية وعدم ضياعها.
   🔗 تنبيه حيوي بشأن العلاقات السببية والشرطية: يجب استخراج كل العلاقات السببية (سبب ونتيجة) والشرطية والوظيفية البيئية الموجودة في النص بدقة متناهية. استخدم أسماء العلاقات التالية عند وجودها:
   - "يؤدي_إلى": لأي علاقة سبب ونتيجة (مثال: 'تكاثر الغزلان يؤدي إلى تدمير الغطاء النباتي' ➔ subject: 'تكاثر_الغزلان', relation: 'يؤدي_إلى', object: 'تدمير_الغطاء_النباتي')
   - "يمنع" أو "يحد_من": لعلاقات الضبط والتحكم (مثال: 'المفترسات تحد من تكاثر آكلات العشب' ➔ subject: 'المفترسات', relation: 'يحد_من', object: 'تكاثر_آكلات_العشب')
   - "يفترس": لعلاقات الافتراس بين الحيوانات
   - "يعتمد_على": لعلاقات الاعتماد
   - "دور_بيئي" أو "وظيفة": لوصف الأدوار الوظيفية (مثال: 'المفترسات هي صمام الأمان للبيئة' ➔ subject: 'المفترسات', relation: 'دور_بيئي', object: 'صمام_أمان_البيئة')
   - "بدون_X_يحدث_Y": للشروط السلبية المهمة (مثال: 'بدون المفترسات تتكاثر الغزلان بجنون' ➔ subject: 'غياب_المفترسات', relation: 'يؤدي_إلى', object: 'تكاثر_آكلات_العشب_الجنوني')
   ⚠️ مهم: إذا وُجدت سلسلة سببية متعددة الخطوات (مثل A يؤدي إلى B مما يؤدي إلى C)، فيجب تفكيكها إلى علاقات ثلاثية منفصلة لكل حلقة في السلسلة.
3. "idioms_translation": قائمة بقواميس تترجم أي كناية عامية (مثل "كبر دماغه من" أو "طنش") إلى مفهومها المجرد الصريح باللغة الفصحى (مثال: {{"idiom": "طنش", "translation": "تجاهل"}}).

أرجع JSON فقط دون أي نصوص تمهيدية أو شرح أو علامات ماركداون.
"""
        response_text = call_llm_api(provider, api_key, model, prompt, logs)
        cleaned_text = self.clean_and_extract_json(response_text)
        
        try:
            return json.loads(cleaned_text)
        except Exception as e:
            logs.append(f"⚠️ Critical error decoding LLM response to semantic JSON: {e}")
            raise ValueError("Failed to parse LLM structured output. Contaminated payload bypassed database ingestion.")

    def check_contradictions(self, parsed_data: Dict[str, Any]) -> List[str]:
        """Detect logical clashes between incoming propositions and historical beliefs stored in SQLite."""
        contradictions = []
        relations = parsed_data.get("relations", [])
        raw_entities = parsed_data.get("entities", [])
        
        categorization_preds = ["هو", "يكون", "يعتبر", "يمثل", "ينتمي", "نوعه", "تصنيفه", "is_a", "من_نوع"]
        negation_preds = ["ليس", "لا_يكون", "لا_يعتبر", "لا_يمثل", "ليس_من", "لا_ينتمي"]
        
        # 1. Direct positive vs negative contradiction
        for rel in relations:
            if not isinstance(rel, dict):
                continue
            subj = normalize_arabic(rel.get("subject", ""))
            pred = normalize_arabic(rel.get("relation", ""))
            obj = normalize_arabic(rel.get("object", ""))
            
            if not subj or not pred or not obj:
                continue
                
            active_graph = self.sandbox_graph if self.in_sandbox else self.graph
            
            if pred in categorization_preds:
                for np in negation_preds:
                    if active_graph.has_edge(subj, obj) and active_graph[subj][obj].get("relation") == np:
                        contradictions.append(f"تلقين ({subj} ➔ {pred} ➔ {obj}) يتناقض مباشرة مع الحقيقة المسجلة السابقة: ({subj} ➔ {np} ➔ {obj})")
            elif pred in negation_preds:
                for pp in categorization_preds:
                    if active_graph.has_edge(subj, obj) and active_graph[subj][obj].get("relation") == pp:
                        contradictions.append(f"تلقين ({subj} ➔ {pred} ➔ {obj}) يتناقض مباشرة مع الحقيقة المسجلة السابقة: ({subj} ➔ {pp} ➔ {obj})")
                        
        # 2. Categorical disjointness conflict
        disjoint_groups = [
            {"انسان", "بشر", "جماد", "اله", "حيوان", "نبات"},
            {"حي", "ميت"}
        ]
        
        entities = {}
        if isinstance(raw_entities, list):
            for item in raw_entities:
                if isinstance(item, dict):
                    name = normalize_arabic(item.get("name", ""))
                    ent_type = normalize_arabic(item.get("abstract_type", item.get("type", "")))
                    if name and ent_type:
                        entities[name] = ent_type
                        
        for name, ent_type in entities.items():
            existing_types = set()
            active_graph = self.sandbox_graph if self.in_sandbox else self.graph
            
            if active_graph.has_node(name):
                current = name
                node_data = active_graph.nodes[name]
                if node_data.get("super_type"):
                    existing_types.add(normalize_arabic(node_data.get("super_type")))
                
                while True:
                    successors = [v for u, v, d in active_graph.out_edges(current, data=True) if d.get("relation") == "is_a"]
                    if successors:
                        current = successors[0]
                        existing_types.add(normalize_arabic(current))
                    else:
                        break
                
                # Check target edges
                for _, target, edata in active_graph.out_edges(name, data=True):
                    edge_rel = normalize_arabic(edata.get("relation", ""))
                    if edge_rel in categorization_preds or edge_rel == "is_a":
                        existing_types.add(normalize_arabic(target))
                        
            for group in disjoint_groups:
                if ent_type in group:
                    conflicts = group.intersection(existing_types)
                    conflicts.discard(ent_type)
                    if conflicts:
                        contradictions.append(f"الكيان '{name}' تم تصنيفه كـ '{ent_type}'، لكنه مسجل سابقاً تحت فئة متناقضة: {list(conflicts)}")
                        
        return contradictions

    def learn_and_store(self, parsed_data: Dict[str, Any], logs: Optional[List[str]] = None) -> List[Tuple[str, str, str]]:
        """Validate, ingest parsed knowledge, trigger modal mapping, and perform recursive forward chaining."""
        if logs is None:
            logs = []
            
        self.last_relations = []
        raw_entities = parsed_data.get("entities", [])
        relations = parsed_data.get("relations", [])
        
        contradictions = self.check_contradictions(parsed_data)
        if contradictions:
            logs.append("🚨 [كاشف التناقض المنطقي]: تم اكتشاف تعارض في الجملة المعالجة مع قاعدة البيانات!")
            for msg in contradictions:
                logs.append(f"   ⚠️ {msg}")
            logs.append("   📌 سيقوم النظام بمحاولة التخزين مع الاحتفاظ بتسجيلات التعارض.")
            
        has_learned = False

        entities = {}
        if isinstance(raw_entities, list):
            for item in raw_entities:
                if isinstance(item, dict):
                    name = item.get("name", "")
                    ent_type = item.get("abstract_type", item.get("type", ""))
                    conf = item.get("confidence", 1.0)
                    if name and ent_type:
                        entities[name] = {"type": ent_type, "confidence": conf}
                        
        for name, info in entities.items():
            ent_type = info["type"]
            conf = info["confidence"]
            
            # Modal modifications based on semantics
            if any(term in name for term in ["غالباً", "احتمال", "ربما", "تقريباً"]):
                conf = min(conf, 0.65)
            elif any(term in name for term in ["تماماً", "بالتأكيد", "قطعاً"]):
                conf = max(conf, 0.98)
            elif any(term in name for term in ["نادراً", "شحيحاً"]):
                conf = min(conf, 0.38)
                
            active_graph = self.sandbox_graph if self.in_sandbox else self.graph
            if not active_graph.has_node(name):
                logs.append(f"🧠 [تعلم تراكمي]: إدراج مفهوم جديد '{name}' ➔ تصنيفه: '{ent_type}' بـثقة {conf:.2f}")
                self.save_concept_to_db(name, ent_type, [], confidence=conf)
                has_learned = True

        for rel in relations:
            if not isinstance(rel, dict):
                continue
            subj = rel.get("subject", "")
            pred = rel.get("relation", "")
            obj = rel.get("object", "")
            valid_from = rel.get("valid_from")
            valid_to = rel.get("valid_to")
            conf = rel.get("confidence", 1.0)
            
            if not subj or not pred or not obj:
                continue
                
            # Modal confidence tweaking
            if any(term in pred or term in obj for term in ["غالباً", "تقريباً", "ربما"]):
                conf = min(conf, 0.60)
                logs.append(f"⚖️ [منطق مضبب]: تعديل ثقة العلاقة ({subj} ➔ {pred} ➔ {obj}) لـ {conf:.2f} لوجود مؤشر احتمالي")
            elif any(term in pred or term in obj for term in ["بالتأكيد", "تماماً", "قطعاً", "دائماً"]):
                conf = max(conf, 0.99)
                logs.append(f"⚖️ [منطق مضبب]: رفع ثقة العلاقة ({subj} ➔ {pred} ➔ {obj}) لـ {conf:.2f} لوجود مؤشر يقيني")
            elif any(term in pred or term in obj for term in ["نادراً", "قليلاً"]):
                conf = min(conf, 0.35)
                logs.append(f"⚖️ [منطق مضبب]: خفض ثقة العلاقة ({subj} ➔ {pred} ➔ {obj}) لـ {conf:.2f} لوجود مؤشر ندرة")
                
            # Emotional valence tagging
            valence = 0.0
            pos_words = ["يحب", "سعيد", "صديق", "جميل", "رائع", "انتصار", "أمل", "حب", "خير", "نجاح", "أمان"]
            neg_words = ["يكره", "حزين", "عدو", "قبيح", "فشل", "موت", "حرب", "خوف", "شر", "غضب", "حزن"]
            
            combined_text = f"{subj} {pred} {obj}"
            if any(w in combined_text for w in pos_words):
                valence = 0.75
            elif any(w in combined_text for w in neg_words):
                valence = -0.75
                
            if abs(valence) > 0.0:
                logs.append(f"❤️ [ذاكرة انفعالية]: ربط شحنة عاطفية (valence = {valence:.2f}) بالرابطة المعرفية الجديدة.")

            self.last_relations.append((subj, pred, obj))
            
            active_graph = self.sandbox_graph if self.in_sandbox else self.graph
            if not (active_graph.has_edge(subj, obj) and active_graph[subj][obj].get("relation") == pred):
                time_info = ""
                if valid_from and valid_to:
                    time_info = f" [🕒 {valid_from} - {valid_to}]"
                elif valid_from:
                    time_info = f" [🕒 منذ {valid_from}]"
                elif valid_to:
                    time_info = f" [🕒 حتى {valid_to}]"
                    
                logs.append(f"🧠 [تعلم تراكمي]: استيعاب حقيقة جديدة: ({subj} ➔ {pred} ➔ {obj}){time_info} بـثقة {conf:.2f}")
                self.save_triple_to_db(subj, pred, obj, valid_from, valid_to, confidence=conf, emotional_valence=valence)
                has_learned = True

        # Run multi-hop deductive chaining
        inferred = self.run_transitive_reasoning(logs)
        if inferred:
            has_learned = True

        if has_learned:
            logs.append("💾 [مزامنة الذاكرة]: تم حفظ كافة المعلومات والاستنتاجات في الذاكرة بنجاح.")
        else:
            logs.append("💤 [الذاكرة التراكمية]: لم يتم العثور على أي معلومات جديدة؛ كافة الحقائق مسجلة مسبقاً.")
            
        return inferred

    def run_transitive_reasoning(self, logs: Optional[List[str]] = None) -> List[Tuple[str, str, str]]:
        """Multi-hop forward chaining deductive logic engine."""
        if logs is None:
            logs = []
            
        if self.strict_mode:
            logs.append("🔒 [وضع الحقائق الثابتة]: تم إيقاف الاستدلال التلقائي لضمان ثبات المعرفة بنسبة 100% دون أي احتمالات.")
            return []
            
        inferred = []
        graph_to_use = self.sandbox_graph if self.in_sandbox else self.graph
        
        # 1. basic taxonomic transitivity (A is_a B and B is_a C => A is_a C)
        for node in list(graph_to_use.nodes):
            current = node
            path = []
            while True:
                successors = [v for u, v, d in graph_to_use.out_edges(current, data=True) if d.get("relation") == "is_a"]
                if successors:
                    current = successors[0]
                    path.append(current)
                else:
                    break
            
            if len(path) > 1:
                ancestor = path[-1]
                if not (graph_to_use.has_edge(node, ancestor) and graph_to_use[node][ancestor].get("relation") == "is_a"):
                    self.save_triple_to_db(node, "is_a", ancestor)
                    logs.append(f"🧠 [استدلال دلالي ذاتي]: تم استنتاج وراثة فئوية جديدة تلقائياً: ({node} ➔ is_a ➔ {ancestor})")
                    inferred.append((node, "is_a", ancestor))

        # 2. Dynamic Recursive Forward Chaining via SQLite rules
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT rule_name, antecedents, consequent, confidence FROM rules WHERE is_active = 1")
            rules_rows = cursor.fetchall()
            conn.close()
        except Exception as e:
            logs.append(f"⚠️ Failed to query reasoning rules: {e}")
            rules_rows = []

        active_rules = []
        for name, ant_json, cons_json, conf in rules_rows:
            try:
                active_rules.append({
                    "name": name,
                    "antecedents": json.loads(ant_json),
                    "consequent": json.loads(cons_json),
                    "confidence": conf or 1.0
                })
            except Exception as e:
                logs.append(f"⚠️ Schema syntax error in rule '{name}': {e}")

        # Backtracking Pattern Matcher
        def match_antecedents(graph, antecedents, index=0, env=None):
            if env is None:
                env = {}
            if index == len(antecedents):
                yield env
                return
                
            pattern = antecedents[index]
            p_s, p_p, p_o = pattern
            p_s = normalize_arabic(p_s)
            p_p = normalize_arabic(p_p)
            p_o = normalize_arabic(p_o)
            
            for u, v, data in list(graph.edges(data=True)):
                rel = normalize_arabic(data.get("relation", ""))
                if rel != p_p:
                    continue
                    
                s_val = env.get(p_s) if p_s.startswith("?") else p_s
                if s_val is not None and s_val != u:
                    continue
                    
                o_val = env.get(p_o) if p_o.startswith("?") else p_o
                if o_val is not None and o_val != v:
                    continue
                    
                new_env = env.copy()
                if p_s.startswith("?"):
                    new_env[p_s] = u
                if p_o.startswith("?"):
                    new_env[p_o] = v
                    
                yield from match_antecedents(graph, antecedents, index + 1, new_env)

        max_iterations = 10
        iteration = 0
        inferred_in_loop = True
        
        logs.append("⚡ [محرك الاستدلال الهجين]: بدء تشغيل حلقة الاستدلال التكرارية...")
        
        while inferred_in_loop and iteration < max_iterations:
            inferred_in_loop = False
            iteration += 1
            new_triples_this_iter = 0
            
            for rule in active_rules:
                ants = rule["antecedents"]
                cons = rule["consequent"]
                conf = rule["confidence"]
                
                for env in match_antecedents(graph_to_use, ants):
                    c_s, c_p, c_o = cons
                    subj = env.get(c_s) if c_s.startswith("?") else c_s
                    pred = env.get(c_p) if c_p.startswith("?") else c_p
                    obj = env.get(c_o) if c_o.startswith("?") else c_o
                    
                    if not subj or not pred or not obj:
                        continue
                        
                    subj = normalize_arabic(subj)
                    pred = normalize_arabic(pred)
                    obj = normalize_arabic(obj)
                    
                    if not (graph_to_use.has_edge(subj, obj) and graph_to_use[subj][obj].get("relation") == pred):
                        self.save_triple_to_db(subj, pred, obj, confidence=conf)
                        logs.append(
                            f"🧠 [استدلال ديناميكي] (تكرار {iteration}): استنتاج علاقة جديدة عبر [{rule['name']}]: "
                            f"({subj} ➔ {pred} ➔ {obj}) بـثقة {conf:.2f}"
                        )
                        inferred.append((subj, pred, obj))
                        inferred_in_loop = True
                        new_triples_this_iter += 1
                        
            if new_triples_this_iter > 0:
                logs.append(f"🔄 Iteration {iteration} completed with {new_triples_this_iter} new logical links.")
                
        if iteration >= max_iterations:
            logs.append("⚠️ [Deduction Engine]: Reasoning loop terminated early to avoid circular logic recursion.")
        else:
            logs.append(f"✅ Reasoning loop stabilized in {iteration} epochs.")
            
        return inferred

    def run_pure_db_rag(self, sentence: str, provider: str, api_key: str, model: str, logs: Optional[List[str]] = None) -> str:
        """Execute strictly hallucination-free reasoning by feeding extracted graph facts to LLM context."""
        if logs is None:
            logs = []
            
        logs.append("🔍 Activating Pure DB Reasoning mode...")
        logs.append("🌐 Isolating keywords for ontology matching...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name, super_type, properties FROM concepts")
        concepts = cursor.fetchall()
        cursor.execute("SELECT subject, predicate, object FROM triples")
        triples = cursor.fetchall()
        conn.close()
        
        words = [normalize_arabic(w) for w in re.findall(r'\w+', sentence)]
        
        def strip_arabic_affixes(w):
            variants = {w}
            for prefix in ['ال', 'وال', 'فال', 'بال', 'كال', 'لل']:
                if w.startswith(prefix) and len(w) > len(prefix) + 2:
                    variants.add(w[len(prefix):])
            if not w.startswith('ال'):
                variants.add('ال' + w)
            return variants
        
        query_variants = set()
        for w in words:
            if len(w) > 2:
                query_variants.update(strip_arabic_affixes(w))
        
        matched_nodes = set()
        for node in self.graph.nodes:
            norm_node = normalize_arabic(node)
            node_variants = strip_arabic_affixes(norm_node)
            for word in words:
                if len(word) > 2:
                    word_variants = strip_arabic_affixes(word)
                    for wv in word_variants:
                        for nv in node_variants:
                            if len(wv) > 2 and len(nv) > 2 and (wv in nv or nv in wv):
                                matched_nodes.add(node)
                                break
                        if node in matched_nodes:
                            break
                if node in matched_nodes:
                    break
        
        for subj, pred, obj in triples:
            norm_pred = normalize_arabic(pred)
            norm_obj = normalize_arabic(obj)
            for wv in query_variants:
                if len(wv) > 2 and (wv in norm_pred or wv in norm_obj or wv in normalize_arabic(subj)):
                    matched_nodes.add(subj)
                    matched_nodes.add(obj)
                    break
                    
        expanded_nodes = set(matched_nodes)
        try:
            undirected_graph = self.graph.to_undirected()
            for node in matched_nodes:
                if undirected_graph.has_node(node):
                    component = nx.node_connected_component(undirected_graph, node)
                    expanded_nodes.update(component)
            logs.append(f"🌐 [Graph Isolation]: Isolated the expanded subgraph for {len(matched_nodes)} matched nodes.")
        except Exception:
            for node in matched_nodes:
                if self.graph.has_node(node):
                    neighbors = list(self.graph.neighbors(node))
                    expanded_nodes.update(neighbors)
                        
        relevant_concepts = []
        relevant_triples = []
        
        for name, super_type, props in concepts:
            if name in expanded_nodes:
                relevant_concepts.append(f"المفهوم '{name}' يندرج كنوع من '{super_type}' ولديه خصائص: {props}")
                
        for subj, pred, obj in triples:
            if subj in expanded_nodes or obj in expanded_nodes:
                relevant_triples.append(f"الحقيقة: '{subj}' ➔ '{pred}' ➔ '{obj}'")
                
        facts = relevant_concepts + relevant_triples
        
        if not facts:
            logs.append("⚠️ [Symbolic Memory]: No matching facts or conceptual nodes found in database.")
            return "عذراً، لم أجد أي معلومات أو حقائق مرتبطة بسؤالك في قاعدة البيانات الرمزية حتى الآن. هل ترغب في تعليمي إياها أولاً؟"
            
        logs.append(f"✅ Found {len(facts)} associated knowledge facts inside memory.")
        facts_context = "\n".join(facts)
        
        prompt = f"""
أنت مساعد ذكاء اصطناعي عصبي-رمزي هجين.
مهمتك هي الإجابة على سؤال المستخدم بناءً **فقط** وبشكل صارم ودقيق على الحقائق المعرفية التالية المسترجعة من الذاكرة الرمزية الخاصة بالنظام.

الحقائق المعرفية المسترجعة:
{facts_context}

سؤال المستخدم المراد الإجابة عنه: "{sentence}"

الشروط والقواعد الصارمة:
1. صغ إجابة لغوية طبيعية وبلسان عربي فصيح وبليغ ومفهوم.
2. التزم تماماً بالحقائق المعطاة أعلاه، ولكن يُسمح لك إجراء الاستنتاجات المنطقية المترابطة والتعدية المنطقية (Multi-hop logical chaining) المباشرة والواضحة بين هذه الحقائق (مثال: إذا كانت "مروة تسكن مع أحمد"، و"أحمد يسكن في الإسكندرية"، فمن البديهي منطقياً أن "مروة تسكن في الإسكندرية" أيضاً). وضح هذا الاستنتاج التفصيلي بأسلوب منطقي جذاب.
3. لا تخترع أو تخمن أو تستعين بأي معلومات خارجية لم تذكر أو يمكن استنتاجها منطقياً من الحقائق إطلاقاً.
4. إذا لم تكن الحقائق كافية للإجابة، قل بكل وضوح: "عذراً، لا تتوفر معلومات كافية في قاعدة معرفتي الحالية للإجابة عن هذا السؤال بدقة."
"""
        logs.append("🤔 Formulating conversational, hallucination-free response strictly bounded by extracted triples...")
        return call_llm_api(provider, api_key, model, prompt, logs)

    def find_relation_path_string(self, concept_a: str, concept_b: str, logs: Optional[List[str]] = None) -> str:
        """Find the shortest path path connecting two nodes inside the graph (Explainable logic)."""
        if logs is None:
            logs = []
            
        def clean_node_name(name):
            name = normalize_arabic(name.strip())
            if name.startswith("ال") and not self.graph.has_node(name) and self.graph.has_node(name[2:]):
                return name[2:]
            return name

        c_a = clean_node_name(concept_a)
        c_b = clean_node_name(concept_b)
        
        if not (self.graph.has_node(c_a) and self.graph.has_node(c_b)):
            return f"لم يتم العثور على مسار مباشر أو غير مباشر يربط بين '{concept_a}' و '{concept_b}' في الشبكة الحالية."
            
        try:
            undirected_graph = self.graph.to_undirected()
            path = nx.shortest_path(undirected_graph, source=c_a, target=c_b)
            
            visual_path = []
            for i in range(len(path) - 1):
                u = path[i]
                v = path[i+1]
                if self.graph.has_edge(u, v):
                    rel = self.graph[u][v].get("relation", "علاقة")
                    visual_path.append(f"'{u}' ➔ ({rel}) ➔ '{v}'")
                else:
                    rel = self.graph[v][u].get("relation", "علاقة")
                    visual_path.append(f"'{u}' ➔ (عكس_{rel}) ➔ '{v}'")
            
            logs.append(f"✅ Discovered a semantic path between '{c_a}' and '{c_b}' spanning {len(path)-1} hops.")
            return f"تم اكتشاف الرابط الدلالي التراكمي بين '{concept_a}' و '{concept_b}':\n" + " ➔ ".join(path) + "\n\nالتفصيل اللينكي:\n" + "\n".join(visual_path)
        except nx.NetworkXNoPath:
            return f"لا يوجد أي رابط مباشر أو غير مباشر يجمع بين '{c_a}' and '{c_b}' في الذاكرة الرمزية حالياً."

    def run_probabilistic_inference(self, concept_a: str, concept_b: str, logs: Optional[List[str]] = None) -> str:
        """Compute semantic logic pathways with cascading confidence score propagation (Probabilistic Logic Networks)."""
        if logs is None:
            logs = []
            
        if self.strict_mode:
            logs.append("🔒 [Fixed Truth Mode]: PLN reasoning is disabled in strict verification mode.")
            return "🔒 تم تعطيل الاستدلال الاحتمالي (PLN) في وضع الحقائق الثابتة لضمان ثبات المعرفة بنسبة 100%."
            
        c_a = normalize_arabic(concept_a.strip())
        c_b = normalize_arabic(concept_b.strip())
        
        graph_to_use = self.sandbox_graph if self.in_sandbox else self.graph
        
        if not (graph_to_use.has_node(c_a) and graph_to_use.has_node(c_b)):
            return f"لا توجد العقد المطلوبة ({c_a}، {c_b}) في الذاكرة حالياً لإجراء الاستدلال الاحتمالي."
            
        try:
            # We calculate all simple paths and accumulate their multiplicative weights
            undirected_graph = graph_to_use.to_undirected()
            paths = list(nx.all_simple_paths(undirected_graph, source=c_a, target=c_b, cutoff=4))
            
            if not paths:
                return f"لم يعثر محرك PLN على أي مسار احتمالي يربط بين [{c_a}] و [{c_b}]."
                
            path_details = []
            max_probability = 0.0
            best_path = None
            
            for path in paths:
                prob = 1.0
                steps = []
                for i in range(len(path) - 1):
                    u, v = path[i], path[i+1]
                    if graph_to_use.has_edge(u, v):
                        edge_data = graph_to_use[u][v]
                        w = edge_data.get("confidence", 1.0)
                        rel = edge_data.get("relation", "علاقة")
                        steps.append(f"({u} ➔ {rel} ➔ {v} [{w:.2f}])")
                    else:
                        edge_data = graph_to_use[v][u]
                        w = edge_data.get("confidence", 1.0)
                        rel = edge_data.get("relation", "علاقة")
                        steps.append(f"({u} ➔ عكس_{rel} ➔ {v} [{w:.2f}])")
                    prob *= w
                
                path_details.append(f"⚡ مسار: {' -> '.join(steps)} => ثقة كلية: {prob:.3f}")
                if prob > max_probability:
                    max_probability = prob
                    best_path = path
                    
            logs.append(f"🎲 PLN assessed {len(paths)} unique pathway connections.")
            return f"🎲 نتائج الاستدلال الاحتمالي (PLN):\n" + "\n".join(path_details) + f"\n\n🏆 أفضل مسار ترابطي له يقين كلي = {max_probability:.3f}"
        except Exception as e:
            return f"فشل الاستدلال الاحتمالي PLN: {str(e)}"

    def self_improve_rule_induction(self, logs: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Mine cycles and patterns in the knowledge graph to generate and save new inference rules (Self-Improvement)."""
        if logs is None:
            logs = []
            
        if self.strict_mode:
            logs.append("🔒 [Fixed Truth Mode]: Symbolic rule induction is locked.")
            return []
            
        graph_to_use = self.sandbox_graph if self.in_sandbox else self.graph
        logs.append("⚡ [حث القواعد الرمزية]: جاري فحص الرسوم المعرفية واكتشاف الأنماط المتكررة...")
        
        candidates = {}
        nodes = list(graph_to_use.nodes)
        if len(nodes) < 3:
            logs.append("⚠️ [حث القواعد]: عدد العقد في الشبكة المعرفية قليل جداً (< 3) لا يسمح بحث القواعد تلقائياً.")
            return []
            
        for x in nodes:
            for y in nodes:
                if x == y: continue
                for _, _, d1 in graph_to_use.out_edges(x, data=True):
                    if d1.get("relation") == "is_a": continue
                    rel_a = d1.get("relation")
                    if not rel_a: continue
                    
                    for _, z, d2 in graph_to_use.out_edges(y, data=True):
                        if z == x or z == y: continue
                        if d2.get("relation") == "is_a": continue
                        rel_b = d2.get("relation")
                        if not rel_b: continue
                        
                        for _, _, d3 in graph_to_use.out_edges(x, data=True):
                            rel_c = d3.get("relation")
                            if not rel_c: continue
                            
                            key = (rel_a, rel_b, rel_c)
                            if key not in candidates:
                                candidates[key] = {"instances": set()}
                            candidates[key]["instances"].add((x, y, z))
                            
        new_rules = []
        for (rel_a, rel_b, rel_c), data in candidates.items():
            support = len(data["instances"])
            confidence = min(1.0, 0.4 + (support * 0.15))
            
            if support >= 1:
                rule_name = f"induced_{rel_a}_{rel_b}_to_{rel_c}"
                antecedents = [["?x", rel_a, "?y"], ["?y", rel_b, "?z"]]
                consequent = ["?x", rel_c, "?z"]
                
                is_duplicate = False
                try:
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM rules WHERE rule_name=?", (rule_name,))
                    if cursor.fetchone():
                        is_duplicate = True
                    conn.close()
                except Exception:
                    pass
                    
                if not is_duplicate:
                    new_rules.append({
                        "rule_name": rule_name,
                        "antecedents": antecedents,
                        "consequent": consequent,
                        "confidence": confidence
                    })
                    
                    if not self.in_sandbox:
                        try:
                            conn = sqlite3.connect(self.db_path)
                            cursor = conn.cursor()
                            cursor.execute("""
                                INSERT OR REPLACE INTO rules (rule_name, antecedents, consequent, confidence, is_active)
                                VALUES (?, ?, ?, ?, 1)
                            """, (rule_name, json.dumps(antecedents, ensure_ascii=False), json.dumps(consequent, ensure_ascii=False), confidence))
                            conn.commit()
                            conn.close()
                        except Exception:
                            pass
                    logs.append(f"✨ [حث القوانين]: تم توليد وتوثيق قانون استنباطي جديد تلقائياً: [أداء {rule_name}] بثقة {confidence:.2f}")
                    
        return new_rules

    def get_curiosity_questions(self) -> List[Dict[str, str]]:
        """Generate high-curiosity questions targeting vague or disconnected concepts (Active Querying)."""
        if self.strict_mode:
            return []
            
        graph = self.sandbox_graph if self.in_sandbox else self.graph
        
        weak_nodes = []
        for node in graph.nodes:
            if node.startswith("event_") or node.startswith("ST_") or len(node) < 2:
                continue
            if graph.degree(node) <= 1:
                weak_nodes.append(node)
                
        if not weak_nodes:
            return []
            
        questions = []
        for node in weak_nodes:
            node_data = graph.nodes[node]
            
            # check taxonomy is_a
            has_taxonomy = bool(node_data.get("super_type"))
            if not has_taxonomy:
                for _, _, data in graph.out_edges(node, data=True):
                    if data.get("relation") == "is_a":
                        has_taxonomy = True
                        break
            if not has_taxonomy:
                questions.append({
                    "question": f"ما هو '{node}'؟ هل هو نوع من أنواع الحيوانات أم الجماد أم فئة أخرى؟",
                    "text_to_paste": f"{node} هو نوع من "
                })
                
            has_properties = bool(node_data.get("properties"))
            if not has_properties:
                questions.append({
                    "question": f"ما هي صفات وخصائص '{node}' المميزة له؟",
                    "text_to_paste": f"صفة {node} هي "
                })
                
            questions.append({
                "question": f"ما هي علاقة '{node}' بالكيانات الأخرى؟ أين يعيش أو ماذا يفعل؟",
                "text_to_paste": f"{node} يعيش في "
            })
            
        import random
        random.shuffle(questions)
        return questions[:6]

    # Sandbox toggles for experiments
    def start_sandbox(self):
        self.in_sandbox = True
        self.sandbox_graph = self.graph.copy()

    def commit_sandbox(self):
        if not self.in_sandbox:
            return
        self.graph = self.sandbox_graph.copy()
        self.in_sandbox = False
        self.sandbox_graph = None
        # Bulk save sandbox records to SQLite
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Save sandbox nodes
            for node, data in self.graph.nodes(data=True):
                super_type = data.get("super_type")
                props = data.get("properties", [])
                conf = data.get("confidence", 1.0)
                emotional_valence = data.get("emotional_valence", 0.0)
                cursor.execute("""
                    INSERT OR REPLACE INTO concepts (name, super_type, properties, confidence, emotional_valence, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (node, super_type, json.dumps(props, ensure_ascii=False), conf, emotional_valence, int(time.time())))
                
            # Save sandbox edges
            for u, v, data in self.graph.edges(data=True):
                pred = data.get("relation", "")
                valid_from = data.get("valid_from")
                valid_to = data.get("valid_to")
                conf = data.get("confidence", 1.0)
                valence = data.get("emotional_valence", 0.0)
                cursor.execute("""
                    INSERT OR REPLACE INTO triples (subject, predicate, object, valid_from, valid_to, confidence, emotional_valence, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (u, pred, v, valid_from, valid_to, conf, valence, int(time.time())))
                
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"⚠️ Failed to commit sandbox transaction to SQLite: {e}")

    def rollback_sandbox(self):
        self.in_sandbox = False
        self.sandbox_graph = None

    def predict_impact_chain(self, start_concept: str, logs: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        يتنبأ بسلسلة التأثيرات المتعاقبة انطلاقاً من حدث أو مفهوم معين
        بناءً على علاقات السببية مثل 'يؤدي_إلى' و'يسبب' و'ينتج_عنه'.
        Calculates cumulative confidence using joint probability chains.
        """
        if logs is None:
            logs = []
            
        start_concept = core_utils.normalize_arabic(start_concept)
        graph = self.sandbox_graph if self.in_sandbox else self.graph
        
        if not graph.has_node(start_concept):
            logs.append(f"⚠️ المفهوم '{start_concept}' غير موجود في قاعدة المعرفة.")
            return []
            
        logs.append(f"🔮 بدء تتبع سلسلة التأثيرات السببية لـ: '{start_concept}'")
        
        causality_relations = {
            core_utils.normalize_arabic(r) for r in {
                "يؤدي_إلى", "يسبب", "ينتج_عنه", "يؤدي إلى", "ينتج عنه", "يسبب في", "leads_to", "causes", "results_in", "leads to", "results in"
            }
        }

        
        visited = set()
        chain = []
        
        def traverse(node, current_conf, depth):
            if node in visited or depth > 5:
                return
            visited.add(node)
            
            for neighbor in graph.neighbors(node):
                edge_data = graph[node][neighbor]
                rel = edge_data.get("relation", "")
                normalized_rel = core_utils.normalize_arabic(rel)
                
                if normalized_rel in causality_relations or any(cr in normalized_rel for cr in causality_relations):
                    edge_conf = edge_data.get("confidence", 1.0)
                    cumulative_conf = current_conf * edge_conf
                    
                    impact_entry = {
                        "from": node,
                        "relation": rel,
                        "to": neighbor,
                        "confidence": edge_conf,
                        "cumulative_confidence": round(cumulative_conf, 3),
                        "depth": depth
                    }
                    chain.append(impact_entry)
                    logs.append(f"🔗 خطوة {depth}: '{node}' ➔ {rel} ➔ '{neighbor}' (ثقة تراكمية: {round(cumulative_conf, 2)})")
                    
                    traverse(neighbor, cumulative_conf, depth + 1)
                    
        traverse(start_concept, 1.0, 1)
        return chain

