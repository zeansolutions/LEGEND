import sys
import os
import json
import sqlite3
import time
import threading
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import core_utils
from neuro_symbolic_engine import ArabicNeuroSymbolicPrototype, normalize_arabic
from cognitive_engine import (
    CognitiveInferenceEngine,
    CognitiveCuriosityEngine,
    CognitiveSleepCycle,
)
from translator import LogTranslator, TranslatableLogList

# Initialize log_translator
log_translator = LogTranslator(
    os.path.join(os.path.dirname(__file__), "python_translations.json")
)

app = FastAPI(title="LEGEND Neuro-Symbolic API")

# Allow CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

progress_lock = threading.Lock()
global_progress = {
    "active": False,
    "process_name": "",
    "phase": "",
    "current": 0,
    "total": 0,
    "start_time": 0.0,
    "elapsed_seconds": 0.0,
    "message": "",
}


def update_progress(
    process_name="",
    phase="",
    current=0,
    total=0,
    start_time=0.0,
    message="",
    active=True,
    lang="ar",
):
    with progress_lock:
        global_progress["active"] = active
        if active:
            global_progress["process_name"] = (
                log_translator.translate(process_name, lang)
                if process_name
                else global_progress["process_name"]
            )
            global_progress["phase"] = (
                log_translator.translate(phase, lang)
                if phase
                else global_progress["phase"]
            )
            global_progress["current"] = current
            global_progress["total"] = total
            if start_time > 0:
                global_progress["start_time"] = start_time
                global_progress["elapsed_seconds"] = round(time.time() - start_time, 1)
            if message:
                global_progress["message"] = message
        else:
            global_progress["process_name"] = ""
            global_progress["phase"] = ""
            global_progress["current"] = 0
            global_progress["total"] = 0
            global_progress["start_time"] = 0.0
            global_progress["elapsed_seconds"] = 0.0
            global_progress["message"] = ""


@app.get("/api/status/current")
def get_current_status():
    with progress_lock:
        if global_progress["active"] and global_progress["start_time"] > 0:
            global_progress["elapsed_seconds"] = round(
                time.time() - global_progress["start_time"], 1
            )
        return global_progress


@app.post("/api/status/abort")
def abort_process():
    prototype.abort_requested = True
    return {"status": "success", "message": "Abort requested"}


# Initialize the prototype
prototype = ArabicNeuroSymbolicPrototype()

# File paths
WORKSPACES_FILE = os.path.join(os.path.dirname(prototype.db_path), "workspaces.json")


class QueryRequest(BaseModel):
    sentence: str
    provider: str
    api_key: str
    model: str
    language: str = "ar"


class LearnRequest(BaseModel):
    sentence: str
    provider: str
    api_key: str
    model: str
    language: str = "ar"


class WorkspaceAddRequest(BaseModel):
    name: str
    mode: str


class RelationDeleteRequest(BaseModel):
    source: str
    relation: str
    target: str


class NodeDeleteRequest(BaseModel):
    name: str


class WorkspaceSelectRequest(BaseModel):
    name: str


class WorkspaceImportRequest(BaseModel):
    workspace_name: str
    mode: Optional[str] = "active"
    concepts: List[Dict[str, Any]]
    triples: List[Dict[str, Any]]
    rules: List[Dict[str, Any]]


class PLNRequest(BaseModel):
    concept_a: str
    concept_b: str


class RuleCreateRequest(BaseModel):
    rule_name: str
    antecedents: List[List[str]]
    consequent: List[str]
    confidence: float = 1.0


