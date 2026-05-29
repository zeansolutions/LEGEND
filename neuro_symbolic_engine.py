import json
import os
import sys
import re
import sqlite3
import networkx as nx
import threading
import time

from typing import List, Dict, Any, Optional
from core_utils import normalize_arabic, call_llm_api, get_local_llm

import core_utils

try:
    import google.generativeai as genai
except ImportError:
    print("Error: google-generativeai is not installed.")
    sys.exit(1)

try:
    import arabic_reshaper
    from bidi.algorithm import get_display

    HAS_RESHAPER = True
except ImportError:
    HAS_RESHAPER = False

try:
    from awesometkinter.bidirender import (
        add_bidi_support,
        render_bidi_text,
        derender_bidi_text,
    )
except ImportError:
    add_bidi_support = None
    render_bidi_text = lambda x: x
    derender_bidi_text = lambda x: x


def ar(text):
    if not text or not HAS_RESHAPER:
        return text
    try:
        # التحقق مما إذا كان النص يحتوي على حروف عربية
        if any(
            "\u0600" <= c <= "\u06ff"
            or "\u0750" <= c <= "\u077f"
            or "\u08a0" <= c <= "\u08ff"
            for c in text
        ):
            import textwrap

            paragraphs = str(text).split("\n")
            reshaped_lines = []
            for para in paragraphs:
                if not para.strip():
                    reshaped_lines.append("")
                    continue
                # لف الأسطر الطويلة يدوياً لتفادي خلل التفاف الكلمات التلقائي في Tkinter (RTL Auto-wrap bug)
                wrapped_sublines = textwrap.wrap(para, width=65)
                for subline in wrapped_sublines:
                    reshaped_line = arabic_reshaper.reshape(subline)
                    bidi_line = get_display(reshaped_line)
                    reshaped_lines.append(bidi_line)
            return "\n".join(reshaped_lines)
    except Exception:
        pass
    return text


# ANSI ألوان وتنسيقات الـ Terminal لتوفير جمالية بصرية استثنائية
class TC:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"


# مفاتيح وقوالب الـ API الافتراضية (تُركت فارغة للأمان لرفع المشروع على GitHub)
DEFAULT_KEYS = {
    "google": {
        "key": "",
        "models": [
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-3.5-flash",
            "gemini-3.1-flash-lite",
            "gemma-4-31b-it",
        ],
    },
    "groq": {
        "key": "",
        "models": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768", "gemma2-9b-it"],
    },
    "openrouter": {
        "key": "",
        "models": [
            "google/gemini-2.5-flash",
            "deepseek/deepseek-chat",
            "meta-llama/llama-3.3-70b-instruct",
        ],
    },
}

# LLM API callers are imported from core_utils


