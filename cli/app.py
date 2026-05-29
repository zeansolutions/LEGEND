# -*- coding: utf-8 -*-
"""
app.py - Clean FastAPI web server exposing LEGEND Arabic Neuro-Symbolic reasoning API
and hosting the interactive premium web demo interface.
"""

import os
import sys
import json
import sqlite3
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

# Add directory to sys path to import engine.py and parent modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import ArabicReasoningEngine, normalize_arabic, call_llm_api
from cognitive_engine import CognitiveInferenceEngine, CognitiveCuriosityEngine, CognitiveSleepCycle

app = FastAPI(
    title="LEGEND Neuro-Symbolic API",
    description="A production-ready clean API for hallucination-free Arabic reasoning engines.",
    version="4.0.0"
)

# Enable CORS for cross-origin frontend queries
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize reasoning engine using a local database path inside the roadmap folder
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ontology.db")
engine = ArabicReasoningEngine(DB_PATH)

# =========================================================================
# Pydantic Schema Definitions
# =========================================================================

class SentenceRequest(BaseModel):
    sentence: str
    provider: str
    api_key: str
    model: str

class LLMRequest(BaseModel):
    provider: str
    api_key: str
    model: str

class HypothesisRequest(BaseModel):
    hypothesis: str
    provider: str
    api_key: str
    model: str

class RelationDeleteRequest(BaseModel):
    source: str
    relation: str
    target: str

class NodeDeleteRequest(BaseModel):
    name: str

class PLNRequest(BaseModel):
    concept_a: str
    concept_b: str

class RuleCreateRequest(BaseModel):
    rule_name: str
    antecedents: List[List[str]]
    consequent: List[str]
    confidence: float = 1.0

class WorkspaceImportRequest(BaseModel):
    workspace_name: str
    mode: Optional[str] = "active"
    concepts: List[Dict[str, Any]]
    triples: List[Dict[str, Any]]
    rules: List[Dict[str, Any]]


# =========================================================================
# Cognitive and Semantic REST API Endpoints
# =========================================================================

@app.get("/api/stats")
def get_stats():
    """Gather metrics, node counts, and sizes of the ontology database."""
    try:
        stats = engine.gather_db_statistics()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")

@app.get("/api/local_models")
def get_local_models():
    """Retrieve list of locally downloaded .gguf models."""
    models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
    if not os.path.exists(models_dir):
        return {"models": []}
    models = [f for f in os.listdir(models_dir) if f.endswith(".gguf")]
    return {"models": models}

@app.get("/api/graph")
def get_graph():
    """Extract nodes, edges, relations, and weights in JSON for real-time visualization."""
    graph = engine.sandbox_graph if engine.in_sandbox else engine.graph
    
    nodes = []
    for node, data in graph.nodes(data=True):
        nodes.append({
            "id": node,
            "type": data.get("type", "concept"),
            "super_type": data.get("super_type", ""),
            "confidence": data.get("confidence", 1.0),
            "properties": data.get("properties", [])
        })
        
    edges = []
    for u, v, data in graph.edges(data=True):
        edges.append({
            "source": u,
            "target": v,
            "relation": data.get("relation", ""),
            "confidence": data.get("confidence", 1.0)
        })
        
    return {
        "nodes": nodes,
        "edges": edges,
        "in_sandbox": engine.in_sandbox,
        "strict_mode": engine.strict_mode
    }