def load_workspaces_dict():
    default_workspaces = {
        "العقل العام (الافتراضي)": {"db_filename": "ontology.db", "mode": "active"}
    }
    if os.path.exists(WORKSPACES_FILE):
        try:
            with open(WORKSPACES_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                workspaces = {}
                for k, v in loaded.items():
                    if isinstance(v, str):
                        workspaces[k] = {"db_filename": v, "mode": "active"}
                    else:
                        workspaces[k] = v
                return workspaces
        except Exception:
            return default_workspaces
    else:
        return default_workspaces


def save_workspaces_dict(workspaces):
    try:
        with open(WORKSPACES_FILE, "w", encoding="utf-8") as f:
            json.dump(workspaces, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"⚠️ Failed to save workspaces: {e}")


@app.get("/api/workspaces")
def get_workspaces():
    workspaces = load_workspaces_dict()
    return workspaces


@app.post("/api/workspace/select")
def select_workspace(req: WorkspaceSelectRequest):
    workspaces = load_workspaces_dict()
    if req.name not in workspaces:
        raise HTTPException(status_code=404, detail="Workspace not found")

    ws_info = workspaces[req.name]
    db_name = ws_info.get("db_filename", "ontology.db")
    mode = ws_info.get("mode", "active")

    new_db_path = os.path.join(os.path.dirname(prototype.db_path), db_name)
    prototype.db_path = new_db_path
    prototype.init_database()
    prototype.load_graph_from_db()
    prototype.strict_mode = mode == "strict"

    return {"status": "success", "name": req.name, "mode": mode, "db_filename": db_name}


@app.post("/api/workspace/add")
def add_workspace(req: WorkspaceAddRequest):
    workspaces = load_workspaces_dict()
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name cannot be empty")
    if name in workspaces:
        raise HTTPException(status_code=400, detail="Workspace already exists")

    import uuid

    safe_db_name = f"ontology_{uuid.uuid4().hex[:8]}.db"
    workspaces[name] = {"db_filename": safe_db_name, "mode": req.mode}
    save_workspaces_dict(workspaces)
    return {"status": "success", "name": name, "mode": req.mode}


@app.post("/api/workspace/delete")
def delete_workspace(req: WorkspaceSelectRequest):
    workspaces = load_workspaces_dict()
    if req.name == "العقل العام (الافتراضي)":
        raise HTTPException(status_code=400, detail="Cannot delete default workspace")
    if req.name not in workspaces:
        raise HTTPException(status_code=404, detail="Workspace not found")

    ws_info = workspaces[req.name]
    db_filename = (
        ws_info
        if isinstance(ws_info, str)
        else ws_info.get("db_filename", "ontology.db")
    )
    db_path = os.path.join(os.path.dirname(prototype.db_path), db_filename)

    del workspaces[req.name]
    save_workspaces_dict(workspaces)

    try:
        if os.path.exists(db_path):
            os.remove(db_path)
    except Exception as e:
        print(f"Failed to remove database file: {e}")

    return {"status": "success"}


@app.get("/api/graph")
def get_graph():
    graph = prototype.sandbox_graph if prototype.in_sandbox else prototype.graph

    nodes = []
    for node, data in graph.nodes(data=True):
        if node is None:
            continue
        nodes.append(
            {
                "id": str(node),
                "type": data.get("type", "concept") or "concept",
                "super_type": data.get("super_type", "") or "",
                "confidence": data.get("confidence", 1.0) or 1.0,
                "properties": data.get("properties", []) or [],
            }
        )

    edges = []
    for u, v, data in graph.edges(data=True):
        if u is None or v is None:
            continue
        edges.append(
            {
                "source": str(u),
                "target": str(v),
                "relation": str(data.get("relation", "") or ""),
                "confidence": data.get("confidence", 1.0) or 1.0,
            }
        )

    return {
        "nodes": nodes,
        "edges": edges,
        "in_sandbox": prototype.in_sandbox,
        "strict_mode": getattr(prototype, "strict_mode", False),
    }


@app.post("/api/learn")
def learn_fact(req: LearnRequest):
    logs = TranslatableLogList(req.language, log_translator)
    t0 = time.time()
    update_progress(
        "تلقين المعرفة النشطة",
        "تحليل الجملة لغوياً ودلالياً عبر LLM",
        1,
        3,
        t0,
        lang=req.language,
    )
    try:
        # 1. Parse sentence with LLM
        parsed = prototype.parse_sentence_with_llm(
            req.sentence,
            req.provider.lower(),
            req.api_key,
            req.model,
            logs,
            language=req.language,
        )
        if not parsed:
            update_progress(active=False)
            return {
                "status": "error",
                "logs": logs,
                "response": "فشل تحليل الجملة معرفياً.",
            }

        # 2. Check contradictions
        update_progress(
            "تلقين المعرفة النشطة",
            "فحص التناقضات والنزاعات المعرفية مع الذاكرة",
            2,
            3,
            t0,
            lang=req.language,
        )
        contradictions = prototype.check_contradictions(parsed)
        if contradictions:
            update_progress(active=False)
            return {
                "status": "contradiction",
                "contradictions": contradictions,
                "logs": logs,
                "parsed": parsed,
            }

        # 3. Store and learn
        update_progress(
            "تلقين المعرفة النشطة",
            "حفظ الكيانات والعلاقات دلالياً في قاعدة البيانات والرسم البياني",
            3,
            3,
            t0,
            lang=req.language,
        )
        prototype.learn_and_store(parsed, logs)

        update_progress(active=False)
        return {"status": "success", "logs": logs, "parsed": parsed}
    except Exception as e:
        import traceback

        traceback.print_exc()
        logs.append(f"❌ خطأ غير متوقع: {str(e)}")
        update_progress(active=False)
        return {
            "status": "error",
            "logs": logs,
            "response": f"فشل الاتصال بمزود الخدمة أو حدث خطأ أثناء المعالجة: {str(e)}",
        }


@app.post("/api/query")
def query_fact(req: QueryRequest):
    logs = TranslatableLogList(req.language, log_translator)
    t0 = time.time()
    update_progress(
        "الاستعلام واستدلال الـ RAG",
        "تحليل السؤال وتفكيك الروابط المعرفية",
        1,
        3,
        t0,
        lang=req.language,
    )
    try:
        # Try logic/PLN query
        parsed = prototype.parse_sentence_with_llm(
            req.sentence,
            req.provider.lower(),
            req.api_key,
            req.model,
            logs,
            language=req.language,
        )
        if not parsed:
            update_progress(active=False)
            return {
                "status": "error",
                "logs": logs,
                "response": "فشل تحليل الاستعلام معرفياً.",
            }

        # Run reasoning RAG
        update_progress(
            "الاستعلام واستدلال الـ RAG",
            "استدعاء شبكة العلاقات وحقائق SQLite لتركيب السياق",
            2,
            3,
            t0,
            lang=req.language,
        )
        response = prototype.run_pure_db_rag(
            req.sentence,
            req.provider.lower(),
            req.api_key,
            req.model,
            logs,
            language=req.language,
        )
        update_progress(
            "الاستعلام واستدلال الـ RAG",
            "الاستنتاج العصبي-الرمزي وحل المسألة منطقياً عبر LLM",
            3,
            3,
            t0,
            lang=req.language,
        )

        update_progress(active=False)
        return {
            "status": "success",
            "response": response,
            "logs": logs,
            "parsed": parsed,
        }
    except Exception as e:
        import traceback

        traceback.print_exc()
        logs.append(f"❌ خطأ غير متوقع: {str(e)}")
        update_progress(active=False)
        return {
            "status": "error",
            "logs": logs,
            "response": f"فشل الاتصال بمزود الخدمة أو حدث خطأ أثناء المعالجة: {str(e)}",
        }


@app.post("/api/pln")
def run_pln(req: PLNRequest):
    logs = []
    result = prototype.run_probabilistic_inference(req.concept_a, req.concept_b, logs)
    return {"result": result, "logs": logs}


@app.get("/api/rules")
def get_rules():
    rules_list = []
    try:
        conn = sqlite3.connect(prototype.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT rule_name, antecedents, consequent, confidence FROM rules WHERE is_active = 1 ORDER BY confidence DESC"
        )
        rows = cursor.fetchall()
        for row in rows:
            rule_name = row[0]

            # Load antecedents JSON safely
            try:
                antecedents = json.loads(row[1])
            except Exception:
                antecedents = []

            # Load consequent JSON safely
            try:
                consequent = json.loads(row[2])
            except Exception:
                consequent = []

            confidence = row[3]

            # Formulate friendly display names for the frontend
            # The frontend expects `rule.antecedent.relation` and `rule.consequent.relation`
            rel_ant = "غير معروف"
            if isinstance(antecedents, list) and len(antecedents) > 0:
                relations = []
                for ant in antecedents:
                    if isinstance(ant, list) and len(ant) >= 2:
                        relations.append(ant[1])
                rel_ant = " & ".join(relations) if relations else "علاقة"

            rel_cons = "غير معروف"
            if isinstance(consequent, list):
                if len(consequent) >= 3 and isinstance(consequent[1], str):
                    rel_cons = consequent[1]
                elif (
                    len(consequent) > 0
                    and isinstance(consequent[0], list)
                    and len(consequent[0]) >= 2
                ):
                    rel_cons = consequent[0][1]
            elif isinstance(consequent, str):
                rel_cons = consequent

            rules_list.append(
                {
                    "rule_name": rule_name,
                    "antecedents": antecedents,
                    "antecedent": {"relation": rel_ant},
                    "consequent": {"relation": rel_cons},
                    "support": len(antecedents) if isinstance(antecedents, list) else 1,
                    "confidence": confidence,
                }
            )
        conn.close()
    except Exception as e:
        print(f"Failed to fetch rules: {e}")
    return rules_list


@app.post("/api/rules")
def add_custom_rule(req: RuleCreateRequest):
    """Add or update a logical reasoning rule manually to the SQLite database."""
    try:
        conn = sqlite3.connect(prototype.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO rules (rule_name, antecedents, consequent, confidence, is_active)
            VALUES (?, ?, ?, ?, 1)
        """,
            (
                req.rule_name,
                json.dumps(req.antecedents, ensure_ascii=False),
                json.dumps(req.consequent, ensure_ascii=False),
                req.confidence,
            ),
        )
        conn.commit()
        conn.close()
        return {
            "status": "success",
            "message": f"تم إدراج/تحديث القاعدة المنطقية [{req.rule_name}] بنجاح.",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"فشل إدراج القاعدة المنطقية: {str(e)}"
        )


@app.delete("/api/rules/{rule_name}")
def delete_rule_by_name(rule_name: str):
    """Delete a specific logical rule from the rules SQLite table."""
    try:
        conn = sqlite3.connect(prototype.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM rules WHERE rule_name = ?", (rule_name,))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        if deleted > 0:
            return {
                "status": "success",
                "message": f"تم حذف القاعدة [{rule_name}] بنجاح.",
            }
        else:
            return {
                "status": "success",
                "message": f"القاعدة [{rule_name}] غير موجودة بالفعل.",
            }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"فشل حذف القاعدة المنطقية: {str(e)}"
        )


@app.get("/api/stats")
def get_stats():
    try:
        stats = prototype.gather_db_statistics()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/clear")
def clear_database():
    success = prototype.clear_all_data()
    if success:
        return {
            "status": "success",
            "message": "تم تصفير العقل المعرفي وقاعدة البيانات خالية تماماً الآن.",
        }
    else:
        raise HTTPException(status_code=500, detail="فشل تصفير قاعدة البيانات.")


@app.post("/api/relation/delete")
def delete_relation_endpoint(req: RelationDeleteRequest):
    # Normalize subjects and targets
    src = normalize_arabic(req.source)
    tgt = normalize_arabic(req.target)
    pred = normalize_arabic(req.relation)
    success = prototype.delete_relation(src, pred, tgt)
    if success:
        return {"status": "success", "message": "تم حذف العلاقة الدلالية بنجاح."}
    else:
        raise HTTPException(status_code=500, detail="فشل حذف العلاقة الدلالية.")


@app.post("/api/node/delete")
def delete_node_endpoint(req: NodeDeleteRequest):
    normalized_name = normalize_arabic(req.name)
    success = prototype.delete_node(normalized_name)
    if success:
        return {"status": "success", "message": "تم حذف الكيان بنجاح مع كافة علاقاته."}
    else:
        raise HTTPException(status_code=500, detail="فشل حذف الكيان.")


@app.post("/api/rules/induct")
def run_rule_induction():
    logs = []
    new_rules = prototype.self_improve_rule_induction(logs)
    return {"new_rules_count": len(new_rules), "logs": logs}


@app.post("/api/sandbox/toggle")
def toggle_sandbox():
    if prototype.in_sandbox:
        prototype.rollback_sandbox()
        status = "inactive"
    else:
        prototype.start_sandbox()
        status = "active"
    return {"status": status}


@app.post("/api/sandbox/commit")
def commit_sandbox():
    if prototype.in_sandbox:
        prototype.commit_sandbox()
        return {"status": "committed"}
    return {"status": "inactive"}


@app.post("/api/sandbox/rollback")
def rollback_sandbox():
    if prototype.in_sandbox:
        prototype.rollback_sandbox()
        return {"status": "rolled_back"}
    return {"status": "inactive"}


@app.post("/api/sleep")
def sleep_cycle():
    try:
        sleep_eng = CognitiveSleepCycle(prototype)
        stats = sleep_eng.run_sleep_cycle()

        # Build beautiful logs for the GUI
        logs = []
        logs.append(
            "💤 [Cognitive Sleep]: Initiating Hebbian relaxation and knowledge consolidation cycle..."
        )

        if stats.get("synonyms_linked", 0) > 0:
            logs.append(
                f"🔗 [Synonym Fusion]: Unified and linked {stats['synonyms_linked']} semantic synonyms based on morphological light stemming."
            )
        else:
            logs.append(
                "🔗 [Synonym Fusion]: No synonym linkages were found to consolidate."
            )

        if stats.get("edges_strengthened", 0) > 0:
            logs.append(
                f"💪 [Link Strengthening]: Reinforced {stats['edges_strengthened']} semantic linkages based on shared co-occurrences."
            )

        if stats.get("edges_pruned", 0) > 0:
            logs.append(
                f"✂️ [Preventative Pruning]: Pruned and cleaned {stats['edges_pruned']} weak edges (confidence < 0.50) to protect memory clarity."
            )
        else:
            logs.append(
                "✂️ [Preventative Pruning]: All current linkages are solid and within acceptable confidence intervals."
            )

        if stats.get("dream_discoveries", 0) > 0:
            logs.append(
                f"💭 [Dream Walks]: Explored and mapped {stats['dream_discoveries']} latent similarity connections via graph random walks."
            )
        else:
            logs.append(
                "💭 [Dream Walks]: Daydream cycles completed with no new latent similarity discoveries."
            )

        if stats.get("new_inferences", 0) > 0:
            logs.append(
                f"🧠 [Automated Logic]: Successfully applied cognitive inference engine, yielding {stats['new_inferences']} new logical facts."
            )
        else:
            logs.append(
                "🧠 [Automated Logic]: No new inferences could be derived at this time."
            )

        if stats.get("noise_nodes_cleaned", 0) > 0:
            logs.append(
                f"🧹 [Cognitive Hygiene]: Swept and cleaned {stats['noise_nodes_cleaned']} isolated or noise nodes for structural purity."
            )

        return {
            "status": "success",
            "message": "Cognitive sleep cycle completed successfully. Memory nodes consolidated and pruned.",
            "logs": logs,
            "stats": stats,
            "inferred_count": stats.get("new_inferences", 0),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to execute semantic sleep cycle: {e}"
        )


@app.get("/api/curiosity")
def get_curiosity_questions(limit: int = 5):
    try:
        # Read saved language setting
        lang = "ar"
        settings_file = os.path.join(
            os.path.dirname(prototype.db_path), "settings.json"
        )
        if os.path.exists(settings_file):
            try:
                with open(settings_file, "r", encoding="utf-8") as f:
                    lang = json.load(f).get("language", "ar")
            except Exception:
                pass

        curiosity_eng = CognitiveCuriosityEngine(prototype)
        questions = curiosity_eng.generate_questions(limit=limit, lang=lang)
        gaps = curiosity_eng.find_knowledge_gaps()

        # Multilingual text_to_paste templates
        paste_templates = {
            "ar": {
                "taxonomy": "{c} هو نوع من ",
                "property": "صفة {c} هي ",
                "action": "{c} يقوم بـ ",
            },
            "en": {
                "taxonomy": "{c} is a type of ",
                "property": "A property of {c} is ",
                "action": "{c} does ",
            },
            "zh": {
                "taxonomy": "{c} 是一种 ",
                "property": "{c} 的属性是 ",
                "action": "{c} 的行为是 ",
            },
            "fr": {
                "taxonomy": "{c} est un type de ",
                "property": "Une propriété de {c} est ",
                "action": "{c} fait ",
            },
            "es": {
                "taxonomy": "{c} es un tipo de ",
                "property": "Una propiedad de {c} es ",
                "action": "{c} hace ",
            },
            "tr": {
                "taxonomy": "{c} bir tür ",
                "property": "{c} özelliği ",
                "action": "{c} yapar ",
            },
            "de": {
                "taxonomy": "{c} ist eine Art von ",
                "property": "Eine Eigenschaft von {c} ist ",
                "action": "{c} macht ",
            },
            "ru": {
                "taxonomy": "{c} является типом ",
                "property": "Свойство {c} — ",
                "action": "{c} делает ",
            },
            "pt": {
                "taxonomy": "{c} é um tipo de ",
                "property": "Uma propriedade de {c} é ",
                "action": "{c} faz ",
            },
            "ja": {
                "taxonomy": "{c} は一種の ",
                "property": "{c} の属性は ",
                "action": "{c} は ",
            },
            "ko": {
                "taxonomy": "{c} 은(는) 일종의 ",
                "property": "{c} 의 속성은 ",
                "action": "{c} 은(는) ",
            },
        }
        templates = paste_templates.get(lang, paste_templates["en"])

        # Add text_to_paste key for GUI compatibility
        formatted_questions = []
        for q in questions:
            concept = q.get("concept", "")
            q_type = q.get("type", "")

            template_key = q_type if q_type in templates else "action"
            text_to_paste = templates[template_key].replace("{c}", concept)

            formatted_questions.append(
                {
                    "question": q["question"],
                    "concept": concept,
                    "type": q_type,
                    "mystery_score": q["mystery_score"],
                    "text_to_paste": text_to_paste,
                }
            )

        return {
            "status": "success",
            "questions": formatted_questions,
            "gaps": gaps[:10],
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to run curiosity engine: {e}"
        )


@app.post("/api/inference")
def trigger_manual_inference():
    try:
        inf_eng = CognitiveInferenceEngine(prototype)
        logs = []
        inferred = inf_eng.run_inference(logs=logs)
        return {
            "status": "success",
            "message": f"اكتمل الاستدلال الحر بنجاح. تم استنتاج {len(inferred)} علاقة جديدة.",
            "inferred_count": len(inferred),
            "inferred": [
                {"subject": s, "predicate": p, "object": o, "confidence": c}
                for s, p, o, c in inferred
            ],
            "logs": logs,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"فشل تشغيل محرك الاستدلال: {e}")


# New Pydantic Request Models for Cognitive Features
class ThoughtExperimentRequest(BaseModel):
    hypothesis: str
    provider: str
    api_key: str
    model: str


class SocraticDialogueRequest(BaseModel):
    provider: str
    api_key: str
    model: str


class AbsorbRequest(BaseModel):
    text: str
    provider: str
    api_key: str
    model: str
    language: str = "ar"


class WorkspaceDiffRequest(BaseModel):
    other_workspace_name: str


class ProceduralAddRequest(BaseModel):
    procedure_name: str
    steps: List[str]


class FederatedSimulateRequest(BaseModel):
    query: str


# Endpoints
@app.get("/api/metacognition")
def get_metacognition():
    import networkx as nx

    graph = prototype.sandbox_graph if prototype.in_sandbox else prototype.graph

    # 1. Calculate isolated subgraphs
    try:
        undirected = graph.to_undirected()
        components = [list(c) for c in nx.connected_components(undirected)]
        isolated = [c for c in components if len(c) <= 2]
    except Exception:
        isolated = []

    # 2. Calculate cyclic dependencies
    try:
        cycles = [c for c in nx.simple_cycles(graph) if len(c) > 1]
    except Exception:
        cycles = []

    # 3. Calculate vague entities (degree <= 1 or confidence < 0.6)
    vague = []
    for node, data in graph.nodes(data=True):
        deg = graph.degree(node)
        conf = data.get("confidence", 1.0)
        emotional = data.get("emotional_valence", 0.0)
        if deg <= 1 or conf < 0.6:
            vague.append(
                {
                    "name": node,
                    "degree": deg,
                    "confidence": conf,
                    "emotional_valence": emotional,
                }
            )

    # 4. Cognitive health index
    total_nodes = graph.number_of_nodes()
    if total_nodes > 0:
        conf_sum = sum(
            data.get("confidence", 1.0) for _, data in graph.nodes(data=True)
        )
        avg_conf = conf_sum / total_nodes
        # Penalize for cycles and isolated components
        penalty = (len(cycles) * 0.1) + (len(isolated) * 0.05)
        cognitive_index = max(0.0, min(1.0, avg_conf - penalty))
    else:
        cognitive_index = 1.0

    healthy = len(cycles) == 0 and cognitive_index >= 0.7

    return {
        "status": "success",
        "cognitive_index": round(cognitive_index, 2),
        "isolated_components": isolated,
        "cyclic_dependencies": cycles,
        "vague_entities": vague[:10],
        "healthy": healthy,
    }


@app.post("/api/rules/evolve")
def evolve_rules():
    import random

    logs = ["🧬 بدء محاكاة التطور الجيني للقواعد المعرفية (Genetic Rule Evolution)..."]

    # We fetch existing rules
    rules_list = []
    try:
        conn = sqlite3.connect(prototype.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, rule_name, antecedents, consequent, confidence FROM rules"
        )
        rows = cursor.fetchall()
        conn.close()
    except Exception as e:
        return {"status": "error", "message": f"تعذر استرجاع القواعد: {e}"}

    if len(rows) < 2:
        logs.append(
            "⚠️ لا يوجد عدد كافٍ من القواعد المسجلة (مطلوب قاعدتين على الأقل لإجراء التزاوج والطفرات)."
        )
        return {"status": "success", "logs": logs, "evolved_count": 0}

    evolved_count = 0

    # Select two random rules
    r1, r2 = random.sample(rows, 2)
    id1, name1, ant1_json, cons1_json, conf1 = r1
    id2, name2, ant2_json, cons2_json, conf2 = r2

    try:
        ant1 = json.loads(ant1_json)
        ant2 = json.loads(ant2_json)
        cons1 = json.loads(cons1_json)
        cons2 = json.loads(cons2_json)

        # 1. Crossover: Combine antecedents of rule 1 and rule 2
        combined_ant = ant1 + [x for x in ant2 if x not in ant1]
        # Crossover consequent: Choose one of them randomly
        new_cons = random.choice([cons1, cons2])

        # 2. Mutation: Randomly tweak the confidence
        mutated_conf = round(
            max(
                0.4,
                min(1.0, random.choice([conf1, conf2]) + random.uniform(-0.15, 0.15)),
            ),
            2,
        )

        new_rule_name = f"evolved_{name1[:6]}_{name2[:6]}_{random.randint(10, 99)}"

        logs.append(f"🧬 تزاوج (Crossover) بين القواعد:")
        logs.append(f"   - القاعدة 1: {name1}")
        logs.append(f"   - القاعدة 2: {name2}")
        logs.append(f"🧬 توليد الكروموسوم المعرفي الجديد:")
        logs.append(
            f"   - الشروط الهجينة: {json.dumps(combined_ant, ensure_ascii=False)}"
        )
        logs.append(
            f"   - النتيجة الموروثة: {json.dumps(new_cons, ensure_ascii=False)}"
        )
        logs.append(f"   - درجة اليقين المتطورة (مع الطفرة العشوائية): {mutated_conf}")

        conn = sqlite3.connect(prototype.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO rules (rule_name, antecedents, consequent, confidence, is_active)
            VALUES (?, ?, ?, ?, 1)
        """,
            (
                new_rule_name,
                json.dumps(combined_ant, ensure_ascii=False),
                json.dumps(new_cons, ensure_ascii=False),
                mutated_conf,
            ),
        )
        conn.commit()
        conn.close()
        logs.append(
            f"✨ نجاح البقاء للأصلح: تم تسجيل القاعدة المتطورة الجديدة [{new_rule_name}] في مستودع القوانين!"
        )
        evolved_count = 1
    except Exception as e:
        logs.append(f"⚠️ فشل حفظ القاعدة المتطورة: {e}")

    return {"status": "success", "logs": logs, "evolved_count": evolved_count}


@app.post("/api/thought_experiment/run")
def run_thought_experiment(req: ThoughtExperimentRequest):
    logs = [
        f"🔬 بدء تجربة فكرية افتراضية (Thought Experiment sandbox): '{req.hypothesis}'"
    ]

    # Save previous sandbox state
    prev_in_sandbox = prototype.in_sandbox
    prev_sandbox_graph = prototype.sandbox_graph

    prototype.in_sandbox = True
    prototype.sandbox_graph = prototype.graph.copy()  # Clone graph for sandbox

    hypothetical_edges = []
    contradictions = []

    try:
        # Parse the hypothesis with LLM in the sandbox
        parsed = prototype.parse_sentence_with_llm(
            req.hypothesis, req.provider.lower(), req.api_key, req.model, logs
        )
        if not parsed:
            raise ValueError("فشل تحليل فرضية التجربة الفكرية.")

        # Check for immediate contradictions in sandbox
        contradictions = prototype.check_contradictions(parsed)
        if contradictions:
            logs.append("⚠️ تم رصد تناقضات فورية مع الحقائق المسبقة:")
            for c in contradictions:
                logs.append(f"   - {c}")

        # Apply hypothetical premise to the sandbox graph
        prototype.learn_and_store(parsed, logs)
        logs.append("⚙️ تم إدخال الفرضية الافتراضية بنجاح إلى بيئة المحاكاة.")

        # Run a Sleep Cycle/Forward-chaining inside the sandbox to discover cascading consequences
        inferred = prototype.run_transitive_reasoning(logs)
        logs.append(
            f"🧠 استدلال تراجعي افتراضي: تم استنباط {len(inferred)} نتائج جديدة متسلسلة:"
        )
        for x in inferred:
            logs.append(f"   ➔ {x}")

        # Gather all newly introduced hypothetical concepts and relations
        for u, v, data in prototype.sandbox_graph.edges(data=True):
            if not prototype.graph.has_edge(u, v):
                hypothetical_edges.append(
                    {
                        "source": u,
                        "target": v,
                        "relation": data.get("relation", ""),
                        "confidence": data.get("confidence", 1.0),
                    }
                )

        logs.append(
            f"🔮 الخلاصة الفكرية: إدخال '{req.hypothesis}' قد يؤدي إلى تعديل {len(hypothetical_edges)} روابط دلالية في النظام المعرفي."
        )

    except Exception as e:
        logs.append(f"⚠️ فشل إجراء التجربة الفكرية: {str(e)}")
    finally:
        # Rollback the sandbox completely!
        prototype.in_sandbox = prev_in_sandbox
        prototype.sandbox_graph = prev_sandbox_graph

    return {
        "status": "success",
        "logs": logs,
        "hypothetical_edges": hypothetical_edges,
        "contradictions": contradictions,
    }


@app.post("/api/socratic/dialogue")
def run_socratic_dialogue(req: SocraticDialogueRequest):
    import random
    from neuro_symbolic_engine import call_llm_api

    logs = []
    t0 = time.time()
    update_progress(
        "المحاكاة والحوار السقراطي",
        "اختيار حقيقة منطقية عشوائية وتفكيك الروابط",
        1,
        3,
        t0,
    )

    try:
        graph = prototype.sandbox_graph if prototype.in_sandbox else prototype.graph

        # 1. Find a random factual relation from the triples
        edges = list(graph.edges(data=True))
        if not edges:
            update_progress(active=False)
            return {
                "status": "error",
                "response": "لا توجد معارف كافية في الذاكرة لبدء حوار سقراطي.",
                "logs": logs,
            }

        u, v, data = random.choice(edges)
        relation = data.get("relation", "")
        belief = f"{u} {relation} {v}"

        prompt = f"""
قم بإجراء حوار فلسفي سقراطي عميق باللغة العربية (سؤال وجواب) يدور حول تفكيك ومساءلة الحقيقة الدلالية التالية:
🚫 "إيمان العقل بـ: {belief}"

المدخلات:
أنت تلعب دورين:
1. "سقراط المشكك": يطرح أسئلة هادفة ومحرجة لتقصي صحة هذا الإيمان، مستخدماً المنطق الاحتمالي والاحتمالات المعاكسة.
2. "العقل المعرفي LEGEND": يحاول الدفاع عن إيمانه أو يقر بضعفه ويصحح ثقته بناءً على منطق الاحتمال والحوار الفلسفي.

صغ الحوار كسيناريو مسرحي مشوق وقصير (3 جولات على الأكثر)، ينتهي بقرار معرفي محدد:
- إما الاحتفاظ بالإيمان بقوة (Confidence = 1.0)
- أو تقليل الثقة فيه (Confidence = 0.5)
- أو نبذ الإيمان تماماً وحذفه (Confidence = 0.0)

صغ الحوار باللغة العربية الفصحى البليغة، وفي نهايته اكتب رمز خاص:
[DECISION] -> الاحتفاظ / التعديل / الحذف
"""

        update_progress(
            "المحاكاة والحوار السقراطي",
            f"توليد الحوار الفلسفي ومساءلة الثقة حول [{belief}]",
            2,
            3,
            t0,
        )
        response = call_llm_api(
            req.provider.lower(), req.api_key, req.model, prompt, logs
        )

        # Parse decision
        update_progress(
            "المحاكاة والحوار السقراطي",
            "تطبيق القرار وتعديل مستوى ثقة العلاقة في SQLite",
            3,
            3,
            t0,
        )
        decision = "الاحتفاظ"
        if "التعديل" in response or "تقليل" in response or "0.5" in response:
            decision = "التعديل"
            new_conf = 0.5
            prototype.save_triple_to_db(u, relation, v, confidence=new_conf)
            logs.append(
                f"🔄 الحوار السقراطي أدى إلى مراجعة الذات وتقليل ثقة العلاقة [{belief}] إلى 0.5!"
            )
        elif "الحذف" in response or "نبذ" in response or "0.0" in response:
            decision = "الحذف"
            prototype.delete_triple(u, relation, v)
            logs.append(
                f"❌ الحوار السقراطي كشف خللاً منطقياً أدى إلى نبذ وحذف العلاقة [{belief}] بالكامل!"
            )
        else:
            logs.append(
                f"✅ الحوار السقراطي عزز يقين العقل بالعلاقة [{belief}] وتم الاحتفاظ بها."
            )

        update_progress(active=False)
        return {
            "status": "success",
            "dialogue": response,
            "decision": decision,
            "belief": belief,
            "logs": logs,
        }
    except Exception as e:
        update_progress(active=False)
        return {
            "status": "error",
            "response": f"فشلت المحاكاة السقراطية: {e}",
            "logs": logs,
        }


@app.post("/api/absorb/text")
def absorb_knowledge(req: AbsorbRequest):
    import re

    logs = [
        "📥 بدء عملية امتصاص المعرفة السلبية الواسعة (Passive Knowledge Absorption)..."
    ]
    t0 = time.time()

    # Smart Text Chunking to preserve contextual references (like pronouns and contiguous facts)
    def chunk_text(text: str, max_chunk_size: int = 1500) -> List[str]:
        # Split by paragraph first (double/single newlines)
        paragraphs = re.split(r"\n+", text)
        chunks = []
        current_chunk = []
        current_length = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # If a single paragraph is too large, we must split it by sentences
            if len(para) > max_chunk_size:
                # Split by sentence terminators (. ? ! ؛ or newlines)
                sentences = re.split(r"([.?!؛]\s*)", para)
                reconstructed_sentences = []
                temp_sentence = ""
                for s in sentences:
                    if not s:
                        continue
                    if re.match(r"^[.?!؛]\s*$", s):
                        temp_sentence += s
                        reconstructed_sentences.append(temp_sentence.strip())
                        temp_sentence = ""
                    else:
                        if temp_sentence:
                            reconstructed_sentences.append(temp_sentence.strip())
                        temp_sentence = s
                if temp_sentence:
                    reconstructed_sentences.append(temp_sentence.strip())

                for sent in reconstructed_sentences:
                    if not sent:
                        continue
                    if current_length + len(sent) > max_chunk_size and current_chunk:
                        chunks.append(" ".join(current_chunk))
                        current_chunk = [sent]
                        current_length = len(sent)
                    else:
                        current_chunk.append(sent)
                        current_length += len(sent)
            else:
                if current_length + len(para) > max_chunk_size and current_chunk:
                    chunks.append(" ".join(current_chunk))
                    current_chunk = [para]
                    current_length = len(para)
                else:
                    current_chunk.append(para)
                    current_length += len(para)

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return [c.strip() for c in chunks if len(c.strip()) > 8]

    chunks = chunk_text(req.text)

    if not chunks:
        logs.append("⚠️ النص فارغ أو يحتوي على نصوص قصيرة جداً لا يمكن امتصاصها معرفياً.")
        update_progress(active=False)
        return {
            "status": "success",
            "logs": logs,
            "absorbed_count": 0,
            "contradictions_count": 0,
        }

    total_chunks = len(chunks)
    logs.append(
        f"📝 تم تقسيم النص دلالياً إلى {len(chunks)} فقرات معرفية متكاملة السياق لتجنب ضياع الضمائر والإشارات."
    )
    update_progress(
        "امتصاص المعرفة السلبية الواسعة",
        "تهيئة النص وجدولة المعالجة الاستباقية",
        0,
        total_chunks,
        t0,
    )

    absorbed_count = 0
    contradictions_count = 0

    try:
        for idx, chunk in enumerate(chunks):
            update_progress(
                "امتصاص المعرفة السلبية الواسعة",
                f"امتصاص الفقرة ({idx + 1}/{total_chunks}): '{chunk[:25]}...'",
                idx + 1,
                total_chunks,
                t0,
            )
            logs.append(
                f"🔄 معالجة الفقرة المعرفية ({idx + 1}/{total_chunks}): '{chunk[:100]}...'"
            )
            try:
                parsed = prototype.parse_sentence_with_llm(
                    chunk,
                    req.provider.lower(),
                    req.api_key,
                    req.model,
                    logs,
                    language=req.language,
                )
                if not parsed:
                    continue

                contradictions = prototype.check_contradictions(parsed)
                if contradictions:
                    logs.append(
                        f"   ⚠️ تم اكتشاف تناقض معرفي (سيتم تجاهل الأجزاء المتناقضة فقط):"
                    )
                    for c in contradictions:
                        logs.append(f"     - {c}")
                    contradictions_count += 1
                    # Do not 'continue' here; we want to save the REST of the non-contradicting facts!

                prototype.learn_and_store(parsed, logs)
                raw_entities = parsed.get(
                    "entities", parsed.get("الكيانات", parsed.get("كيانات", []))
                )
                relations = parsed.get(
                    "relations", parsed.get("العلاقات", parsed.get("علاقات", []))
                )
                entities_count = (
                    len(raw_entities)
                    if isinstance(raw_entities, list)
                    else len(raw_entities.keys())
                    if isinstance(raw_entities, dict)
                    else 0
                )
                relations_count = len(relations)
                absorbed_count += 1
                logs.append(
                    f"   ✅ تم امتصاص وتخزين الفقرة بنجاح (استخراج {entities_count} كيانات و {relations_count} علاقات دلالية)."
                )
            except Exception as e:
                import traceback

                logs.append(f"   ❌ خطأ أثناء معالجة الفقرة المعرفية: {e}")
                logs.append(f"   📋 تفاصيل الخطأ: {traceback.format_exc()[:500]}")
    finally:
        update_progress(active=False)

    logs.append(
        f"🎉 تم الانتهاء من دورة الامتصاص بنجاح: تم دمج {absorbed_count} فقرات معرفية مع تجنب {contradictions_count} تناقضات."
    )
    return {
        "status": "success",
        "logs": logs,
        "absorbed_count": absorbed_count,
        "contradictions_count": contradictions_count,
    }


@app.post("/api/workspace/diff")
def diff_workspaces(req: WorkspaceDiffRequest):
    workspaces = load_workspaces_dict()
    if req.other_workspace_name not in workspaces:
        raise HTTPException(status_code=404, detail="Workspace not found")

    other_ws = workspaces[req.other_workspace_name]
    other_db = other_ws.get("db_filename", "ontology.db")
    other_db_path = os.path.join(os.path.dirname(prototype.db_path), other_db)

    if not os.path.exists(other_db_path):
        return {"status": "error", "message": "قاعدة بيانات العقل الآخر غير موجودة."}

    other_proto = ArabicNeuroSymbolicPrototype(other_db_path)
    other_graph = other_proto.graph

    current_graph = prototype.sandbox_graph if prototype.in_sandbox else prototype.graph

    # 1. Added concepts (in other_graph but not in current_graph)
    added_concepts = []
    for node in other_graph.nodes:
        if not current_graph.has_node(node):
            added_concepts.append(node)

    # 2. Deleted concepts (in current_graph but not in other_graph)
    deleted_concepts = []
    for node in current_graph.nodes:
        if not other_graph.has_node(node):
            deleted_concepts.append(node)

    # 3. Diff triples
    added_triples = []
    deleted_triples = []
    conflicting_triples = []

    for u, v, data in other_graph.edges(data=True):
        pred = data.get("relation", "")
        if not current_graph.has_edge(u, v):
            added_triples.append(
                {
                    "subject": u,
                    "predicate": pred,
                    "object": v,
                    "confidence": data.get("confidence", 1.0),
                }
            )
        else:
            curr_pred = current_graph[u][v].get("relation", "")
            if curr_pred != pred:
                conflicting_triples.append(
                    {
                        "subject": u,
                        "predicate_current": curr_pred,
                        "predicate_other": pred,
                        "object": v,
                    }
                )

    for u, v, data in current_graph.edges(data=True):
        pred = data.get("relation", "")
        if not other_graph.has_edge(u, v):
            deleted_triples.append(
                {
                    "subject": u,
                    "predicate": pred,
                    "object": v,
                    "confidence": data.get("confidence", 1.0),
                }
            )

    return {
        "status": "success",
        "added_concepts": added_concepts,
        "deleted_concepts": deleted_concepts,
        "added_triples": added_triples,
        "deleted_triples": deleted_triples,
        "conflicting_triples": conflicting_triples,
    }


@app.post("/api/procedural/add")
def add_procedure(req: ProceduralAddRequest):
    try:
        conn = sqlite3.connect(prototype.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM procedural_steps WHERE procedure_name=?", (req.procedure_name,)
        )
        for idx, step in enumerate(req.steps):
            cursor.execute(
                """
                INSERT INTO procedural_steps (procedure_name, step_number, step_description)
                VALUES (?, ?, ?)
            """,
                (req.procedure_name, idx + 1, step),
            )
        conn.commit()
        conn.close()
        return {"status": "success", "message": "تم حفظ الإجراء المعرفي المبرمج بنجاح."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"تعذر حفظ الخطوات الإجرائية: {e}")


@app.get("/api/procedural/get")
def get_procedures():
    procedures = {}
    try:
        conn = sqlite3.connect(prototype.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT procedure_name, step_number, step_description FROM procedural_steps ORDER BY procedure_name, step_number"
        )
        rows = cursor.fetchall()
        conn.close()
        for name, num, desc in rows:
            if name not in procedures:
                procedures[name] = []
            procedures[name].append(desc)
    except Exception as e:
        print(f"Failed to fetch procedural steps: {e}")
    return procedures


@app.post("/api/federated/simulate")
def simulate_federated(req: FederatedSimulateRequest):
    import random

    logs = [
        "📡 الاتصال ببروتوكول الذكاء التعاوني الفيدرالي (Federated Cognitive simulated network)..."
    ]
    logs.append("🌐 البحث عن عقد أقران (P2P nodes) تمتلك معارف متخصصة عن الاستعلام...")

    q = req.query.strip()
    logs.append(f"🔍 إرسال حزم التقصي الدلالية عن: '{q}'")

    peers = ["العقل_دمشق_01", "العقل_بغداد_07", "العقل_القاهرة_12"]
    peer = random.choice(peers)
    logs.append(f"⚡ استجابة سريعة من القرين الفيدرالي [{peer}]:")

    concepts_found = []
    triples_found = []

    if any(k in q for k in ["فلك", "كوكب", "نجم", "مجرة"]):
        concepts_found = ["المشتري", "المريخ", "أورانوس"]
        triples_found = [
            {
                "subject": "المشتري",
                "predicate": "هو",
                "object": "كوكب غازي ضخم",
                "confidence": 0.98,
            },
            {
                "subject": "المريخ",
                "predicate": "يحتوي_على",
                "object": "أكسيد الحديد الأحمر",
                "confidence": 0.95,
            },
        ]
    elif any(k in q for k in ["طب", "صحة", "مرض", "علاج"]):
        concepts_found = ["الإنفلونزا", "فيتامين_سي", "المناعة"]
        triples_found = [
            {
                "subject": "فيتامين_سي",
                "predicate": "يقوي",
                "object": "المناعة البشرية",
                "confidence": 0.96,
            },
            {
                "subject": "الإنفلونزا",
                "predicate": "علاجها",
                "object": "الراحة والسوائل",
                "confidence": 0.90,
            },
        ]
    else:
        concepts_found = [f"{q}_الفيدرالي"]
        triples_found = [
            {
                "subject": q,
                "predicate": "يعرف_فيدرالياً_بـ",
                "object": f"مفهوم متقدم لدى {peer}",
                "confidence": 0.88,
            }
        ]

    for c in concepts_found:
        logs.append(f"   📥 تم استكشاف كيان: [{c}]")
    for t in triples_found:
        logs.append(
            f"   📥 تم استلام حقيقة: ({t['subject']} ➔ {t['predicate']} ➔ {t['object']})"
        )

    logs.append(
        "✨ تم تحميل الحزم المعرفية الفيدرالية بنجاح. جاهزة للدمج الفوري عند الطلب."
    )

    return {
        "status": "success",
        "peer": peer,
        "concepts": concepts_found,
        "triples": triples_found,
        "logs": logs,
    }


# End of Cognitive Suite Setup

SETTINGS_FILE = os.path.join(os.path.dirname(prototype.db_path), "settings.json")


class SettingsRequest(BaseModel):
    language: str


@app.get("/api/settings")
def get_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"language": "ar"}


