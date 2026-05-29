# 🔌 Headless Developer API Reference (LEGEND Developer Portal)

Welcome to the **LEGEND Neuro-Symbolic Developer Reference**. The backend FastAPI server serves as the cognitive powerhouse of the entire platform. It exposes a robust, headless REST API that allows any external client or application to interface with the logical ontology, trigger cognitive cycles, ingestion sessions, and run zero-hallucination queries.

---

## 🌐 Base Connection Metadata
* **Local Endpoint:** `http://127.0.0.1:8000`
* **Default Content-Type:** `application/json`
* **Response Format:** JSON

---

## 📌 Complete API Endpoint Map

| Endpoint | Method | Category | Description |
| :--- | :--- | :--- | :--- |
| `/` | `GET` | System | Retrieve server health and system overview status. |
| `/api/stats` | `GET` | Metrics | Fetch ontology statistics, size of the SQLite DB, and node connectivity counts. |
| `/api/local_models` | `GET` | Models | Discover local GGUF models downloaded in the `/models` directory. |
| `/api/learn` | `POST` | Cognition | Ingest a natural language sentence into the ontology after contradiction checks. |
| `/api/query` | `POST` | Cognition | Query the database with **100% hallucination-free, grounded multi-hop RAG**. |
| `/api/pln` | `POST` | Logic | Run Probabilistic Logic Network weight multiplication across hops. |
| `/api/triples/latest` | `GET` | Storage | Retrieve all semantic triples ingested during the very last learn session. |
| `/api/triples/latest` | `DELETE`| Storage | Roll back and delete all triples ingested during the last learn session. |
| `/api/triples` | `GET` | Storage | Retrieve all database triples with support for Arabic query search and pagination. |
| `/api/triples` | `DELETE`| Storage | Delete a specific semantic triple RESTfully using a JSON body match. |
| `/api/concepts/{name}` | `DELETE`| Storage | Cascading delete a concept node along with all its connected relations. |
| `/api/rules` | `GET` | Logic | Retrieve active logical rules currently stored in the SQLite database. |
| `/api/rules` | `POST` | Logic | Manually inject or update a symbolic reasoning rule inside the SQLite database. |
| `/api/rules/{name}` | `DELETE`| Logic | Delete a specific logical reasoning rule from the ontology by its unique name. |
| `/api/rules/induct` | `POST` | Cognition | Auto-scan semantic graph patterns to generate new transitivity rules. |
| `/api/rules/evolve` | `POST` | Cognition | Breed active rules and mutate certainty factors using a Genetic Algorithm. |
| `/api/sleep` | `POST` | Cognition | Trigger Hebbian consolidation, memory optimization, and weak relation pruning. |
| `/api/curiosity` | `GET` | Cognition | Scan network structures for knowledge gaps and generate question prompt ideas. |
| `/api/inference` | `POST` | Cognition | Manually trigger recursive forward-chaining logical deduction across the graph. |
| `/api/socratic/dialogue` | `POST` | Cognition | Spin an internal Socratic debate questioning deep beliefs to adjust confidence. |
| `/api/thought_experiment/run`| `POST` | Sandbox | Run counterfactual simulations on an isolated temporary clone sandbox. |
| `/api/clear` | `POST` | Storage | Wipe the SQLite database and restore the engine to default settings. |

---

## 📡 Model Configurations & Routing

LEGEND supports multiple LLM providers. Requests targeting reasoning endpoints (such as `learn`, `query`, `socratic`, and `thought_experiment`) must pass a valid configuration structure.

### Supported Providers
1. **Google:** Integrates Gemini models (default model: `gemini-2.5-flash`).
2. **Groq:** Integrates OpenAI-compatible high-speed endpoints (default model: `llama-3.3-70b-versatile`).
3. **OpenRouter:** Dynamic proxy to global foundational models (default model: `google/gemini-2.5-flash`).
4. **Local:** Bypasses API key requirements and runs offline inference on local hardware using `.gguf` files loaded via `llama_cpp`.

---

## ⚡ Endpoint Reference with Payloads & Response Examples

### 1. Ingest a Fact (`POST /api/learn`)
Parses natural language input, matches it onto current taxonomies, runs a contradiction filter, and commits the resulting triple to permanent memory.

* **Payload Structure:**
```json
{
  "sentence": "Ahmed is a Software Engineer, and he works at Google.",
  "provider": "google",
  "model": "gemini-2.5-flash",
  "api_key": "YOUR_API_KEY_HERE"
}
```

* **Offline Local Execution Payload:**
```json
{
  "sentence": "احمد مهندس برمجيات ويعمل في جوجل.",
  "provider": "local",
  "model": "qwen2.5-7b-instruct-q4_k_m.gguf",
  "api_key": "local"
}
```

* **Successful Response:**
```json
{
  "status": "success",
  "logs": [
    "🧠 [Learning]: Concept created: Ahmed -> type: Human",
    "🧠 [Learning]: Concept created: Google -> type: Corporation",
    "🧠 [Learning]: Fact ingested: (Ahmed ➔ works_at ➔ Google) with confidence 1.00",
    "💾 [Storage Sync]: Saved 2 concepts and 1 triple to SQLite successfully."
  ],
  "parsed": {
    "entities": [
      {"name": "Ahmed", "type": "Human", "confidence": 1.0},
      {"name": "Google", "type": "Corporation", "confidence": 1.0}
    ],
    "relations": [
      {"subject": "Ahmed", "relation": "works_at", "object": "Google", "confidence": 1.0}
    ]
  }
}
```