class ArabicNeuroSymbolicPrototype:
    def __init__(self, db_filename="ontology.db"):
        self.db_path = db_filename
        self.graph = nx.DiGraph()
        self.last_relations = []
        self.in_sandbox = False
        self.sandbox_graph = None
        self.abort_requested = False
        self.init_database()
        self.load_graph_from_db()

    def init_database(self):
        """إنشاء الجداول اللازمة وفهرستها في SQLite لسرعة متناهية"""
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
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_triples_sub_pred ON triples(subject, predicate)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_triples_obj ON triples(object)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_concepts_super ON concepts(super_type)"
            )

            # محاولة إضافة حقل السياق للنسخ القديمة من قاعدة البيانات
            try:
                cursor.execute(
                    "ALTER TABLE triples ADD COLUMN context TEXT DEFAULT '{}'"
                )
            except Exception:
                pass

            # محاولة إضافة حقول الزمن والثقة والأنطولوجيا الانفعالية للنسخ القديمة من قاعدة البيانات لمنع أخطاء الترقية
            try:
                cursor.execute("ALTER TABLE triples ADD COLUMN valid_from INTEGER")
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE triples ADD COLUMN valid_to INTEGER")
            except Exception:
                pass
            try:
                cursor.execute(
                    "ALTER TABLE triples ADD COLUMN confidence REAL DEFAULT 1.0"
                )
            except Exception:
                pass
            try:
                cursor.execute(
                    "ALTER TABLE triples ADD COLUMN emotional_valence REAL DEFAULT 0.0"
                )
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE triples ADD COLUMN created_at INTEGER")
            except Exception:
                pass
            try:
                cursor.execute(
                    "ALTER TABLE triples ADD COLUMN inferred INTEGER DEFAULT 0"
                )
            except Exception:
                pass

            try:
                cursor.execute(
                    "ALTER TABLE concepts ADD COLUMN confidence REAL DEFAULT 1.0"
                )
            except Exception:
                pass
            try:
                cursor.execute(
                    "ALTER TABLE concepts ADD COLUMN emotional_valence REAL DEFAULT 0.0"
                )
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE concepts ADD COLUMN created_at INTEGER")
            except Exception:
                pass

            conn.commit()
            conn.close()

            # تم إلغاء تهيئة القواعد الافتراضية لتبدأ الشبكة بوعي فارغ تماماً يبني منطقه الخاص
            pass

        except Exception as e:
            print(f" ⚠️ [خطأ SQLite] فشل تهيئة قاعدة البيانات: {e}")

    def init_default_rules(self):
        """%تهيئة القواعد المنطقية الافتراضية في قاعدة البيانات إذا لم تكن موجودة"""
        default_rules = [
            {
                "rule_name": "transitive_is_a",
                "antecedents": json.dumps(
                    [["?x", "is_a", "?y"], ["?y", "is_a", "?z"]], ensure_ascii=False
                ),
                "consequent": json.dumps(["?x", "is_a", "?z"], ensure_ascii=False),
                "confidence": 1.0,
            },
            {
                "rule_name": "transitive_lives_in",
                "antecedents": json.dumps(
                    [["?x", "يعيش_في", "?y"], ["?y", "جزء_من", "?z"]],
                    ensure_ascii=False,
                ),
                "consequent": json.dumps(["?x", "يعيش_في", "?z"], ensure_ascii=False),
                "confidence": 0.95,
            },
            {
                "rule_name": "transitive_works_in",
                "antecedents": json.dumps(
                    [["?x", "يعمل_في", "?y"], ["?y", "جزء_من", "?z"]],
                    ensure_ascii=False,
                ),
                "consequent": json.dumps(["?x", "يعمل_في", "?z"], ensure_ascii=False),
                "confidence": 0.95,
            },
            {
                "rule_name": "transitive_causation",
                "antecedents": json.dumps(
                    [["?x", "يؤدي_إلى", "?y"], ["?y", "يؤدي_إلى", "?z"]],
                    ensure_ascii=False,
                ),
                "consequent": json.dumps(["?x", "يؤدي_إلى", "?z"], ensure_ascii=False),
                "confidence": 0.90,
            },
        ]

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            for r in default_rules:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO rules (rule_name, antecedents, consequent, confidence, is_active)
                    VALUES (?, ?, ?, ?, 1)
                """,
                    (
                        r["rule_name"],
                        r["antecedents"],
                        r["consequent"],
                        r["confidence"],
                    ),
                )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"⚠️ فشل تهيئة القواعد الافتراضية: {e}")

    def load_graph_from_db(self):
        """تحميل المعرفة الكاملة من SQLite إلى كائن NetworkX في الذاكرة (RAM)"""
        try:
            self.graph.clear()
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            try:
                cursor.execute(
                    "SELECT name, super_type, properties, confidence, emotional_valence, created_at FROM concepts"
                )
                concept_rows = cursor.fetchall()
            except sqlite3.OperationalError:
                try:
                    cursor.execute(
                        "SELECT name, super_type, properties, confidence FROM concepts"
                    )
                    concept_rows = [r + (0.0, None) for r in cursor.fetchall()]
                except sqlite3.OperationalError:
                    cursor.execute("SELECT name, super_type, properties FROM concepts")
                    concept_rows = [r + (1.0, 0.0, None) for r in cursor.fetchall()]

            for (
                name,
                super_type,
                props_json,
                confidence,
                emotional_valence,
                created_at,
            ) in concept_rows:
                if confidence is None:
                    confidence = 1.0
                if emotional_valence is None:
                    emotional_valence = 0.0
                props = json.loads(props_json) if props_json else []
                self.graph.add_node(
                    name,
                    type="concept",
                    super_type=super_type,
                    properties=props,
                    confidence=confidence,
                    emotional_valence=emotional_valence,
                    created_at=created_at,
                )
                if super_type:
                    self.graph.add_edge(
                        name,
                        super_type,
                        relation="is_a",
                        confidence=1.0,
                        emotional_valence=0.0,
                        created_at=created_at,
                    )

            try:
                cursor.execute(
                    "SELECT subject, predicate, object, valid_from, valid_to, confidence, emotional_valence, created_at, inferred, context FROM triples"
                )
                rows = cursor.fetchall()
            except sqlite3.OperationalError:
                try:
                    cursor.execute(
                        "SELECT subject, predicate, object, valid_from, valid_to, confidence, emotional_valence, created_at, inferred FROM triples"
                    )
                    rows = [r + ("{}",) for r in cursor.fetchall()]
                except sqlite3.OperationalError:
                    try:
                        cursor.execute(
                            "SELECT subject, predicate, object, valid_from, valid_to, confidence, emotional_valence, created_at FROM triples"
                        )
                        rows = [r + (0, "{}") for r in cursor.fetchall()]
                    except sqlite3.OperationalError:
                        try:
                            cursor.execute(
                                "SELECT subject, predicate, object, valid_from, valid_to, confidence FROM triples"
                            )
                            rows = [r + (0.0, None, 0, "{}") for r in cursor.fetchall()]
                        except sqlite3.OperationalError:
                            cursor.execute(
                                "SELECT subject, predicate, object FROM triples"
                            )
                            rows = [
                                r + (None, None, 1.0, 0.0, None, 0, "{}")
                                for r in cursor.fetchall()
                            ]

            for (
                subj,
                pred,
                obj,
                valid_from,
                valid_to,
                confidence,
                emotional_valence,
                created_at,
                inferred,
                context,
            ) in rows:
                if confidence is None:
                    confidence = 1.0
                if emotional_valence is None:
                    emotional_valence = 0.0
                if inferred is None:
                    inferred = 0
                try:
                    ctx = (
                        json.loads(context)
                        if isinstance(context, str)
                        else (context or {})
                    )
                except Exception:
                    ctx = {}
                if not self.graph.has_node(subj):
                    self.graph.add_node(subj, type="instance")
                if not self.graph.has_node(obj):
                    self.graph.add_node(obj, type="instance")
                self.graph.add_edge(
                    subj,
                    obj,
                    relation=pred,
                    valid_from=valid_from,
                    valid_to=valid_to,
                    confidence=confidence,
                    emotional_valence=emotional_valence,
                    created_at=created_at,
                    inferred=inferred,
                    context=ctx,
                )

            conn.close()
        except Exception as e:
            print(f" ⚠️ [خطأ تحميل RAM] فشل ملء كائن NetworkX: {e}")

    def save_concept_to_db(
        self, name, super_type, properties=[], confidence=1.0, emotional_valence=0.0
    ):
        name = normalize_arabic(name)
        super_type = normalize_arabic(super_type) if super_type else super_type
        if confidence is None:
            confidence = 1.0

        graph_to_use = self.sandbox_graph if self.in_sandbox else self.graph
        graph_to_use.add_node(
            name,
            type="concept",
            super_type=super_type,
            properties=properties,
            confidence=confidence,
            emotional_valence=emotional_valence,
            created_at=int(time.time()),
        )
        if super_type:
            graph_to_use.add_edge(
                name,
                super_type,
                relation="is_a",
                confidence=1.0,
                emotional_valence=0.0,
                created_at=int(time.time()),
            )

        if self.in_sandbox:
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO concepts (name, super_type, properties, confidence, emotional_valence, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    name,
                    super_type,
                    json.dumps(properties),
                    confidence,
                    emotional_valence,
                    int(time.time()),
                ),
            )
            conn.commit()
            conn.close()
        except sqlite3.OperationalError:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO concepts (name, super_type, properties) VALUES (?, ?, ?)",
                    (name, super_type, json.dumps(properties)),
                )
                conn.commit()
                conn.close()
            except Exception as e:
                print(f" ⚠️ تعذر حفظ المفهوم {name}: {e}")
        except Exception as e:
            print(f" ⚠️ تعذر حفظ المفهوم {name}: {e}")

    def save_triple_to_db(
        self,
        subj,
        pred,
        obj,
        valid_from=None,
        valid_to=None,
        confidence=1.0,
        emotional_valence=0.0,
        inferred=0,
        context=None,
    ):
        subj = normalize_arabic(subj)
        pred = normalize_arabic(pred)
        obj = normalize_arabic(obj)
        if confidence is None:
            confidence = 1.0
        ctx = context or {}

        graph_to_use = self.sandbox_graph if self.in_sandbox else self.graph

        if not graph_to_use.has_node(subj):
            graph_to_use.add_node(subj, type="instance")
        if not graph_to_use.has_node(obj):
            graph_to_use.add_node(obj, type="instance")
        graph_to_use.add_edge(
            subj,
            obj,
            relation=pred,
            valid_from=valid_from,
            valid_to=valid_to,
            confidence=confidence,
            emotional_valence=emotional_valence,
            created_at=int(time.time()),
            inferred=inferred,
            context=ctx,
        )

        if self.in_sandbox:
            return

        context_json = json.dumps(ctx, ensure_ascii=False)

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO triples (subject, predicate, object, valid_from, valid_to, confidence, emotional_valence, created_at, inferred, context)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    subj,
                    pred,
                    obj,
                    valid_from,
                    valid_to,
                    confidence,
                    emotional_valence,
                    int(time.time()),
                    inferred,
                    context_json,
                ),
            )
            conn.commit()
            conn.close()
        except sqlite3.OperationalError:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO triples (subject, predicate, object, valid_from, valid_to, confidence, emotional_valence, created_at, inferred)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        subj,
                        pred,
                        obj,
                        valid_from,
                        valid_to,
                        confidence,
                        emotional_valence,
                        int(time.time()),
                        inferred,
                    ),
                )
                conn.commit()
                conn.close()
            except sqlite3.OperationalError:
                try:
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO triples (subject, predicate, object, valid_from, valid_to, confidence, emotional_valence, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            subj,
                            pred,
                            obj,
                            valid_from,
                            valid_to,
                            confidence,
                            emotional_valence,
                            int(time.time()),
                        ),
                    )
                    conn.commit()
                    conn.close()
                except sqlite3.OperationalError:
                    try:
                        conn = sqlite3.connect(self.db_path)
                        cursor = conn.cursor()
                        cursor.execute(
                            """
                            INSERT OR REPLACE INTO triples (subject, predicate, object, valid_from, valid_to) 
                            VALUES (?, ?, ?, ?, ?)
                        """,
                            (subj, pred, obj, valid_from, valid_to),
                        )
                        conn.commit()
                        conn.close()
                    except Exception as e:
                        print(f" ⚠️ تعذر حفظ العلاقة ({subj} -> {pred} -> {obj}): {e}")
        except Exception as e:
            print(f" ⚠️ تعذر حفظ العلاقة ({subj} -> {pred} -> {obj}): {e}")

    def delete_triple(self, subj, pred, obj):
        """حذف حقيقة معينة (ثلاثية) من قاعدة البيانات ورام الأنتولوجيا"""
        subj = normalize_arabic(subj)
        pred = normalize_arabic(pred)
        obj = normalize_arabic(obj)

        graph_to_use = self.sandbox_graph if self.in_sandbox else self.graph
        if (
            graph_to_use.has_edge(subj, obj)
            and graph_to_use[subj][obj].get("relation") == pred
        ):
            graph_to_use.remove_edge(subj, obj)

        if self.in_sandbox:
            return True

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM triples WHERE subject=? AND predicate=? AND object=?",
                (subj, pred, obj),
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"⚠️ تعذر حذف العلاقة ({subj} -> {pred} -> {obj}): {e}")
            return False

    def get_all_triples(self):
        """جلب كافة الروابط الثلاثية المسجلة في قاعدة البيانات حالياً"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "SELECT subject, predicate, object, valid_from, valid_to, confidence FROM triples"
                )
                rows = cursor.fetchall()
            except sqlite3.OperationalError:
                cursor.execute(
                    "SELECT subject, predicate, object, valid_from, valid_to FROM triples"
                )
                rows = [r + (1.0,) for r in cursor.fetchall()]
            conn.close()
            return rows
        except Exception as e:
            print(f"⚠️ تعذر جلب العلاقات: {e}")
            return []

    def clear_all_data(self):
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
            return True
        except Exception as e:
            print(f"⚠️ فشل تصفير المعرفة: {e}")
            return False

    def delete_relation(self, subject, predicate, object_node):
        """حذف علاقة دلالية معينة من قاعدة البيانات والرسم البياني"""
        active_graph = self.sandbox_graph if self.in_sandbox else self.graph

        # 1. إزالة العلاقة من الرسم البياني النشط
        if active_graph.has_edge(subject, object_node):
            edge_data = active_graph.get_edge_data(subject, object_node)
            if edge_data and edge_data.get("relation") == predicate:
                active_graph.remove_edge(subject, object_node)

        # 2. إذا كنا في البيئة التجريبية، لا نلمس قاعدة البيانات المستقرة
        if self.in_sandbox:
            return True

        # 3. الحذف الفعلي من SQLite للمساحة المستقرة
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM triples WHERE subject=? AND predicate=? AND object=?",
                (subject, predicate, object_node),
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"⚠️ فشل حذف العلاقة من قاعدة البيانات: {e}")
            return False

    def delete_node(self, node_name):
        """حذف مفهوم/كيان بالكامل من قاعدة البيانات والرسم البياني مع كافة العلاقات المرتبطة به"""
        active_graph = self.sandbox_graph if self.in_sandbox else self.graph

        # 1. إزالة الكيان والعلاقات المرتبطة به من الرسم البياني النشط
        if active_graph.has_node(node_name):
            active_graph.remove_node(node_name)

        # 2. إذا كنا في البيئة التجريبية، لا نلمس قاعدة البيانات المستقرة
        if self.in_sandbox:
            return True

        # 3. الحذف الفعلي من SQLite للمساحة المستقرة
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM concepts WHERE name=?", (node_name,))
            cursor.execute(
                "DELETE FROM triples WHERE subject=? OR object=?",
                (node_name, node_name),
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"⚠️ فشل حذف الكيان {node_name} من قاعدة البيانات: {e}")
            return False

    def gather_db_statistics(self):
        """جمع وتحليل مقاييس وإحصاءات الأنتولوجيا من SQLite ورام الرسم البياني"""
        active_graph = self.sandbox_graph if self.in_sandbox else self.graph
        total_concepts = active_graph.number_of_nodes()
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM concepts")
            total_concepts = cursor.fetchone()[0]
        except Exception:
            pass

        total_triples = 0
        try:
            cursor.execute("SELECT COUNT(*) FROM triples")
            total_triples = cursor.fetchone()[0]
        except Exception:
            pass

        total_instances = 0
        try:
            instances = [
                n
                for n, d in active_graph.nodes(data=True)
                if d.get("type") == "instance"
            ]
            total_instances = len(instances)
        except Exception:
            pass

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
            top_connected = sorted(degrees.items(), key=lambda x: x[1], reverse=True)[
                :5
            ]
        except Exception:
            pass

        top_predicates = []
        try:
            cursor.execute(
                "SELECT predicate, COUNT(*) as c FROM triples GROUP BY predicate ORDER BY c DESC LIMIT 5"
            )
            top_predicates = cursor.fetchall()
            conn.close()
        except Exception:
            try:
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
            "top_predicates": top_predicates,
        }

    def clean_and_extract_json(self, text):
        if not text:
            return "{}"
        text = text.strip()

        # 1. إزالة أي علامات اقتباس أو ماركداون محيطة بالنص كخطوة أولية
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

        # 2. البحث عن أول قوس فتح { أو [ ليتلاءم مع المصفوفات والقواميس
        first_brace = text.find("{")
        first_bracket = text.find("[")

        start_char = "{"
        first_idx = first_brace
        if first_bracket != -1 and (first_brace == -1 or first_bracket < first_brace):
            start_char = "["
            first_idx = first_bracket

        if first_idx == -1:
            return text

        # إيجاد كافة مواقع أقواس الإغلاق } و ]
        end_char = "}" if start_char == "{" else "]"
        brace_indices = [i for i, char in enumerate(text) if char == end_char]
        if not brace_indices:
            return text

        # 3. محاولة فك الترميز تنازلياً من أقصى نافذة إلى أصغر نافذة صالحة كـ JSON
        for idx in reversed(brace_indices):
            if idx > first_idx:
                candidate = text[first_idx : idx + 1]
                candidate_clean = re.sub(r",\s*([\]}])", r"\1", candidate)
                try:
                    json.loads(candidate_clean)
                    return candidate_clean
                except Exception:
                    continue

        # 4. محاولة تنظيف وتجهيز النافذة الكاملة كخيار أخير
        last_brace = text.rfind(end_char)
        if last_brace > first_idx:
            candidate = text[first_idx : last_brace + 1]
            return re.sub(r",\s*([\]}])", r"\1", candidate)

        return text

    def parse_sentence_with_llm(
        self, sentence, provider, api_key, model, logs=None, language="ar"
    ):
        if logs is None:
            logs = []

        # Build multilingual prompt based on user's UI language
        lang_instructions = {
            "ar": {
                "role": "أنت المحلل الدلالي العصبي (Semantic Parser) لنظام ذكي هجين فائق الذكاء.",
                "task": "مهمتك هي إجراء تحليل دلالي شامل وعميق وتفصيلي للنص المرفق واستخراج جميع الكيانات والعلاقات الدلالية (الظاهرة والضمنية)، والروابط السببية والشرطية والصفات والأفعال والحالات بدقة فائقة دون إغفال أي تفصيلة دقيقة (Exhaustive Extraction).",
                "sentence_label": "النص المراد تحليله دلالياً",
                "output_lang": "يجب أن تكون أسماء الكيانات والعلاقات باللغة العربية (لغة الجملة المدخلة).",
                "intransitive_note": "💡 تنبيه هام: للأفعال اللازمة أو الصفات والحالات، صِغها كعلاقة ثلاثية دلالية (مثال: 'القطة تنام' ➔ subject: 'القطة'، relation: 'تنام'، object: 'النوم'، أو 'الماء صلب' ➔ subject: 'ماء'، relation: 'صفته'، object: 'صلب').",
                "causal_note": "🔗 استخرج كل العلاقات السببية، الشرطية، والحدثية والزمنية والمكانية بدقة متناهية. لا تترك أي حقيقة أو تفصيل يمر دون تحليله واستخراجه.",
                "idioms_note": "ترجم أي كنايات عامية إلى مفاهيم مجردة صريحة.",
                "comprehensive_note": "⚠️ تنبيه بالغ الأهمية: يجب استخراج كل علاقة ممكنة من النص بالكامل. لا تكتفِ بالعلاقات الأساسية فقط؛ بل استخرج العلاقات التفصيلية والضمنية، روابط الصفات، الأماكن، الأحداث، التغييرات، والأسباب والمسببات بدقة وعمق متناهٍ لضمان الاكتمال المعرفي الشامل.",
                "json_only": "أرجع JSON فقط دون أي نصوص تمهيدية أو شرح أو علامات ماركداون.",
            },
            "en": {
                "role": "You are the highly advanced Neuro-Symbolic Semantic Parser for a hybrid intelligent system.",
                "task": "Your task is to conduct an exhaustive, granular, and deep semantic analysis of the provided text, extracting all entities, detailed semantic relations (both explicit and implicit), causal, conditional, attribute, state, and spatial/temporal connections precisely without overlooking any minor detail.",
                "sentence_label": "Text to analyze semantically",
                "output_lang": "Entity names and relation names MUST be in the SAME language as the input sentence.",
                "intransitive_note": "💡 Important: For intransitive verbs, states, or adjectives, formulate them as semantic triples (e.g., 'The cat sleeps' ➔ subject: 'cat', relation: 'sleeps', object: 'sleeping', or 'Water is solid' ➔ subject: 'water', relation: 'property', object: 'solid').",
                "causal_note": "🔗 Extract all causal, conditional, event, spatial, and temporal relationships with maximum precision. Leave no factual detail unextracted.",
                "idioms_note": "Translate any colloquial idioms into their abstract formal meanings.",
                "comprehensive_note": "⚠️ CRITICAL: You must extract EVERY possible relationship from the entire text. Do not limit yourself to basic relations; extract detailed, implicit, attribute-value, spatial, temporal, causal, and sequential connections with maximum depth and granularity to ensure cognitive completeness.",
                "json_only": "Return JSON only, no preamble, no markdown fences.",
            },
            "zh": {
                "role": "你是一个混合智能系统的神经-符号语义分析器 (Semantic Parser)。",
                "task": "你的任务是分析以下句子，提取实体、关系，并将任何习语翻译成抽象概念，包括时间维度和置信度评分。",
                "sentence_label": "待分析的句子",
                "output_lang": "实体名称和关系名称必须使用与输入句子相同的语言。",
                "intransitive_note": "💡 重要提示：对于不及物动词或状态，请将其表述为语义三元组（例如：'猫在睡觉' ➔ subject: '猫', relation: '睡觉', object: '睡眠'）。",
                "causal_note": "🔗 精确提取所有因果关系和条件关系。",
                "idioms_note": "将任何口语习语翻译为其抽象的正式含义。",
                "json_only": "仅返回JSON，不要前言，不要markdown标记。",
            },
            "fr": {
                "role": "Vous êtes l'analyseur sémantique neuro-symbolique d'un système intelligent hybride.",
                "task": "Votre tâche est d'analyser la phrase suivante et d'extraire les entités, les relations et de traduire les expressions idiomatiques en concepts abstraits, y compris les dimensions temporelles et les scores de confiance.",
                "sentence_label": "Phrase à analyser",
                "output_lang": "Les noms d'entités et de relations DOIVENT être dans la MÊME langue que la phrase d'entrée.",
                "intransitive_note": "💡 Important : Pour les verbes intransitifs ou les états, formulez-les en triplets sémantiques.",
                "causal_note": "🔗 Extrayez toutes les relations causales et conditionnelles avec précision.",
                "idioms_note": "Traduisez les expressions idiomatiques en leurs significations abstraites formelles.",
                "json_only": "Retournez uniquement du JSON, sans préambule ni balises markdown.",
            },
            "es": {
                "role": "Eres el analizador semántico neuro-simbólico de un sistema inteligente híbrido.",
                "task": "Tu tarea es analizar la siguiente oración y extraer entidades, relaciones, y traducir modismos a conceptos abstractos, incluyendo dimensiones temporales y puntuaciones de confianza.",
                "sentence_label": "Oración a analizar",
                "output_lang": "Los nombres de entidades y relaciones DEBEN estar en el MISMO idioma que la oración de entrada.",
                "intransitive_note": "💡 Importante: Para verbos intransitivos o estados, formúlalos como tripletas semánticas.",
                "causal_note": "🔗 Extrae todas las relaciones causales y condicionales con precisión.",
                "idioms_note": "Traduce cualquier modismo coloquial a su significado abstracto formal.",
                "json_only": "Devuelve solo JSON, sin preámbulo ni marcas markdown.",
            },
            "tr": {
                "role": "Bir hibrit akıllı sistemin Nöro-Sembolik Anlamsal Çözümleyicisisiniz (Semantic Parser).",
                "task": "Göreviniz aşağıdaki cümleyi analiz etmek, varlıkları ve ilişkileri çıkarmak ve deyimleri soyut kavramlara dönüştürmektir.",
                "sentence_label": "Analiz edilecek cümle",
                "output_lang": "Varlık adları ve ilişki adları girdi cümlesiyle AYNI dilde olmalıdır.",
                "intransitive_note": "💡 Önemli: Geçişsiz fiiller veya durumlar için bunları anlamsal üçlüler olarak formüle edin (örn. 'Kedi uyuyor' ➔ subject: 'kedi', relation: 'uyuyor', object: 'uyku').",
                "causal_note": "🔗 Tüm nedensel ve koşullu ilişkileri kesin olarak çıkarın.",
                "idioms_note": "Tüm deyimleri soyut resmi anlamlarına çevirin.",
                "json_only": "Yalnızca JSON döndürün, ön söz yok, markdown yok.",
            },
            "de": {
                "role": "Sie sind der Neuro-Symbolische Semantische Parser für ein hybrides intelligentes System.",
                "task": "Ihre Aufgabe ist es, den folgenden Satz zu analysieren, Entitäten und Beziehungen zu extrahieren sowie Redewendungen in abstrakte Konzepte zu übersetzen.",
                "sentence_label": "Zu analysierender Satz",
                "output_lang": "Entitätsnamen und Beziehungsnamen MÜSSEN in derselben Sprache wie der Eingabesatz sein.",
                "intransitive_note": "💡 Wichtig: Für intransitive Verben oder Zustände formulieren Sie diese als semantische Tripel (z.B. 'Die Katze schläft' ➔ subject: 'Katze', relation: 'schläft', object: 'Schlaf').",
                "causal_note": "🔗 Extrahieren Sie alle kausalen und konditionalen Beziehungen präzise.",
                "idioms_note": "Übersetzen Sie umgangssprachliche Redewendungen in ihre abstrakte formale Bedeutung.",
                "json_only": "Geben Sie nur JSON zurück, keine Einleitung, keine Markdown-Formatierung.",
            },
            "ru": {
                "role": "Вы являетесь нейросимволическим семантическим парсером для гибридной интеллектуальной системы.",
                "task": "Ваша задача — проанализировать следующее предложение, извлечь сущности и отношения, а также перевести разговорные идиомы в абстрактные понятия.",
                "sentence_label": "Предложение для анализа",
                "output_lang": "Имена сущностей и отношений ДОЛЖНЫ быть на том же языке, что и входное предложение.",
                "intransitive_note": "💡 Важно: Для непереходных глаголов или состояний формулируйте их в виде семантических троек (например, 'Кошка спит' ➔ subject: 'Кошка', relation: 'спит', object: 'Сон').",
                "causal_note": "🔗 Точно извлекайте все причинно-следственные и условные связи.",
                "idioms_note": "Переводите разговорные идиомы в их абстрактные формальные значения.",
                "json_only": "Возвращайте только JSON, без вступлений и разметки markdown.",
            },
            "pt": {
                "role": "Você é o Analisador Semântico Neuro-Simbólico de um sistema inteligente híbrido.",
                "task": "Sua tarefa é analisar a seguinte frase, extrair entidades e relações, e traduzir quaisquer expressões idiomáticas em conceitos abstratos.",
                "sentence_label": "Frase para analisar",
                "output_lang": "Os nomes das entidades e relações DEVEM estar no mesmo idioma que a frase de entrada.",
                "intransitive_note": "💡 Importante: Para verbos intransitivos ou estados, formule-os como triplos semânticos (ex: 'O gato dorme' ➔ subject: 'gato', relation: 'dorme', object: 'sono').",
                "causal_note": "🔗 Extraia todas as relações causais e condicionais com precisão.",
                "idioms_note": "Traduza expressões idiomáticas coloquiais em seus significados formais abstratos.",
                "json_only": "Retorne apenas JSON, sem preâmbulo ou marcações markdown.",
            },
            "ja": {
                "role": "あなたはハイブリッド人工知能システムの神経記号的意味解析器（Semantic Parser）です。",
                "task": "あなたの任務は、次の文を分析してエンティティと関係性を抽出し、慣用句を抽象的な概念に翻訳することです。",
                "sentence_label": "分析する文",
                "output_lang": "エンティティ名および関係性名は、入力文と同じ言語でなければなりません。",
                "intransitive_note": "💡 重要: 自動詞や状態については、意味的トリプルとして定式化してください（例: '猫が眠る' ➔ subject: '猫', relation: '眠る', object: '睡眠'）。",
                "causal_note": "🔗 すべての因果関係と条件関係を正確に抽出してください。",
                "idioms_note": "口語的な慣用句をその抽象的な正式な意味に翻訳してください。",
                "json_only": "JSONのみを返し、前置きやmarkdownタグは含めないでください。",
            },
            "ko": {
                "role": "당신은 하이브리드 지능형 시스템을 위한 신경-기호적 의미 분석기 (Semantic Parser)입니다.",
                "task": "당신의 임무는 다음 문장을 분석하여 개체, 관계를 추출하고 관용구를 추상적 개념으로 번역하는 것입니다.",
                "sentence_label": "분석할 문장",
                "output_lang": "개체 이름과 관계 이름은 반드시 입력 문장과 동일한 언어여야 합니다.",
                "intransitive_note": "💡 중요: 자동사나 상태의 경우, 의미론적 트리플로 구성하십시오 (예: '고양이가 잔다' ➔ subject: '고양이', relation: '잔다', object: '수면').",
                "causal_note": "🔗 모든 인과 관계와 조건 관계를 정확하게 추출하십시오.",
                "idioms_note": "구어체 관용구를 추상적인 공식 의미로 번역하십시오.",
                "json_only": "JSON만 반환하고, 서론이나 마크다운 표시는 제외하십시오.",
            },
        }

        # Fallback: use English for unsupported languages
        instr = lang_instructions.get(language, lang_instructions["en"])

        # Language-aware JSON schema instructions to prevent LLMs from mixing languages
        json_schema_instructions = {
            "ar": """أخرج JSON نظيف بالمفاتيح التالية:
1. "entities": قائمة الكيانات المستخرجة مع "name" (بالعربية)، "type"/"abstract_type" (بالعربية)، و "confidence" (رقم عشري 0.0-1.0).
2. "relations": قائمة العلاقات الثلاثية مع "subject" (بالعربية)، "relation" (بالعربية)، "object" (بالعربية)، اختيارياً "valid_from"/"valid_to" (سنة)، و "confidence" (رقم عشري 0.0-1.0).
   ⚠️ إذا وُجدت سلسلة سببية متعددة (أ يسبب ب الذي يسبب ج)، قسّمها إلى علاقات ثلاثية منفصلة.
3. "idioms_translation": قائمة تحتوي ترجمة الكنايات العامية إلى مفاهيم مجردة ({{"idiom": "...", "translation": "..."}}).

⚠️ تحذير صارم: جميع القيم النصية (name, type, subject, relation, object) يجب أن تكون بنفس لغة الجملة المدخلة حصرياً. لا تستخدم أي لغة أخرى مطلقاً.""",
            "en": """Output clean JSON with the following keys:
1. "entities": list of extracted entities with "name", "type"/"abstract_type", and "confidence" (float 0.0-1.0).
2. "relations": list of triples with "subject", "relation", "object", optional "valid_from"/"valid_to" (integer year), and "confidence" (float 0.0-1.0).
   ⚠️ If a multi-step causal chain exists (A causes B which causes C), decompose it into separate triples.
3. "idioms_translation": list of dicts translating any colloquial idioms to formal abstract concepts ({{"idiom": "...", "translation": "..."}}).

⚠️ STRICT: All text values (name, type, subject, relation, object) MUST be in the SAME language as the input sentence. Never use any other language.""",
            "zh": """输出干净的JSON，包含以下键:
1. "entities": 提取的实体列表，包含 "name"（中文）、"type"/"abstract_type"（中文）和 "confidence"（浮点数 0.0-1.0）。
2. "relations": 三元组列表，包含 "subject"（中文）、"relation"（中文）、"object"（中文）、可选 "valid_from"/"valid_to"（整数年份）和 "confidence"（浮点数 0.0-1.0）。
   ⚠️ 如果存在多步因果链（A导致B，B导致C），请分解为独立的三元组。
3. "idioms_translation": 将口语习语翻译为抽象概念的字典列表（{{"idiom": "...", "translation": "..."}}）。

⚠️ 严格要求：所有文本值（name、type、subject、relation、object）必须使用与输入句子相同的语言。绝不使用其他语言。""",
            "fr": """Produisez du JSON propre avec les clés suivantes :
1. "entities" : liste d'entités extraites avec "name" (en français), "type"/"abstract_type" (en français) et "confidence" (flottant 0.0-1.0).
2. "relations" : liste de triplets avec "subject" (en français), "relation" (en français), "object" (en français), optionnellement "valid_from"/"valid_to" (année entière) et "confidence" (flottant 0.0-1.0).
   ⚠️ Si une chaîne causale multi-étapes existe (A cause B qui cause C), décomposez-la en triplets séparés.
3. "idioms_translation" : liste de dicts traduisant les expressions idiomatiques en concepts abstraits ({{"idiom": "...", "translation": "..."}}).

⚠️ STRICT : Toutes les valeurs textuelles (name, type, subject, relation, object) DOIVENT être dans la MÊME langue que la phrase d'entrée. N'utilisez jamais une autre langue.""",
            "es": """Produce JSON limpio con las siguientes claves:
1. "entities": lista de entidades extraídas con "name" (en español), "type"/"abstract_type" (en español) y "confidence" (flotante 0.0-1.0).
2. "relations": lista de tripletas con "subject" (en español), "relation" (en español), "object" (en español), opcionalmente "valid_from"/"valid_to" (año entero) y "confidence" (flotante 0.0-1.0).
   ⚠️ Si existe una cadena causal de múltiples pasos (A causa B que causa C), descompóngala en tripletas separadas.
3. "idioms_translation": lista de dicts traduciendo modismos coloquiales a conceptos abstractos ({{"idiom": "...", "translation": "..."}}).

⚠️ ESTRICTO: Todos los valores de texto (name, type, subject, relation, object) DEBEN estar en el MISMO idioma que la oración de entrada. Nunca use otro idioma.""",
            "tr": """Aşağıdaki anahtarlarla temiz JSON çıktısı verin:
1. "entities": Çıkarılan varlıkların listesi: "name" (Türkçe), "type"/"abstract_type" (Türkçe) ve "confidence" (ondalık 0.0-1.0).
2. "relations": Üçlü listesi: "subject" (Türkçe), "relation" (Türkçe), "object" (Türkçe), isteğe bağlı "valid_from"/"valid_to" (tamsayı yıl) ve "confidence" (ondalık 0.0-1.0).
   ⚠️ Çok adımlı bir nedensel zincir varsa (A, B'ye neden olur, B de C'ye neden olur), ayrı üçlülere bölün.
3. "idioms_translation": Konuşma dili deyimlerini soyut kavramlara çeviren sözlük listesi ({{"idiom": "...", "translation": "..."}}).

⚠️ KESİN KURAL: Tüm metin değerleri (name, type, subject, relation, object) giriş cümlesiyle AYNI dilde olmalıdır. Başka bir dil asla kullanmayın.""",
            "de": """Geben Sie sauberes JSON mit den folgenden Schlüsseln aus:
1. "entities": Liste der extrahierten Entitäten mit "name" (auf Deutsch), "type"/"abstract_type" (auf Deutsch) und "confidence" (Gleitkomma 0.0-1.0).
2. "relations": Liste von Tripeln mit "subject" (auf Deutsch), "relation" (auf Deutsch), "object" (auf Deutsch), optional "valid_from"/"valid_to" (ganzzahliges Jahr) und "confidence" (Gleitkomma 0.0-1.0).
   ⚠️ Wenn eine mehrstufige Kausalkette existiert (A verursacht B, das C verursacht), zerlegen Sie sie in separate Tripel.
3. "idioms_translation": Liste von Wörterbüchern, die umgangssprachliche Redewendungen in abstrakte Konzepte übersetzen ({{"idiom": "...", "translation": "..."}}).

⚠️ STRENG: Alle Textwerte (name, type, subject, relation, object) MÜSSEN in derselben Sprache wie der Eingabesatz sein. Verwenden Sie niemals eine andere Sprache.""",
            "ru": """Выведите чистый JSON со следующими ключами:
1. "entities": список извлечённых сущностей с "name" (на русском), "type"/"abstract_type" (на русском) и "confidence" (число с плавающей точкой 0.0-1.0).
2. "relations": список троек с "subject" (на русском), "relation" (на русском), "object" (на русском), необязательно "valid_from"/"valid_to" (целое число — год) и "confidence" (число с плавающей точкой 0.0-1.0).
   ⚠️ Если существует многошаговая причинно-следственная цепочка (A вызывает B, которое вызывает C), разбейте её на отдельные тройки.
3. "idioms_translation": список словарей, переводящих разговорные идиомы в абстрактные понятия ({{"idiom": "...", "translation": "..."}}).

⚠️ СТРОГО: Все текстовые значения (name, type, subject, relation, object) ДОЛЖНЫ быть на том же языке, что и входное предложение. Никогда не используйте другой язык.""",
            "pt": """Produza JSON limpo com as seguintes chaves:
1. "entities": lista de entidades extraídas com "name" (em português), "type"/"abstract_type" (em português) e "confidence" (flutuante 0.0-1.0).
2. "relations": lista de triplas com "subject" (em português), "relation" (em português), "object" (em português), opcionalmente "valid_from"/"valid_to" (ano inteiro) e "confidence" (flutuante 0.0-1.0).
   ⚠️ Se existir uma cadeia causal de múltiplos passos (A causa B que causa C), decomponha em triplas separadas.
3. "idioms_translation": lista de dicts traduzindo expressões idiomáticas em conceitos abstratos ({{"idiom": "...", "translation": "..."}}).

⚠️ ESTRITO: Todos os valores de texto (name, type, subject, relation, object) DEVEM estar no MESMO idioma da frase de entrada. Nunca use outro idioma.""",
            "ja": """以下のキーを持つクリーンなJSONを出力してください：
1. "entities": 抽出されたエンティティのリスト。"name"（日本語）、"type"/"abstract_type"（日本語）、"confidence"（浮動小数点 0.0-1.0）を含む。
2. "relations": トリプルのリスト。"subject"（日本語）、"relation"（日本語）、"object"（日本語）、オプションで "valid_from"/"valid_to"（整数の年）、"confidence"（浮動小数点 0.0-1.0）を含む。
   ⚠️ 多段階の因果連鎖が存在する場合（AがBを引き起こし、BがCを引き起こす）、別々のトリプルに分解してください。
3. "idioms_translation": 口語的な慣用句を抽象的概念に翻訳する辞書のリスト（{{"idiom": "...", "translation": "..."}}）。

⚠️ 厳格なルール：すべてのテキスト値（name、type、subject、relation、object）は入力文と同じ言語でなければなりません。他の言語は絶対に使用しないでください。""",
            "ko": """다음 키를 가진 깨끗한 JSON을 출력하십시오:
1. "entities": 추출된 개체 목록. "name"(한국어), "type"/"abstract_type"(한국어), "confidence"(부동소수점 0.0-1.0) 포함.
2. "relations": 트리플 목록. "subject"(한국어), "relation"(한국어), "object"(한국어), 선택적 "valid_from"/"valid_to"(정수 연도), "confidence"(부동소수점 0.0-1.0) 포함.
   ⚠️ 다단계 인과 관계 체인이 있는 경우(A가 B를 유발하고 B가 C를 유발), 별도의 트리플로 분해하십시오.
3. "idioms_translation": 구어체 관용구를 추상적 개념으로 번역하는 딕셔너리 목록({{"idiom": "...", "translation": "..."}}).

⚠️ 엄격한 규칙: 모든 텍스트 값(name, type, subject, relation, object)은 입력 문장과 동일한 언어여야 합니다. 다른 언어를 절대 사용하지 마십시오.""",
        }

        schema_instr = json_schema_instructions.get(
            language, json_schema_instructions["en"]
        )

        canonical_instruction = {
            "ar": """
💡 توجيه إضافي للتناسق الدلالي المعرفي (اختياري):
- لكل كائن في "entities"، يمكن إضافة مفتاح "canonical_form" يحتوي على الصيغة المفردة النكرة المبسطة المعيارية للمفهوم (مثال: "الكائنات الحية" ➔ "كائن حي"، "القطة" ➔ "قطة").
- لكل كائن في "relations"، يمكن إضافة مفتاح "subject_canonical" (الصيغة المفردة النكرة للفاعل) ومفتاح "object_canonical" (الصيغة المفردة النكرة للمفعول).
هذه الحقول اختيارية وتساعد في توحيد العقد المعرفية.""",
            "en": """
💡 OPTIONAL HINT FOR SEMANTIC ONTOLOGICAL ALIGNMENT:
- For each object in "entities", you MAY optionally add a "canonical_form" key containing the singular, lowercase, lemma/root form of the entity (e.g. "cats" -> "cat").
- For each object in "relations", you MAY optionally add "subject_canonical" and "object_canonical" keys (singular root forms).
These fields are OPTIONAL and help with entity deduplication.""",
        }
        canonical_suffix = canonical_instruction.get(
            language, canonical_instruction["en"]
        )

        context_instruction = {
            "ar": """
🔗 توجيه السياق الدلالي (Context-Bounded Relations):
- لكل علاقة في "relations"، يمكن إضافة مفتاح "context" (سياق) يحدد الشروط أو الظروف التي تنطبق فيها هذه العلاقة فقط.
- مثال: "اللمس يسبب حزناً إذا كان اللون أحمر" ➔ {"subject": "اللمس", "relation": "يسبب", "object": "حزن", "context": {"condition": "اللون = أحمر"}}
- مثال: "اللمس يسبب فرحاً إذا كان اللون أزرق" ➔ {"subject": "اللمس", "relation": "يسبب", "object": "فرح", "context": {"condition": "اللون = أزرق"}}
- يساعد هذا في تخزين علاقات متعددة لنفس الزوج (subject, object) بشروط مختلفة دون تناقض.""",
            "en": """
🔗 CONTEXT-BOUNDED RELATIONS (Semantic Context):
- For each relation object, you MAY add a "context" key describing the conditions under which this relation holds true.
- Example: "touching causes sadness if the color is red" ➔ {"subject": "touching", "relation": "causes", "object": "sadness", "context": {"condition": "color = red"}}
- Example: "touching causes joy if the color is blue" ➔ {"subject": "touching", "relation": "causes", "object": "joy", "context": {"condition": "color = blue"}}
- This allows storing multiple relations for the same (subject, object) pair under different conditions without contradiction.""",
        }
        context_suffix = context_instruction.get(language, context_instruction["en"])

        prompt = f"""{instr["role"]}
{instr["task"]}

{instr["output_lang"]}

{instr["sentence_label"]}: "{sentence}"

{instr["intransitive_note"]}
{instr["causal_note"]}
{instr["idioms_note"]}
{instr.get("comprehensive_note", "")}

{schema_instr}
{canonical_suffix}
{context_suffix}

{instr["json_only"]}
"""
        response_text = call_llm_api(provider, api_key, model, prompt, logs)
        cleaned_text = self.clean_and_extract_json(response_text)

        try:
            return json.loads(cleaned_text)
        except Exception as e:
            logs.append(
                f"⚠️ Critical: Failed to decode LLM response as valid JSON ({str(e)})."
            )
            logs.append(
                f"   📋 Raw LLM response (first 300 chars): {str(response_text)[:300]}"
            )
            logs.append(
                f"   📋 Cleaned text (first 300 chars): {str(cleaned_text)[:300]}"
            )
            return None

    def check_contradictions(self, parsed_data):
        """التحقق من وجود أي تناقضات منطقية مع المعرفة السابقة المخزنة"""
        contradictions = []
        relations = parsed_data.get(
            "relations", parsed_data.get("العلاقات", parsed_data.get("علاقات", []))
        )
        raw_entities = parsed_data.get(
            "entities", parsed_data.get("الكيانات", parsed_data.get("كيانات", []))
        )

        # قوائم موسعة لأفعال التصنيف والإثبات والنفي
        categorization_preds = [
            "هو",
            "يكون",
            "يعتبر",
            "يمثل",
            "ينتمي",
            "نوعه",
            "تصنيفه",
            "is_a",
            "من_نوع",
        ]
        negation_preds = ["ليس", "لا_يكون", "لا_يعتبر", "لا_يمثل", "ليس_من", "لا_ينتمي"]

        # 1. فحص التناقض المباشر (مثل: هو vs ليس) مع قوائم موسعة
        for rel in relations:
            if not isinstance(rel, dict):
                continue
            subj = normalize_arabic(rel.get("subject", rel.get("فاعل", "")))
            pred = normalize_arabic(rel.get("relation", rel.get("علاقة", "")))
            obj = normalize_arabic(rel.get("object", rel.get("مفعول", "")))

            if not subj or not pred or not obj:
                continue

            # استخراج السياق من العلاقة الجديدة
            new_ctx = rel.get(
                "context", rel.get("سياق", rel.get("condition", rel.get("شرط", {})))
            )
            if isinstance(new_ctx, str):
                try:
                    new_ctx = json.loads(new_ctx)
                except Exception:
                    new_ctx = {"condition": new_ctx}
            if not isinstance(new_ctx, dict):
                new_ctx = {}

            # إذا كنا نحاول إضافة علاقة إثبات ولدينا علاقة نفي، أو العكس
            if pred in categorization_preds:
                for np in negation_preds:
                    if (
                        self.graph.has_edge(subj, obj)
                        and self.graph[subj][obj].get("relation") == np
                    ):
                        existing_ctx = self.graph[subj][obj].get("context", {})
                        # إذا كان للعلاقتين سياقات مختلفة، فهما لا تتعارضان
                        if new_ctx and existing_ctx and new_ctx != existing_ctx:
                            continue
                        contradictions.append(
                            f"تلقين ({subj} ➔ {pred} ➔ {obj}) يتناقض مباشرة مع الحقيقة المسجلة السابقة: ({subj} ➔ {np} ➔ {obj})"
                        )
            elif pred in negation_preds:
                for pp in categorization_preds:
                    if (
                        self.graph.has_edge(subj, obj)
                        and self.graph[subj][obj].get("relation") == pp
                    ):
                        existing_ctx = self.graph[subj][obj].get("context", {})
                        # إذا كان للعلاقتين سياقات مختلفة، فهما لا تتعارضان
                        if new_ctx and existing_ctx and new_ctx != existing_ctx:
                            continue
                        contradictions.append(
                            f"تلقين ({subj} ➔ {pred} ➔ {obj}) يتناقض مباشرة مع الحقيقة المسجلة السابقة: ({subj} ➔ {pp} ➔ {obj})"
                        )

        # 2. فحص التناقض الفئوي (Disjoint Class)
        disjoint_groups = [
            {"انسان", "بشر", "جماد", "اله", "حيوان", "نبات"},
            {"حي", "ميت"},
        ]

        # 2أ. فحص الكيانات المستخرجة مقابل الأنواع المسجلة سابقاً
        entities = {}
        if isinstance(raw_entities, list):
            for item in raw_entities:
                if isinstance(item, dict):
                    name = normalize_arabic(item.get("name", item.get("اسم", "")))
                    ent_type = normalize_arabic(
                        item.get("abstract_type", item.get("type", item.get("نوع", "")))
                    )
                    if name and ent_type:
                        entities[name] = ent_type

        for name, ent_type in entities.items():
            existing_types = set()
            if self.graph.has_node(name):
                current = name
                node_data = self.graph.nodes[name]
                if node_data.get("super_type"):
                    existing_types.add(normalize_arabic(node_data.get("super_type")))

                while True:
                    successors = [
                        v
                        for u, v, d in self.graph.out_edges(current, data=True)
                        if d.get("relation") == "is_a"
                    ]
                    if successors:
                        current = successors[0]
                        existing_types.add(normalize_arabic(current))
                    else:
                        break

                # جمع الفئات من العلاقات التصنيفية المسجلة سابقاً (هو، يكون، is_a...)
                for _, target, edata in self.graph.out_edges(name, data=True):
                    edge_rel = normalize_arabic(edata.get("relation", ""))
                    if edge_rel in categorization_preds or edge_rel == "is_a":
                        existing_types.add(normalize_arabic(target))

            for group in disjoint_groups:
                if ent_type in group:
                    conflicts = group.intersection(existing_types)
                    conflicts.discard(ent_type)
                    if conflicts:
                        contradictions.append(
                            f"الكيان '{name}' تم تصنيفه كـ '{ent_type}'، لكنه مسجل سابقاً تحت فئة متناقضة: {list(conflicts)}"
                        )

        # 2ب. فحص العلاقات (Triples) التصنيفية الجديدة مقابل العلاقات المسجلة سابقاً
        for rel in relations:
            if not isinstance(rel, dict):
                continue
            subj = normalize_arabic(rel.get("subject", rel.get("فاعل", "")))
            pred = normalize_arabic(rel.get("relation", rel.get("علاقة", "")))
            obj = normalize_arabic(rel.get("object", rel.get("مفعول", "")))

            if not subj or not pred or not obj:
                continue

            # إذا كانت العلاقة تصنيفية (هو/يكون/is_a...)، تحقق من الفئات المتعارضة
            if pred in categorization_preds or pred == "is_a":
                new_category = normalize_arabic(obj)

                # جمع كل الفئات المسجلة سابقاً لهذا الكيان
                existing_categories = set()
                if self.graph.has_node(subj):
                    node_data = self.graph.nodes[subj]
                    if node_data.get("super_type"):
                        existing_categories.add(
                            normalize_arabic(node_data.get("super_type"))
                        )

                    for _, target, edata in self.graph.out_edges(subj, data=True):
                        edge_rel = normalize_arabic(edata.get("relation", ""))
                        if edge_rel in categorization_preds or edge_rel == "is_a":
                            existing_categories.add(normalize_arabic(target))

                # فحص التعارض مع الفئات المسجلة
                for group in disjoint_groups:
                    if new_category in group:
                        conflicts = group.intersection(existing_categories)
                        conflicts.discard(new_category)
                        if conflicts:
                            contradictions.append(
                                f"🚫 تناقض فئوي: تصنيف '{subj}' كـ '{new_category}' (عبر العلاقة '{pred}') "
                                f"يتعارض مع التصنيف المسجل سابقاً: {list(conflicts)}"
                            )

        return contradictions

    def run_transitive_reasoning(self, logs=None):
        """محرك استدلال دلالي بالخلفية يستنتج روابط جديدة بناءً على العلاقات الحالية"""
        if logs is None:
            logs = []

        if getattr(self, "strict_mode", False):
            logs.append(
                "🔒 [وضع الحقائق الثابتة]: تم إيقاف الاستدلال التلقائي لضمان ثبات المعرفة بنسبة 100% دون أي احتمالات."
            )
            return []

        inferred = []
        graph_to_use = self.sandbox_graph if self.in_sandbox else self.graph

        # 1. الاستدلال بالتعدي الأساسي التلقائي لعلاقة الميراث الفئوي (is_a)
        for node in list(graph_to_use.nodes):
            current = node
            path = []
            visited = {current}
            while True:
                successors = [
                    v
                    for u, v, d in graph_to_use.out_edges(current, data=True)
                    if d.get("relation") == "is_a"
                ]
                if successors:
                    current = successors[0]
                    if current in visited:
                        break  # Cycle detected
                    visited.add(current)
                    path.append(current)
                else:
                    break

            if len(path) > 1:
                ancestor = path[-1]
                if not (
                    graph_to_use.has_edge(node, ancestor)
                    and graph_to_use[node][ancestor].get("relation") == "is_a"
                ):
                    self.save_triple_to_db(node, "is_a", ancestor)
                    logs.append(
                        f"🧠 [استدلال دلالي ذاتي]: تم استنتاج وراثة فئوية جديدة تلقائياً: ({node} ➔ is_a ➔ {ancestor})"
                    )
                    inferred.append((node, "is_a", ancestor))

        # 2. محرك استدلال أمامي تكراري ديناميكي متناهي القفزات (Dynamic Recursive Forward Chaining)
        # يقوم بتحميل كافة القواعد النشطة من قاعدة البيانات وتطبيقها تكرارياً حتى نقطة الاستقرار (Fixpoint)
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT rule_name, antecedents, consequent, confidence FROM rules WHERE is_active = 1"
            )
            rules_rows = cursor.fetchall()
            conn.close()
        except Exception as e:
            logs.append(f"⚠️ تعذر تحميل القواعد النشطة من قاعدة البيانات: {e}")
            rules_rows = []

        active_rules = []
        for name, ant_json, cons_json, conf in rules_rows:
            try:
                active_rules.append(
                    {
                        "name": name,
                        "antecedents": json.loads(ant_json),
                        "consequent": json.loads(cons_json),
                        "confidence": conf or 1.0,
                    }
                )
            except Exception as e:
                logs.append(f"⚠️ خطأ في قراءة صيغة القاعدة {name}: {e}")

        # دالة الموائمة والتوحيد (Backtracking Pattern Matcher) للبحث عن مطابقات المتغيرات في الرسم البياني
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

            # البحث في جميع العلاقات الحالية بالرسم المعرفي
            for u, v, data in list(graph.edges(data=True)):
                rel = normalize_arabic(data.get("relation", ""))
                if rel != p_p:
                    continue

                # مطابقة الفاعل (Subject)
                s_val = env.get(p_s) if p_s.startswith("?") else p_s
                if s_val is not None and s_val != u:
                    continue

                # مطابقة المفعول به (Object)
                o_val = env.get(p_o) if p_o.startswith("?") else p_o
                if o_val is not None and o_val != v:
                    continue

                # بناء بيئة متغيرات جديدة والاستمرار في مطابقة باقي الشروط
                new_env = env.copy()
                if p_s.startswith("?"):
                    new_env[p_s] = u
                if p_o.startswith("?"):
                    new_env[p_o] = v

                yield from match_antecedents(graph, antecedents, index + 1, new_env)

        # تشغيل حلقة الاستدلال التكراري (Fixpoint Reasoning Loop)
        max_iterations = 10
        iteration = 0
        inferred_in_loop = True

        logs.append(
            "⚡ [محرك الاستدلال الهجين]: بدء تشغيل حلقة الاستدلال التكرارية لانهائية الخطوات..."
        )

        while inferred_in_loop and iteration < max_iterations:
            inferred_in_loop = False
            iteration += 1
            new_triples_this_iter = 0

            for rule in active_rules:
                ants = rule["antecedents"]
                cons = rule["consequent"]
                conf = rule["confidence"]

                # البحث عن كافة التعويضات الصالحة لمتغيرات هذه القاعدة
                for env in match_antecedents(graph_to_use, ants):
                    # تكوين الحقيقة الجديدة من النتيجة المترتبة
                    c_s, c_p, c_o = cons

                    subj = env.get(c_s) if c_s.startswith("?") else c_s
                    pred = env.get(c_p) if c_p.startswith("?") else c_p
                    obj = env.get(c_o) if c_o.startswith("?") else c_o

                    if not subj or not pred or not obj:
                        continue

                    subj = normalize_arabic(subj)
                    pred = normalize_arabic(pred)
                    obj = normalize_arabic(obj)

                    # التحقق مما إذا كانت الحقيقة مستنتجة مسبقاً
                    if not (
                        graph_to_use.has_edge(subj, obj)
                        and graph_to_use[subj][obj].get("relation") == pred
                    ):
                        self.save_triple_to_db(subj, pred, obj, confidence=conf)
                        logs.append(
                            f"🧠 [استدلال ديناميكي] (تكرار {iteration}): استنتاج علاقة جديدة عبر [{rule['name']}]: "
                            f"({subj} ➔ {pred} ➔ {obj}) بـثقة {conf:.2f}"
                        )
                        inferred.append((subj, pred, obj))
                        inferred_in_loop = True
                        new_triples_this_iter += 1

            if new_triples_this_iter > 0:
                logs.append(
                    f"🔄 التكرار رقم {iteration} انتهى باستنتاج {new_triples_this_iter} روابط جديدة."
                )

        if iteration >= max_iterations:
            logs.append(
                "⚠️ [تنبيه محرك الاستدلال]: تم إيقاف حلقة الاستدلال للوصول للحد الأقصى للتكرارات (10 قفزات) منعاً للدوران اللانهائي."
            )
        else:
            logs.append(
                f"✅ استقر محرك الاستدلال بنجاح بعد {iteration} تكرار معرفي دون روابط جديدة إضافية."
            )

        return inferred

    def learn_and_store(self, parsed_data, logs=None):
        if logs is None:
            logs = []

        self.last_relations = []
        raw_entities = parsed_data.get(
            "entities", parsed_data.get("الكيانات", parsed_data.get("كيانات", []))
        )
        relations = parsed_data.get(
            "relations", parsed_data.get("العلاقات", parsed_data.get("علاقات", []))
        )

        # كشف التناقضات الدلالية قبل الحفظ
        contradictions = self.check_contradictions(parsed_data)
        if contradictions:
            logs.append(
                "🚨 [كاشف التناقض المنطقي]: تم اكتشاف تعارض في الجملة المعالجة مع العقل المعرفي!"
            )
            for msg in contradictions:
                logs.append(f"   ⚠️ {msg}")
            logs.append(
                "   📌 سيقوم النظام بتسجيل المعلومات مع الاحتفاظ بالتحذير في شاشة الرصد."
            )

        has_learned = False

        entities = {}
        if isinstance(raw_entities, list):
            for item in raw_entities:
                if isinstance(item, dict):
                    name_raw = item.get("name", item.get("اسم", ""))
                    name = item.get("canonical_form", name_raw)
                    if not name:
                        name = name_raw
                    ent_type = item.get(
                        "abstract_type", item.get("type", item.get("نوع", ""))
                    )
                    conf = item.get("confidence", 1.0)
                    if name and ent_type:
                        entities[name] = {"type": ent_type, "confidence": conf}
        elif isinstance(raw_entities, dict):
            for name, val in raw_entities.items():
                if isinstance(val, dict):
                    entities[name] = {
                        "type": val.get("type"),
                        "confidence": val.get("confidence", 1.0),
                    }
                else:
                    entities[name] = {"type": val, "confidence": 1.0}

        for name, info in entities.items():
            if getattr(self, "abort_requested", False):
                logs.append(
                    "⚠️ [تلقين المعرفة النشطة]: تم إلغاء عملية حفظ المفاهيم بناءً على طلب المستخدم."
                )
                self.abort_requested = False
                return False
            ent_type = info["type"]
            conf = info["confidence"]

            # [Arabic Fuzzy-Modal Logic]
            # Adjust concept confidence based on fuzzy terms in name or type
            if any(term in name for term in ["غالباً", "احتمال", "ربما", "تقريباً"]):
                conf = min(conf, 0.65)
            elif any(term in name for term in ["تماماً", "بالتأكيد", "قطعاً"]):
                conf = max(conf, 0.98)
            elif any(term in name for term in ["نادراً", "شحيحاً"]):
                conf = min(conf, 0.38)

            graph_to_use = self.sandbox_graph if self.in_sandbox else self.graph
            if not graph_to_use.has_node(name):
                logs.append(
                    f"🧠 [تعلم تراكمي]: إدراج مفهوم جديد '{name}' ➔ تصنيفه: '{ent_type}' بـثقة {conf:.2f}"
                )
                self.save_concept_to_db(name, ent_type, [], confidence=conf)
                has_learned = True

        for rel in relations:
            if getattr(self, "abort_requested", False):
                logs.append(
                    "⚠️ [تلقين المعرفة النشطة]: تم إلغاء عملية حفظ العلاقات بناءً على طلب المستخدم."
                )
                self.abort_requested = False
                return False
            if not isinstance(rel, dict):
                continue
            subj_raw = rel.get("subject", rel.get("فاعل", ""))
            subj = rel.get("subject_canonical", subj_raw)
            if not subj:
                subj = subj_raw

            pred = rel.get("relation", rel.get("علاقة", ""))

            obj_raw = rel.get("object", rel.get("مفعول", ""))
            obj = rel.get("object_canonical", obj_raw)
            if not obj:
                obj = obj_raw

            valid_from = rel.get("valid_from")
            valid_to = rel.get("valid_to")
            conf = rel.get("confidence", 1.0)

            ctx = rel.get(
                "context", rel.get("سياق", rel.get("condition", rel.get("شرط", {})))
            )
            if isinstance(ctx, str):
                try:
                    ctx = json.loads(ctx)
                except Exception:
                    ctx = {"condition": ctx}
            elif not isinstance(ctx, dict):
                ctx = {}

            if not subj or not pred or not obj:
                continue

            # [Arabic Fuzzy-Modal Logic Engine]
            # Check for modal descriptors in relationship description or predicate
            if any(term in pred or term in obj for term in ["غالباً", "تقريباً", "ربما"]):
                conf = min(conf, 0.60)
                logs.append(
                    f"⚖️ [منطق مضبب]: تعديل ثقة العلاقة ({subj} ➔ {pred} ➔ {obj}) لـ {conf:.2f} لوجود مؤشر احتمالي ('غالباً/تقريباً/ربما')"
                )
            elif any(
                term in pred or term in obj
                for term in ["بالتأكيد", "تماماً", "قطعاً", "دائماً"]
            ):
                conf = max(conf, 0.99)
                logs.append(
                    f"⚖️ [منطق مضبب]: رفع ثقة العلاقة ({subj} ➔ {pred} ➔ {obj}) لـ {conf:.2f} لوجود مؤشر يقيني ('بالتأكيد/تماماً')"
                )
            elif any(term in pred or term in obj for term in ["نادراً", "قليلاً"]):
                conf = min(conf, 0.35)
                logs.append(
                    f"⚖️ [منطق مضبب]: خفض ثقة العلاقة ({subj} ➔ {pred} ➔ {obj}) لـ {conf:.2f} لوجود مؤشر ندرة ('نادراً/قليلاً')"
                )

            # [Emotional-Semantic Tagging]
            # Analyze emotional valence based on word embeddings/keywords
            valence = 0.0
            pos_words = [
                "يحب",
                "سعيد",
                "صديق",
                "جميل",
                "رائع",
                "انتصار",
                "أمل",
                "حب",
                "خير",
                "نجاح",
                "أمان",
            ]
            neg_words = [
                "يكره",
                "حزين",
                "عدو",
                "قبيح",
                "فشل",
                "موت",
                "حرب",
                "خوف",
                "شر",
                "غضب",
                "حزن",
            ]

            combined_text = f"{subj} {pred} {obj}"
            if any(w in combined_text for w in pos_words):
                valence = 0.75
            elif any(w in combined_text for w in neg_words):
                valence = -0.75

            if abs(valence) > 0.0:
                logs.append(
                    f"❤️ [ذاكرة انفعالية]: ربط شحنة عاطفية (valence = {valence:.2f}) بالرابطة المعرفية الجديدة."
                )

            self.last_relations.append((subj, pred, obj))

            graph_to_use = self.sandbox_graph if self.in_sandbox else self.graph
            if not (
                graph_to_use.has_edge(subj, obj)
                and graph_to_use[subj][obj].get("relation") == pred
            ):
                time_info = ""
                if valid_from and valid_to:
                    time_info = f" [🕒 {valid_from} - {valid_to}]"
                elif valid_from:
                    time_info = f" [🕒 منذ {valid_from}]"
                elif valid_to:
                    time_info = f" [🕒 حتى {valid_to}]"

                ctx_log = ""
                if ctx and any(v for v in ctx.values()):
                    ctx_str = json.dumps(ctx, ensure_ascii=False)[:80]
                    ctx_log = f" [🌐 سياق: {ctx_str}]"
                logs.append(
                    f"🧠 [تعلم تراكمي]: استيعاب حقيقة جديدة: ({subj} ➔ {pred} ➔ {obj}){time_info}{ctx_log} بـثقة {conf:.2f}"
                )
                self.save_triple_to_db(
                    subj,
                    pred,
                    obj,
                    valid_from,
                    valid_to,
                    confidence=conf,
                    emotional_valence=valence,
                    context=ctx,
                )
                has_learned = True

        # تشغيل محرك الاستدلال والتعدي الدلالي الذاتي
        inferred = self.run_transitive_reasoning(logs)
        if inferred:
            has_learned = True

        if has_learned:
            logs.append(
                "💾 [مزامنة الذاكرة]: تم حفظ كافة المعلومات والاستنتاجات في SQLite و RAM بنجاح."
            )
        else:
            logs.append(
                "💤 [الذاكرة التراكمية]: لم يتم العثور على أي معلومات جديدة؛ كافة الحقائق مسجلة مسبقاً."
            )

    def run_symbolic_reasoning(self, parsed_data, logs=None):
        if logs is None:
            logs = []

        raw_entities = parsed_data.get("entities", [])
        relations = parsed_data.get("relations", [])
        raw_idioms = parsed_data.get("idioms_translation", [])

        idioms = {}
        if isinstance(raw_idioms, list):
            for item in raw_idioms:
                if isinstance(item, dict):
                    k = item.get("idiom", item.get("عامية", item.get("key", "")))
                    v = item.get(
                        "translation", item.get("ترجمة", item.get("value", ""))
                    )
                    if k and v:
                        idioms[k] = v
        elif isinstance(raw_idioms, dict):
            idioms = raw_idioms

        if idioms:
            logs.append("💡 [فك الكنايات العامية]:")
            for key, val in idioms.items():
                logs.append(
                    f"   • التعبير العامي: '{key}' ➔ المفهوم المعياري الصريح: '{val}'"
                )

        entities = {}
        if isinstance(raw_entities, list):
            for item in raw_entities:
                if isinstance(item, dict):
                    name = item.get("name", item.get("اسم", ""))
                    ent_type = item.get(
                        "abstract_type", item.get("type", item.get("نوع", ""))
                    )
                    if name and ent_type:
                        entities[name] = {"type": ent_type}
        elif isinstance(raw_entities, dict):
            entities = raw_entities

        for entity_name, entity_info in entities.items():
            node_name = entity_name
            if not self.graph.has_node(node_name):
                continue

            logs.append(f"🔎 [تتبع الوراثة الكيان: '{node_name}']:")
            path = [node_name]
            current = node_name
            inherited_properties = []

            while True:
                successors = [
                    v
                    for u, v, d in self.graph.out_edges(current, data=True)
                    if d.get("relation") == "is_a"
                ]
                if successors:
                    current = successors[0]
                    path.append(current)
                    node_data = self.graph.nodes[current]
                    if "properties" in node_data and node_data["properties"]:
                        inherited_properties.extend(node_data["properties"])
                else:
                    break

            logs.append(f"   • شجرة النسب المعرفي: {' ➔ '.join(path)}")
            if inherited_properties:
                logs.append(
                    f"   • الصفات والخصائص الموروثة: {', '.join(inherited_properties)}"
                )

        for rel in relations:
            if not isinstance(rel, dict):
                continue
            subj = rel.get("subject", rel.get("فاعل", ""))
            pred = rel.get("relation", rel.get("علاقة", ""))
            obj = rel.get("object", rel.get("مفعول", ""))

            is_ignoring = False
            for ignore_word in ["تجاهل", "كبر دماغه", "طنش", "يصرف النظر", "إهمال"]:
                if ignore_word in pred or ignore_word in str(idioms.values()):
                    is_ignoring = True

            if is_ignoring and (
                "المذاكرة" in obj
                or "دراسة" in obj
                or "تعلم" in obj
                or "نشاط_أكاديمي" in obj
            ):
                logs.append(
                    f"⚠️ [استنتاج منطقي حاسم]: بما أن '{subj}' قد تجاهل '{obj}'، فإن مستقبله الدراسي مهدد بالخطر الأكيد!"
                )

            if "يلعب" in pred or "لعب" in pred:
                if "كورة" in obj or "الكورة" in obj or "لعب_كرة_القدم" in obj:
                    logs.append(
                        f"🏅 [استنتاج رياضي]: بما أن '{subj}' يمارس '{obj}'، فإنه في حالة نشاط بدني وترويح عن النفس."
                    )

    def run_pure_db_rag(
        self, sentence, provider, api_key, model, logs=None, language="ar"
    ):
        if logs is None:
            logs = []

        logs.append("🔍 Starting Pure DB Reasoning mode...")
        logs.append("🌐 Extracting keywords for ontology search...")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name, super_type, properties FROM concepts")
        concepts = cursor.fetchall()
        cursor.execute("SELECT subject, predicate, object FROM triples")
        triples = cursor.fetchall()
        conn.close()

        # AI-Assisted Query Expansion for Semantic Bridging (replaces full graph injection)
        expansion_prompt = f"""Extract the core keywords from this question, and generate 5-10 synonyms or semantically related terms (e.g., if 'laws' -> add 'rules, system, math', if 'addition' -> add 'plus, math').
Question: "{sentence}"
Return ONLY the words separated by spaces, no other text."""
        try:
            from core_utils import call_llm_api

            expanded_text = call_llm_api(provider, api_key, model, expansion_prompt, [])
            expanded_words = re.findall(r"\w+", expanded_text)
            sentence_words = re.findall(r"\w+", sentence)
            words = [normalize_arabic(w) for w in (sentence_words + expanded_words)]
            logs.append(
                f"🧠 AI Query Expansion active. Bridged vocabulary: {' '.join(expanded_words[:15])}..."
            )
        except Exception as e:
            words = [normalize_arabic(w) for w in re.findall(r"\w+", sentence)]
            logs.append(f"⚠️ Query expansion failed, using exact words. Error: {e}")

        # Universal affix stripping (works for Arabic + passes through other languages)
        def strip_affixes(w):
            """Strip common Arabic prefixes/articles. Non-Arabic words pass through unchanged."""
            variants = {w}
            # Arabic definite articles and prefixes
            for prefix in ["ال", "وال", "فال", "بال", "كال", "لل"]:
                if w.startswith(prefix) and len(w) > len(prefix) + 2:
                    variants.add(w[len(prefix) :])
            if not w.startswith("ال"):
                variants.add("ال" + w)
            return variants

        # Generate all morphological variants for query words
        query_variants = set()
        for w in words:
            if (
                len(w) > 1
            ):  # Allow shorter words for CJK languages (single char can be meaningful)
                query_variants.update(strip_affixes(w))

        # 1. Find matching concepts/entities for the query keywords
        matched_nodes = set()
        for node in self.graph.nodes:
            norm_node = normalize_arabic(node)
            node_variants = strip_affixes(norm_node)
            for word in words:
                if len(word) > 1:
                    word_variants = strip_affixes(word)
                    for wv in word_variants:
                        for nv in node_variants:
                            if len(wv) > 1 and len(nv) > 1 and (wv in nv or nv in wv):
                                matched_nodes.add(node)
                                break
                        if node in matched_nodes:
                            break
                if node in matched_nodes:
                    break

        # 1b. Also search in relation content (predicates and objects)
        for subj, pred, obj in triples:
            norm_pred = normalize_arabic(pred)
            norm_obj = normalize_arabic(obj)
            for wv in query_variants:
                if len(wv) > 1 and (
                    wv in norm_pred or wv in norm_obj or wv in normalize_arabic(subj)
                ):
                    matched_nodes.add(subj)
                    matched_nodes.add(obj)
                    break

        # 2. Expand semantically to include the full connected component
        expanded_nodes = set(matched_nodes)
        try:
            undirected_graph = self.graph.to_undirected()
            for node in matched_nodes:
                if undirected_graph.has_node(node):
                    component = nx.node_connected_component(undirected_graph, node)
                    expanded_nodes.update(component)
            logs.append(
                f"🌐 Extracted full connected component for {len(matched_nodes)} discovered entities."
            )
        except Exception as e:
            for node in matched_nodes:
                if self.graph.has_node(node):
                    neighbors = list(self.graph.neighbors(node))
                    expanded_nodes.update(neighbors)
                    for neighbor in neighbors:
                        if self.graph.has_node(neighbor):
                            expanded_nodes.update(self.graph.neighbors(neighbor))

        relevant_concepts = []
        relevant_triples = []

        # We rely on AI Query Expansion and graph traversal instead of full graph injection
        # to ensure it scales elegantly to very large databases.
        for name, super_type, props in concepts:
            if name in expanded_nodes:
                relevant_concepts.append(
                    f"Concept '{name}' is a type of '{super_type}' with properties: {props}"
                )

        for subj, pred, obj in triples:
            if subj in expanded_nodes or obj in expanded_nodes:
                ctx = ""
                if self.graph.has_edge(subj, obj) and self.graph[subj][obj].get(
                    "context"
                ):
                    edge_ctx = self.graph[subj][obj]["context"]
                    if isinstance(edge_ctx, dict) and any(v for v in edge_ctx.values()):
                        ctx = f" [Context: {json.dumps(edge_ctx, ensure_ascii=False)}]"
                relevant_triples.append(f"Fact: '{subj}' ➔ '{pred}' ➔ '{obj}'{ctx}")

        facts = relevant_concepts + relevant_triples

        # Language-aware "no facts found" responses
        no_facts_responses = {
            "ar": "عذراً، لم أجد أي معلومات أو حقائق مرتبطة بسؤالك في قاعدة البيانات الرمزية حتى الآن. هل ترغب في تعليمي إياها أولاً؟",
            "en": "Sorry, I could not find any facts related to your question in the symbolic database yet. Would you like to teach me first?",
            "zh": "抱歉，我在符号数据库中没有找到与您的问题相关的任何事实。您是否想先教我？",
            "fr": "Désolé, je n'ai trouvé aucun fait lié à votre question dans la base de données symbolique. Voulez-vous d'abord me l'enseigner ?",
            "es": "Lo siento, no encontré ningún dato relacionado con tu pregunta en la base de datos simbólica. ¿Te gustaría enseñármelo primero?",
            "tr": "Üzgünüm, sembolik veri tabanında henüz sorunuzla ilgili herhangi bir bilgi veya gerçek bulamadım. Bana önce öğretmek ister misiniz?",
            "de": "Entschuldigung, ich konnte in der symbolischen Datenbank noch keine Fakten zu Ihrer Frage finden. Möchten Sie mir diese zuerst beibringen?",
            "ru": "Извините, мне пока не удалось найти в символической базе данных факты, связанные с вашим вопросом. Не хотите ли вы сначала научить меня?",
            "pt": "Desculpe, ainda não encontrei fatos relacionados à sua pergunta no banco de dados simbólico. Gostaria de me ensinar primeiro?",
            "ja": "申し訳ありませんが、記号データベースにはまだあなたの質問に関連する事実が見つかりません。まず私に教えていただけますか？",
            "ko": "죄송합니다. 기호 데이터베이스에서 질문과 관련된 사실을 아직 찾지 못했습니다. 먼저 저에게 가르쳐 주시겠습니까?",
        }

        if not facts:
            logs.append("⚠️ No matching concepts or facts found in the database.")
            return no_facts_responses.get(language, no_facts_responses["en"])

        logs.append(f"✅ Found {len(facts)} relevant knowledge facts.")
        facts_context = "\n".join(facts)

        # Language-aware RAG response prompt
        rag_prompts = {
            "ar": f"""أنت مساعد ذكاء اصطناعي عصبي-رمزي هجين، تتميز بقدرتك الخارقة على الاستنتاج المنطقي الصارم.
مهمتك هي الإجابة على سؤال المستخدم بناءً **حصرياً وبشكل قاطع** على الحقائق المعرفية التالية المسترجعة من الذاكرة الرمزية.

الحقائق المعرفية المسترجعة:
{facts_context}

سؤال المستخدم: "{sentence}"

الشروط الصارمة جداً (Strict Alignment):
1. **كبت المعرفة المسبقة بالكامل**: تجاهل أي قوانين فيزيائية، رياضية، أو منطقية من العالم الحقيقي (مثل 1+1=2 أو أن الفراشات تطير) إذا كانت تتعارض أو لم تُذكر صراحةً في الحقائق المرفقة. يجب أن تبني استنتاجك *فقط* على قواعد وحقائق العالم الموصوف في البيانات المرفقة.
2. **الاستنتاج المترابط (Cross-Relational Inference)**: قم بربط الحقائق المنفصلة للوصول إلى استنتاج منطقي عميق. (مثال: إذا كان أ=ب، وب=ج، إذن أ=ج وفقاً للقواعد المرفقة فقط).
3. **لا تخترع معلومات نهائياً**: إذا لم تكن الإجابة موجودة أو يمكن استنتاجها بشكل مباشر من الحقائق المرفقة، قل بوضوح أنه لا توجد معلومات كافية.
4. صغ الإجابة بلسان عربي فصيح موضحاً كيف استنتجت الإجابة خطوة بخطوة من الحقائق المعطاة.""",
            "en": f"""You are a highly advanced hybrid neuro-symbolic AI assistant, distinguished by your strict logical reasoning capabilities.
Answer the user's question STRICTLY AND EXCLUSIVELY based on these retrieved knowledge facts from the symbolic memory.

Retrieved knowledge facts:
{facts_context}

User's question: "{sentence}"

Strict Rules for Alignment:
1. **ABSOLUTE SUPPRESSION OF PRIOR KNOWLEDGE**: Completely ignore real-world physics, math, or logic (e.g., 1+1=2 or that butterflies fly) if they contradict or are absent from the provided facts. You must build your deductions *solely* on the rules of the world described in the facts.
2. **Cross-Relational Inference**: Connect disparate facts to reach deep logical conclusions (e.g., if A=B and B=C, then A=C according to the provided rules).
3. **DO NOT invent information**: If the answer cannot be directly found or deduced from the facts, state clearly that there is insufficient information.
4. Provide a clear natural language answer, explaining your step-by-step deduction from the provided facts.""",
            "zh": f"""你是一个混合神经-符号AI助手。
请仅根据以下从符号记忆中检索到的知识事实来回答用户的问题。

检索到的知识事实:
{facts_context}

用户的问题: "{sentence}"

规则: 1. 用自然语言回答。2. 严格基于给定事实，但鼓励多跳逻辑推理。3. 不要编造信息。4. 如果事实不足，请明确说明。""",
            "fr": f"""Vous êtes un assistant IA neuro-symbolique hybride.
Répondez à la question de l'utilisateur en vous basant STRICTEMENT sur ces faits de connaissance récupérés.

Faits récupérés:
{facts_context}

Question de l'utilisateur: "{sentence}"

Règles: 1. Fournissez une réponse en langage naturel. 2. Respectez les faits donnés mais le chaînage logique multi-sauts est encouragé. 3. N'inventez PAS d'information. 4. Si les faits sont insuffisants, dites-le clairement.""",
            "es": f"""Eres un asistente de IA neuro-simbólico híbrido.
Responde la pregunta del usuario basándote ESTRICTAMENTE en estos hechos de conocimiento recuperados.

Hechos recuperados:
{facts_context}

Pregunta del usuario: "{sentence}"

Reglas: 1. Da una respuesta en lenguaje natural. 2. Ciñete a los hechos dados pero se alienta el encadenamiento lógico multi-salto. 3. NO inventes información. 4. Si los hechos son insuficientes, dilo claramente.""",
            "tr": f"""Siz hibrit bir nöro-sembolik yapay zeka yardımcısısınız.
Kullanıcının sorusunu KESİNLİKLE geri getirilen bu bilgi gerçeklerine dayanarak yanıtlayın.

Geri getirilen bilgi gerçekleri:
{facts_context}

Kullanıcının sorusu: "{sentence}"

Kurallar: 1. Doğal bir dille cevap verin. 2. Yalnızca verilen gerçeklere bağlı kalın ancak çok adımlı mantıksal zincirleme teşvik edilir. 3. Bilgi uydurmayın. 4. Gerçekler yetersizse bunu açıkça belirtin.""",
            "de": f"""Sie sind ein hybrider neuro-symbolischer KI-Assistent.
Beantworten Sie die Frage des Benutzers STRENG basierend auf diesen abgerufenen Wissensfakten.

Abgerufene Wissensfakten:
{facts_context}

Benutzerfrage: "{sentence}"

Regeln: 1. Formulieren Sie eine Antwort in natürlicher Sprache. 2. Halten Sie sich strikt an die vorgegebenen Fakten, aber logische Schlussfolgerungen über mehrere Schritte sind erwünscht. 3. Erfinden Sie KEINE Informationen. 4. Wenn die Fakten nicht ausreichen, sagen Sie dies deutlich.""",
            "ru": f"""Вы — гибридный нейросимволический ИИ-ассистент.
Ответьте на вопрос пользователя, СТРОГО основываясь на следующих извлеченных фактах.

Извлеченные факты знаний:
{facts_context}

Вопрос пользователя: "{sentence}"

Правила: 1. Предоставьте ответ на естественном языке. 2. Строго придерживайтесь предоставленных фактов, однако поощряется многошаговое логическое рассуждение. 3. НЕ выдумывайте информацию. 4. Если фактов недостаточно, заявите об этом прямо.""",
            "pt": f"""Você é um assistente de IA neuro-simbólico híbrido.
Responda à pergunta do usuário baseando-se ESTRITAMENTE nestes fatos de conhecimento recuperados.

Fatos de conhecimento recuperados:
{facts_context}

Pergunta do usuário: "{sentence}"

Regras: 1. Dê uma resposta em linguagem natural. 2. Cumpra rigorosamente os fatos fornecidos, mas o encadeamento lógico de várias etapas é incentivado. 3. NÃO invente informações. 4. Se os fatos forem insuficientes, diga claramente.""",
            "ja": f"""あなたはハイブリッド神経記号AIアシスタントです。
検索された以下の知識事実のみに厳密に基づいて、ユーザーの質問に答えてください。

検索された知識事実:
{facts_context}

ユーザーの質問: "{sentence}"

ルール: 1. 自然な言語で答えてください。 2. 与えられた事実に厳密に従ってください。ただし、マルチホップ論理チェーンによる推論は強く推奨されます。 3. 情報を捏造しないでください。 4. 事実が不十分な場合は、その旨を明確に述べてください。""",
            "ko": f"""당신은 하이브리드 신경-기호적 AI 어시스턴트입니다.
검색된 다음 지식 사실에만 엄격히 기초하여 사용자의 질문에 답하십시오.

검색된 지식 사실:
{facts_context}

사용자의 질문: "{sentence}"

규칙: 1. 자연스러운 언어로 답변하십시오. 2. 주어진 사실을 엄격히 고수하되 다중 홉 논리적 연결 추론을 권장합니다. 3. 정보를 지어내지 마십시오. 4. 사실이 불충분한 경우 이를 명확히 밝히십시오.""",
        }

        prompt = rag_prompts.get(language, rag_prompts["en"])
        logs.append("🤔 Generating fact-based response...")
        return call_llm_api(provider, api_key, model, prompt, logs)

    def query_with_context(
        self,
        subject=None,
        predicate=None,
        object=None,
        context_filter=None,
        include_no_context=True,
    ):
        """
        استعلام عن العلاقات مع مراعاة السياق.
        - context_filter: dict of conditions that must match (e.g. {"condition": "اللون = أحمر"})
        - include_no_context: if True, also include relations without context
        Returns list of (subj, pred, obj, context) matching the query.
        """
        results = []
        for u, v, data in self.graph.edges(data=True):
            relation = data.get("relation", "")
            ctx = data.get("context", {})

            if subject and normalize_arabic(u) != normalize_arabic(subject):
                continue
            if predicate and normalize_arabic(relation) != normalize_arabic(predicate):
                continue
            if object and normalize_arabic(v) != normalize_arabic(object):
                continue
            if context_filter:
                ctx_matches = all(ctx.get(k) == v for k, v in context_filter.items())
                if not ctx_matches:
                    if not (include_no_context and not ctx):
                        continue
            results.append((u, relation, v, ctx))
        return results

    def find_relation_path_string(self, concept_a, concept_b, logs=None):
        if logs is None:
            logs = []

        def clean_node_name(name):
            name = normalize_arabic(name.strip())
            if (
                name.startswith("ال")
                and not self.graph.has_node(name)
                and self.graph.has_node(name[2:])
            ):
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
                v = path[i + 1]
                if self.graph.has_edge(u, v):
                    rel = self.graph[u][v].get("relation", "علاقة")
                    visual_path.append(f"'{u}' ➔ ({rel}) ➔ '{v}'")
                else:
                    rel = self.graph[v][u].get("relation", "علاقة")
                    visual_path.append(f"'{u}' ➔ (عكس_{rel}) ➔ '{v}'")

            logs.append(
                f"✅ تم اكتشاف مسار دلالي يربط بين '{c_a}' و '{c_b}' عبر {len(path) - 1} قفزات."
            )
            return (
                f"تم اكتشاف الرابط الدلالي التراكمي بين '{concept_a}' و '{concept_b}':\n"
                + " ➔ ".join(path)
                + "\n\nالتفصيل اللينكي:\n"
                + "\n".join(visual_path)
            )
        except nx.NetworkXNoPath:
            return f"لا يوجد أي رابط مباشر أو غير مباشر يجمع بين '{c_a}' و '{c_b}' في الذاكرة الرمزية حالياً."

    # =========================================================================
    # 1. الاستدلال الاحتمالي تحت عدم اليقين (PLN - Probabilistic Logic Networks)
    # =========================================================================
    def run_probabilistic_inference(self, concept_a, concept_b, logs=None):
        """حساب مسارات الترابط والاحتمالية التراكمية بناءً على معاملات الثقة لكل علاقة"""
        if logs is None:
            logs = []

        if getattr(self, "strict_mode", False):
            logs.append(
                "🔒 [وضع الحقائق الثابتة]: تم إيقاف الاستدلال الاحتمالي لضمان ثبات المعرفة بنسبة 100%."
            )
            return "🔒 تم تعطيل الاستدلال الاحتمالي (PLN) في وضع الحقائق الثابتة لضمان ثبات المعرفة بنسبة 100%."

        c_a = normalize_arabic(concept_a.strip())
        c_b = normalize_arabic(concept_b.strip())

        graph_to_use = self.sandbox_graph if self.in_sandbox else self.graph

        if not (graph_to_use.has_node(c_a) and graph_to_use.has_node(c_b)):
            logs.append(
                f"⚠️ [الاستدلال الاحتمالي]: الكيان '{concept_a}' أو '{concept_b}' غير موجود في الذاكرة الحالية."
            )
            return f"لا يمكن حساب الاحتمالية لعدم وجود الكيانات في الشبكة."

        try:
            # استخدام خوارزمية أقصر المسارات للحصول على مسار الترابط
            undirected = graph_to_use.to_undirected()
            path = nx.shortest_path(undirected, source=c_a, target=c_b)

            cumulative_confidence = 1.0
            steps = []

            for i in range(len(path) - 1):
                u = path[i]
                v = path[i + 1]

                # جلب معامل ثقة الحافة
                if graph_to_use.has_edge(u, v):
                    edge_data = graph_to_use[u][v]
                    rel = edge_data.get("relation", "علاقة")
                    conf = edge_data.get("confidence", 1.0)
                    steps.append(f"({u} ➔ {rel} ➔ {v} بـثقة {conf:.2f})")
                else:
                    edge_data = graph_to_use[v][u]
                    rel = edge_data.get("relation", "علاقة")
                    conf = edge_data.get("confidence", 1.0)
                    steps.append(f"({u} ➔ عكس_{rel} ➔ {v} بـثقة {conf:.2f})")

                # استخدام الضرب لمعادلة الاحتمالية التراكمية (Product T-norm)
                cumulative_confidence *= conf

            logs.append(
                f"🎲 [PLN]: تم تحليل مسار الترابط الدلالي الاحتمالي بين '{c_a}' و '{c_b}'."
            )
            logs.append(f"   • مسار القفزات: {' ➔ '.join(path)}")
            logs.append(
                f"   • ثقة العلاقات الفردية: {' × '.join([f'{float(s.split()[-1][:-1]):.2f}' for s in steps])}"
            )
            logs.append(
                f"   • معامل اليقين التراكمي النهائي: {cumulative_confidence * 100:.1f}%"
            )

            result_str = (
                f"🎲 **نتائج الاستدلال الاحتمالي (PLN Engine):**\n"
                f"• المسار الدلالي المكتشف: {' ➔ '.join(path)}\n"
                f"• التفصيل الدقيق للروابط:\n  " + "\n  ".join(steps) + "\n"
                f"• **نسبة اليقين/الاحتمالية الإجمالية لترابط الكيانات: {cumulative_confidence * 100:.1f}%**"
            )
            return result_str

        except nx.NetworkXNoPath:
            logs.append(
                f"⚠️ [PLN]: لا يوجد أي مسار ترابط احتمالي بين '{c_a}' و '{c_b}'."
            )
            return f"لا يوجد أي مسار ترابط بين '{concept_a}' و '{concept_b}'."

    # =========================================================================
    # 2. الحث التلقائي للقواعد المنطقية (Self-Improving Symbolic Rule Induction)
    # =========================================================================
    def self_improve_rule_induction(self, logs=None):
        """البحث التلقائي عن تكرار أنماط العلاقات في الأنطولوجيا وتوليد قواعد جديدة وحفظها"""
        if logs is None:
            logs = []

        if getattr(self, "strict_mode", False):
            logs.append(
                "🔒 [وضع الحقائق الثابتة]: تم إيقاف حث واستخلاص القواعد المنطقية لضمان ثبات المعرفة بنسبة 100%."
            )
            return []

        graph_to_use = self.sandbox_graph if self.in_sandbox else self.graph

        logs.append(
            "⚡ [حث القواعد الرمزية]: جاري فحص الرسوم المعرفية واكتشاف الأنماط المتكررة (Pattern Mining)..."
        )

        # سنبحث عن مثلثات من العلاقات: X -> A -> Y و Y -> B -> Z يؤدي لـ X -> C -> Z
        # نجمع التكرارات
        candidates = {}  # (relation_a, relation_b, relation_c) -> { "support": count, "total_ab": count }

        nodes = list(graph_to_use.nodes)
        if len(nodes) < 3:
            logs.append(
                "⚠️ [حث القواعد]: عدد العقد في الشبكة المعرفية قليل جداً (< 3) لا يسمح بحث القواعد تلقائياً."
            )
            return []

        # فحص كافة الثلاثيات الممكنة للعثور على المسارات
        for x in nodes:
            for y in nodes:
                if x == y:
                    continue
                # جلب العلاقات من x إلى y
                for _, _, d1 in graph_to_use.out_edges(x, data=True):
                    if d1.get("relation") == "is_a":
                        continue  # نتفادى العلاقات الهرمية الأساسية
                    rel_a = d1.get("relation")
                    if not rel_a:
                        continue

                    # هل y له جيران z؟
                    for _, z, d2 in graph_to_use.out_edges(y, data=True):
                        if z == x or z == y:
                            continue
                        if d2.get("relation") == "is_a":
                            continue
                        rel_b = d2.get("relation")
                        if not rel_b:
                            continue

                        # وجدنا مسار طوله 2: x -> rel_a -> y -> rel_b -> z
                        # هل هناك علاقة مباشرة من x إلى z؟
                        for _, _, d3 in graph_to_use.out_edges(x, data=True):
                            rel_c = d3.get("relation")
                            if not rel_c:
                                continue

                            key = (rel_a, rel_b, rel_c)
                            if key not in candidates:
                                candidates[key] = {
                                    "instances": set(),
                                    "ab_pairs": set(),
                                }
                            candidates[key]["instances"].add((x, y, z))
                            candidates[key]["ab_pairs"].add((x, y, z))

        new_rules = []
        for (rel_a, rel_b, rel_c), data in candidates.items():
            support = len(data["instances"])
            # حساب إجمالي الأزواج التي تحقق rel_a و rel_b
            # سنقوم بحسابه بشكل تقريبي لمعرفة الثقة
            confidence = min(
                1.0, 0.4 + (support * 0.15)
            )  # معادلة استكشافية تعتمد على حجم التكرار

            if support >= 1:  # إذا تكررت ولو مرة واحدة كبداية
                rule_name = f"induced_{rel_a}_{rel_b}_to_{rel_c}"
                antecedents = [["?x", rel_a, "?y"], ["?y", rel_b, "?z"]]
                consequent = ["?x", rel_c, "?z"]

                # فحص ما إذا كانت القاعدة موجودة مسبقاً في قاعدة البيانات
                is_duplicate = False
                try:
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT id FROM rules WHERE rule_name=?", (rule_name,)
                    )
                    if cursor.fetchone():
                        is_duplicate = True
                    conn.close()
                except Exception:
                    pass

                if not is_duplicate:
                    new_rules.append(
                        {
                            "rule_name": rule_name,
                            "antecedents": antecedents,
                            "consequent": consequent,
                            "confidence": confidence,
                        }
                    )

                    # حفظ القاعدة الجديدة في قاعدة البيانات إذا لم نكن في وضع الرمل
                    if not self.in_sandbox:
                        try:
                            conn = sqlite3.connect(self.db_path)
                            cursor = conn.cursor()
                            cursor.execute(
                                """
                                INSERT OR IGNORE INTO rules (rule_name, antecedents, consequent, confidence, is_active)
                                VALUES (?, ?, ?, ?, 1)
                            """,
                                (
                                    rule_name,
                                    json.dumps(antecedents, ensure_ascii=False),
                                    json.dumps(consequent, ensure_ascii=False),
                                    confidence,
                                ),
                            )
                            conn.commit()
                            conn.close()
                        except Exception as e:
                            print(f"⚠️ فشل حفظ القاعدة المستحثة: {e}")

                    logs.append(
                        f"✨ [حث القواعد تلقائياً]: تم استخلاص قاعدة استدلالية جديدة بدعم {support} حالات وثقة {confidence * 100:.1f}%:"
                    )
                    logs.append(
                        f"   📜 {rule_name}: (?x, {rel_a}, ?y) ∧ (?y, {rel_b}, ?z) ➔ (?x, {rel_c}, ?z)"
                    )

        if not new_rules:
            logs.append(
                "💤 [حث القواعد]: لم يتم العثور على أنماط جديدة لتكوين قواعد فريدة إضافية."
            )

        return new_rules

    # =========================================================================
    # 3. محاكاة العوالم البديلة (Counterfactual "What-If" Sandbox)
    # =========================================================================
    def start_sandbox(self):
        """بدء بيئة تجريبية معزولة لا تؤثر على قاعدة البيانات الحقيقية"""
        self.sandbox_graph = self.graph.copy()
        self.in_sandbox = True
        return True

    def commit_sandbox(self):
        """اعتماد التعديلات المجراة في البيئة التجريبية ودمجها بقاعدة البيانات الرسمية"""
        if not self.in_sandbox or self.sandbox_graph is None:
            return False

        # دمج التغييرات
        self.graph = self.sandbox_graph.copy()
        self.in_sandbox = False

        # حفظ المفاهيم والعلاقات الجديدة لقاعدة البيانات
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # جلب المفاهيم الحالية وتحديثها
            for node, ndata in self.graph.nodes(data=True):
                super_type = ndata.get("super_type")
                props = ndata.get("properties", [])
                conf = ndata.get("confidence", 1.0)
                cursor.execute(
                    "INSERT OR REPLACE INTO concepts (name, super_type, properties, confidence) VALUES (?, ?, ?, ?)",
                    (node, super_type, json.dumps(props), conf),
                )

            # جلب العلاقات الحالية وتحديثها
            for u, v, edata in self.graph.edges(data=True):
                pred = edata.get("relation")
                v_from = edata.get("valid_from")
                v_to = edata.get("valid_to")
                conf = edata.get("confidence", 1.0)
                cursor.execute(
                    "INSERT OR REPLACE INTO triples (subject, predicate, object, valid_from, valid_to, confidence) VALUES (?, ?, ?, ?, ?, ?)",
                    (u, pred, v, v_from, v_to, conf),
                )

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"⚠️ فشل حفظ تعديلات بيئة الرمل: {e}")
            return False

    def rollback_sandbox(self):
        """التراجع التام عن كافة التغييرات والافتراضات التي أجريت في بيئة الرمل"""
        self.sandbox_graph = None
        self.in_sandbox = False
        return True

    def predict_impact_chain(
        self, start_concept: str, logs: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        يتنبأ بسلسلة التأثيرات المتعاقبة انطلاقاً من حدث أو مفهوم معين
        بناءً على علاقات السببية مثل 'يؤدي_إلى' و'يسبب' و'ينتج_عنه'.
        Calculates cumulative confidence using joint probability chains.
        """
        if logs is None:
            logs = []

        start_concept = normalize_arabic(start_concept)
        graph = self.sandbox_graph if self.in_sandbox else self.graph

        if not graph.has_node(start_concept):
            logs.append(f"⚠️ المفهوم '{start_concept}' غير موجود في قاعدة المعرفة.")
            return []

        logs.append(f"🔮 بدء تتبع سلسلة التأثيرات السببية لـ: '{start_concept}'")

        causality_relations = {
            normalize_arabic(r)
            for r in {
                "يؤدي_إلى",
                "يسبب",
                "ينتج_عنه",
                "يؤدي إلى",
                "ينتج عنه",
                "يسبب في",
                "leads_to",
                "causes",
                "results_in",
                "leads to",
                "results in",
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
                normalized_rel = normalize_arabic(rel)

                if normalized_rel in causality_relations or any(
                    cr in normalized_rel for cr in causality_relations
                ):
                    edge_conf = edge_data.get("confidence", 1.0)
                    cumulative_conf = current_conf * edge_conf

                    impact_entry = {
                        "from": node,
                        "relation": rel,
                        "to": neighbor,
                        "confidence": edge_conf,
                        "cumulative_confidence": round(cumulative_conf, 3),
                        "depth": depth,
                    }
                    chain.append(impact_entry)
                    logs.append(
                        f"🔗 خطوة {depth}: '{node}' ➔ {rel} ➔ '{neighbor}' (ثقة تراكمية: {round(cumulative_conf, 2)})"
                    )

                    traverse(neighbor, cumulative_conf, depth + 1)

        traverse(start_concept, 1.0, 1)
        return chain


# =========================================================================
# تهيئة الكائن المعرفي العالمي (Global Prototype Instance)
# =========================================================================
prototype = ArabicNeuroSymbolicPrototype()


# =========================================================================
# محاكي الفيزياء ثنائي الأبعاد لعقد الشبكة على Canvas في Tkinter
# =========================================================================
class PhysicsGraph:
    def __init__(self, canvas):
        self.canvas = canvas
        self.nodes = {}  # name -> {x, y, vx, vy, group}
        self.edges = []  # list of (u, v, relation)
        self.dragged_node = None

        # نوع التخطيط البصري الفعال (physics | circular | tree)
        self.layout_mode = "physics"

        # مؤشرات الاستقرار وخفض استهلاك المعالج
        self.is_stable = False
        self.ticks_since_stable = 0

        # معامل القوى الفيزيائية
        self.k_repulsion = 10000.0  # قوة التنافر المتبادل (كولوم)
        self.c_attraction = 0.05  # قوة تجاذب الروابط الحافية (هوك)
        self.rest_length = 130.0  # طول الزنبرك الطبيعي المفضل
        self.damping = 0.82  # احتكاك لتخميد الحركة وإيقاف الاهتزاز
        self.gravity = 0.04  # سحب خفيف لمركز الشاشة لمنع الشتات

        # ربط أحداث الفأرة للسحب والإفلات التفاعلي
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

    def add_node(self, name, group="concept"):
        if name not in self.nodes:
            import random

            w = self.canvas.winfo_width() or 600
            h = self.canvas.winfo_height() or 500
            self.nodes[name] = {
                "x": w / 2 + random.uniform(-60, 60),
                "y": h / 2 + random.uniform(-60, 60),
                "vx": 0.0,
                "vy": 0.0,
                "group": group,
            }
            # إيقاظ محاكي الفيزياء عند إضافة عقدة جديدة
            self.is_stable = False
            self.ticks_since_stable = 0

    def add_edge(self, u, v, relation):
        self.add_node(u, "instance")
        self.add_node(v, "instance")
        if not any(e[0] == u and e[1] == v and e[2] == relation for e in self.edges):
            self.edges.append((u, v, relation))
            # إيقاظ محاكي الفيزياء عند إضافة حافة جديدة
            self.is_stable = False
            self.ticks_since_stable = 0

    def update_physics(self):
        # تخطي الحسابات إذا كانت المحاكاة مستقرة لتوفير المعالج 100%
        if self.is_stable and self.dragged_node is None:
            return

        w = self.canvas.winfo_width() or 600
        h = self.canvas.winfo_height() or 500
        cx, cy = w / 2, h / 2

        # إذا تم اختيار وضع تخطيط ثابت (دائري أو هرمي)
        if self.layout_mode != "physics":
            target_positions = {}
            node_names = sorted(list(self.nodes.keys()))
            num_nodes = len(node_names)

            if num_nodes > 0:
                if self.layout_mode == "circular":
                    import math

                    radius = min(w, h) * 0.35
                    for i, name in enumerate(node_names):
                        angle = (2 * math.pi * i) / num_nodes
                        target_positions[name] = (
                            cx + radius * math.cos(angle),
                            cy + radius * math.sin(angle),
                        )

                elif self.layout_mode == "tree":
                    # تقسيم ثنائي الأعمدة: المفاهيم/الأصناف يساراً، والكيانات/الحالات يميناً
                    left_nodes = [
                        n for n in node_names if self.nodes[n]["group"] == "concept"
                    ]
                    right_nodes = [
                        n for n in node_names if self.nodes[n]["group"] != "concept"
                    ]

                    if not left_nodes or not right_nodes:
                        mid = num_nodes // 2
                        left_nodes = node_names[:mid]
                        right_nodes = node_names[mid:]

                    for idx, name in enumerate(left_nodes):
                        spacing = h / (len(left_nodes) + 1)
                        target_positions[name] = (cx - 150, spacing * (idx + 1))

                    for idx, name in enumerate(right_nodes):
                        spacing = h / (len(right_nodes) + 1)
                        target_positions[name] = (cx + 150, spacing * (idx + 1))

            # انزلاق سلس للعقد نحو إحداثيات التخطيط المستهدف (Smooth Glide Transition)
            total_error = 0.0
            for name, (tx, ty) in target_positions.items():
                if name == self.dragged_node:
                    continue
                node = self.nodes[name]
                dx = tx - node["x"]
                dy = ty - node["y"]
                node["x"] += dx * 0.15
                node["y"] += dy * 0.15
                node["vx"] = 0.0
                node["vy"] = 0.0
                total_error += dx * dx + dy * dy

            # التحقق من استقرار الانتقال السلس للتجميد وتوفير المعالج
            if self.dragged_node is None:
                if total_error < 1.0:  # إجمالي الخطأ أقل من بكسل واحد
                    self.ticks_since_stable += 1
                    if self.ticks_since_stable > 30:
                        self.is_stable = True
                else:
                    self.ticks_since_stable = 0
                    self.is_stable = False
            return

        # 1. حساب قوى التنافر الكولومي المتبادل
        node_names = list(self.nodes.keys())
        for i in range(len(node_names)):
            u_name = node_names[i]
            u = self.nodes[u_name]
            if u_name == self.dragged_node:
                continue
            for j in range(i + 1, len(node_names)):
                v_name = node_names[j]
                v = self.nodes[v_name]

                dx = u["x"] - v["x"]
                dy = u["y"] - v["y"]
                dist_sq = dx * dx + dy * dy + 0.1
                dist = dist_sq**0.5

                if dist < 320:
                    force = self.k_repulsion / dist_sq
                    fx = (dx / dist) * force
                    fy = (dy / dist) * force

                    if u_name != self.dragged_node:
                        u["vx"] += fx
                        u["vy"] += fy
                    if v_name != self.dragged_node:
                        v["vx"] -= fx
                        v["vy"] -= fy

        # 2. حساب قوى التجاذب الزنبركي على طول الحواف
        for u_name, v_name, relation in self.edges:
            if u_name not in self.nodes or v_name not in self.nodes:
                continue
            u = self.nodes[u_name]
            v = self.nodes[v_name]

            dx = u["x"] - v["x"]
            dy = u["y"] - v["y"]
            dist = (dx * dx + dy * dy) ** 0.5 + 0.1

            force = self.c_attraction * (dist - self.rest_length)
            fx = (dx / dist) * force
            fy = (dy / dist) * force

            if u_name != self.dragged_node:
                u["vx"] -= fx
                u["vy"] -= fy
            if v_name != self.dragged_node:
                v["vx"] += fx
                v["vy"] += fy

        # 3. سحب خفيف نحو المركز وتطبيق الإزاحة والحدود
        total_kinetic_energy = 0.0
        for name, node in self.nodes.items():
            if name == self.dragged_node:
                continue

            dx = cx - node["x"]
            dy = cy - node["y"]
            node["vx"] += dx * self.gravity
            node["vy"] += dy * self.gravity

            # تطبيق الاحتكاك وتحديث الموقع
            node["vx"] *= self.damping
            node["vy"] *= self.damping
            node["x"] += node["vx"]
            node["y"] += node["vy"]

            # الحدود لضمان بقائها داخل الكانفاس
            node["x"] = max(35, min(w - 35, node["x"]))
            node["y"] = max(35, min(h - 35, node["y"]))

            total_kinetic_energy += node["vx"] ** 2 + node["vy"] ** 2

        # التحقق التلقائي من حالة السكون لتجميد المحرك مؤقتاً
        if self.dragged_node is None:
            if total_kinetic_energy < 0.02:
                self.ticks_since_stable += 1
                if self.ticks_since_stable > 45:  # مستقرة لحوالي 3/4 ثانية
                    self.is_stable = True
            else:
                self.ticks_since_stable = 0
                self.is_stable = False

    def draw(self):
        # تخطي إعادة الرسم المكلفة إذا كانت الأشكال مستقرة ولم تتحرك
        if self.is_stable and self.dragged_node is None:
            return

        self.canvas.delete("all")

        w = self.canvas.winfo_width() or 600
        h = self.canvas.winfo_height() or 500

        # 1. رسم شبكة خلفية مستقبلية خفيفة جداً
        grid_size = 40
        for x in range(0, w, grid_size):
            self.canvas.create_line(x, 0, x, h, fill="#0b0e1e", width=1)
        for y in range(0, h, grid_size):
            self.canvas.create_line(0, y, w, y, fill="#0b0e1e", width=1)

        # 2. رسم الروابط (الحواف)
        for u_name, v_name, relation in self.edges:
            if u_name not in self.nodes or v_name not in self.nodes:
                continue
            u = self.nodes[u_name]
            v = self.nodes[v_name]

            color = "#bd00ff" if relation == "is_a" else "#00f0ff"
            # خط مع رأس سهم دلالي موجه
            self.canvas.create_line(
                u["x"],
                u["y"],
                v["x"],
                v["y"],
                fill=color,
                width=2,
                arrow="last",
                arrowshape=(10, 12, 4),
            )

            # كتابة اسم العلاقة في المنتصف
            mx = (u["x"] + v["x"]) / 2
            my = (u["y"] + v["y"]) / 2
            self.canvas.create_text(
                mx,
                my - 8,
                text=ar(relation),
                fill="#94a3b8",
                font=("Tajawal", 8, "bold"),
            )

        # 3. رسم العقد ذات الإضاءات المزدوجة النيون
        for name, node in self.nodes.items():
            x, y = node["x"], node["y"]
            glow_color = "#bd00ff" if node["group"] == "concept" else "#00f0ff"
            bg_color = "#070913" if node["group"] == "concept" else "#1e1b4b"

            # تأثير هالة النيون المضيئة (دائرة خارجية خفيفة)
            self.canvas.create_oval(
                x - 22, y - 22, x + 22, y + 22, outline=glow_color, fill="", width=2
            )
            # النواة الصلبة للعقدة (دائرة داخلية ملونة)
            self.canvas.create_oval(
                x - 14,
                y - 14,
                x + 14,
                y + 14,
                outline=glow_color,
                fill=bg_color,
                width=2,
            )

            # نص العقدة
            self.canvas.create_text(
                x, y + 30, text=ar(name), fill="#ffffff", font=("Tajawal", 9, "bold")
            )

    def on_press(self, event):
        # إيقاظ المحاكاة عند النقر للتفاعل السحب
        self.is_stable = False
        self.ticks_since_stable = 0
        for name, node in self.nodes.items():
            dx = node["x"] - event.x
            dy = node["y"] - event.y
            if dx * dx + dy * dy < 625:  # مسافة النقر 25 بيكسل
                self.dragged_node = name
                node["vx"] = 0.0
                node["vy"] = 0.0
                break

    def on_drag(self, event):
        # الحفاظ على إيقاظ التحديث أثناء السحب
        self.is_stable = False
        self.ticks_since_stable = 0
        if self.dragged_node and self.dragged_node in self.nodes:
            node = self.nodes[self.dragged_node]
            node["x"] = event.x
            node["y"] = event.y

    def on_release(self, event):
        self.dragged_node = None
        self.is_stable = False
        self.ticks_since_stable = 0


# =========================================================================
# واجهة سطح المكتب المضيئة والمطورة بالكامل باستخدام CustomTkinter
# =========================================================================
try:
    import customtkinter as ctk
except ImportError:
    # سيحدث خطأ عند تشغيل الواجهة إذا لم تثبت المكتبة، وسيتعامل معها سكريبت الإطلاق
    pass


class WorkspaceDialog(ctk.CTkFrame if "ctk" not in globals() else ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title(ar("مساحة عمل معرفية جديدة"))
        self.geometry("420x330")
        self.resizable(False, False)
        self.configure(fg_color="#070913")

        # Make modal
        self.transient(parent)
        self.grab_set()

        self.result_name = None
        self.result_mode = None

        # Title Label
        title_lbl = ctk.CTkLabel(
            self,
            text=ar("⚙️ إنشاء مساحة عمل جديدة"),
            font=("Tajawal", 13, "bold"),
            text_color="#00f0ff",
        )
        title_lbl.pack(pady=15)

        # Name Entry
        lbl_name = ctk.CTkLabel(
            self,
            text=ar("اسم مساحة العمل:"),
            font=("Tajawal", 11),
            text_color="#94a3b8",
        )
        lbl_name.pack(anchor="e", padx=30, pady=(10, 2))

        self.entry_name = ctk.CTkEntry(
            self,
            placeholder_text=ar("مثال: الطب الشرعي، الرياضيات..."),
            fg_color="#020617",
            border_color="#0891b2",
            font=("Tajawal", 11),
            justify="right",
        )
        self.entry_name.pack(fill="x", padx=30, pady=2)

        # Mode Selection
        lbl_mode = ctk.CTkLabel(
            self,
            text=ar("نوع ونمط تشغيل المساحة:"),
            font=("Tajawal", 11),
            text_color="#94a3b8",
        )
        lbl_mode.pack(anchor="e", padx=30, pady=(15, 2))

        self.mode_var = ctk.StringVar(value="active")

        self.radio_active = ctk.CTkRadioButton(
            self,
            text=ar("🧠 الوضع المعرفي النشط (يحلم ويستنتج ويبحث عن فجوات)"),
            variable=self.mode_var,
            value="active",
            fg_color="#8b5cf6",
            hover_color="#7c3aed",
            font=("Tajawal", 9),
            text_color="#e2e8f0",
        )
        self.radio_active.pack(anchor="e", padx=30, pady=5)

        self.radio_strict = ctk.CTkRadioButton(
            self,
            text=ar("🔒 وضع الحقائق الثابتة (يلتزم بالمدخلات 100% ويكتشف التعارض فقط)"),
            variable=self.mode_var,
            value="strict",
            fg_color="#ef4444",
            hover_color="#dc2626",
            font=("Tajawal", 9),
            text_color="#e2e8f0",
        )
        self.radio_strict.pack(anchor="e", padx=30, pady=5)

        # Buttons
        btns_frame = ctk.CTkFrame(self, fg_color="transparent")
        btns_frame.pack(fill="x", padx=30, pady=20)

        btn_cancel = ctk.CTkButton(
            btns_frame,
            text=ar("إلغاء"),
            fg_color="#1e293b",
            hover_color="#0f172a",
            text_color="#94a3b8",
            font=("Tajawal", 11, "bold"),
            width=100,
            command=self.destroy,
        )
        btn_cancel.pack(side="left", padx=5)

        btn_create = ctk.CTkButton(
            btns_frame,
            text=ar("🚀 إنشاء وتفعيل"),
            fg_color="#10b981",
            hover_color="#059669",
            text_color="#fff",
            font=("Tajawal", 11, "bold"),
            width=120,
            command=self.on_create,
        )
        btn_create.pack(side="right", padx=5)

        # Center in parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def on_create(self):
        name = self.entry_name.get().strip()
        if not name:
            from tkinter import messagebox

            messagebox.showwarning(ar("تنبيه"), ar("يرجى إدخال اسم مساحة العمل!"))
            return
        self.result_name = name
        self.result_mode = self.mode_var.get()
        self.destroy()


class CyberpunkApp(ctk.CTk if "ctk" in globals() else object):
    def __init__(self):
        super().__init__()

        # تهيئة المحرك العصبي الرمزي الخلفي
        self.prototype = prototype

        # إعداد نافذة سطح المكتب
        self.title("LEGEND - المساعد العصبي-الرمزي الذكي")
        self.geometry("1300x820")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # متغيرات التشغيل
        self.active_mode = "chat"
        self.thinking = False
        self.timer_start = 0.0
        self.show_stats = False

        # تحميل مساحات العمل الديناميكية
        self.workspaces_file = os.path.join(
            os.path.dirname(self.prototype.db_path), "workspaces.json"
        )
        self.load_workspaces()

        # بناء تصميم الواجهة
        self.build_ui()

        # تهيئة كلاس الفيزياء
        self.physics = PhysicsGraph(self.canvas)
        self.sync_graph_to_physics()
        self.refresh_relations_list()
        self.refresh_rules_display()

        # بدء حلقة الفيزياء والتحديث المستمر بـ 60 إطار بالثانية
        self.update_loop()

        # ربط أحداث التمرير بالفأرة عالمياً لحل مشكلة التمرير في أنظمة لينكس والتبعية للمكونات الأبناء
        self.bind_all("<Button-4>", self.on_global_scroll)
        self.bind_all("<Button-5>", self.on_global_scroll)
        self.bind_all("<MouseWheel>", self.on_global_scroll)

        # الفتح الافتراضي على شاشة الإحصائيات الفاخرة لتسريع الاستجابة وتخفيف معالجة الفيزياء
        self.toggle_view()

    def load_workspaces(self):
        default_workspaces = {
            ar("العقل العام (الافتراضي)"): {
                "db_filename": "ontology.db",
                "mode": "active",
            }
        }
        if os.path.exists(self.workspaces_file):
            try:
                with open(self.workspaces_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self.workspaces = {}
                    for k, v in loaded.items():
                        if isinstance(v, str):
                            self.workspaces[k] = {"db_filename": v, "mode": "active"}
                        else:
                            self.workspaces[k] = v
            except Exception:
                self.workspaces = default_workspaces
        else:
            self.workspaces = default_workspaces
            self.save_workspaces()

    def save_workspaces(self):
        try:
            with open(self.workspaces_file, "w", encoding="utf-8") as f:
                json.dump(self.workspaces, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"⚠️ فشل حفظ ملف مساحات العمل: {e}")

    def build_ui(self):
        # 1. تصميم شريط العنوان العلوي (Top Ambient Bar)
        self.top_bar = ctk.CTkFrame(
            self,
            height=70,
            corner_radius=0,
            fg_color="#070913",
            border_width=1,
            border_color="#00f0ff",
        )
        self.top_bar.pack(fill="x", side="top")

        self.logo_label = ctk.CTkLabel(
            self.top_bar,
            text=" LEGEND",
            font=("Inter", 24, "bold"),
            text_color="#00f0ff",
        )
        self.logo_label.pack(side="left", padx=25)

        self.sub_label = ctk.CTkLabel(
            self.top_bar,
            text=ar("المساعد العصبي-الرمزي التفاعلي لسطح المكتب"),
            font=("Tajawal", 12, "bold"),
            text_color="#bd00ff",
        )
        self.sub_label.pack(side="left", padx=10)

        # مساحات العمل متعددة القواعد (Multi-Ontology Workspaces)
        self.workspace_lbl = ctk.CTkLabel(
            self.top_bar,
            text=ar("📁 مساحة العمل:"),
            font=("Tajawal", 11, "bold"),
            text_color="#00f0ff",
        )
        self.workspace_lbl.pack(side="left", padx=(40, 5))

        self.workspace_selector = ctk.CTkOptionMenu(
            self.top_bar,
            values=list(self.workspaces.keys()),
            command=self.on_workspace_change,
            fg_color="#070913",
            button_color="#054552",
            button_hover_color="#00f0ff",
            dropdown_fg_color="#070913",
            dropdown_hover_color="#bd00ff",
            dropdown_text_color="#fff",
            font=("Tajawal", 10, "bold"),
            width=160,
        )
        self.workspace_selector.set(ar("العقل العام (الافتراضي)"))
        self.workspace_selector.pack(side="left", padx=5)

        # زر إضافة مساحة عمل
        self.add_workspace_btn = ctk.CTkButton(
            self.top_bar,
            text="➕",
            width=28,
            height=28,
            fg_color="#070913",
            border_width=1,
            border_color="#39ff14",
            hover_color="#39ff14",
            text_color="#fff",
            font=("Inter", 11, "bold"),
            command=self.add_workspace,
        )
        self.add_workspace_btn.pack(side="left", padx=2)

        # زر حذف مساحة عمل
        self.del_workspace_btn = ctk.CTkButton(
            self.top_bar,
            text="❌",
            width=28,
            height=28,
            fg_color="#070913",
            border_width=1,
            border_color="#ff007a",
            hover_color="#ff007a",
            text_color="#fff",
            font=("Inter", 11, "bold"),
            command=self.delete_workspace,
        )
        self.del_workspace_btn.pack(side="left", padx=2)

        # مؤشر الحالة المضيء
        self.status_indicator = ctk.CTkLabel(
            self.top_bar,
            text=ar("🟢 جاهز للعمل"),
            font=("Tajawal", 13, "bold"),
            text_color="#39ff14",
        )
        self.status_indicator.pack(side="right", padx=25)

        # 2. جسم التطبيق الرئيسي (شبكة تقسيم)
        self.main_body = ctk.CTkFrame(self, fg_color="#05070f")
        self.main_body.pack(fill="both", expand=True, padx=15, pady=15)

        # لوحة التحكم اليسرى (Control Panel)
        self.left_panel = ctk.CTkScrollableFrame(
            self.main_body,
            width=420,
            fg_color="#0a0d1e",
            border_width=1,
            border_color="#054552",
        )
        self.left_panel.pack(fill="y", side="left", padx=(0, 10))

        # 3. إعدادات المزود والـ API (API Configuration)
        self.api_title = ctk.CTkLabel(
            self.left_panel,
            text=ar("🛠️ تكوين خوادم الـ API"),
            font=("Tajawal", 14, "bold"),
            text_color="#fff",
        )
        self.api_title.pack(anchor="w", padx=10, pady=(10, 10))

        # اختيار مزود الخدمة
        self.provider_label = ctk.CTkLabel(
            self.left_panel,
            text=ar("مزود الخدمة اللغوية:"),
            font=("Tajawal", 11, "bold"),
            text_color="#94a3b8",
        )
        self.provider_label.pack(anchor="w", padx=10)
        self.provider_select = ctk.CTkOptionMenu(
            self.left_panel,
            values=[
                ar("Google API (الافتراضي)"),
                ar("Groq High-Speed API"),
                ar("OpenRouter Gateway"),
            ],
            command=self.on_provider_change,
            fg_color="#070913",
            button_color="#00f0ff",
            button_hover_color="#bd00ff",
        )
        self.provider_select.pack(fill="x", padx=10, pady=(0, 10))

        # مفتاح API
        self.key_label = ctk.CTkLabel(
            self.left_panel,
            text=ar("مفتاح الـ API النشط:"),
            font=("Tajawal", 11, "bold"),
            text_color="#94a3b8",
        )
        self.key_label.pack(anchor="w", padx=10)
        self.key_entry = ctk.CTkEntry(
            self.left_panel,
            fg_color="#070913",
            border_color="#054552",
            font=("Courier New", 12),
        )
        self.key_entry.pack(fill="x", padx=10, pady=(0, 10))

        # اختيار الموديل
        self.model_label = ctk.CTkLabel(
            self.left_panel,
            text=ar("نموذج الذكاء الاصطناعي النشط:"),
            font=("Tajawal", 11, "bold"),
            text_color="#94a3b8",
        )
        self.model_label.pack(anchor="w", padx=10)
        self.model_select = ctk.CTkOptionMenu(
            self.left_panel, values=[], fg_color="#070913", button_color="#00f0ff"
        )
        self.model_select.pack(fill="x", padx=10, pady=(0, 20))

        self.set_api_defaults("google")  # التحميل الافتراضي لجوجل

        # 4. الأنماط المعرفية الثلاثة (Modes Selector Switch)
        self.mode_title = ctk.CTkLabel(
            self.left_panel,
            text=ar("🕹️ نمط المعالجة والاتصال"),
            font=("Tajawal", 14, "bold"),
            text_color="#fff",
        )
        self.mode_title.pack(anchor="w", padx=10, pady=(0, 10))

        self.mode_frame = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        self.mode_frame.pack(fill="x", padx=10, pady=(0, 15))

        self.mode_btn_chat = ctk.CTkButton(
            self.mode_frame,
            text=ar("💬 محادثة ذكية"),
            fg_color="#bd00ff",
            text_color="#fff",
            font=("Tajawal", 11, "bold"),
            command=lambda: self.set_mode("chat"),
        )
        self.mode_btn_chat.pack(side="left", fill="x", expand=True, padx=2)

        self.mode_btn_teach = ctk.CTkButton(
            self.mode_frame,
            text=ar("🧠 تلقين وحفظ"),
            fg_color="#070913",
            text_color="#94a3b8",
            border_width=1,
            border_color="#1f2937",
            font=("Tajawal", 11, "bold"),
            command=lambda: self.set_mode("teach"),
        )
        self.mode_btn_teach.pack(side="left", fill="x", expand=True, padx=2)

        self.mode_btn_db = ctk.CTkButton(
            self.mode_frame,
            text=ar("📂 استنباط رمزي"),
            fg_color="#070913",
            text_color="#94a3b8",
            border_width=1,
            border_color="#1f2937",
            font=("Tajawal", 11, "bold"),
            command=lambda: self.set_mode("db_only"),
        )
        self.mode_btn_db.pack(side="left", fill="x", expand=True, padx=2)

        # 5. مربع الإدخال (Prompt Input Frame)
        self.input_header_frame = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        self.input_header_frame.pack(fill="x", padx=10, pady=(5, 5))

        self.input_title = ctk.CTkLabel(
            self.input_header_frame,
            text=ar("✨ دردشة واستكشاف منطقي"),
            font=("Tajawal", 11, "bold"),
            text_color="#94a3b8",
        )
        self.input_title.pack(side="right")

        self.article_btn = ctk.CTkButton(
            self.input_header_frame,
            text=ar("📝 كتابة مقال كامل"),
            fg_color="#0891b2",
            text_color="#fff",
            hover_color="#0e7490",
            font=("Tajawal", 9, "bold"),
            height=20,
            width=110,
            command=self.open_article_modal,
        )
        self.article_btn.pack(side="left")

        self.prompt_entry = ctk.CTkEntry(
            self.left_panel,
            placeholder_text=ar("اكتب هنا، مثل: أحمد يطنش المذاكرة..."),
            fg_color="#070913",
            border_color="#0891b2",
            font=("Tajawal", 12),
            justify="right",
        )
        self.prompt_entry.pack(fill="x", padx=10, pady=(0, 5))
        self.prompt_entry.bind("<Return>", lambda e: self.on_send_click())
        self.prompt_entry.bind("<KeyRelease>", self.on_key_release)

        if add_bidi_support is not None:
            try:
                add_bidi_support(self.prompt_entry._entry)
            except Exception:
                pass

        # إطار الاقتراحات والإكمال التلقائي الذكي (Smart Auto-Complete Panel)
        self.autocomplete_frame = ctk.CTkFrame(
            self.left_panel,
            fg_color="#070913",
            border_width=1,
            border_color="#054552",
            height=1,
        )
        self.autocomplete_frame.pack_forget()  # مخفي افتراضياً

        # تسمية المعاينة اللحظية
        self.preview_lbl = ctk.CTkLabel(
            self.left_panel,
            text="",
            font=("Tajawal", 11, "italic"),
            text_color="#00f0ff",
        )
        self.preview_lbl.pack(anchor="e", padx=15, pady=(0, 10))

        self.send_btn = ctk.CTkButton(
            self.left_panel,
            text=ar("🚀 إرسال للمعالجة العصبيّة الرمزيّة"),
            fg_color="#00f0ff",
            text_color="#05070f",
            hover_color="#bd00ff",
            font=("Tajawal", 12, "bold"),
            command=self.on_send_click,
        )
        self.send_btn.pack(fill="x", padx=10, pady=(0, 20))

        # 6. لوحة المقاييس الحية والمؤقت (Metrics Frame)
        self.metrics_title = ctk.CTkLabel(
            self.left_panel,
            text=ar("📊 المقاييس والتحليل الزمني"),
            font=("Tajawal", 14, "bold"),
            text_color="#fff",
        )
        self.metrics_title.pack(anchor="w", padx=10, pady=(0, 10))

        self.metrics_grid = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        self.metrics_grid.pack(fill="x", padx=10, pady=(0, 10))

        self.nodes_lbl = ctk.CTkLabel(
            self.metrics_grid,
            text=ar("عقد المعرفة (RAM): 0"),
            font=("Tajawal", 12, "bold"),
            text_color="#00f0ff",
        )
        self.nodes_lbl.pack(side="left", padx=10)

        self.edges_lbl = ctk.CTkLabel(
            self.metrics_grid,
            text=ar("الروابط الدلالية: 0"),
            font=("Tajawal", 12, "bold"),
            text_color="#bd00ff",
        )
        self.edges_lbl.pack(side="right", padx=10)

        self.timer_lbl = ctk.CTkLabel(
            self.left_panel,
            text=ar("⏱️ سرعة المعالجة: 0.00 ثانية"),
            font=("Tajawal", 14, "bold"),
            text_color="#ff007a",
        )
        self.timer_lbl.pack(fill="x", padx=10, pady=(0, 15))

        # 7. وحدة المراقبة والتحليل اللحظي (Terminal Logs)
        self.terminal_header = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        self.terminal_header.pack(fill="x", padx=10, pady=(0, 5))

        self.terminal_title = ctk.CTkLabel(
            self.terminal_header,
            text=ar("🖥️ شاشة رصد وتحليل الخطوات والشبكة"),
            font=("Tajawal", 12, "bold"),
            text_color="#fff",
        )
        self.terminal_title.pack(side="left")

        self.clear_logs_btn = ctk.CTkButton(
            self.terminal_header,
            text=ar("🧹 مسح الشاشة"),
            fg_color="#e11d48",
            text_color="#fff",
            hover_color="#be123c",
            width=80,
            height=20,
            font=("Tajawal", 10, "bold"),
            command=self.clear_logs,
        )
        self.clear_logs_btn.pack(side="right")

        self.log_box = ctk.CTkTextbox(
            self.left_panel,
            height=180,
            fg_color="#03050a",
            border_color="#1f2937",
            font=("Courier New", 11),
            text_color="#a7f3d0",
        )
        self.log_box.pack(fill="x", padx=10, pady=(0, 15))

        # 8. الجزء الأيمن: الكانفاس والمخرجات (Right Section)
        self.right_panel = ctk.CTkFrame(self.main_body, fg_color="transparent")
        self.right_panel.pack(fill="both", expand=True, side="right")

        # شبكة فيزيائية (Canvas)
        self.canvas_frame = ctk.CTkFrame(
            self.right_panel, fg_color="#05070e", border_width=1, border_color="#00f0ff"
        )
        self.canvas_frame.pack(fill="both", expand=True, pady=(0, 10))

        self.canvas = ctk.CTkCanvas(
            self.canvas_frame, bg="#05070e", highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True)

        # أزرار تحكم على الرسم الكانفاس
        self.canvas_controls = ctk.CTkFrame(self.canvas_frame, fg_color="transparent")
        self.canvas_controls.place(x=15, y=15)

        self.refresh_btn = ctk.CTkButton(
            self.canvas_controls,
            text=ar("🔄 تحديث"),
            width=70,
            fg_color="#070913",
            font=("Tajawal", 11),
            command=self.sync_graph_to_physics,
        )
        self.refresh_btn.pack(side="left", padx=5)

        self.reset_btn = ctk.CTkButton(
            self.canvas_controls,
            text=ar("🗑️ تصفير العقل"),
            width=90,
            fg_color="#070913",
            hover_color="#ff007a",
            font=("Tajawal", 11),
            command=self.on_clear_click,
        )
        self.reset_btn.pack(side="left", padx=5)

        # اختيار طريقة العرض والتخطيط البصري (Segmented Layout Selector Switch)
        self.layout_selector = ctk.CTkSegmentedButton(
            self.canvas_controls,
            values=[ar("متحرك فيزيائي"), ar("دائري منظم"), ar("تدرج هرمي")],
            command=self.change_layout_mode,
            fg_color="#070913",
            selected_color="#bd00ff",
            selected_hover_color="#ff007a",
            unselected_color="#070913",
            unselected_hover_color="#1e1b4b",
            font=("Tajawal", 10, "bold"),
        )
        self.layout_selector.set(ar("متحرك فيزيائي"))
        self.layout_selector.pack(side="left", padx=15)

        # زر تبديل العرض بين الشبكة والإحصائيات
        self.view_toggle_btn = ctk.CTkButton(
            self.canvas_controls,
            text=ar("📊 إحصائيات المعرفة"),
            width=140,
            fg_color="#0984e3",
            hover_color="#00cec9",
            text_color="#fff",
            font=("Tajawal", 10, "bold"),
            command=self.toggle_view,
        )
        self.view_toggle_btn.pack(side="left", padx=5)

        # 9. نافذة مخرجات الاستجابة اللغوية وإدارة الروابط التفاعلية (Tabbed Semantic & Relations Panel)
        self.output_frame = ctk.CTkFrame(
            self.right_panel,
            height=270,
            fg_color="#0a0d1e",
            border_width=1,
            border_color="#bd00ff",
        )
        self.output_frame.pack(fill="x", side="bottom", pady=(5, 0))

        self.output_tabview = ctk.CTkTabview(
            self.output_frame,
            fg_color="#0a0d1e",
            segmented_button_fg_color="#05070e",
            segmented_button_selected_color="#bd00ff",
            segmented_button_selected_hover_color="#9d00db",
            segmented_button_unselected_color="#070913",
            segmented_button_unselected_hover_color="#1a1c2e",
            text_color="#fff",
        )
        self.output_tabview.pack(fill="both", expand=True, padx=5, pady=5)

        # إضافة التبويبات المعربة
        self.tab_response = self.output_tabview.add(ar("💬 الاستجابة اللغوية المعرفية"))
        self.tab_relations = self.output_tabview.add(ar("🕸️ إدارة الروابط الدلالية"))
        self.tab_pln = self.output_tabview.add(ar("🎲 استدلال احتمالي (PLN)"))
        self.tab_rules = self.output_tabview.add(ar("⚡ حث القواعد"))
        self.tab_sandbox = self.output_tabview.add(ar("🪐 العوالم البديلة"))
        self.tab_cognitive = self.output_tabview.add(ar("🧠 النوم المعرفي والفضول"))

        # أ) تبويب الاستجابة اللغوية
        self.response_text = ctk.CTkTextbox(
            self.tab_response,
            height=160,
            fg_color="transparent",
            font=("Tajawal", 13),
            text_color="#fff",
        )
        self.response_text.pack(fill="both", expand=True, padx=10, pady=5)
        self.response_text.insert(
            "1.0",
            ar(
                "ابدأ بكتابة جملة تفاعلية في اليسار ليقوم النظام بفكها وتحليل علاقاتها دلالياً ورمزياً، وعرض روابطها بالشبكة الفيزيائية فوراً..."
            ),
        )
        self.response_text.configure(state="disabled")

        # ب) تبويب إدارة الروابط
        self.relations_control = ctk.CTkFrame(
            self.tab_relations, fg_color="transparent"
        )
        self.relations_control.pack(fill="x", padx=10, pady=(5, 2))

        self.relation_filter_var = ctk.StringVar(value="all")

        self.filter_all_btn = ctk.CTkRadioButton(
            self.relations_control,
            text=ar("كل الروابط المسجلة"),
            value="all",
            variable=self.relation_filter_var,
            font=("Tajawal", 11, "bold"),
            text_color="#fff",
            fg_color="#bd00ff",
            hover_color="#bd00ff",
            command=self.reset_relations_page_and_refresh,
        )
        self.filter_all_btn.pack(side="left", padx=5)

        self.filter_last_btn = ctk.CTkRadioButton(
            self.relations_control,
            text=ar("روابط آخر رد فقط"),
            value="last",
            variable=self.relation_filter_var,
            font=("Tajawal", 11, "bold"),
            text_color="#fff",
            fg_color="#bd00ff",
            hover_color="#bd00ff",
            command=self.reset_relations_page_and_refresh,
        )
        self.filter_last_btn.pack(side="left", padx=5)

        self.delete_visible_btn = ctk.CTkButton(
            self.relations_control,
            text=ar("🗑️ حذف القائمة المعروضة"),
            fg_color="#e11d48",
            hover_color="#be123c",
            text_color="#fff",
            font=("Tajawal", 11, "bold"),
            height=25,
            command=self.delete_all_visible_relations,
        )
        self.delete_visible_btn.pack(side="right", padx=5)

        # حقل البحث الجديد عن الروابط
        self.search_frame = ctk.CTkFrame(self.tab_relations, fg_color="transparent")
        self.search_frame.pack(fill="x", padx=10, pady=(2, 5))

        self.search_lbl = ctk.CTkLabel(
            self.search_frame,
            text=ar("🔎 بحث:"),
            font=("Tajawal", 10, "bold"),
            text_color="#00f0ff",
        )
        self.search_lbl.pack(side="right", padx=5)

        self.relation_search_var = ctk.StringVar()
        self.relation_search_entry = ctk.CTkEntry(
            self.search_frame,
            textvariable=self.relation_search_var,
            placeholder_text=ar("ابحث عن مفهوم، علاقة، أو كلمة..."),
            font=("Tajawal", 11),
            fg_color="#070913",
            border_color="#054552",
            height=26,
        )
        self.relation_search_entry.pack(fill="x", side="right", expand=True, padx=5)
        self.relation_search_var.trace_add("write", self.on_relation_search_change)

        # القائمة القابلة للتمرير للروابط
        self.relations_scroll = ctk.CTkScrollableFrame(
            self.tab_relations,
            height=100,  # تقليل الارتفاع قليلاً لاستيعاب أزرار التصفح والبحث
            fg_color="#03050a",
            border_width=1,
            border_color="#1f2937",
        )
        self.relations_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 2))

        # شريط التصفح (Pagination Controls Panel)
        self.relations_pagination_frame = ctk.CTkFrame(
            self.tab_relations, fg_color="transparent"
        )
        self.relations_pagination_frame.pack(fill="x", padx=10, pady=(2, 5))

        self.prev_page_btn = ctk.CTkButton(
            self.relations_pagination_frame,
            text="◀",
            width=30,
            height=24,
            fg_color="#070913",
            hover_color="#bd00ff",
            font=("Inter", 10, "bold"),
            command=self.prev_relations_page,
        )
        self.prev_page_btn.pack(side="left", padx=5)

        self.page_info_lbl = ctk.CTkLabel(
            self.relations_pagination_frame,
            text=ar("الصفحة 1 من 1"),
            font=("Tajawal", 11, "bold"),
            text_color="#fff",
        )
        self.page_info_lbl.pack(side="left", padx=10)

        self.next_page_btn = ctk.CTkButton(
            self.relations_pagination_frame,
            text="▶",
            width=30,
            height=24,
            fg_color="#070913",
            hover_color="#bd00ff",
            font=("Inter", 10, "bold"),
            command=self.next_relations_page,
        )
        self.next_page_btn.pack(side="left", padx=5)

        self.total_relations_lbl = ctk.CTkLabel(
            self.relations_pagination_frame,
            text=ar("إجمالي الروابط: 0"),
            font=("Tajawal", 11),
            text_color="#94a3b8",
        )
        self.total_relations_lbl.pack(side="right", padx=10)

        self.relation_current_page = 1
        self.relation_items_per_page = 10

        # ج) تبويب الاستدلال الاحتمالي (PLN)
        self.pln_control_frame = ctk.CTkFrame(self.tab_pln, fg_color="transparent")
        self.pln_control_frame.pack(fill="x", padx=10, pady=5)

        self.pln_lbl_a = ctk.CTkLabel(
            self.pln_control_frame,
            text=ar("الكيان أ:"),
            font=("Tajawal", 11, "bold"),
            text_color="#00f0ff",
        )
        self.pln_lbl_a.pack(side="right", padx=5)
        self.pln_concept_a_entry = ctk.CTkEntry(
            self.pln_control_frame,
            width=120,
            fg_color="#070913",
            border_color="#054552",
            font=("Tajawal", 11),
            justify="right",
        )
        self.pln_concept_a_entry.pack(side="right", padx=5)

        if add_bidi_support is not None:
            try:
                add_bidi_support(self.pln_concept_a_entry._entry)
            except Exception:
                pass

        self.pln_lbl_b = ctk.CTkLabel(
            self.pln_control_frame,
            text=ar("الكيان ب:"),
            font=("Tajawal", 11, "bold"),
            text_color="#bd00ff",
        )
        self.pln_lbl_b.pack(side="right", padx=5)
        self.pln_concept_b_entry = ctk.CTkEntry(
            self.pln_control_frame,
            width=120,
            fg_color="#070913",
            border_color="#054552",
            font=("Tajawal", 11),
            justify="right",
        )
        self.pln_concept_b_entry.pack(side="right", padx=5)

        if add_bidi_support is not None:
            try:
                add_bidi_support(self.pln_concept_b_entry._entry)
            except Exception:
                pass

        self.run_pln_btn = ctk.CTkButton(
            self.pln_control_frame,
            text=ar("🎲 احسب الترابط واليقين"),
            fg_color="#00f0ff",
            text_color="#05070f",
            hover_color="#bd00ff",
            font=("Tajawal", 11, "bold"),
            height=26,
            command=self.on_run_pln_click,
        )
        self.run_pln_btn.pack(side="left", padx=5)

        self.pln_result_textbox = ctk.CTkTextbox(
            self.tab_pln,
            height=110,
            fg_color="#03050a",
            border_color="#1f2937",
            font=("Tajawal", 12),
            text_color="#00f0ff",
        )
        self.pln_result_textbox.pack(fill="both", expand=True, padx=10, pady=5)
        self.pln_result_textbox.insert(
            "1.0", ar("نتائج الاستدلال الاحتمالي PLN ستعرض هنا بالتفصيل...")
        )
        self.pln_result_textbox.configure(state="disabled")

        # د) تبويب حث القواعد (Rule Induction)
        self.rules_control_frame = ctk.CTkFrame(self.tab_rules, fg_color="transparent")
        self.rules_control_frame.pack(fill="x", padx=10, pady=5)

        self.run_rules_btn = ctk.CTkButton(
            self.rules_control_frame,
            text=ar("⚡ استحثاث القواعد الرمزية تلقائياً (Induce Rules)"),
            fg_color="#bd00ff",
            text_color="#fff",
            hover_color="#00f0ff",
            font=("Tajawal", 11, "bold"),
            height=26,
            command=self.on_run_rule_induction_click,
        )
        self.run_rules_btn.pack(side="right", padx=5)

        self.rules_result_textbox = ctk.CTkTextbox(
            self.tab_rules,
            height=110,
            fg_color="#03050a",
            border_color="#1f2937",
            font=("Tajawal", 12),
            text_color="#39ff14",
        )
        self.rules_result_textbox.pack(fill="both", expand=True, padx=10, pady=5)
        self.rules_result_textbox.insert(
            "1.0", ar("القواعد المنطقية النشطة في العقل المعرفي...")
        )
        self.rules_result_textbox.configure(state="disabled")

        # هـ) تبويب محاكاة العوالم البديلة (Counterfactual Sandbox)
        self.sandbox_control_frame = ctk.CTkFrame(
            self.tab_sandbox, fg_color="transparent"
        )
        self.sandbox_control_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.sandbox_status_lbl = ctk.CTkLabel(
            self.sandbox_control_frame,
            text=ar(
                "🪐 بيئة الرمل الافتراضية: ❌ غير نشطة (تعديلاتك مباشرة على قاعدة المعرفة الحقيقية)"
            ),
            font=("Tajawal", 12, "bold"),
            text_color="#94a3b8",
        )
        self.sandbox_status_lbl.pack(anchor="w", pady=5)

        self.sandbox_btns_frame = ctk.CTkFrame(
            self.sandbox_control_frame, fg_color="transparent"
        )
        self.sandbox_btns_frame.pack(fill="x", pady=10)

        self.sandbox_toggle_btn = ctk.CTkButton(
            self.sandbox_btns_frame,
            text=ar("🪐 تفعيل وضع الرمل (What-If)"),
            fg_color="#f59e0b",
            text_color="#000",
            hover_color="#d97706",
            font=("Tajawal", 11, "bold"),
            command=self.toggle_sandbox_mode,
        )
        self.sandbox_toggle_btn.pack(side="right", padx=5)

        self.sandbox_commit_btn = ctk.CTkButton(
            self.sandbox_btns_frame,
            text=ar("💾 حفظ واعتماد التغييرات (Commit)"),
            fg_color="#10b981",
            text_color="#fff",
            hover_color="#059669",
            font=("Tajawal", 11, "bold"),
            state="disabled",
            command=self.commit_sandbox_changes,
        )
        self.sandbox_commit_btn.pack(side="right", padx=5)

        self.sandbox_rollback_btn = ctk.CTkButton(
            self.sandbox_btns_frame,
            text=ar("🔄 تراجع وتصفير (Rollback)"),
            fg_color="#ef4444",
            text_color="#fff",
            hover_color="#dc2626",
            font=("Tajawal", 11, "bold"),
            state="disabled",
            command=self.rollback_sandbox_changes,
        )
        self.sandbox_rollback_btn.pack(side="right", padx=5)

        # و) تبويب النوم المعرفي ورصد الفضول (Cognitive Sleep & Active Curiosity Engine)
        self.cognitive_control_frame = ctk.CTkFrame(
            self.tab_cognitive, fg_color="transparent"
        )
        self.cognitive_control_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # تقسيم التبويب إلى قسمين رئيسيين (يسار لـ النوم المعرفي، ويمين لـ الفضول والأسئلة)
        self.cognitive_panes_frame = ctk.CTkFrame(
            self.cognitive_control_frame, fg_color="transparent"
        )
        self.cognitive_panes_frame.pack(fill="both", expand=True)

        # 1. لوحة النوم المعرفي (Cognitive Sleep Pane - Left/West side)
        self.sleep_pane = ctk.CTkFrame(
            self.cognitive_panes_frame,
            fg_color="#070913",
            border_width=1,
            border_color="#1e1b4b",
        )
        self.sleep_pane.pack(side="left", fill="both", expand=True, padx=(0, 5), pady=5)

        self.sleep_title_lbl = ctk.CTkLabel(
            self.sleep_pane,
            text=ar("🌙 دورة النوم المعرفي والتحصين (Cognitive Sleep)"),
            font=("Tajawal", 12, "bold"),
            text_color="#a78bfa",
        )
        self.sleep_title_lbl.pack(anchor="w", padx=10, pady=5)

        self.sleep_desc_lbl = ctk.CTkLabel(
            self.sleep_pane,
            text=ar(
                "تقوية روابط المفاهيم المشتركة، تقليم العلاقات الضعيفة، إجراء أحلام اليقظة لاستكشاف الصلات، ثم استقرار المعرفة الاستنتاجية."
            ),
            font=("Tajawal", 10),
            text_color="#94a3b8",
            wraplength=280,
            justify="right",
        )
        self.sleep_desc_lbl.pack(anchor="w", padx=10, pady=(0, 10))

        self.sleep_run_btn = ctk.CTkButton(
            self.sleep_pane,
            text=ar("💤 تشغيل دورة الاسترخاء والنوم المعرفي"),
            fg_color="#8b5cf6",
            text_color="#fff",
            hover_color="#7c3aed",
            font=("Tajawal", 11, "bold"),
            command=self.run_cognitive_sleep_cycle,
        )
        self.sleep_run_btn.pack(fill="x", padx=10, pady=5)

        self.sleep_log_box = ctk.CTkTextbox(
            self.sleep_pane,
            fg_color="#020617",
            border_width=1,
            border_color="#1e1b4b",
            font=("Courier New", 10),
            text_color="#c084fc",
        )
        self.sleep_log_box.pack(fill="both", expand=True, padx=10, pady=5)
        self.sleep_log_box.insert(
            "1.0",
            ar(
                "سجل دورة النوم خالي حالياً. اضغط على الزر بالأعلى لبدء النوم والتحصين..."
            ),
        )
        self.sleep_log_box.configure(state="disabled")

        # 2. لوحة الفضول والأسئلة (Active Curiosity Pane - Right/East side)
        self.curiosity_pane = ctk.CTkFrame(
            self.cognitive_panes_frame,
            fg_color="#070913",
            border_width=1,
            border_color="#172554",
        )
        self.curiosity_pane.pack(
            side="right", fill="both", expand=True, padx=(5, 0), pady=5
        )

        self.curiosity_title_lbl = ctk.CTkLabel(
            self.curiosity_pane,
            text=ar("💡 محرك الفضول الفعال (Active Curiosity)"),
            font=("Tajawal", 12, "bold"),
            text_color="#38bdf8",
        )
        self.curiosity_title_lbl.pack(anchor="e", padx=10, pady=5)

        self.curiosity_desc_lbl = ctk.CTkLabel(
            self.curiosity_pane,
            text=ar(
                "اكتشاف المفاهيم المعزولة أو ضعيفة الترابط وتوليد أسئلة فضولية لمطالبة المستخدم بالتعليم وسد فجوات العقل."
            ),
            font=("Tajawal", 10),
            text_color="#94a3b8",
            wraplength=280,
            justify="right",
        )
        self.curiosity_desc_lbl.pack(anchor="e", padx=10, pady=(0, 10))

        self.curiosity_find_btn = ctk.CTkButton(
            self.curiosity_pane,
            text=ar("💡 رصد فجوات المعرفة وتوليد الأسئلة"),
            fg_color="#0ea5e9",
            text_color="#fff",
            hover_color="#0284c7",
            font=("Tajawal", 11, "bold"),
            command=self.run_active_curiosity_check,
        )
        self.curiosity_find_btn.pack(fill="x", padx=10, pady=5)

        # إطار الأسئلة التفاعلي
        self.curiosity_questions_frame = ctk.CTkScrollableFrame(
            self.curiosity_pane,
            fg_color="#020617",
            border_width=1,
            border_color="#172554",
        )
        self.curiosity_questions_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.no_questions_lbl = ctk.CTkLabel(
            self.curiosity_questions_frame,
            text=ar(
                "اضغط على الزر بالأعلى للبحث عن ثغرات المعرفة وتوليد أسئلة تفاعلية."
            ),
            font=("Tajawal", 10),
            text_color="#64748b",
            wraplength=220,
        )
        self.no_questions_lbl.pack(pady=40)

    def set_api_defaults(self, provider_id):
        key_info = DEFAULT_KEYS[provider_id]
        self.key_entry.delete(0, "end")
        self.key_entry.insert(0, key_info["key"])
        self.model_select.configure(values=key_info["models"])
        self.model_select.set(key_info["models"][0])

    def on_provider_change(self, choice):
        p_id = "google"
        if "Groq" in choice:
            p_id = "groq"
        elif "OpenRouter" in choice:
            p_id = "openrouter"

        self.set_api_defaults(p_id)
        self.add_log(f"تم الانتقال إلى مزود الخدمة: {choice}", "info")

    def refresh_rules_display(self):
        try:
            conn = sqlite3.connect(self.prototype.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT rule_name, antecedents, consequent, confidence FROM rules WHERE is_active = 1"
            )
            rows = cursor.fetchall()
            conn.close()

            self.rules_result_textbox.configure(state="normal")
            self.rules_result_textbox.delete("1.0", "end")

            if not rows:
                self.rules_result_textbox.insert(
                    "1.0",
                    ar("لا توجد قواعد مستحثة نشطة حالياً. اضغط على زر الاستحثاث للبدء!"),
                )
            else:
                self.rules_result_textbox.insert(
                    "1.0", ar("📜 القواعد المنطقية النشطة في العقل المعرفي:\n\n")
                )
                for name, ant_json, cons_json, conf in rows:
                    try:
                        ants = json.loads(ant_json)
                        cons = json.loads(cons_json)

                        # تنسيق جميل ومقروء
                        ant_str = " ∧ ".join([f"({x}, {p}, {y})" for x, p, y in ants])
                        cons_str = f"({cons[0]}, {cons[1]}, {cons[2]})"

                        self.rules_result_textbox.insert(
                            "end",
                            f"• {name} (الثقة: {conf * 100:.1f}%):\n  {ant_str} ➔ {cons_str}\n\n",
                        )
                    except Exception as e:
                        self.rules_result_textbox.insert(
                            "end", f"• {name}: {ant_json} ➔ {cons_json} ({conf})\n\n"
                        )
            self.rules_result_textbox.configure(state="disabled")
        except Exception as e:
            print(f"⚠️ فشل تحديث شاشة القواعد: {e}")

    def on_run_rule_induction_click(self):
        self.add_log("جاري البحث عن أنماط وحث قواعد منطقية جديدة...", "process")
        logs = []
        new_rules = self.prototype.self_improve_rule_induction(logs)
        for log in logs:
            self.add_log(log, "info")

        self.refresh_rules_display()
        self.add_log("اكتملت عملية حث القواعد المنطقية بنجاح!", "success")

    def on_run_pln_click(self):
        concept_a = (
            self.pln_concept_a_entry._entry.get().strip()
            if hasattr(self.pln_concept_a_entry, "_entry")
            else self.pln_concept_a_entry.get().strip()
        )
        concept_b = (
            self.pln_concept_b_entry._entry.get().strip()
            if hasattr(self.pln_concept_b_entry, "_entry")
            else self.pln_concept_b_entry.get().strip()
        )

        if not concept_a or not concept_b:
            from tkinter import messagebox

            messagebox.showwarning(
                ar("تنبيه"), ar("يرجى إدخال اسم الكيان أ والكيان ب للبدء!")
            )
            return

        self.add_log(
            f"تشغيل الاستدلال الاحتمالي PLN بين '{concept_a}' و '{concept_b}'...",
            "process",
        )
        logs = []
        result = self.prototype.run_probabilistic_inference(concept_a, concept_b, logs)
        for log in logs:
            self.add_log(log, "info")

        self.pln_result_textbox.configure(state="normal")
        self.pln_result_textbox.delete("1.0", "end")
        self.pln_result_textbox.insert("1.0", ar(result))
        self.pln_result_textbox.configure(state="disabled")

    def toggle_sandbox_mode(self):
        if not self.prototype.in_sandbox:
            self.prototype.start_sandbox()
            self.sandbox_status_lbl.configure(
                text=ar(
                    "🪐 بيئة الرمل الافتراضية: 🟡 نشطة (كافة التلقينات والتعديلات مؤقتة وافتراضية فقط)"
                ),
                text_color="#f59e0b",
            )
            self.top_bar.configure(border_color="#f59e0b")
            self.status_indicator.configure(
                text=ar("🟡 وضع العوالم البديلة"), text_color="#f59e0b"
            )
            self.sandbox_toggle_btn.configure(
                text=ar("تعطيل بيئة الرمل"), state="disabled"
            )
            self.sandbox_commit_btn.configure(state="normal")
            self.sandbox_rollback_btn.configure(state="normal")
            self.add_log(
                "🪐 تم تنشيط بيئة الرمل بنجاح! جرب تلقين أي مفاهيم أو افتراضات دون الخوف على البيانات الأصلية.",
                "warning",
            )
        else:
            self.add_log(
                "⚠️ بيئة الرمل نشطة بالفعل. يرجى استخدام Commit أو Rollback للإغلاق.",
                "error",
            )

    def commit_sandbox_changes(self):
        if self.prototype.in_sandbox:
            self.prototype.commit_sandbox()
            self.sandbox_status_lbl.configure(
                text=ar(
                    "🪐 بيئة الرمل الافتراضية: ❌ غير نشطة (تعديلاتك مباشرة على قاعدة المعرفة الحقيقية)"
                ),
                text_color="#94a3b8",
            )
            self.top_bar.configure(border_color="#00f0ff")
            self.status_indicator.configure(
                text=ar("🟢 جاهز للعمل"), text_color="#39ff14"
            )
            self.sandbox_toggle_btn.configure(
                text=ar("🪐 تفعيل وضع الرمل (What-If)"), state="normal"
            )
            self.sandbox_commit_btn.configure(state="disabled")
            self.sandbox_rollback_btn.configure(state="disabled")

            # إعادة بناء العرض
            self.sync_graph_to_physics()
            self.relation_current_page = 1
            self.refresh_relations_list()

            self.add_log(
                "💾 تم حفظ واعتماد كافة الفرضيات والتغييرات بنجاح في قاعدة البيانات الحقيقية!",
                "success",
            )

    def rollback_sandbox_changes(self):
        if self.prototype.in_sandbox:
            self.prototype.rollback_sandbox()
            self.sandbox_status_lbl.configure(
                text=ar(
                    "🪐 بيئة الرمل الافتراضية: ❌ غير نشطة (تعديلاتك مباشرة على قاعدة المعرفة الحقيقية)"
                ),
                text_color="#94a3b8",
            )
            self.top_bar.configure(border_color="#00f0ff")
            self.status_indicator.configure(
                text=ar("🟢 جاهز للعمل"), text_color="#39ff14"
            )
            self.sandbox_toggle_btn.configure(
                text=ar("🪐 تفعيل وضع الرمل (What-If)"), state="normal"
            )
            self.sandbox_commit_btn.configure(state="disabled")
            self.sandbox_rollback_btn.configure(state="disabled")

            # إعادة بناء العرض
            self.sync_graph_to_physics()
            self.relation_current_page = 1
            self.refresh_relations_list()

            self.add_log(
                "🔄 تم التراجع التام وإلغاء كافة التغييرات والافتراضات التي تمت في بيئة الرمل المعزولة بنجاح.",
                "info",
            )

    def run_cognitive_sleep_cycle(self):
        """تشغيل دورة الاسترخاء والنوم المعرفي على الرسم المعرفي"""
        self.sleep_log_box.configure(state="normal")
        self.sleep_log_box.delete("1.0", "end")
        self.sleep_log_box.insert(
            "end", ar("🌙 بدء دورة النوم المعرفي وتصفية الضوضاء...\n")
        )
        self.sleep_log_box.insert(
            "end", ar("========================================\n")
        )

        logs = []
        graph = (
            self.prototype.sandbox_graph
            if self.prototype.in_sandbox
            else self.prototype.graph
        )

        # 1. تقوية الروابط المشتركة (Co-occurrence Strengthening)
        strengthened = 0
        nodes = list(graph.nodes)
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                node_a = nodes[i]
                node_b = nodes[j]

                # إيجاد الجيران المشتركين (Shared Neighbors)
                a_neighbors = (
                    set(graph.neighbors(node_a)) if graph.has_node(node_a) else set()
                )
                b_neighbors = (
                    set(graph.neighbors(node_b)) if graph.has_node(node_b) else set()
                )
                shared = a_neighbors.intersection(b_neighbors)

                if len(shared) >= 2:
                    # إذا كانت هناك علاقة مباشرة، نقوي ثقتها
                    if graph.has_edge(node_a, node_b):
                        curr_conf = graph[node_a][node_b].get("confidence", 1.0)
                        if curr_conf < 1.0:
                            new_conf = min(1.0, curr_conf + 0.15)
                            graph[node_a][node_b]["confidence"] = new_conf
                            strengthened += 1
                            # حفظ التحديث في قاعدة البيانات
                            relation = graph[node_a][node_b].get(
                                "relation", "relatedTo"
                            )
                            self.prototype.save_triple_to_db(
                                node_a, relation, node_b, confidence=new_conf
                            )

        if strengthened > 0:
            logs.append(
                f"💪 تم تقوية {strengthened} رابطة دلالية بناءً على الترابط المعرفي المشترك."
            )
        else:
            logs.append("💪 لم يتم العثور على روابط بحاجة لتقوية إضافية حالياً.")

        # 2. تقليم العلاقات الضعيفة جداً (Pruning weak edges)
        pruned = 0
        edges_to_prune = []
        for u, v, data in list(graph.edges(data=True)):
            conf = data.get("confidence", 1.0)
            relation = data.get("relation", "")
            # لا نقلم العلاقات الفئوية الأساسية (is_a)
            if conf < 0.35 and relation != "is_a":
                # حماية العقد من العزل الكامل
                if graph.degree(u) > 1 and graph.degree(v) > 1:
                    edges_to_prune.append((u, v))

        for u, v in edges_to_prune:
            if graph.has_edge(u, v):
                graph.remove_edge(u, v)
                pruned += 1
                # حذف من قاعدة البيانات
                try:
                    conn = sqlite3.connect(self.prototype.db_path)
                    cursor = conn.cursor()
                    cursor.execute(
                        "DELETE FROM triples WHERE subject=? AND object=?", (u, v)
                    )
                    conn.commit()
                    conn.close()
                except Exception:
                    pass

        if pruned > 0:
            logs.append(
                f"✂️ تم تقليم وحذف {pruned} رابطة ضعيفة (ثقة أقل من 0.35) لحماية الذاكرة من التشتت."
            )
        else:
            logs.append("✂️ جميع الروابط الحالية متماسكة وذات ثقة مقبولة.")

        # 3. أحلام اليقظة المعرفية (Dream Walks)
        import random

        dreams = 0
        logs.append("💭 بدء مرحلة أحلام اليقظة لاستكشاف الروابط الدلالية الخفية...")
        all_nodes = list(graph.nodes)
        if len(all_nodes) >= 4:
            for _ in range(15):
                start_node = random.choice(all_nodes)
                # عمل مسار عشوائي بطول 3
                path = [start_node]
                curr = start_node
                for _ in range(3):
                    neighbors = (
                        list(graph.neighbors(curr)) if graph.has_node(curr) else []
                    )
                    if not neighbors:
                        break
                    next_node = random.choice(neighbors)
                    if next_node in path:
                        break
                    path.append(next_node)
                    curr = next_node

                if len(path) >= 3:
                    n_start = path[0]
                    n_end = path[-1]
                    # إذا كان البداية والنهاية يشتركان في خاصية ولا توجد بينهما علاقة مباشرة
                    start_rels = {
                        data.get("relation")
                        for _, _, data in graph.out_edges(n_start, data=True)
                    }
                    end_rels = {
                        data.get("relation")
                        for _, _, data in graph.out_edges(n_end, data=True)
                    }
                    shared_rels = start_rels.intersection(end_rels)
                    # استبعاد علاقات عامة جداً
                    shared_rels.discard("is_a")

                    if shared_rels and not graph.has_edge(n_start, n_end):
                        shared_r = list(shared_rels)[0]
                        logs.append(
                            f"   💭 حلم: قد يكون هناك رابط خفي بين [{n_start}] و [{n_end}] لأنهما يشتركان في العلاقة '{shared_r}'!"
                        )
                        dreams += 1

        if dreams == 0:
            logs.append("💭 لم تسفر أحلام اليقظة عن اكتشاف روابط خفية جديدة هذه المرة.")

        # 4. تشغيل محرك الاستنتاج التكراري (v2 forward chaining)
        logs.append("🧠 تشغيل محرك الاستنتاج التكراري v2 لتثبيت المعرفة المستنبطة...")
        inferred = self.prototype.run_transitive_reasoning(logs)

        # 5. التحديث والعرض
        for log in logs:
            self.sleep_log_box.insert("end", ar(log) + "\n")

        self.sleep_log_box.insert(
            "end", ar("========================================\n")
        )
        self.sleep_log_box.insert(
            "end",
            ar(
                f"✅ انتهت دورة النوم المعرفي بنجاح! تم استنتاج {len(inferred)} حقيقة جديدة.\n"
            ),
        )
        self.sleep_log_box.configure(state="disabled")

        # تحديث الرسم البياني المرئي وقائمة العلاقات
        self.sync_graph_to_physics()
        self.relation_current_page = 1
        self.refresh_relations_list()

        self.add_log("اكتملت دورة النوم المعرفي والتحصين بنجاح دلالي رائع!", "success")

    def run_active_curiosity_check(self):
        """اكتشاف فجوات المعرفة وتوليد الأسئلة النشطة لمطالبة المستخدم بالتعليم"""
        # تنظيف الإطار
        for widget in self.curiosity_questions_frame.winfo_children():
            widget.destroy()

        graph = (
            self.prototype.sandbox_graph
            if self.prototype.in_sandbox
            else self.prototype.graph
        )

        # إيجاد العقد ضعيفة الترابط (درجة الاتصال <= 1)
        weak_nodes = []
        for node in graph.nodes:
            # استبعاد عقد العلاقات أو العقد الوصفية الخاصة
            if node.startswith("event_") or node.startswith("ST_") or len(node) < 2:
                continue
            deg = graph.degree(node)
            if deg <= 1:
                weak_nodes.append((node, deg))

        if not weak_nodes:
            no_gaps_lbl = ctk.CTkLabel(
                self.curiosity_questions_frame,
                text=ar(
                    "🎉 ممتاز! عقلك المعرفي متكامل تماماً ولا توجد به فجوات أو كيانات معزولة حالياً."
                ),
                font=("Tajawal", 11, "bold"),
                text_color="#10b981",
                wraplength=220,
            )
            no_gaps_lbl.pack(pady=40)
            return

        # توليد أسئلة فضولية
        questions = []
        for node, deg in weak_nodes:
            node_data = graph.nodes[node]
            # فحص نوع الفجوة
            # 1. هل تفتقر للتصنيف (super_type / is_a)؟
            has_taxonomy = bool(node_data.get("super_type"))
            if not has_taxonomy:
                for _, _, data in graph.out_edges(node, data=True):
                    if data.get("relation") == "is_a":
                        has_taxonomy = True
                        break

            if not has_taxonomy:
                questions.append(
                    {
                        "question": f"ما هو '{node}'؟ هل هو نوع من أنواع الحيوانات أم الجماد أم فئة أخرى؟",
                        "text_to_paste": f"{node} هو نوع من ",
                    }
                )

            # 2. فحص الخصائص (properties)
            has_properties = bool(node_data.get("properties"))
            if not has_properties:
                questions.append(
                    {
                        "question": f"ما هي صفات وخصائص '{node}' المميزة له؟",
                        "text_to_paste": f"صفة {node} هي ",
                    }
                )

            # 3. سؤال عام
            questions.append(
                {
                    "question": f"ما هي علاقة '{node}' بالكيانات الأخرى؟ أين يعيش أو ماذا يفعل؟",
                    "text_to_paste": f"{node} يعيش في ",
                }
            )

        # عرض الأسئلة
        import random

        random.shuffle(questions)
        selected_questions = questions[:6]

        for q in selected_questions:
            q_frame = ctk.CTkFrame(
                self.curiosity_questions_frame,
                fg_color="#070913",
                border_width=1,
                border_color="#1e293b",
                corner_radius=6,
            )
            q_frame.pack(fill="x", padx=5, pady=4)

            lbl = ctk.CTkLabel(
                q_frame,
                text=ar(q["question"]),
                font=("Tajawal", 10),
                text_color="#e2e8f0",
                wraplength=200,
                justify="right",
            )
            lbl.pack(fill="x", padx=10, pady=5)

            # زر النقر للاجابة
            paste_txt = q["text_to_paste"]
            btn = ctk.CTkButton(
                q_frame,
                text=ar("✍️ إجابة وسد الفجوة"),
                fg_color="#0f172a",
                text_color="#38bdf8",
                hover_color="#1e293b",
                font=("Tajawal", 9, "bold"),
                height=18,
                command=lambda pt=paste_txt: self.click_curiosity_question(pt),
            )
            btn.pack(pady=(0, 5))

        self.add_log(
            f"تم رصد {len(weak_nodes)} فجوة معرفية وتوليد أسئلة فضولية نشطة للتفاعل معها!",
            "info",
        )

    def click_curiosity_question(self, text_to_paste):
        """لصق بداية الإجابة في صندوق الإدخال وتركيز المؤشر عليه ليجيب المستخدم مباشرة"""
        self.prompt_entry.delete(0, "end")
        self.prompt_entry.insert(0, text_to_paste)
        self.prompt_entry.focus()
        self.add_log(
            ar(
                f"تم نسخ قالب الإجابة: '{text_to_paste}'. يمكنك إكمال الجملة الآن لتعليم النظام!"
            ),
            "info",
        )

    def on_workspace_change(self, choice):
        # تحديد اسم قاعدة البيانات المناسبة للمساحة المختارة من القاموس الديناميكي
        ws_info = self.workspaces.get(choice)
        if isinstance(ws_info, str):
            db_name = ws_info
            mode = "active"
        else:
            db_name = ws_info.get("db_filename", "ontology.db")
            mode = ws_info.get("mode", "active")

        self.current_workspace_mode = mode
        self.prototype.strict_mode = mode == "strict"

        new_db_path = os.path.join(os.path.dirname(self.prototype.db_path), db_name)
        self.add_log(f"جاري الانتقال إلى مساحة عمل: {choice}...", "process")

        # حفظ المسار الجديد والتحميل
        self.prototype.db_path = new_db_path
        self.prototype.init_database()
        self.prototype.load_graph_from_db()

        # إعادة مزامنة الكانفاس وقائمة الروابط والإحصائيات
        self.sync_graph_to_physics()
        self.relation_current_page = 1
        self.refresh_relations_list()
        self.refresh_rules_display()

        # تحديث أزرار وتنبيهات تبويب النوم والفضول بناءً على الوضع
        if mode == "strict":
            self.sleep_run_btn.configure(
                state="disabled", text=ar("🔒 معطل (وضع الحقائق الثابتة الصارم)")
            )
            self.sleep_log_box.configure(state="normal")
            self.sleep_log_box.delete("1.0", "end")
            self.sleep_log_box.insert(
                "1.0",
                ar(
                    "🔒 تم تعطيل دورة النوم والتحصين بالكامل في هذه المساحة.\nهذه المساحة مخصصة للحقائق المدخلة يدوياً بنسبة 100% دون أي احتمالات أو استدلال تلقائي."
                ),
            )
            self.sleep_log_box.configure(state="disabled")

            self.curiosity_find_btn.configure(
                state="disabled", text=ar("🔒 معطل (وضع الحقائق الثابتة)")
            )
            for widget in self.curiosity_questions_frame.winfo_children():
                widget.destroy()
            no_gaps_lbl = ctk.CTkLabel(
                self.curiosity_questions_frame,
                text=ar(
                    "🔒 محرك الفضول معطل لضمان ثبات المعرفة بنسبة 100% دون استدلال أو اقتراح فجوات دلالية."
                ),
                font=("Tajawal", 10),
                text_color="#94a3b8",
                wraplength=220,
            )
            no_gaps_lbl.pack(pady=40)
        else:
            self.sleep_run_btn.configure(
                state="normal", text=ar("💤 تشغيل دورة الاسترخاء والنوم المعرفي")
            )
            self.sleep_log_box.configure(state="normal")
            self.sleep_log_box.delete("1.0", "end")
            self.sleep_log_box.insert(
                "1.0",
                ar(
                    "سجل دورة النوم خالي حالياً. اضغط على الزر بالأعلى لبدء النوم والتحصين..."
                ),
            )
            self.sleep_log_box.configure(state="disabled")

            self.curiosity_find_btn.configure(
                state="normal", text=ar("💡 رصد فجوات المعرفة وتوليد الأسئلة")
            )
            for widget in self.curiosity_questions_frame.winfo_children():
                widget.destroy()
            no_gaps_lbl = ctk.CTkLabel(
                self.curiosity_questions_frame,
                text=ar(
                    "اضغط على الزر بالأعلى للبحث عن ثغرات المعرفة وتوليد أسئلة تفاعلية."
                ),
                font=("Tajawal", 10),
                text_color="#64748b",
                wraplength=220,
            )
            no_gaps_lbl.pack(pady=40)

        if getattr(self, "show_stats", False):
            self.build_or_update_stats_view()

        mode_text = "النشط المساهم" if mode == "active" else "الحقائق الثابتة الصارم"
        self.add_log(
            f"تم بنجاح فتح مساحة العمل المعرفية: {choice} (نمط: {mode_text}) وقاعدة بيانات {db_name} نشطة الآن.",
            "success",
        )

    def add_workspace(self):
        """إضافة مساحة عمل دلالية جديدة وحفظها"""
        from tkinter import messagebox

        dialog = WorkspaceDialog(self)
        self.wait_window(dialog)

        name = dialog.result_name
        mode = dialog.result_mode

        if not name:
            return

        if name in self.workspaces:
            messagebox.showwarning(ar("تنبيه"), ar("مساحة العمل هذه موجودة بالفعل!"))
            return

        # توليد اسم ملف قاعدة بيانات آمن
        import uuid

        safe_db_name = f"ontology_{uuid.uuid4().hex[:8]}.db"

        # حفظ مساحة العمل الجديدة بمعلوماتها الكاملة والنمط المختار
        self.workspaces[name] = {"db_filename": safe_db_name, "mode": mode}
        self.save_workspaces()

        # تحديث قائمة الخيارات المنسدلة
        self.workspace_selector.configure(values=list(self.workspaces.keys()))
        self.workspace_selector.set(name)

        # الانتقال للمساحة الجديدة تلقائياً
        self.on_workspace_change(name)

        mode_text = "النشط المساهم" if mode == "active" else "الحقائق الثابتة الصارم"
        self.add_log(
            f"تم إنشاء مساحة عمل جديدة بنجاح: {name} (نمط: {mode_text})", "success"
        )
        messagebox.showinfo(
            ar("تم الإنشاء"),
            ar(
                f"تم إنشاء مساحة العمل '{name}' بنجاح وهي نشطة الآن بالنمط {mode_text}!"
            ),
        )

    def delete_workspace(self):
        """حذف مساحة العمل المعرفية النشطة الحالية"""
        from tkinter import messagebox

        current_name = self.workspace_selector.get()

        if current_name == ar("العقل العام (الافتراضي)"):
            messagebox.showwarning(
                ar("غير مسموح"), ar("لا يمكن حذف مساحة العمل الافتراضية الرئيسية!")
            )
            return

        if current_name not in self.workspaces:
            return

        if not messagebox.askyesno(
            ar("تأكيد الحذف"),
            ar(
                f"هل أنت متأكد تماماً من رغبتك في حذف مساحة العمل '{current_name}' وكل محتوياتها من القرص نهائياً؟"
            ),
        ):
            return

        # مسح ملف قاعدة البيانات من القرص
        ws_info = self.workspaces[current_name]
        db_filename = (
            ws_info
            if isinstance(ws_info, str)
            else ws_info.get("db_filename", "ontology.db")
        )
        db_path = os.path.join(os.path.dirname(self.prototype.db_path), db_filename)

        # إزالة مساحة العمل
        del self.workspaces[current_name]
        self.save_workspaces()

        try:
            if os.path.exists(db_path):
                os.remove(db_path)
                self.add_log(
                    f"تم حذف ملف قاعدة البيانات {db_filename} من القرص.", "info"
                )
        except Exception as e:
            self.add_log(f"فشل حذف ملف قاعدة البيانات: {e}", "warn")

        # تحديث الخيارات المنسدلة والعودة للمساحة الافتراضية
        default_name = ar("العقل العام (الافتراضي)")
        self.workspace_selector.configure(values=list(self.workspaces.keys()))
        self.workspace_selector.set(default_name)
        self.on_workspace_change(default_name)

        self.add_log(f"تم حذف مساحة العمل '{current_name}' بنجاح.", "success")
        messagebox.showinfo(
            ar("تم الحذف"),
            ar(f"تم حذف مساحة العمل '{current_name}' والعودة للمساحة الافتراضية."),
        )

    def set_mode(self, mode):
        self.active_mode = mode

        # إعادة تعيين ألوان الأزرار لتبدو تفاعلية
        self.mode_btn_chat.configure(
            fg_color="#070913" if mode != "chat" else "#bd00ff",
            text_color="#94a3b8" if mode != "chat" else "#fff",
        )
        self.mode_btn_teach.configure(
            fg_color="#070913" if mode != "teach" else "#39ff14",
            text_color="#94a3b8" if mode != "teach" else "#05070f",
        )
        self.mode_btn_db.configure(
            fg_color="#070913" if mode != "db_only" else "#ff007a",
            text_color="#94a3b8" if mode != "db_only" else "#fff",
        )

        if mode == "chat":
            self.input_title.configure(
                text=ar("✨ أدخل جملة تفاعلية للدردشة وفك العلاقات منطقياً")
            )
        elif mode == "teach":
            self.input_title.configure(
                text=ar("🧠 أدخل حقيقة أو علاقة جديدة ليحفظها النظام بذاكرته الدائمة")
            )
        else:
            self.input_title.configure(
                text=ar("🔎 أدخل سؤالاً للاستنباط الدلالي من قاعدة البيانات والشبكة فقط")
            )

        self.add_log(f"تم تبديل النمط الدلالي إلى: {mode}", "info")

    def add_log(self, text, log_type="info"):
        now = time.strftime("%H:%M:%S")
        prefix = f"[{now}] "
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"{prefix}{ar(text)}\n")
        self.log_box.configure(state="disabled")
        self.log_box.see("end")

    def clear_logs(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        self.add_log(
            "تم تنظيف شاشة الرصد بنجاح. شاشة رصد LEGEND فارغة وجاهزة للرصد الجديد.",
            "success",
        )

    def update_loop(self):
        # تشغيل حلقة الفيزياء المستمرة بـ 60 FPS فقط عند عرض الشبكة البصرية
        if not getattr(self, "show_stats", False):
            self.physics.update_physics()
            self.physics.draw()

        # تحديث عداد التفكير
        if self.thinking:
            elapsed = time.time() - self.timer_start
            self.timer_lbl.configure(
                text=ar(f"⏱️ سرعة المعالجة: {elapsed:.2f} ثانية (جاري التفكير...)")
            )

        self.after(16, self.update_loop)

    def get_filtered_relations(self):
        """تصفية وفلترة الروابط بناءً على الفلتر المختار وكلمة البحث"""
        filter_mode = self.relation_filter_var.get()
        if filter_mode == "last":
            relations = getattr(self.prototype, "last_relations", [])
        else:
            relations = self.prototype.get_all_triples()

        search_query = self.relation_search_var.get().strip().lower()
        if not search_query:
            return relations

        filtered = []
        for triple in relations:
            if len(triple) < 3:
                continue
            subj, pred, obj = triple
            # البحث بشكل مرن غير حساس لحالة الأحرف
            if (
                search_query in str(subj).lower()
                or search_query in str(pred).lower()
                or search_query in str(obj).lower()
            ):
                filtered.append(triple)
        return filtered

    def refresh_relations_list(self):
        """تنظيف وتحديث قائمة الروابط في الواجهة التفاعلية بناءً على الفلتر، البحث، والصفحة الحالية"""
        import math

        # تنظيف العناصر القديمة
        for widget in self.relations_scroll.winfo_children():
            widget.destroy()

        filtered_relations = self.get_filtered_relations()
        total_items = len(filtered_relations)

        # تحديث رقم الصفحة الإجمالي والبيانات
        items_per_page = getattr(self, "relation_items_per_page", 10)
        total_pages = max(1, math.ceil(total_items / items_per_page))

        if getattr(self, "relation_current_page", 1) > total_pages:
            self.relation_current_page = total_pages

        # تحديث نصوص واجهة التصفح
        self.page_info_lbl.configure(
            text=ar(f"الصفحة {self.relation_current_page} من {total_pages}")
        )
        self.total_relations_lbl.configure(text=ar(f"إجمالي الروابط: {total_items}"))

        # تفعيل وتعطيل أزرار التصفح بناءً على رقم الصفحة
        self.prev_page_btn.configure(
            state="normal" if self.relation_current_page > 1 else "disabled"
        )
        self.next_page_btn.configure(
            state="normal" if self.relation_current_page < total_pages else "disabled"
        )

        if not filtered_relations:
            no_rel_lbl = ctk.CTkLabel(
                self.relations_scroll,
                text=ar("⚠️ لا توجد روابط لعرضها حالياً في هذا النطاق."),
                font=("Tajawal", 11, "italic"),
                text_color="#94a3b8",
            )
            no_rel_lbl.pack(pady=20)
            return

        # استقطاع العلاقات الخاصة بالصفحة الحالية
        start_idx = (self.relation_current_page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        relations_to_show = filtered_relations[start_idx:end_idx]

        # إدراج كل علاقة كسطر تفاعلي جذاب
        for triple in relations_to_show:
            if len(triple) < 3:
                continue
            subj, pred, obj = triple[0], triple[1], triple[2]
            valid_from = triple[3] if len(triple) > 3 else None
            valid_to = triple[4] if len(triple) > 4 else None

            row = ctk.CTkFrame(
                self.relations_scroll,
                fg_color="#070913",
                border_width=1,
                border_color="#1e293b",
            )
            row.pack(fill="x", padx=5, pady=3)

            # عرض المفهوم والعلاقة باللغة العربية الفصيحة بصرياً
            text_repr = f"({subj} ➔ {pred} ➔ {obj})"
            if valid_from and valid_to:
                text_repr += f" [🕒 {valid_from} - {valid_to}]"
            elif valid_from:
                text_repr += f" [🕒 منذ {valid_from}]"
            elif valid_to:
                text_repr += f" [🕒 حتى {valid_to}]"

            lbl = ctk.CTkLabel(
                row,
                text=ar(text_repr),
                font=("Tajawal", 11, "bold"),
                text_color="#39ff14",  # لون أخضر نيون ناصع للروابط النشطة
            )
            lbl.pack(side="left", padx=10, pady=5)

            # زر الحذف الفردي الفوري
            del_btn = ctk.CTkButton(
                row,
                text="❌",
                width=24,
                height=24,
                fg_color="#e11d48",
                hover_color="#be123c",
                text_color="#fff",
                font=("Tajawal", 9, "bold"),
                command=lambda s=subj, p=pred, o=obj: self.delete_single_relation(
                    s, p, o
                ),
            )
            del_btn.pack(side="right", padx=10, pady=5)

    def reset_relations_page_and_refresh(self):
        self.relation_current_page = 1
        self.refresh_relations_list()

    def on_relation_search_change(self, *args):
        self.relation_current_page = 1
        self.refresh_relations_list()

    def prev_relations_page(self):
        if self.relation_current_page > 1:
            self.relation_current_page -= 1
            self.refresh_relations_list()

    def next_relations_page(self):
        import math

        filtered_relations = self.get_filtered_relations()
        total_items = len(filtered_relations)
        items_per_page = getattr(self, "relation_items_per_page", 10)
        total_pages = max(1, math.ceil(total_items / items_per_page))

        if self.relation_current_page < total_pages:
            self.relation_current_page += 1
            self.refresh_relations_list()

    def delete_single_relation(self, subj, pred, obj):
        """حذف علاقة منفردة من قاعدة البيانات، شبكة الرام والكانفاس فوراً"""
        success = self.prototype.delete_triple(subj, pred, obj)
        if success:
            # تحديث علاقات آخر رد إذا تواجدت بها
            if hasattr(self.prototype, "last_relations"):
                self.prototype.last_relations = [
                    t
                    for t in self.prototype.last_relations
                    if not (t[0] == subj and t[1] == pred and t[2] == obj)
                ]

            self.add_log(
                f"تم حذف الرابط دلالياً وفيزيائياً: ({subj} ➔ {pred} ➔ {obj})", "success"
            )
            self.refresh_relations_list()
            self.sync_graph_to_physics()
            if getattr(self, "show_stats", False):
                self.build_or_update_stats_view()

    def delete_all_visible_relations(self):
        """حذف شامل لكافة العلاقات المعروضة حالياً حسب الفلتر المختار وكلمة البحث"""
        relations = self.get_filtered_relations()
        if not relations:
            return

        from tkinter import messagebox

        if not messagebox.askyesno(
            ar("حذف جماعي"),
            ar(f"هل أنت متأكد من حذف {len(relations)} رابط دلالي معروض حالياً؟"),
        ):
            return

        deleted_count = 0
        for triple in relations:
            if len(triple) < 3:
                continue
            subj, pred, obj = triple
            if self.prototype.delete_triple(subj, pred, obj):
                # إزالة من روابط آخر رد إن وجدت
                if hasattr(self.prototype, "last_relations"):
                    self.prototype.last_relations = [
                        t
                        for t in self.prototype.last_relations
                        if not (t[0] == subj and t[1] == pred and t[2] == obj)
                    ]
                deleted_count += 1

        self.add_log(
            f"تم بنجاح حذف {deleted_count} رابط معرفي دفعة واحدة من الأنتولوجيا والشبكة الفيزيائية.",
            "success",
        )

        # إعادة تعيين الصفحة الحالية لتجنب الخروج عن المدى
        self.relation_current_page = 1
        self.refresh_relations_list()
        self.sync_graph_to_physics()
        if getattr(self, "show_stats", False):
            self.build_or_update_stats_view()

    def sync_graph_to_physics(self):
        # مزامنة كلاس الفيزياء مع كائن الرسم البياني في الذاكرة
        self.physics.nodes.clear()
        self.physics.edges.clear()

        graph_to_use = (
            self.prototype.sandbox_graph
            if self.prototype.in_sandbox
            else self.prototype.graph
        )

        # إضافة العقد
        for node, data in graph_to_use.nodes(data=True):
            group = data.get("type", "concept")
            self.physics.add_node(node, group)

        # إضافة الحواف
        for u, v, data in graph_to_use.edges(data=True):
            self.physics.add_edge(u, v, data.get("relation", "علاقة"))

        # إيقاظ محاكي الفيزياء للتحديث بعد التغييرات التراكمية
        self.physics.is_stable = False
        self.physics.ticks_since_stable = 0

        # تحديث المقاييس
        self.nodes_lbl.configure(
            text=ar(f"عقد المعرفة (RAM): {graph_to_use.number_of_nodes()}")
        )
        self.edges_lbl.configure(
            text=ar(f"الروابط الدلالية: {graph_to_use.number_of_edges()}")
        )

    def change_layout_mode(self, value):
        if value == ar("متحرك فيزيائي"):
            self.physics.layout_mode = "physics"
        elif value == ar("دائري منظم"):
            self.physics.layout_mode = "circular"
        elif value == ar("تدرج هرمي"):
            self.physics.layout_mode = "tree"

        # إيقاظ محاكي الفيزياء والانتقال بسلاسة للعرض الجديد
        self.physics.is_stable = False
        self.physics.ticks_since_stable = 0

    def toggle_view(self):
        self.show_stats = not self.show_stats
        if self.show_stats:
            # إخفاء عناصر الشبكة البصرية
            self.canvas.pack_forget()
            self.layout_selector.pack_forget()
            self.refresh_btn.pack_forget()

            # بناء وعرض لوحة الإحصائيات
            self.build_or_update_stats_view()
            self.stats_frame.pack(fill="both", expand=True, padx=20, pady=(60, 20))

            # تحديث لون ونص زر التبديل
            self.view_toggle_btn.configure(
                text=ar("🕸️ عرض الشبكة البصرية"),
                fg_color="#bd00ff",
                hover_color="#ff007a",
            )
            self.add_log("تم تبديل العرض إلى إحصائيات المعرفة وقاعدة البيانات.", "info")
        else:
            # إخفاء لوحة الإحصائيات
            if hasattr(self, "stats_frame"):
                self.stats_frame.pack_forget()

            # إعادة إظهار عناصر الشبكة البصرية
            self.canvas.pack(fill="both", expand=True)

            # إعادة ترتيب الأزرار لتبسيط التخطيط
            self.refresh_btn.pack_forget()
            self.reset_btn.pack_forget()
            self.layout_selector.pack_forget()
            self.view_toggle_btn.pack_forget()

            self.refresh_btn.pack(side="left", padx=5)
            self.reset_btn.pack(side="left", padx=5)
            self.layout_selector.pack(side="left", padx=15)
            self.view_toggle_btn.pack(side="left", padx=5)

            # تحديث لون ونص زر التبديل
            self.view_toggle_btn.configure(
                text=ar("📊 إحصائيات المعرفة"),
                fg_color="#0984e3",
                hover_color="#00cec9",
            )

            # إيقاظ محاكي الفيزياء
            self.physics.is_stable = False
            self.physics.ticks_since_stable = 0
            self.add_log("تم إعادة تفعيل الشبكة الفيزيائية التفاعلية البصرية.", "info")

    def gather_db_statistics(self):
        """جمع وتحليل مقاييس وإحصاءات الأنتولوجيا من SQLite ورام الرسم البياني"""
        total_concepts = self.prototype.graph.number_of_nodes()
        try:
            conn = sqlite3.connect(self.prototype.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM concepts")
            total_concepts = cursor.fetchone()[0]
        except Exception:
            pass

        total_triples = 0
        try:
            cursor.execute("SELECT COUNT(*) FROM triples")
            total_triples = cursor.fetchone()[0]
        except Exception:
            pass

        total_instances = 0
        try:
            instances = [
                n
                for n, d in self.prototype.graph.nodes(data=True)
                if d.get("type") == "instance"
            ]
            total_instances = len(instances)
        except Exception:
            pass

        max_depth = 0
        try:
            is_a_graph = nx.DiGraph()
            for u, v, d in self.prototype.graph.edges(data=True):
                if d.get("relation") == "is_a":
                    is_a_graph.add_edge(u, v)
            if is_a_graph.number_of_nodes() > 0:
                max_depth = nx.dag_longest_path_length(is_a_graph)
        except Exception:
            pass

        db_size_kb = 0.0
        try:
            if os.path.exists(self.prototype.db_path):
                db_size_kb = round(os.path.getsize(self.prototype.db_path) / 1024, 2)
        except Exception:
            pass

        top_connected = []
        try:
            degrees = dict(self.prototype.graph.degree())
            top_connected = sorted(degrees.items(), key=lambda x: x[1], reverse=True)[
                :5
            ]
        except Exception:
            pass

        top_predicates = []
        try:
            cursor.execute(
                "SELECT predicate, COUNT(*) as c FROM triples GROUP BY predicate ORDER BY c DESC LIMIT 5"
            )
            top_predicates = cursor.fetchall()
            conn.close()
        except Exception:
            try:
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
            "top_predicates": top_predicates,
        }

    def build_or_update_stats_view(self):
        """إنشاء أو تحديث لوحة الإحصائيات المعرفية وتنسيق مظهرها المستقبلي"""
        if hasattr(self, "stats_frame") and self.stats_frame.winfo_exists():
            # إزالة كافة المكونات القديمة لتفادي التكرار والازدواجية
            for widget in self.stats_frame.winfo_children():
                widget.destroy()
        else:
            self.stats_frame = ctk.CTkScrollableFrame(
                self.canvas_frame, fg_color="#05070e", label_text=""
            )

        # جلب الإحصائيات الحالية
        stats = self.gather_db_statistics()

        # 1. العنوان الرئيسي
        title_lbl = ctk.CTkLabel(
            self.stats_frame,
            text=ar("📊 لوحة تحليلات وإحصاءات الأنتولوجيا المعرفية"),
            font=("Tajawal", 18, "bold"),
            text_color="#00f0ff",
        )
        title_lbl.pack(pady=(15, 20))

        # 2. كروت المؤشرات النيون المضيئة
        cards_frame = ctk.CTkFrame(self.stats_frame, fg_color="transparent")
        cards_frame.pack(fill="x", padx=10, pady=(0, 20))
        cards_frame.grid_columnconfigure((0, 1, 2, 3, 4), weight=1, uniform="equal")

        def create_stat_card(
            parent, col, title, value, unit="", color="#00f0ff", border_color="#054552"
        ):
            card = ctk.CTkFrame(
                parent, fg_color="#070913", border_width=1, border_color=border_color
            )
            card.grid(row=0, column=col, padx=4, pady=5, sticky="nsew")

            t_lbl = ctk.CTkLabel(
                card, text=ar(title), font=("Tajawal", 10, "bold"), text_color="#94a3b8"
            )
            t_lbl.pack(pady=(10, 2))

            v_lbl = ctk.CTkLabel(
                card,
                text=f"{value} {ar(unit)}".strip(),
                font=("Inter", 22, "bold"),
                text_color=color,
            )
            v_lbl.pack(pady=(0, 10))
            return card

        create_stat_card(
            cards_frame,
            0,
            "المفاهيم الكلية",
            stats["total_concepts"],
            "",
            "#39ff14",
            "#054552",
        )
        create_stat_card(
            cards_frame,
            1,
            "العلاقات والروابط",
            stats["total_triples"],
            "",
            "#bd00ff",
            "#054552",
        )
        create_stat_card(
            cards_frame,
            2,
            "الكيانات الفردية",
            stats["total_instances"],
            "",
            "#00f0ff",
            "#054552",
        )
        create_stat_card(
            cards_frame,
            3,
            "عمق شجرة النسب",
            stats["max_depth"],
            "",
            "#ff007a",
            "#054552",
        )
        create_stat_card(
            cards_frame,
            4,
            "حجم قاعدة البيانات",
            stats["db_size_kb"],
            "كيلوبايت",
            "#ff9f43",
            "#054552",
        )

        # 3. التحليلات التفصيلية الجانبية
        details_frame = ctk.CTkFrame(self.stats_frame, fg_color="transparent")
        details_frame.pack(fill="both", expand=True, padx=10, pady=10)
        details_frame.grid_columnconfigure((0, 1), weight=1, uniform="equal")

        # أ) العلاقات الأكثر تكراراً (الجانب الأيمن)
        pred_card = ctk.CTkFrame(
            details_frame, fg_color="#0a0d1e", border_width=1, border_color="#054552"
        )
        pred_card.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")

        pred_title = ctk.CTkLabel(
            pred_card,
            text=ar("🕸️ توزيع العلاقات الأكثر تكراراً"),
            font=("Tajawal", 13, "bold"),
            text_color="#00f0ff",
        )
        pred_title.pack(pady=10, padx=15, anchor="e")

        if not stats["top_predicates"]:
            no_pred = ctk.CTkLabel(
                pred_card,
                text=ar("لا توجد علاقات مسجلة حالياً."),
                font=("Tajawal", 11, "italic"),
                text_color="#94a3b8",
            )
            no_pred.pack(pady=35)
        else:
            max_p_count = (
                max([item[1] for item in stats["top_predicates"]])
                if stats["top_predicates"]
                else 1
            )
            for pred, count in stats["top_predicates"]:
                row_f = ctk.CTkFrame(pred_card, fg_color="transparent")
                row_f.pack(fill="x", padx=15, pady=6)

                # النص والعدد
                lbl = ctk.CTkLabel(
                    row_f,
                    text=ar(f"{pred} ({count})"),
                    font=("Tajawal", 11, "bold"),
                    text_color="#fff",
                )
                lbl.pack(side="right")

                # شريط النسبة
                pbar = ctk.CTkProgressBar(
                    row_f,
                    width=140,
                    height=8,
                    progress_color="#00f0ff",
                    fg_color="#1e293b",
                )
                pbar.set(count / max_p_count)
                pbar.pack(side="left", padx=10, pady=8)

        # ب) الكيانات الأكثر ارتباطاً بالشبكة (الجانب الأيسر)
        node_card = ctk.CTkFrame(
            details_frame, fg_color="#0a0d1e", border_width=1, border_color="#054552"
        )
        node_card.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

        node_title = ctk.CTkLabel(
            node_card,
            text=ar("🧠 الكيانات الأكثر ارتباطاً بالشبكة"),
            font=("Tajawal", 13, "bold"),
            text_color="#bd00ff",
        )
        node_title.pack(pady=10, padx=15, anchor="e")

        if not stats["top_connected"]:
            no_node = ctk.CTkLabel(
                node_card,
                text=ar("لا توجد عقد في الشبكة حالياً."),
                font=("Tajawal", 11, "italic"),
                text_color="#94a3b8",
            )
            no_node.pack(pady=35)
        else:
            max_degree = (
                max([item[1] for item in stats["top_connected"]])
                if stats["top_connected"]
                else 1
            )
            for name, deg in stats["top_connected"]:
                row_f = ctk.CTkFrame(node_card, fg_color="transparent")
                row_f.pack(fill="x", padx=15, pady=6)

                # النص والعدد
                lbl = ctk.CTkLabel(
                    row_f,
                    text=ar(f"{name} ({deg} روابط)"),
                    font=("Tajawal", 11, "bold"),
                    text_color="#fff",
                )
                lbl.pack(side="right")

                # شريط النسبة
                pbar = ctk.CTkProgressBar(
                    row_f,
                    width=140,
                    height=8,
                    progress_color="#bd00ff",
                    fg_color="#1e293b",
                )
                pbar.set(deg / max_degree)
                pbar.pack(side="left", padx=10, pady=8)

        # 4. معلومات النظام وزر التحديث السريع بالأسفل
        sys_frame = ctk.CTkFrame(
            self.stats_frame, fg_color="#070913", border_width=1, border_color="#1e293b"
        )
        sys_frame.pack(fill="x", padx=10, pady=(20, 10))

        db_lbl = ctk.CTkLabel(
            sys_frame,
            text=ar(
                f"📁 مسار قاعدة البيانات النشطة: {os.path.basename(self.prototype.db_path)}"
            ),
            font=("Tajawal", 10, "italic"),
            text_color="#94a3b8",
        )
        db_lbl.pack(side="right", padx=15, pady=10)

        ref_stats_btn = ctk.CTkButton(
            sys_frame,
            text=ar("🔄 تحديث الإحصائيات الحالية"),
            width=140,
            height=25,
            fg_color="#054552",
            hover_color="#00f0ff",
            text_color="#fff",
            font=("Tajawal", 10, "bold"),
            command=self.build_or_update_stats_view,
        )
        ref_stats_btn.pack(side="left", padx=15, pady=10)

        # تصدير المعرفة
        export_btn = ctk.CTkButton(
            sys_frame,
            text=ar("📤 تصدير المعرفة (JSON)"),
            width=140,
            height=25,
            fg_color="#070913",
            border_width=1,
            border_color="#ff9f43",
            hover_color="#ff9f43",
            text_color="#fff",
            font=("Tajawal", 10, "bold"),
            command=self.export_knowledge,
        )
        export_btn.pack(side="left", padx=5, pady=10)

        # استيراد المعرفة
        import_btn = ctk.CTkButton(
            sys_frame,
            text=ar("📥 استيراد المعرفة (JSON)"),
            width=140,
            height=25,
            fg_color="#070913",
            border_width=1,
            border_color="#bd00ff",
            hover_color="#bd00ff",
            text_color="#fff",
            font=("Tajawal", 10, "bold"),
            command=self.import_knowledge,
        )
        import_btn.pack(side="left", padx=5, pady=10)

    def export_knowledge(self):
        """تصدير كامل العلاقات والمفاهيم من قاعدة البيانات الحالية إلى ملف JSON"""
        from tkinter import filedialog, messagebox

        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json")],
            title=ar("تصدير العقل المعرفي"),
        )
        if not file_path:
            return

        try:
            triples = self.prototype.get_all_triples()

            # جلب المفاهيم
            conn = sqlite3.connect(self.prototype.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name, super_type, properties FROM concepts")
            concepts_data = []
            for name, super_type, props_json in cursor.fetchall():
                concepts_data.append(
                    {
                        "name": name,
                        "super_type": super_type,
                        "properties": json.loads(props_json) if props_json else [],
                    }
                )
            conn.close()

            triples_data = []
            for t in triples:
                triples_data.append(
                    {
                        "subject": t[0],
                        "relation": t[1],
                        "object": t[2],
                        "valid_from": t[3] if len(t) > 3 else None,
                        "valid_to": t[4] if len(t) > 4 else None,
                    }
                )

            export_data = {
                "source_db": os.path.basename(self.prototype.db_path),
                "export_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "concepts": concepts_data,
                "relations": triples_data,
            }

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, ensure_ascii=False, indent=4)

            self.add_log(
                f"تم بنجاح تصدير العقل المعرفي ({len(concepts_data)} مفهوم و {len(triples_data)} رابط) إلى {os.path.basename(file_path)}",
                "success",
            )
            messagebox.showinfo(
                ar("نجاح التصدير"), ar("تم تصدير البنية المعرفة بنجاح وبسرعة فائقة!")
            )
        except Exception as e:
            self.add_log(f"فشل تصدير المعرفة: {e}", "error")
            messagebox.showerror(ar("خطأ تصدير"), ar(f"تعذر تصدير الملف: {e}"))

    def import_knowledge(self):
        """استيراد المفاهيم والروابط المعرفية من ملف JSON ودمجها مع القاعدة النشطة"""
        from tkinter import filedialog, messagebox

        file_path = filedialog.askopenfilename(
            filetypes=[("JSON Files", "*.json")], title=ar("استيراد عقل معرفي")
        )
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                import_data = json.load(f)

            concepts = import_data.get("concepts", [])
            relations = import_data.get("relations", [])

            if not concepts and not relations:
                messagebox.showwarning(
                    ar("ملف غير صالح"),
                    ar("لا يحتوي الملف المحدد على بنية معرفية صالحة."),
                )
                return

            # جلب تأكيد المستخدم
            if not messagebox.askyesno(
                ar("تأكيد الدمج المعرفي"),
                ar(
                    f"هل أنت متأكد من دمج {len(concepts)} مفهوم و {len(relations)} علاقة معرفية في مساحة العمل الحالية؟"
                ),
            ):
                return

            # حفظ المفاهيم
            for c in concepts:
                name = c.get("name")
                super_type = c.get("super_type")
                properties = c.get("properties", [])
                if name:
                    self.prototype.save_concept_to_db(name, super_type, properties)

            # حفظ العلاقات
            for r in relations:
                subj = r.get("subject", r.get("فاعل"))
                pred = r.get("relation", r.get("علاقة"))
                obj = r.get("object", r.get("مفعول"))
                valid_from = r.get("valid_from")
                valid_to = r.get("valid_to")
                if subj and pred and obj:
                    self.prototype.save_triple_to_db(
                        subj, pred, obj, valid_from, valid_to
                    )

            # تحديث الواجهات
            self.prototype.load_graph_from_db()
            self.sync_graph_to_physics()
            self.relation_current_page = 1
            self.refresh_relations_list()
            self.build_or_update_stats_view()

            self.add_log(
                f"تم دمج واستيعاب المعرفة المستوردة بنجاح من ملف: {os.path.basename(file_path)}",
                "success",
            )
            messagebox.showinfo(
                ar("نجاح الدمج"),
                ar(
                    "تم استيراد ودمج البنية المعرفية بالكامل وتحديث الذاكرة والرسومات المعرفية!"
                ),
            )
        except Exception as e:
            self.add_log(f"فشل استيراد المعرفة: {e}", "error")
            messagebox.showerror(
                ar("خطأ استيراد"), ar(f"تعذر استيراد الملف المعرفي: {e}")
            )

    def on_global_scroll(self, event):
        """حل مشكلة التمرير في أنظمة لينكس والتبعية للمكونات الأبناء في CustomTkinter"""
        try:
            # الحصول على إحداثيات مؤشر الفأرة المطلقة والبحث عن المكون الذي تحتها
            x = self.winfo_pointerx()
            y = self.winfo_pointery()
            widget = self.winfo_containing(x, y)
        except Exception:
            return

        if not widget:
            return

        # إذا كان المكون تحت الفأرة هو حقل نصي قابل للتمرير داخلياً (كصندوق السجلات أو المخرجات)، اتركه يتعامل مع التمرير بنفسه
        try:
            if widget.winfo_class() in ("Text", "Listbox"):
                return
        except Exception:
            pass

        # البحث في الشجرة الأبوية للعناصر عن CTkScrollableFrame
        current = widget
        while current:
            if hasattr(current, "_parent_canvas") and current._parent_canvas:
                canvas = current._parent_canvas
                # نظام لينكس: Button-4 للأعلى و Button-5 للأسفل
                if event.num == 4:
                    canvas.yview_scroll(-1, "units")
                elif event.num == 5:
                    canvas.yview_scroll(1, "units")
                # أنظمة ويندوز وماك: delta
                elif event.delta:
                    scroll_dir = -1 if event.delta > 0 else 1
                    canvas.yview_scroll(scroll_dir, "units")
                return

            if hasattr(current, "master") and current.master:
                current = current.master
            else:
                break

    def on_clear_click(self):
        from tkinter import messagebox

        if messagebox.askyesno(
            ar("تصفير المعرفة"),
            ar(
                "هل أنت متأكد تماماً من رغبتك في تصفير العقل المعرفي ومسح كافة البيانات من الصفر المطلق؟"
            ),
        ):
            self.prototype.clear_all_data()
            self.sync_graph_to_physics()
            if getattr(self, "show_stats", False):
                self.build_or_update_stats_view()
            self.add_log(
                "تم تصفير العقل المعرفي بنجاح وقاعدة البيانات خالية تماماً الآن.", "warn"
            )

            self.response_text.configure(state="normal")
            self.response_text.delete("1.0", "end")
            self.response_text.insert(
                "1.0",
                ar(
                    "تم إعادة تعيين النظام بنجاح. ابدأ بتلقين المساعد روابط أو حقائق جديدة."
                ),
            )
            self.response_text.configure(state="disabled")

    def on_key_release(self, event=None):
        text = self.prompt_entry.get().strip()
        if text:
            # التحقق من وجود حروف عربية
            if any("\u0600" <= c <= "\u06ff" for c in text):
                self.preview_lbl.configure(
                    text=ar(f"🔮 معاينة الخط العربي اللحظية: {text}")
                )
            else:
                self.preview_lbl.configure(text="")
            # تشغيل الإكمال التلقائي الذكي
            self.show_autocomplete_suggestions(text)
        else:
            self.preview_lbl.configure(text="")
            if hasattr(self, "autocomplete_frame"):
                self.autocomplete_frame.pack_forget()

    def show_autocomplete_suggestions(self, text):
        if (
            not hasattr(self, "autocomplete_frame")
            or not self.autocomplete_frame.winfo_exists()
        ):
            return

        # تدمير أي اقتراحات قديمة
        for widget in self.autocomplete_frame.winfo_children():
            widget.destroy()

        words = text.split()
        if not words:
            self.autocomplete_frame.pack_forget()
            return

        last_word = words[-1].lower()
        if len(last_word) < 2:
            self.autocomplete_frame.pack_forget()
            return

        # جلب المفاهيم والعلاقات الموجودة لمطابقتها
        all_concepts = list(self.prototype.graph.nodes)
        all_relations = set()
        for u, v, d in self.prototype.graph.edges(data=True):
            if "relation" in d:
                all_relations.add(d["relation"])

        suggestions = []
        for c in all_concepts:
            if c.lower().startswith(last_word) and c.lower() != last_word:
                suggestions.append((c, "concept"))
        for r in all_relations:
            if r.lower().startswith(last_word) and r.lower() != last_word:
                suggestions.append((r, "relation"))

        suggestions = suggestions[:5]

        if not suggestions:
            self.autocomplete_frame.pack_forget()
            return

        self.autocomplete_frame.pack(fill="x", padx=10, pady=(2, 5))

        lbl = ctk.CTkLabel(
            self.autocomplete_frame,
            text=ar("🔎 اقتراحات دلالية:"),
            font=("Tajawal", 9, "bold"),
            text_color="#00f0ff",
        )
        lbl.pack(side="right", padx=5)

        for item, item_type in suggestions:
            btn_color = "#bd00ff" if item_type == "concept" else "#39ff14"
            txt_color = "#fff" if item_type == "concept" else "#05070f"

            btn = ctk.CTkButton(
                self.autocomplete_frame,
                text=ar(item),
                font=("Tajawal", 9, "bold"),
                fg_color="#070913",
                border_width=1,
                border_color=btn_color,
                text_color="#fff" if item_type == "concept" else btn_color,
                hover_color=btn_color,
                height=20,
                width=60,
                command=lambda val=item: self.apply_autocomplete(val),
            )
            btn.pack(side="right", padx=3, pady=3)

    def apply_autocomplete(self, value):
        current_text = self.prompt_entry.get()
        words = current_text.split()
        if words:
            words[-1] = value
            new_text = " ".join(words) + " "
            self.prompt_entry.delete(0, "end")
            self.prompt_entry.insert(0, new_text)
            self.prompt_entry.focus()

        self.autocomplete_frame.pack_forget()

    def on_send_click(self):
        sentence = self.prompt_entry._entry.get().strip()
        if not sentence or self.thinking:
            return

        self.prompt_entry.delete(0, "end")
        self.preview_lbl.configure(text="")

        provider_choice = self.provider_select.get()
        provider = "google"
        if "Groq" in provider_choice:
            provider = "groq"
        elif "OpenRouter" in provider_choice:
            provider = "openrouter"

        api_key = self.key_entry.get().strip()
        model = self.model_select.get()

        # تغيير حالة الواجهة إلى التفكير والتشغيل غير القابل للتجميد
        self.thinking = True
        self.timer_start = time.time()
        self.status_indicator.configure(
            text=ar("🔴 جاري التفكير بالـ AI..."), text_color="#ff007a"
        )
        self.send_btn.configure(state="disabled", text=ar("جاري المعالجة..."))

        self.add_log(f"بدء معالجة: '{sentence}'", "info")

        # إطلاق معالجة الخلفية في ثريد مستقل لحماية الواجهة من التعليق
        threading.Thread(
            target=self.background_executor,
            args=(sentence, provider, api_key, model, self.active_mode),
            daemon=True,
        ).start()

    def background_executor(self, sentence, provider, api_key, model, mode):
        logs = []
        response_text = ""

        try:
            # معالجة طلب الربط الدلالي
            match_path = re.match(
                r"(?:ما هي\s+)?العلاقة بين\s+(.+?)\s+(?:و\s*|وال\s*)(.+)",
                sentence,
                re.IGNORECASE,
            )
            if match_path:
                concept_a = match_path.group(1).strip()
                concept_b = match_path.group(2).strip()
                logs.append(
                    f"🔍 طلب كشف مسار العلاقات بين: '{concept_a}' و '{concept_b}'"
                )
                response_text = self.prototype.find_relation_path_string(
                    concept_a, concept_b, logs
                )
            else:
                if mode == "db_only":
                    response_text = self.prototype.run_pure_db_rag(
                        sentence, provider, api_key, model, logs
                    )
                else:
                    parsed_json = self.prototype.parse_sentence_with_llm(
                        sentence, provider, api_key, model, logs
                    )
                    logs.append("✅ نجاح دلالي! تم تحليل الجملة بنجاح.")

                    if mode == "teach":
                        logs.append(
                            "🧠 [نمط التلقين المباشر]: جاري حفظ الكيانات والعلاقات الجديدة..."
                        )
                        self.prototype.learn_and_store(parsed_json, logs)
                        response_text = "تم تلقين النظام وتخزين المفاهيم والحقائق الجديدة بنجاح في قاعدة البيانات وجدول الذاكرة RAM الرسومية!"
                    else:
                        logs.append(
                            "💬 [نمط المحادثة الذكية]: جاري التعلم التراكمي وتحديث الذاكرة تلقائياً..."
                        )
                        self.prototype.learn_and_store(parsed_json, logs)
                        self.prototype.run_symbolic_reasoning(parsed_json, logs)

                        logs.append("🤔 جاري صياغة رد لغوي بليغ ومناسب...")
                        prompt_chat = f"""
أنت نظام ذكاء اصطناعي عصبي-رمزي هجين ومساعد ذكي بليغ.
قام المستخدم بإدخال هذه الجملة: "{sentence}"
وقد قمنا بتحليلها واستخراج العلاقات التالية منها وحفظها:
{json.dumps(parsed_json, ensure_ascii=False)}

اكتب رداً تفاعلياً طبيعياً باللغة العربية الفصحى يرحب بالجملة ويؤكد استيعابها دلالياً، وصغ أي استنتاجات منطقية أو وراثة مفاهيمية مفيدة بأسلوب جذاب وبليغ دون شرح للتركيبة البرمجية.
"""
                        response_text = call_llm_api(
                            provider, api_key, model, prompt_chat, logs
                        )

        except Exception as e:
            logs.append(f"❌ حدث خطأ فني أثناء المعالجة: {str(e)}")
            response_text = f"عذراً، واجهنا مشكلة في معالجة طلبك: {str(e)}"

        # تحديث الواجهة بشكل آمن عبر ثريد الواجهة الرئيسي عند اكتمال العمل
        self.after(0, self.finish_processing, response_text, logs)

    def finish_processing(self, response, logs):
        self.thinking = False
        elapsed = time.time() - self.timer_start
        self.timer_lbl.configure(text=ar(f"⏱️ سرعة المعالجة: {elapsed:.2f} ثانية"))

        # إعادة تفعيل الأزرار والمؤشرات
        self.status_indicator.configure(text=ar("🟢 جاهز للعمل"), text_color="#39ff14")
        self.send_btn.configure(
            state="normal", text=ar("🚀 إرسال للمعالجة العصبيّة الرمزيّة")
        )

        # طباعة السجلات في وحدة التحكم
        for step in logs:
            log_type = "info"
            if "✅" in step or "نجاح" in step:
                log_type = "success"
            elif "⚠️" in step or "فشل" in step or "❌" in step:
                log_type = "warn"
            elif "🔄" in step or "جاري" in step:
                log_type = "process"
            self.add_log(step, log_type)

        self.add_log(
            f"اكتملت المعالجة دلالياً ورمزياً بنجاح خلال {elapsed:.2f} ثانية.", "success"
        )

        # مزامنة الكانفاس لتظهر العقد الطائرة الجديدة فوراً!
        self.sync_graph_to_physics()
        self.refresh_relations_list()

        # تحديث لوحة الإحصائيات إذا كانت معروضة حالياً
        if getattr(self, "show_stats", False):
            self.build_or_update_stats_view()

        # عرض المخرج النهائي بجمالية بليغة
        self.response_text.configure(state="normal")
        self.response_text.delete("1.0", "end")
        self.response_text.insert("1.0", ar(response))
        self.response_text.configure(state="disabled")

    def open_article_modal(self):
        # إنشاء نافذة منبثقة جديدة للمقالات الطويلة بتصميم سيبربانك داكن ومبهر
        self.modal = ctk.CTkToplevel(self)
        self.modal.title("📝 معالج المقالات والنصوص الطويلة")
        self.modal.geometry("800x650")
        self.modal.configure(fg_color="#070913")

        # جعل النافذة فوق النافذة الرئيسية ومركزة
        self.modal.transient(self)
        self.modal.focus_force()

        title_lbl = ctk.CTkLabel(
            self.modal,
            text=ar("✨ اكتب أو الصق مقالك هنا - يتم التنسيق وتوصيل الحروف تلقائياً"),
            font=("Tajawal", 13, "bold"),
            text_color="#00f0ff",
        )
        title_lbl.pack(pady=(15, 5))

        # إطار أزرار التحكم العلوي للتنسيق اليدوي
        ctrl_frame = ctk.CTkFrame(self.modal, fg_color="transparent")
        ctrl_frame.pack(fill="x", padx=20, pady=5)

        format_btn = ctk.CTkButton(
            ctrl_frame,
            text=ar("✨ تنسيق وربط الحروف العربية"),
            fg_color="#10b981",
            text_color="#fff",
            hover_color="#059669",
            font=("Tajawal", 10, "bold"),
            height=25,
            command=self.format_modal_text,
        )
        format_btn.pack(side="right", padx=5)

        unformat_btn = ctk.CTkButton(
            ctrl_frame,
            text=ar("🔄 إلغاء التنسيق (للتعديل والكتابة)"),
            fg_color="#4b5563",
            text_color="#fff",
            hover_color="#374151",
            font=("Tajawal", 10, "bold"),
            height=25,
            command=self.unformat_modal_text,
        )
        unformat_btn.pack(side="right", padx=5)

        # صندوق النصوص الكبير للمقالة
        self.modal_textbox = ctk.CTkTextbox(
            self.modal,
            height=260,
            fg_color="#0c0e1a",
            border_color="#0891b2",
            border_width=1,
            font=("Tajawal", 12),
        )
        self.modal_textbox.pack(fill="both", expand=True, padx=20, pady=5)
        self.modal_textbox.focus_force()

        # ربط أحداث لوحة المفاتيح واللصق
        self.modal_textbox.bind("<KeyRelease>", self.on_modal_key_release)
        self.modal_textbox.bind("<<Paste>>", self.on_modal_paste)

        # إطار المعاينة اللحظية الضخمة والمضيئة بالأسفل
        preview_frame = ctk.CTkFrame(
            self.modal, fg_color="#070913", border_color="#10b981", border_width=1
        )
        preview_frame.pack(fill="x", padx=20, pady=5)

        preview_title = ctk.CTkLabel(
            preview_frame,
            text=ar("🔮 معاينة الخط العربي المتصل لحظياً:"),
            font=("Tajawal", 9, "bold"),
            text_color="#10b981",
        )
        preview_title.pack(anchor="e", padx=10, pady=(5, 0))

        # تسمية توضيحية للمعاينة اللحظية
        self.modal_preview_text = ctk.CTkTextbox(
            preview_frame,
            height=120,
            fg_color="#070913",
            border_width=0,
            font=("Tajawal", 11, "bold"),
            wrap="word",
        )
        self.modal_preview_text.pack(fill="both", expand=True, padx=15, pady=(5, 10))
        self.modal_preview_text.insert(
            "1.0", ar("💡 اكتب شيئاً أو الصق نصاً لرؤية المعاينة المتصلة هنا فوراً...")
        )
        self.modal_preview_text.configure(state="disabled")

        # إطار الأزرار بالأسفل
        btn_frame = ctk.CTkFrame(self.modal, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(5, 15))

        # زر الإرسال والتحليل
        analyze_btn = ctk.CTkButton(
            btn_frame,
            text=ar("🚀 تحليل المقال واستنباط العلاقات"),
            fg_color="#00f0ff",
            text_color="#05070f",
            hover_color="#bd00ff",
            font=("Tajawal", 12, "bold"),
            command=self.on_analyze_article_click,
        )
        analyze_btn.pack(side="right", padx=5)

        # زر الإلغاء
        cancel_btn = ctk.CTkButton(
            btn_frame,
            text=ar("إلغاء"),
            fg_color="#374151",
            text_color="#fff",
            hover_color="#4b5563",
            font=("Tajawal", 11, "bold"),
            command=self.modal.destroy,
        )
        cancel_btn.pack(side="left", padx=5)

    def on_modal_key_release(self, event=None):
        raw_text = self.modal_textbox.get("1.0", "end-1c")
        self.modal_preview_text.configure(state="normal")
        self.modal_preview_text.delete("1.0", "end")
        if raw_text.strip():
            # الحصول على النص منطقياً ثم عرضه منسقاً
            logical = derender_bidi_text(raw_text)
            self.modal_preview_text.insert("1.0", ar(logical))
            self.modal_preview_text.configure(text_color="#10b981")
        else:
            self.modal_preview_text.insert(
                "1.0", ar("💡 اكتب شيئاً أو الصق نصاً لرؤية المعاينة المتصلة هنا فوراً...")
            )
            self.modal_preview_text.configure(text_color="#94a3b8")
        self.modal_preview_text.configure(state="disabled")

    def format_modal_text(self):
        raw_text = self.modal_textbox.get("1.0", "end-1c").strip()
        if not raw_text:
            return
        # تنسيق النص بالكامل وربط حروفه
        logical = derender_bidi_text(raw_text)
        rendered = render_bidi_text(logical)
        self.modal_textbox.delete("1.0", "end")
        self.modal_textbox.insert("1.0", rendered)
        self.on_modal_key_release()

    def unformat_modal_text(self):
        raw_text = self.modal_textbox.get("1.0", "end-1c").strip()
        if not raw_text:
            return
        # فك تنسيق النص للعودة إلى وضع الكتابة الطبيعي
        logical = derender_bidi_text(raw_text)
        self.modal_textbox.delete("1.0", "end")
        self.modal_textbox.insert("1.0", logical)
        self.on_modal_key_release()

    def on_modal_paste(self, event=None):
        # ننتظر 50ms للتأكد من اكتمال عملية اللصق ثم نقوم بالتنسيق التلقائي الفوري!
        self.modal.after(50, self._perform_modal_paste_formatting)

    def _perform_modal_paste_formatting(self):
        raw_text = self.modal_textbox.get("1.0", "end-1c").strip()
        if not raw_text:
            return
        logical = derender_bidi_text(raw_text)
        rendered = render_bidi_text(logical)
        self.modal_textbox.delete("1.0", "end")
        self.modal_textbox.insert("1.0", rendered)
        self.on_modal_key_release()

    def on_analyze_article_click(self):
        article_text = self.modal_textbox.get("1.0", "end-1c").strip()
        if not article_text:
            return

        # إغلاق النافذة المنبثقة
        self.modal.destroy()

        # فك أي ترتيبات بصرية للحصول على النص العربي المنطقي النظيف
        logical_text = derender_bidi_text(article_text)

        # تفعيل المؤشرات وبدء الإرسال
        self.response_text.configure(state="normal")
        self.response_text.delete("1.0", "end")
        self.response_text.insert(
            "1.0", ar("جاري معالجة واستخلاص العلاقات من المقال المكتوب...")
        )
        self.response_text.configure(state="disabled")

        self.thinking = True
        self.status_indicator.configure(
            text=ar("🔄 جاري التفكير منطقياً..."), text_color="#00f0ff"
        )
        self.send_btn.configure(state="disabled", text=ar("جاري المعالجة..."))
        self.timer_start = time.time()

        provider_choice = self.provider_select.get()
        provider = "google"
        if "Groq" in provider_choice:
            provider = "groq"
        elif "OpenRouter" in provider_choice:
            provider = "openrouter"

        api_key = self.key_entry.get().strip()
        model = self.model_select.get()

        # تشغيل المعالجة في الخلفية لمنع تجميد الواجهة الرسومية
        threading.Thread(
            target=self.background_executor,
            args=(logical_text, provider, api_key, model, self.active_mode),
            daemon=True,
        ).start()


# =========================================================================
# التشغيل الرئيسي: سويتش للـ CLI أو واجهة سطح المكتب
# =========================================================================
if __name__ == "__main__":
    if "--cli" in sys.argv:
        print(
            f"\n{TC.CYAN}{TC.BOLD}=========================================================================="
        )
        print(
            f"🌟       مرحباً بك في نظام الذكاء الاصطناعي العصبي-الرمزي الهجين التفاعلي (CLI)     🌟"
        )
        print(
            f"  {TC.YELLOW}دقة استدلال منطقية صارمة (NetworkX) | فك دلالي (LLM) | قاعدة SQLite{TC.CYAN}"
        )
        print(
            f"=========================================================================={TC.RESET}\n"
        )

        while True:
            try:
                prompt_str = f"{TC.YELLOW}{TC.BOLD}✨ أدخل جملة ليتعلمها النظام (أو 'خروج') ❯ {TC.RESET}"
                sentence = input(prompt_str).strip()
                if not sentence:
                    continue
                if sentence.lower() in ["خروج", "exit", "quit"]:
                    print(f"\n{TC.GREEN}👋 إلى اللقاء في جلسات تعلم قادمة!{TC.RESET}\n")
                    break

                # مطابقة المسار
                match_path = re.match(
                    r"(?:ما هي\s+)?العلاقة بين\s+(.+?)\s+(?:و\s*|وال\s*)(.+)",
                    sentence,
                    re.IGNORECASE,
                )
                if match_path:
                    concept_a = match_path.group(1).strip()
                    concept_b = match_path.group(2).strip()
                    logs_temp = []
                    res_path = prototype.find_relation_path_string(
                        concept_a, concept_b, logs_temp
                    )
                    print(f"\n{TC.CYAN}{res_path}{TC.RESET}\n")
                    continue

                cli_key = os.environ.get(
                    "GEMINI_API_KEY", os.environ.get("GOOGLE_API_KEY", "")
                )
                parsed_json = prototype.parse_sentence_with_llm(
                    sentence, "google", cli_key, "gemini-2.5-flash", logs_temp
                )
                prototype.learn_and_store(parsed_json, logs_temp)
                prototype.run_symbolic_reasoning(parsed_json, logs_temp)

                print(f"\n{TC.BLUE}📜 رصد خطوات الشبكة والتحليل اللحظي:{TC.RESET}")
                for log in logs_temp:
                    print(f"   ➔ {log}")
                print(
                    f"{TC.WHITE}──────────────────────────────────────────────────────────────────────────{TC.RESET}\n"
                )

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"⚠️ حدث خطأ: {e}")
    else:
        # إطلاق واجهة سطح المكتب المستقبلية والمثيرة
        print(
            f"\n{TC.CYAN}{TC.BOLD}=========================================================================="
        )
        print(
            f"🚀        جاري تشغيل واجهة سطح المكتب المضيئة والمطورة لـ LEGEND           "
        )
        print(
            f"       إصدار سطح المكتب ثنائي الأبعاد المعتمد بالكامل على قوى الفيزياء     "
        )
        print(
            f"=========================================================================={TC.RESET}"
        )

        try:
            app = CyberpunkApp()
            app.mainloop()
        except Exception as e:
            print(
                f"\n{TC.RED}⚠️ [خطأ في تشغيل سطح المكتب]:{TC.RESET} تعذر فتح الواجهة الرسومية."
            )
            print(f"📄 تفاصيل الخطأ الفني (Error Details): {e}")
            import traceback

            traceback.print_exc()
            print(
                f"{TC.CYAN}🔄 [تراجع تلقائي موثوق]:{TC.RESET} جاري تشغيل نمط الطرفية التفاعلي CLI كاحتياطي..."
            )

            # تشغيل الاحتياطي التفاعلي CLI
            sys.argv.append("--cli")
            os.execv(sys.executable, [sys.executable] + sys.argv)