@app.get("/api/local_models")
def get_local_models():
    models_dir = os.path.join(os.path.dirname(__file__), "models")
    if not os.path.exists(models_dir):
        return {"models": []}
    models = [f for f in os.listdir(models_dir) if f.endswith(".gguf")]
    return {"models": models}


@app.post("/api/settings")
def save_settings(req: SettingsRequest):
    try:
        settings = {}
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                settings = json.load(f)
        settings["language"] = req.language
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=4)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/workspace/export")
def export_workspace(name: Optional[str] = None):
    workspaces = load_workspaces_dict()
    target_name = name or ""
    current_db = os.path.basename(prototype.db_path)

    if not target_name:
        for k, v in workspaces.items():
            if v.get("db_filename") == current_db:
                target_name = k
                break

    if not target_name:
        target_name = "العقل العام (الافتراضي)"

    if target_name not in workspaces:
        raise HTTPException(status_code=404, detail="Workspace not found")

    ws_info = workspaces[target_name]
    db_filename = ws_info.get("db_filename", "ontology.db")
    db_file_path = os.path.join(os.path.dirname(prototype.db_path), db_filename)

    if not os.path.exists(db_file_path):
        return {
            "workspace_name": target_name,
            "mode": ws_info.get("mode", "active"),
            "concepts": [],
            "triples": [],
            "rules": [],
        }

    try:
        conn = sqlite3.connect(db_file_path)
        cursor = conn.cursor()

        # 1. Fetch Concepts
        cursor.execute(
            "SELECT name, super_type, properties, confidence, emotional_valence FROM concepts"
        )
        concepts_rows = cursor.fetchall()
        concepts = []
        for (
            r_name,
            super_type,
            props_json,
            confidence,
            emotional_valence,
        ) in concepts_rows:
            try:
                props = json.loads(props_json) if props_json else []
            except Exception:
                props = []
            concepts.append(
                {
                    "name": r_name,
                    "super_type": super_type,
                    "properties": props,
                    "confidence": confidence,
                    "emotional_valence": emotional_valence,
                }
            )

        # 2. Fetch Triples
        try:
            cursor.execute(
                "SELECT subject, predicate, object, valid_from, valid_to, confidence, emotional_valence, inferred FROM triples"
            )
            triples_rows = cursor.fetchall()
        except sqlite3.OperationalError:
            cursor.execute(
                "SELECT subject, predicate, object, valid_from, valid_to, confidence, emotional_valence FROM triples"
            )
            triples_rows = [r + (0,) for r in cursor.fetchall()]

        triples = []
        for (
            subject,
            predicate,
            obj,
            valid_from,
            valid_to,
            confidence,
            emotional_valence,
            inferred,
        ) in triples_rows:
            triples.append(
                {
                    "subject": subject,
                    "predicate": predicate,
                    "object": obj,
                    "valid_from": valid_from,
                    "valid_to": valid_to,
                    "confidence": confidence,
                    "emotional_valence": emotional_valence,
                    "inferred": inferred,
                }
            )

        # 3. Fetch Rules
        cursor.execute(
            "SELECT rule_name, antecedents, consequent, confidence, is_active FROM rules"
        )
        rules_rows = cursor.fetchall()
        rules = []
        for (
            rule_name,
            antecedents_json,
            consequent_json,
            confidence,
            is_active,
        ) in rules_rows:
            try:
                antecedents = json.loads(antecedents_json) if antecedents_json else []
            except Exception:
                antecedents = []
            try:
                consequent = json.loads(consequent_json) if consequent_json else []
            except Exception:
                consequent = []
            rules.append(
                {
                    "rule_name": rule_name,
                    "antecedents": antecedents,
                    "consequent": consequent,
                    "confidence": confidence,
                    "is_active": is_active,
                }
            )

        conn.close()

        return {
            "workspace_name": target_name,
            "mode": ws_info.get("mode", "active"),
            "concepts": concepts,
            "triples": triples,
            "rules": rules,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to export workspace: {str(e)}"
        )


