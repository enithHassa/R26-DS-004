# My Component — Simple Guide
### Component C: Intelligent Tax Advisory Language Model
**Owner: Hewagama S.R (IT22896186)**

---

## What is my component?

Your component is like a **smart chatbot that knows Sri Lankan tax law**.

You type a question like *"What is personal relief for 2025?"* and it:
1. Understands what you are asking
2. Searches through real IRD (Inland Revenue Department) documents
3. Finds the exact law that answers your question
4. Generates a plain English answer
5. Double-checks the answer against real numbers (like LKR 1,800,000 for personal relief)
6. Shows you exactly where the answer came from (which law, which section)

It is part of a bigger AI Tax Advisory system (4 components total). Your component is **Component C — the language model brain** of the whole system.

---

## What can it do?

| Feature | What it means in simple words |
|---|---|
| **Chat** | Have a back-and-forth conversation about taxes |
| **Law Query** | Ask a direct tax law question and get a cited answer |
| **NLU Parse** | Shows how the system understood your question (intent + keywords) |
| **Singlish Support** | Understands mixed Sinhala-English like *"tax ekak denna one da"* |
| **Proof Map** | Shows the full reasoning — which law was found, was it validated |
| **Off-topic Block** | If you ask about cricket or weather, it politely refuses |
| **Knowledge Graph** | Connected to a Neo4j tax knowledge database for extra facts |
| **Symbolic Validation** | Checks generated answers against hard-coded tax rules (no hallucination) |

---

## How does it work? (Simple version)

Think of it like a **smart librarian + fact-checker**:

```
You ask a question
        ↓
Step 1: Clean up your question (fix Singlish, informal words)
        ↓
Step 2: Is this a tax question? → NO → "Sorry, I only answer tax questions"
        ↓ YES
Step 3: Search IRD documents → Find the best matching law sections
        ↓
Step 4: Rank results (newer laws ranked higher than old ones)
        ↓
Step 5: Look up extra facts from the Tax Knowledge Graph (Neo4j)
        ↓
Step 6: Send everything to Gemini AI → Generate a plain English answer
        ↓
Step 7: Check the answer — is the personal relief amount correct?
        Is the tax rate below 36%? → If wrong → replace with safe message
        ↓
Step 8: Return answer + which laws were cited + full audit trail (Proof Map)
```

---

## The 4 parts of your component

### 1. Backend (The Brain) — Port 8004
This is the Python FastAPI server. It does all the thinking.
- File location: `backend/comp-language-model/`
- Main file: `app/main.py`
- It handles 3 routes: `/nlu`, `/query`, `/chat`

### 2. Database (The Memory) — Port 7687
This is Neo4j — a graph database storing tax knowledge.
- Stores: Tax concepts, relief amounts, rate bands, law relationships
- Example: It knows that "personal relief" links to "LKR 1,800,000" for 2025/26

### 3. API Gateway (The Door) — Port 8000
This is the single entry point for all requests.
- Your browser talks to port 8000
- Gateway forwards to port 8004 (your component)

### 4. Frontend (The Face) — Port 5173
This is the React website you see in the browser.
- Has 3 pages: Chat, NLU Parse, Law Query
- File location: `frontend/src/features/language-model/`

---

## How to run the project (Step by Step)

> **Important:** Always run these in order. Neo4j must start first.

---

### Step 1 — Start Neo4j (Tax Knowledge Database)

Open Neo4j Desktop app on your computer and click **Start** on the `taxkg2025` database.

Or if using the service version, it is already running on port **7687**.

**How to check:** Open your browser → go to `http://localhost:7474`
You should see the Neo4j browser. Login: `neo4j` / `taxkg2025`

---

### Step 2 — Start the Backend (Language Model Service)

Open a **new PowerShell window** and run:

```powershell
cd D:\research\R26-DS-004

$env:PYTHONPATH = "D:\research\R26-DS-004;D:\research\R26-DS-004\backend\comp-language-model"

.venv-backend\Scripts\uvicorn app.main:app --app-dir backend/comp-language-model --port 8004 --reload
```

**How to check:** Open browser → `http://localhost:8004/docs`
You should see the Swagger API documentation page.

---

### Step 3 — Start the API Gateway

Open a **new PowerShell window** and run:

```powershell
cd D:\research\R26-DS-004

.venv-backend\Scripts\python -m uvicorn gateway.main:app --port 8000 --reload
```