@app.post("/api/learn")
def learn_fact(req: SentenceRequest):
    """Parse input sentence, run semantic mapping, contradiction filters, and store triple."""
    logs = []
    try:
        # 1. Parse Arabic statement with LLM to extract entities and triples
        parsed = engine.parse_sentence_with_llm(req.sentence, req.provider, req.api_key, req.model, logs)
        if not parsed:
            raise HTTPException(status_code=422, detail="فشل استخلاص الحقائق الدلالية من النص.")
            
        # 2. Check for ontological contradictions before database commit
        contradictions = engine.check_contradictions(parsed)
        if contradictions:
            return {
                "status": "contradiction",
                "contradictions": contradictions,
                "logs": logs,
                "parsed": parsed
            }
            
        # 3. Commit to permanent DB and network memory
        engine.learn_and_store(parsed, logs)
        
        return {
            "status": "success",
            "logs": logs,
            "parsed": parsed
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        logs.append(f"❌ خطأ غير متوقع: {str(e)}")
        return {
            "status": "error",
            "logs": logs,
            "response": f"حدث خطأ أثناء معالجة الجملة: {str(e)}"
        }

@app.post("/api/query")
def query_fact(req: SentenceRequest):
    """Answer question strictly based on database ontology with clean multi-hop logical trace."""
    logs = []
    try:
        # Answer via strictly verified logical context in prompt (Pure DB Reasoning)
        response = engine.run_pure_db_rag(req.sentence, req.provider, req.api_key, req.model, logs)
        
        return {
            "status": "success",
            "response": response,
            "logs": logs
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        logs.append(f"❌ خطأ غير متوقع: {str(e)}")
        return {
            "status": "error",
            "logs": logs,
            "response": f"فشل إجراء الاستعلام المعرفي: {str(e)}"
        }

@app.post("/api/pln")
def run_pln(req: PLNRequest):
    """Run PLN calculations across logical hops with cascading weight multiplication."""
    logs = []
    result = engine.run_probabilistic_inference(req.concept_a, req.concept_b, logs)
    return {"result": result, "logs": logs}

@app.get("/api/rules")
def get_rules():
    """Retrieve active logical rules from SQLite database."""
    rules_list = []
    try:
        conn = sqlite3.connect(engine.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT rule_name, antecedents, consequent, confidence FROM rules WHERE is_active = 1 ORDER BY confidence DESC")
        rows = cursor.fetchall()
        for row in rows:
            rule_name = row[0]
            try:
                antecedents = json.loads(row[1])
            except Exception:
                antecedents = []
            try:
                consequent = json.loads(row[2])
            except Exception:
                consequent = []
            confidence = row[3]
            
            # Formatting display names for visual user tables
            rel_ant = "علاقة غير معروفة"
            if isinstance(antecedents, list) and len(antecedents) > 0:
                relations = [ant[1] for ant in antecedents if isinstance(ant, list) and len(ant) >= 2]
                rel_ant = " & ".join(relations) if relations else "علاقة"
                
            rel_cons = "علاقة غير معروفة"
            if isinstance(consequent, list):
                if len(consequent) >= 3 and isinstance(consequent[1], str):
                    rel_cons = consequent[1]
                elif len(consequent) > 0 and isinstance(consequent[0], list) and len(consequent[0]) >= 2:
                    rel_cons = consequent[0][1]
            elif isinstance(consequent, str):
                rel_cons = consequent
                
            rules_list.append({
                "rule_name": rule_name,
                "antecedents": antecedents,
                "antecedent": {"relation": rel_ant},
                "consequent": {"relation": rel_cons},
                "support": len(antecedents) if isinstance(antecedents, list) else 1,
                "confidence": confidence
            })
        conn.close()
    except Exception as e:
        print(f"Failed to fetch rules: {e}")
    return rules_list

@app.post("/api/rules/induct")
def run_rule_induction():
    """Trigger pattern mining inside memory graph to discover new global transitivity rules."""
    logs = []
    new_rules = engine.self_improve_rule_induction(logs)
    return {"new_rules_count": len(new_rules), "logs": logs}

@app.post("/api/rules/evolve")
def evolve_rules():
    """Genetic algorithm: crossover antecedents and mutate certainty levels of surviving rules."""
    import random
    logs = ["🧬 بدء محاكاة التطور الجيني للقواعد المعرفية (Genetic Rule Evolution)..."]
    
    try:
        conn = sqlite3.connect(engine.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, rule_name, antecedents, consequent, confidence FROM rules")
        rows = cursor.fetchall()
        conn.close()
    except Exception as e:
        return {"status": "error", "message": f"تعذر استرجاع القواعد: {e}"}
        
    if len(rows) < 2:
        logs.append("⚠️ لا يوجد عدد كافٍ من القواعد المسجلة (مطلوب قاعدتين على الأقل للتزاوج الجيني).")
        return {"status": "success", "logs": logs, "evolved_count": 0}
        
    evolved_count = 0
    r1, r2 = random.sample(rows, 2)
    id1, name1, ant1_json, cons1_json, conf1 = r1
    id2, name2, ant2_json, cons2_json, conf2 = r2
    
    try:
        ant1 = json.loads(ant1_json)
        ant2 = json.loads(ant2_json)
        cons1 = json.loads(cons1_json)
        cons2 = json.loads(cons2_json)
        
        # 1. Crossover: Merge antecedents together
        combined_ant = ant1 + [x for x in ant2 if x not in ant1]
        new_cons = random.choice([cons1, cons2])
        
        # 2. Mutation: Jitter confidence score within [-0.15, +0.15] range
        mutated_conf = round(max(0.4, min(1.0, random.choice([conf1, conf2]) + random.uniform(-0.15, 0.15))), 2)
        new_rule_name = f"evolved_{name1[:6]}_{name2[:6]}_{random.randint(10,99)}"
        
        logs.append(f"🧬 تزاوج (Crossover) بين القواعد:")
        logs.append(f"   - القاعدة 1: {name1}")
        logs.append(f"   - القاعدة 2: {name2}")
        logs.append(f"🧬 توليد الشروط الهجينة: {json.dumps(combined_ant, ensure_ascii=False)}")
        logs.append(f"   - النتيجة الموروثة: {json.dumps(new_cons, ensure_ascii=False)}")
        logs.append(f"   - درجة اليقين المتطورة (مع الطفرة العشوائية): {mutated_conf}")
        
        conn = sqlite3.connect(engine.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO rules (rule_name, antecedents, consequent, confidence, is_active)
            VALUES (?, ?, ?, ?, 1)
        """, (new_rule_name, json.dumps(combined_ant, ensure_ascii=False), json.dumps(new_cons, ensure_ascii=False), mutated_conf))
        conn.commit()
        conn.close()
        logs.append(f"✨ نجاح البقاء للأصلح: تم تسجيل القاعدة المتطورة الجديدة [{new_rule_name}] في قاعدة البيانات!")
        evolved_count = 1
    except Exception as e:
        logs.append(f"⚠️ فشل حفظ القاعدة المتطورة: {e}")
        
    return {"status": "success", "logs": logs, "evolved_count": evolved_count}

@app.post("/api/clear")
def clear_database():
    """Truncate the SQLite tables and reload empty memory state."""
    success = engine.clear_all_data()
    if success:
        return {"status": "success", "message": "تم تصفير العقل المعرفي وقاعدة البيانات خالية تماماً الآن."}
    else:
        raise HTTPException(status_code=500, detail="فشل تصفير قاعدة البيانات.")

@app.post("/api/relation/delete")
def delete_relation_endpoint(req: RelationDeleteRequest):
    """Delete a specific semantic triple."""
    src = normalize_arabic(req.source)
    tgt = normalize_arabic(req.target)
    pred = normalize_arabic(req.relation)
    success = engine.delete_relation(src, pred, tgt)
    if success:
        return {"status": "success", "message": "تم حذف العلاقة الدلالية بنجاح."}
    else:
        raise HTTPException(status_code=500, detail="فشل حذف العلاقة الدلالية.")

@app.post("/api/node/delete")
def delete_node_endpoint(req: NodeDeleteRequest):
    """Delete concept node and cascades across associated edges."""
    normalized_name = normalize_arabic(req.name)
    success = engine.delete_node(normalized_name)
    if success:
        return {"status": "success", "message": "تم حذف الكيان بنجاح مع كافة علاقاته."}
    else:
        raise HTTPException(status_code=500, detail="فشل حذف الكيان.")

@app.get("/api/triples/latest")
def get_latest_triples():
    """Fetch direct triples added in the very last learning session."""
    triples = []
    for subj, pred, obj in engine.last_relations:
        triples.append({
            "source": subj,
            "relation": pred,
            "target": obj
        })
    return {"triples": triples}

@app.delete("/api/triples/latest")
def delete_latest_triples():
    """Delete all direct triples added in the very last learning session."""
    if not engine.last_relations:
        return {"status": "success", "deleted_count": 0, "message": "لا توجد روابط مضافة حديثاً لحذفها."}
        
    deleted_count = 0
    for subj, pred, obj in list(engine.last_relations):
        success = engine.delete_relation(subj, pred, obj)
        if success:
            deleted_count += 1
            
    engine.last_relations = []
    return {"status": "success", "deleted_count": deleted_count, "message": f"تم حذف {deleted_count} من العلاقات المضافة حديثاً."}

@app.get("/api/triples")
def get_triples(page: int = 1, limit: int = 20, query: Optional[str] = None):
    """Retrieve all semantic relations with pagination, searching across sources, relations, and targets."""
    try:
        conn = sqlite3.connect(engine.db_path)
        cursor = conn.cursor()
        
        if query:
            normalized_query = normalize_arabic(query)
            sql_count = "SELECT COUNT(*) FROM triples WHERE subject LIKE ? OR predicate LIKE ? OR object LIKE ?"
            params = (f"%{normalized_query}%", f"%{normalized_query}%", f"%{normalized_query}%")
            cursor.execute(sql_count, params)
            total = cursor.fetchone()[0]
            
            sql_select = "SELECT subject, predicate, object, confidence, created_at FROM triples WHERE subject LIKE ? OR predicate LIKE ? OR object LIKE ? ORDER BY created_at DESC LIMIT ? OFFSET ?"
            cursor.execute(sql_select, params + (limit, (page - 1) * limit))
        else:
            cursor.execute("SELECT COUNT(*) FROM triples")
            total = cursor.fetchone()[0]
            
            cursor.execute("SELECT subject, predicate, object, confidence, created_at FROM triples ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, (page - 1) * limit))
            
        rows = cursor.fetchall()
        conn.close()
        
        triples = []
        for subject, predicate, obj, confidence, created_at in rows:
            triples.append({
                "source": subject,
                "relation": predicate,
                "target": obj,
                "confidence": confidence,
                "created_at": created_at
            })
            
        return {
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit if limit > 0 else 0,
            "triples": triples
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch triples: {str(e)}")

@app.delete("/api/triples")
def delete_triple_by_match(req: RelationDeleteRequest):
    """Delete a specific semantic triple RESTfully using a JSON payload."""
    src = normalize_arabic(req.source)
    tgt = normalize_arabic(req.target)
    pred = normalize_arabic(req.relation)
    success = engine.delete_relation(src, pred, tgt)
    if success:
        return {"status": "success", "message": "تم حذف العلاقة الدلالية بنجاح."}
    else:
        raise HTTPException(status_code=500, detail="فشل حذف العلاقة الدلالية.")

@app.delete("/api/concepts/{concept_name}")
def delete_concept_by_name(concept_name: str):
    """Delete concept node completely with cascading deletions of all its connected relations."""
    normalized_name = normalize_arabic(concept_name)
    success = engine.delete_node(normalized_name)
    if success:
        return {"status": "success", "message": f"تم حذف الكيان '{concept_name}' بنجاح مع كافة علاقاته المرتبطة."}
    else:
        raise HTTPException(status_code=500, detail=f"فشل حذف الكيان '{concept_name}'.")

@app.post("/api/rules")
def add_custom_rule(req: RuleCreateRequest):
    """Add or update a logical reasoning rule manually to the SQLite database."""
    try:
        conn = sqlite3.connect(engine.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO rules (rule_name, antecedents, consequent, confidence, is_active)
            VALUES (?, ?, ?, ?, 1)
        """, (req.rule_name, json.dumps(req.antecedents, ensure_ascii=False), json.dumps(req.consequent, ensure_ascii=False), req.confidence))
        conn.commit()
        conn.close()
        return {"status": "success", "message": f"تم إدراج/تحديث القاعدة المنطقية [{req.rule_name}] بنجاح."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"فشل إدراج القاعدة المنطقية: {str(e)}")

@app.delete("/api/rules/{rule_name}")
def delete_rule_by_name(rule_name: str):
    """Delete a specific logical rule from the rules SQLite table."""
    try:
        conn = sqlite3.connect(engine.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM rules WHERE rule_name = ?", (rule_name,))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        if deleted > 0:
            return {"status": "success", "message": f"تم حذف القاعدة [{rule_name}] بنجاح."}
        else:
            return {"status": "success", "message": f"القاعدة [{rule_name}] غير موجودة بالفعل."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"فشل حذف القاعدة المنطقية: {str(e)}")

@app.post("/api/sleep")
def sleep_cycle():
    try:
        sleep_eng = CognitiveSleepCycle(engine)
        stats = sleep_eng.run_sleep_cycle()
        return {
            "status": "success",
            "message": "اكتملت دورة النوم المعرفية بنجاح وتم تقوية ودمج العلاقات المعرفية في الذاكرة.",
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"فشل تشغيل دورة النوم الدلالية: {e}")

@app.get("/api/curiosity")
def get_curiosity_questions(limit: int = 5):
    try:
        curiosity_eng = CognitiveCuriosityEngine(engine)
        questions = curiosity_eng.generate_questions(limit=limit)
        gaps = curiosity_eng.find_knowledge_gaps()
        return {
            "status": "success",
            "questions": questions,
            "gaps": gaps[:10]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"فشل تشغيل محرك الفضول: {e}")

@app.post("/api/inference")
def trigger_manual_inference():
    try:
        inf_eng = CognitiveInferenceEngine(engine)
        logs = []
        inferred = inf_eng.run_inference(logs=logs)
        return {
            "status": "success",
            "message": f"اكتمل الاستدلال الحر بنجاح. تم استنتاج {len(inferred)} علاقة جديدة.",
            "inferred_count": len(inferred),
            "inferred": [{"subject": s, "predicate": p, "object": o, "confidence": c} for s, p, o, c in inferred],
            "logs": logs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"فشل تشغيل محرك الاستدلال: {e}")

@app.post("/api/thought_experiment/run")
def run_thought_experiment(req: HypothesisRequest):
    """Spin a hypothetical clone sandbox graph to run thought experiments without corrupting reality."""
    logs = [f"🔬 بدء تجربة فكرية افتراضية (Hypothetical Thought Sandbox): '{req.hypothesis}'"]
    
    prev_in_sandbox = engine.in_sandbox
    prev_sandbox_graph = engine.sandbox_graph
    
    engine.in_sandbox = True
    engine.sandbox_graph = engine.graph.copy() # Clone the current graph
    
    hypothetical_edges = []
    contradictions = []
    
    try:
        # Parse logic rules within the sandbox boundary
        parsed = engine.parse_sentence_with_llm(req.hypothesis, req.provider, req.api_key, req.model, logs)
        if not parsed:
            raise ValueError("فشل تحليل فرضية التجربة الفكرية.")
            
        contradictions = engine.check_contradictions(parsed)
        if contradictions:
            logs.append("⚠️ تم رصد تناقضات فورية مع الحقائق المسبقة:")
            for c in contradictions:
                logs.append(f"   - {c}")
                
        engine.learn_and_store(parsed, logs)
        logs.append("⚙️ تم إدخال الفرضية الافتراضية بنجاح إلى بيئة المحاكاة.")
        
        # Deduct cascade effects in the sandbox
        inferred = engine.run_transitive_reasoning(logs)
        logs.append(f"🧠 استدلال تراجعي افتراضي: تم استنباط {len(inferred)} نتائج جديدة متسلسلة:")
        for x in inferred:
            logs.append(f"   ➔ {x}")
            
        for u, v, data in engine.sandbox_graph.edges(data=True):
            if not engine.graph.has_edge(u, v):
                hypothetical_edges.append({
                    "source": u,
                    "target": v,
                    "relation": data.get("relation", ""),
                    "confidence": data.get("confidence", 1.0)
                })
                
        logs.append(f"🔮 الخلاصة: إدخال '{req.hypothesis}' قد يؤدي إلى تعديل {len(hypothetical_edges)} روابط دلالية في النظام المعرفي.")
        
    except Exception as e:
        logs.append(f"⚠️ فشل إجراء التجربة الفكرية: {str(e)}")
    finally:
        # Absolutely destroy and roll back the sandbox
        engine.in_sandbox = prev_in_sandbox
        engine.sandbox_graph = prev_sandbox_graph
        
    return {
        "status": "success",
        "logs": logs,
        "hypothetical_edges": hypothetical_edges,
        "contradictions": contradictions
    }

@app.post("/api/socratic/dialogue")
def run_socratic_dialogue(req: LLMRequest):
    """Run auto-skeptic Socratic dialogues pitting custom prompts against beliefs to update confidence bounds."""
    import random
    logs = []
    graph = engine.sandbox_graph if engine.in_sandbox else engine.graph
    
    # 1. Grab random active belief from graph edges
    edges = list(graph.edges(data=True))
    if not edges:
        return {"status": "error", "response": "لا توجد معارف كافية في الذاكرة لبدء حوار سقراطي.", "logs": logs}
        
    u, v, data = random.choice(edges)
    relation = data.get("relation", "")
    belief = f"{u} {relation} {v}"
    
    prompt = f"""
قم بإجراء حوار فلسفي سقراطي عميق باللغة العربية (سؤال وجواب) يدور حول تفكيك ومساءلة الحقيقة الدلالية التالية:
🚫 "إيمان العقل بـ: {belief}"

المدخلات:
أنت تلعب دورين:
1. "سقراط المشكك": يطرح أسئلة هادفة ومحرجة لتقصي صحة هذا الإيمان، مستخدماً المنطق الاحتمالي والاحتمالات المعاكسة.
2. "العقل المعرفي LEGEND": يحاول الدفاع عن إيمانه أو يقر بضعفه ويصحح ثقته بناءً على حوار سقراط الفلسفي.

صغ الحوار كسيناريو مسرحي مشوق وقصير (3 جولات على الأكثر)، ينتهي بقرار معرفي محدد:
- إما الاحتفاظ بالإيمان بقوة (Confidence = 1.0)
- أو تعديل وتقليل الثقة فيه (Confidence = 0.5)
- أو نبذ الإيمان تماماً وحذفه (Confidence = 0.0)

صغ الحوار باللغة العربية الفصحى البليغة، وفي نهايته اكتب رمز خاص:
[DECISION] -> الاحتفاظ / التعديل / الحذف
"""
    
    try:
        response = call_llm_api(req.provider, req.api_key, req.model, prompt, logs)
        
        decision = "الاحتفاظ"
        if "التعديل" in response or "تقليل" in response or "0.5" in response:
            decision = "التعديل"
            new_conf = 0.5
            engine.save_triple_to_db(u, relation, v, confidence=new_conf)
            logs.append(f"🔄 الحوار السقراطي أدى إلى مراجعة الذات وتقليل ثقة العلاقة [{belief}] إلى 0.5!")
        elif "الحذف" in response or "نبذ" in response or "0.0" in response:
            decision = "الحذف"
            engine.delete_triple(u, relation, v)
            logs.append(f"❌ الحوار السقراطي كشف خللاً منطقياً أدى إلى نبذ وحذف العلاقة [{belief}] بالكامل!")
        else:
            logs.append(f"✅ الحوار السقراطي عزز يقين العقل بالعلاقة [{belief}] وتم الاحتفاظ بها.")
            
        return {
            "status": "success",
            "dialogue": response,
            "decision": decision,
            "belief": belief,
            "logs": logs
        }
    except Exception as e:
        return {"status": "error", "response": f"فشلت المحاكاة السقراطية: {str(e)}", "logs": logs}


# =========================================================================
# API Service Health Endpoint
# =========================================================================

@app.get("/api/workspace/export")
def export_workspace(name: Optional[str] = None):
    target_name = name or "العقل العام (الافتراضي)"
    db_file_path = engine.db_path
    
    if not os.path.exists(db_file_path):
        return {
            "workspace_name": target_name,
            "mode": "active",
            "concepts": [],
            "triples": [],
            "rules": []
        }
        
    try:
        conn = sqlite3.connect(db_file_path)
        cursor = conn.cursor()
        
        # 1. Fetch Concepts
        cursor.execute("SELECT name, super_type, properties, confidence, emotional_valence FROM concepts")
        concepts_rows = cursor.fetchall()
        concepts = []
        for r_name, super_type, props_json, confidence, emotional_valence in concepts_rows:
            try:
                props = json.loads(props_json) if props_json else []
            except Exception:
                props = []
            concepts.append({
                "name": r_name,
                "super_type": super_type,
                "properties": props,
                "confidence": confidence,
                "emotional_valence": emotional_valence
            })
            
        # 2. Fetch Triples
        try:
            cursor.execute("SELECT subject, predicate, object, valid_from, valid_to, confidence, emotional_valence, inferred FROM triples")
            triples_rows = cursor.fetchall()
        except sqlite3.OperationalError:
            cursor.execute("SELECT subject, predicate, object, valid_from, valid_to, confidence, emotional_valence FROM triples")
            triples_rows = [r + (0,) for r in cursor.fetchall()]
            
        triples = []
        for subject, predicate, obj, valid_from, valid_to, confidence, emotional_valence, inferred in triples_rows:
            triples.append({
                "subject": subject,
                "predicate": predicate,
                "object": obj,
                "valid_from": valid_from,
                "valid_to": valid_to,
                "confidence": confidence,
                "emotional_valence": emotional_valence,
                "inferred": inferred
            })
            
        # 3. Fetch Rules
        cursor.execute("SELECT rule_name, antecedents, consequent, confidence, is_active FROM rules")
        rules_rows = cursor.fetchall()
        rules = []
        for rule_name, antecedents_json, consequent_json, confidence, is_active in rules_rows:
            try:
                antecedents = json.loads(antecedents_json) if antecedents_json else []
            except Exception:
                antecedents = []
            try:
                consequent = json.loads(consequent_json) if consequent_json else []
            except Exception:
                consequent = []
            rules.append({
                "rule_name": rule_name,
                "antecedents": antecedents,
                "consequent": consequent,
                "confidence": confidence,
                "is_active": is_active
            })
            
        conn.close()
        
        return {
            "workspace_name": target_name,
            "mode": "active",
            "concepts": concepts,
            "triples": triples,
            "rules": rules
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export workspace: {str(e)}")

@app.post("/api/workspace/import")
def import_workspace(req: WorkspaceImportRequest):
    name = req.workspace_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Workspace name cannot be empty")
        
    db_file_path = engine.db_path
    
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
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_triples_sub_pred ON triples(subject, predicate)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_triples_obj ON triples(object)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_concepts_super ON concepts(super_type)")
        
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
            cursor.execute("""
                INSERT OR REPLACE INTO concepts (name, super_type, properties, confidence, emotional_valence, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (c_name, super_type, json.dumps(props, ensure_ascii=False), conf, valence, int(time.time())))
            
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
            cursor.execute("""
                INSERT OR REPLACE INTO triples (subject, predicate, object, valid_from, valid_to, confidence, emotional_valence, created_at, inferred)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (subject, predicate, obj, valid_from, valid_to, conf, valence, int(time.time()), inferred))
            
        # 3. Insert Rules
        for r in req.rules:
            rule_name = r.get("rule_name")
            if not rule_name:
                continue
            antecedents = r.get("antecedents", [])
            consequent = r.get("consequent", [])
            conf = r.get("confidence", 1.0)
            is_active = r.get("is_active", 1)
            cursor.execute("""
                INSERT OR REPLACE INTO rules (rule_name, antecedents, consequent, confidence, is_active)
                VALUES (?, ?, ?, ?, ?)
            """, (rule_name, json.dumps(antecedents, ensure_ascii=False), json.dumps(consequent, ensure_ascii=False), conf, is_active))
            
        conn.commit()
        conn.close()
        
        engine.load_graph_from_db()
            
        return {"status": "success", "workspace_name": name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to import workspace: {str(e)}")

@app.get("/", response_class=JSONResponse)
def api_health():
    """Returns a simple API status health block instead of the removed web demo."""
    return {
        "status": "online",
        "engine": "LEGEND Arabic Neuro-Symbolic Reasoning Engine",
        "version": "4.0.0",
        "documentation": "To inspect the API definitions, use the interactive terminal via: ./start.sh --terminal"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