@app.post("/api/workspace/import")
def import_workspace(req: WorkspaceImportRequest):
    workspaces = load_workspaces_dict()
    name = req.workspace_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Workspace name cannot be empty")

    if name not in workspaces:
        import uuid

        safe_db_name = f"ontology_{uuid.uuid4().hex[:8]}.db"
        workspaces[name] = {"db_filename": safe_db_name, "mode": req.mode or "active"}
        save_workspaces_dict(workspaces)
    else:
        safe_db_name = workspaces[name]["db_filename"]

    db_file_path = os.path.join(os.path.dirname(prototype.db_path), safe_db_name)

    try:
        conn = sqlite3.connect(db_file_path)
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
                inferred INTEGER DEFAULT 0,
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
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_triples_sub_pred ON triples(subject, predicate)"
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_triples_obj ON triples(object)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_concepts_super ON concepts(super_type)"
        )

        cursor.execute("DELETE FROM concepts")
        cursor.execute("DELETE FROM triples")
        cursor.execute("DELETE FROM rules")

        # 1. Insert Concepts
        for c in req.concepts:
            c_name = c.get("name")
            if not c_name:
                continue
            super_type = c.get("super_type")
            props = c.get("properties", [])
            conf = c.get("confidence", 1.0)
            valence = c.get("emotional_valence", 0.0)
            cursor.execute(
                """
                INSERT OR REPLACE INTO concepts (name, super_type, properties, confidence, emotional_valence, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    c_name,
                    super_type,
                    json.dumps(props, ensure_ascii=False),
                    conf,
                    valence,
                    int(time.time()),
                ),
            )

        # 2. Insert Triples
        for t in req.triples:
            subject = t.get("subject")
            predicate = t.get("predicate")
            obj = t.get("object")
            if not subject or not predicate or not obj:
                continue
            valid_from = t.get("valid_from")
            valid_to = t.get("valid_to")
            conf = t.get("confidence", 1.0)
            valence = t.get("emotional_valence", 0.0)
            inferred = t.get("inferred", 0)
            cursor.execute(
                """
                INSERT OR REPLACE INTO triples (subject, predicate, object, valid_from, valid_to, confidence, emotional_valence, created_at, inferred)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    subject,
                    predicate,
                    obj,
                    valid_from,
                    valid_to,
                    conf,
                    valence,
                    int(time.time()),
                    inferred,
                ),
            )

        # 3. Insert Rules
        for r in req.rules:
            rule_name = r.get("rule_name")
            if not rule_name:
                continue
            antecedents = r.get("antecedents", [])
            consequent = r.get("consequent", [])
            conf = r.get("confidence", 1.0)
            is_active = r.get("is_active", 1)
            cursor.execute(
                """
                INSERT OR REPLACE INTO rules (rule_name, antecedents, consequent, confidence, is_active)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    rule_name,
                    json.dumps(antecedents, ensure_ascii=False),
                    json.dumps(consequent, ensure_ascii=False),
                    conf,
                    is_active,
                ),
            )

        conn.commit()
        conn.close()

        if os.path.basename(prototype.db_path) == safe_db_name:
            prototype.load_graph_from_db()

        return {"status": "success", "workspace_name": name}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to import workspace: {str(e)}"
        )


@app.get("/api/workspace/export/rdf")
def export_workspace_rdf(format: str = "xml"):
    if format not in ["xml", "turtle"]:
        raise HTTPException(
            status_code=400, detail="Invalid format. Choose 'xml' or 'turtle'."
        )
    try:
        rdf_data = core_utils.export_to_rdf(
            prototype.sandbox_graph if prototype.in_sandbox else prototype.graph,
            format=format,
        )
        return {"rdf": rdf_data, "format": format}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/workspace/export/jsonld")
def export_workspace_jsonld():
    try:
        jsonld_data = core_utils.export_to_json_ld(
            prototype.sandbox_graph if prototype.in_sandbox else prototype.graph
        )
        return json.loads(jsonld_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/wikidata/enrich")
def enrich_from_wikidata(concept: str):
    try:
        result = core_utils.enrich_concept_from_wikidata(concept)
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=result.get("error"))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/workspace/predict-impact")
def predict_impact(concept: str):
    try:
        logs = []
        chain = prototype.predict_impact_chain(concept, logs=logs)
        return {"concept": concept, "impact_chain": chain, "logs": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