Or check if it is already running:
```powershell
netstat -ano | findstr ":8000"
```

---

### Step 4 — Start the Frontend (Website)

Open a **new PowerShell window** and run:

```powershell
cd D:\research\R26-DS-004\frontend

npm run dev
```

**How to check:** Open browser → `http://localhost:5173`
You should see the Tax Advisory website.

---

### Step 5 — Open your component in the browser

Go to: **`http://localhost:5173/language-model`**

You will see three tabs:
- **Chat** — Talk to the tax advisor
- **NLU Parse** — See how your question is understood
- **Law Query** — Get a cited law answer

---

## Quick test inputs to try

Once everything is running, try these:

**In Chat tab:**
```
What is personal relief for 2025?
```
Expected: Answer mentioning LKR 1,800,000

```
When is the tax return deadline?
```
Expected: Answer about 3 months after year end

**Test off-topic block:**
```
Who won the cricket match?
```
Expected: "This system only handles income tax questions"

**Test Singlish:**
```
tax ekak denna one da mama ekekuta?
```
Expected: Normalized to English and answered

---

## How to run tests

Open PowerShell and run:

```powershell
cd D:\research\R26-DS-004

$env:PYTHONPATH = "D:\research\R26-DS-004;D:\research\R26-DS-004\backend\comp-language-model"

.venv-backend\Scripts\pytest backend\comp-language-model\app\tests\ -v --tb=short
```

Expected result: **35 tests passed** ✓

---

## File structure (what each folder does)

```
D:\research\R26-DS-004\
│
├── backend\comp-language-model\      ← YOUR COMPONENT (backend)
│   └── app\
│       ├── main.py                   ← Starts the server
│       ├── config.py                 ← All settings
│       ├── routers\
│       │   ├── chat.py               ← Chat conversation route
│       │   ├── query.py              ← Law query route
│       │   └── nlu.py                ← NLU parse route
│       ├── services\
│       │   ├── query_pipeline.py     ← Main logic (retrieval + validation)
│       │   ├── query_preprocess.py   ← Singlish normalizer
│       │   ├── symbolic_engine.py    ← Fact checker
│       │   ├── think_twice.py        ← Validation loop
│       │   ├── lex_rank.py           ← Lex Specialis reranker
│       │   ├── proof_map.py          ← Audit trail builder
│       │   └── chat_session.py       ← Conversation memory
│       └── tests\                    ← 35 automated tests
│
├── frontend\src\features\language-model\  ← YOUR COMPONENT (frontend)
│   ├── pages\
│   │   └── chat.tsx                  ← Chat UI page
│   ├── components\
│   │   └── proof-map-panel.tsx       ← Audit trail display
│   ├── api.ts                        ← API calls to backend
│   └── types.ts                      ← Data types
│
├── data\processed\ird\
│   ├── corpus_v1.jsonl               ← 1200+ IRD law chunks
│   └── intent_benchmark_v1.jsonl    ← 55 training examples
│
├── reasoning\
│   └── symbolic_rules_v1.json        ← Hard tax rules (relief, rates, WHT)
│
└── .env                              ← API keys and settings
```

---

## Important settings (.env file)

Your `.env` file has these key settings:

| Setting | What it does |
|---|---|
| `COMP_LLM_GEMINI_API_KEY` | Your Gemini AI key (for generating answers) |
| `COMP_LLM_ANSWER_SYNTHESIS_ENABLED=true` | Turns on AI answer generation |
| `COMP_LLM_THINK_TWICE_ENABLED=true` | Turns on fact checking |
| `COMP_LLM_PROOF_MAP_ENABLED=true` | Turns on audit trail |
| `NEO4J_PASSWORD=taxkg2025` | Your database password |
| `COMP_LLM_RETRIEVAL_TOP_K=8` | Returns top 8 law chunks per query |

---

## What makes your component special?

Most chatbots just guess. Your component:

1. **Only answers from real law** — Every answer is backed by an actual IRD document section
2. **Respects legal hierarchy** — A 2025 amendment beats a 2017 base Act automatically
3. **Checks its own answers** — If it says personal relief is LKR 2,000,000 (wrong), it catches the error and refuses to show it
4. **Shows its work** — The Proof Map shows every step: what was found, what was validated, what was cited
5. **Handles Sri Lankan language** — Works even if you type in Singlish

---

*Guide written for IT22896186 — Hewagama S.R, Component C owner*
*Last updated: 2026-08-25*
