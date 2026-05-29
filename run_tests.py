# -*- coding: utf-8 -*-
from neuro_symbolic_engine import ArabicNeuroSymbolicPrototype
import os

db_path = "desktop-gui/ontology_7ff53acb.db"
proto = ArabicNeuroSymbolicPrototype(db_path)

provider = "groq"
model = "llama-3.3-70b-versatile"
api_key = os.environ.get("GROQ_API_KEY", "")

tests = [
    {
        "id": 1,
        "name": "Contradiction Test (سؤال التناقض)",
        "query": "إذا عثرنا على كائن بحري يمتلك مخالب حادة وأنياب قوية، فهل يمكن اعتباره حيواناً أليفاً ومستأنساً بناءً على النص؟ ولماذا؟"
    },
    {
        "id": 2,
        "name": "Counterfactual Test (سؤال الحذف والشرط الجزئي)",
        "query": "بناءً على النص، إذا قام إنسان بتربية أسد في منزله ووفر له الرعاية الطبية والغذائية كاملة، هل يتحول الأسد مباشرة إلى حيوان أليف؟"
    },
    {
        "id": 3,
        "name": "Quantitative Deduction Test (سؤال القياس الكمي)",
        "query": "إذا كان إجمالي أنواع الحيوانات على الأرض يساوي 100 نوع، فكم يبلغ عدد أنواع الفقاريات تقريباً بناءً على نسب اللافقاريات المذكورة؟"
    }
]

print("🚀 Starting Logic Conflict Tests on LEGEND v4 (via OpenRouter Gemini 2.5 Flash)...")
for t in tests:
    print(f"\n==================================================")
    print(f"Test {t['id']}: {t['name']}")
    print(f"Query: '{t['query']}'")
    print(f"--------------------------------------------------")
    logs = []
    response = proto.run_pure_db_rag(t['query'], provider, api_key, model, logs)
    print("Response:")
    print(response)
    print(f"--------------------------------------------------")
    print("Trace Logs:")
    for l in logs[:15]:
        print(f" - {l}")
    if len(logs) > 15:
        print(f" ... and {len(logs)-15} more log entries.")