* **Contradiction Clashes Block Response:**
```json
{
  "status": "contradiction",
  "contradictions": [
    "🚨 [Disjointness Conflict]: Concept 'Google' cannot be defined as 'Human' because it is already registered as a 'Corporation'."
  ]
}
```

---

### 2. Zero-Hallucination Query (`POST /api/query`)
Queries the ontology strictly based on verified logical triples, completely insulating the model from inventing data.

* **Payload Structure:**
```json
{
  "sentence": "Where does Ahmed work?",
  "provider": "google",
  "model": "gemini-2.5-flash",
  "api_key": "YOUR_API_KEY_HERE"
}
```

* **Response Example:**
```json
{
  "status": "success",
  "response": "Ahmed works at Google. This is verified by the contract/ontology fact (Ahmed ➔ works_at ➔ Google) registered in the database.",
  "logs": [
    "🔍 [Query Engine]: Matched keyword concepts: Ahmed, Google",
    "🌐 [Subgraph Extraction]: Isolated 3 direct nodes and Hebbian paths",
    "🤖 [Neural Synthesis]: Compiling safe natural language report strictly using DB facts."
  ]
}
```

---

### 3. Hebbian Sleep & Consolidation Cycle (`POST /api/sleep`)
Simulates biological sleep cycles. Hebbian weight reinforcement occurs for frequent pathways, while vague relationships (confidence drops below `0.35`) are automatically pruned to keep logical processing fast and clean.

* **Trigger Request (No Body Required):**
```bash
curl -X POST http://127.0.0.1:8000/api/sleep
```

* **Response Example:**
```json
{
  "status": "success",
  "message": "Cognitive sleep cycle successfully completed.",
  "stats": {
    "synonyms_linked": 2,
    "new_inferences": 4,
    "edges_strengthened": 12,
    "dream_discoveries": 1,
    "edges_pruned": 3,
    "noise_nodes_cleaned": 1
  }
}
```

---

### 4. Socratic Internal Debate Dialogue (`POST /api/socratic/dialogue`)
Simulates an internal philosophy script between a Skeptic Socrates role and the system's core beliefs. Misplaced high-confidence assumptions are challenged, potentially revising belief trusts down or deleting them entirely.

* **Payload Structure:**
```json
{
  "provider": "google",
  "model": "gemini-2.5-flash",
  "api_key": "YOUR_API_KEY_HERE"
}
```

* **Response Example:**
```json
{
  "status": "success",
  "belief": "Ahmed ➔ works_at ➔ Google",
  "decision": "REVISED (Confidence updated to 0.50)",
  "dialogue": "[Socrates]: Why do we assert Ahmed is active at Google?\n[Engine]: Because a fact was learned from natural language text.\n[Socrates]: Has Ahmed's contract expired? Can we assume absolute permanence?\n[Engine]: Indeed, conditions change. I shall reflect and adjust certainty bounds...",
  "logs": [
    "🎭 [Socratic dialogue launched successfully]",
    "🔄 [Confidence Revised]: Ahmed works_at Google updated to 0.50 due to temporal uncertainty."
  ]
}
```

---

### 5. Hypothetical Sandbox Thought Experiment (`POST /api/thought_experiment/run`)
Spins a temporary clones of the active concept network inside RAM. Users can test complex counterfactual hypothesis (e.g., *"What if Google goes bankrupt?"*) to study logical cascades without corrupting main production tables.

* **Payload Structure:**
```json
{
  "hypothesis": "Google goes bankrupt.",
  "provider": "google",
  "model": "gemini-2.5-flash",
  "api_key": "YOUR_API_KEY_HERE"
}
```

* **Response Example:**
```json
{
  "status": "success",
  "logs": [
    "🔬 [Sandbox]: Cloned active memory graph (18 nodes, 34 edges)",
    "🔬 [Sandbox]: Ingesting hypothetical condition...",
    "🧠 [Reasoning Engine]: Triggering forward-chaining rules...",
    "💀 [Reasoning Engine]: Ahmed works_at Google (inferred confidence dropped to 0.00)",
    "🔬 [Sandbox]: Closed sandbox environment and purged RAM."
  ],
  "contradictions": [],
  "hypothetical_edges": [
    {"source": "Ahmed", "relation": "unemployed", "target": "Market", "confidence": 0.90}
  ]
}
```

---

### 6. Dynamic Genetic Rule Evolution (`POST /api/rules/evolve`)
Exposes active transitivity rules to dynamic crossovers and mutations, optimizing confidence parameters over generations.

* **Trigger Request:**
```bash
curl -X POST http://127.0.0.1:8000/api/rules/evolve
```

* **Response Example:**
```json
{
  "status": "success",
  "logs": [
    "🧬 [Genetic Evolution]: Selecting parents...",
    "🧬 [Genetic Evolution]: Parent 1: transitive_is_a, Parent 2: transitive_works_in",
    "🧬 [Crossover]: Merging antecedents and mutating certainty bounds",
    "🧬 [Mutation]: New rule evolved: evolved_trans_is_a_works_in_42 with confidence 0.88",
    "✨ [Storage]: Registered evolved logical rule successfully."
  ],
  "evolved_count": 1
}
```

---

## 🚀 Cloud & Production Deployments

The backend engine is designed to be **Stateless** (with the single exception of the local SQLite database). It can be deployed in seconds to major PaaS providers like Render, Railway, or Heroku.

### Sample Build Command
```bash
pip install -r requirements.txt
```

### Sample Startup Command
```bash
uvicorn app:app --host 0.0.0.0 --port $PORT
```

*Note: You can expose `GEMINI_API_KEY` or `GROQ_API_KEY` as Server Environment Variables to bypass API Key parameter requests on standard, client-facing payloads.*
