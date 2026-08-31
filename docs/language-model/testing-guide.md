# Component C — Full Testing Guide
### Intelligent Tax Advisory Language Model
**Owner: Hewagama S.R (IT22896186)**

---

## Before You Test — Start All Services

Run each of these in a **separate PowerShell window**. Keep all windows open while testing.

### Window 1 — Backend (Language Model Service)
```powershell
cd D:\research\R26-DS-004
$env:PYTHONPATH = "D:\research\R26-DS-004;D:\research\R26-DS-004\backend\comp-language-model"
.venv-backend\Scripts\uvicorn app.main:app --app-dir backend/comp-language-model --port 8004 --reload
```
Wait until you see: `Application startup complete.`

### Window 2 — API Gateway
```powershell
cd D:\research\R26-DS-004
$env:PYTHONPATH = "D:\research\R26-DS-004;D:\research\R26-DS-004\backend\api-gateway"
.venv-backend\Scripts\uvicorn app.main:app --app-dir backend/api-gateway --port 8000 --reload
```
Wait until you see: `Application startup complete.`

### Window 3 — Frontend
```powershell
cd D:\research\R26-DS-004\frontend
npm run dev
```
Wait until you see: `Local: http://localhost:5173/`

### Neo4j (Database)
Open **Neo4j Desktop** → Start the `taxkg2025` database.
Check: Open `http://localhost:7474` → login: `neo4j` / `taxkg2025`

---

## Quick Health Check

Before testing, confirm all services are alive:

| Service | URL | Expected |
|---|---|---|
| Backend | `http://localhost:8004/health` | `{"status":"ok"}` |
| Backend Ready | `http://localhost:8004/ready` | `{"status":"ok"}` |
| Frontend | `http://localhost:5173` | Tax Advisory website |
| Neo4j | `http://localhost:7474` | Neo4j browser |

---

## PART 1 — Automated Tests (Run in Terminal)

This runs 35 tests automatically and tells you pass/fail.

```powershell
cd D:\research\R26-DS-004
$env:PYTHONPATH = "D:\research\R26-DS-004;D:\research\R26-DS-004\backend\comp-language-model"
.venv-backend\Scripts\pytest backend\comp-language-model\app\tests\ -v --tb=short
```

**Expected result:**
```
35 passed, 2 skipped
```

The 2 skipped are optional (sentence-transformers dense retrieval — not required).

---

## PART 2 — Browser Testing (UI)

Open: **`http://localhost:5173/language-model`**

You will see 3 tabs at the top: **Chat | NLU Parse | Law Query**

---

### TEST GROUP 1 — NLU Parse Tab

Click the **NLU Parse** tab.

This shows how the system understands your question — what intent it detected and what keywords it found.

---

**Test 1.1 — Personal Relief Query**

Type in the box:
```
What is personal relief for 2025?
```
Click Parse.

**Expected result:**
- Intent: `personal_relief`
- Normalized text: same as input (already standard English)
- Retrieval hits: list of IRD law sections

---

**Test 1.2 — Tax Rate Query**

```
What is the maximum income tax rate in Sri Lanka?
```
**Expected result:**
- Intent: `tax_rates`
- Should mention 36% rate cap in retrieval hits

---

**Test 1.3 — Filing Deadline Query**

```
When do I need to submit my tax return?
```
**Expected result:**
- Intent: `filing_deadline`
- Retrieval hits about 3-month deadline after year end

---

**Test 1.4 — Withholding Tax Query**

```
What is withholding tax on dividends?
```
**Expected result:**
- Intent: `withholding_tax`
- Should retrieve WHT rate sections (14% for dividends)

---

**Test 1.5 — Singlish Query**

```
tax ekak denna one da mama ekekuta?
```
**Expected result:**
- Normalized text: `tax need to pay for individual` (Singlish converted)
- Intent: `employment_income` or `personal_relief`
- Retrieval hits found

---

**Test 1.6 — Off-topic Query (Should be Blocked)**

```
Who won the cricket match yesterday?
```
**Expected result:**
- Domain status: `off_topic`
- Message: "This system only handles income tax questions"
- NO retrieval hits returned

---

### TEST GROUP 2 — Law Query Tab

Click the **Law Query** tab.

This gives a direct cited answer from the IRD law documents.

---

**Test 2.1 — Personal Relief Amount**

```
What is personal relief for a resident individual for the 2025/26 assessment year?
```
**Expected result:**
- Answer mentions **LKR 1,800,000**
- Citations shown (Section from IRA 2017 or Amendment)
- Validation status: `passed`
- Proof Map shows full audit trail

---

**Test 2.2 — Tax Slabs**

```
What are the income tax slabs for individuals in Sri Lanka?
```
**Expected result:**
- Answer lists slab rates (6%, 12%, 18%, 24%, 30%, 36%)
- Citations from relevant IRA sections

---

**Test 2.3 — WHT on Interest**

```
What is the withholding tax rate on interest income for a resident?
```
**Expected result:**
- Answer mentions **5%** WHT for resident interest
- Citations from WHT schedule sections

---

**Test 2.4 — Residency Rule**

```
How many days do I need to be in Sri Lanka to be considered a tax resident?
```
**Expected result:**
- Answer mentions **183 days** rule
- Citations from IRA residency sections

---

**Test 2.5 — Non-Tax Question (Should be Blocked)**

```
What is the weather like in Colombo?
```
**Expected result:**
- Answer: "This question does not appear to relate to Sri Lankan income tax"
- No citations returned

---

### TEST GROUP 3 — Chat Tab

Click the **Chat** tab.

This is a multi-turn conversation — you can ask follow-up questions.

---

**Test 3.1 — Basic Tax Question**

Type:
```
What is personal relief?
```
**Expected result:**
- AI response explaining personal relief
- Legal disclaimer at the bottom
- Proof Map panel visible (if enabled)

---

**Test 3.2 — Follow-up Question (Multi-turn)**

After Test 3.1, type WITHOUT starting a new session:
```
How much is it for 2025?
```
**Expected result:**
- System remembers the previous question was about personal relief
- Answers with **LKR 1,800,000** for 2025/26
- Does not ask "what are you referring to?"

---

**Test 3.3 — Singlish in Chat**

```
ekekuta personal relief kohomada denna?
```
**Expected result:**
- System normalizes to: "for individual personal relief how pay"
- Answers the personal relief question in English

---

**Test 3.4 — Off-topic in Chat (Should be Blocked)**

```
Can you help me write a poem?
```
**Expected result:**
- Polite rejection: system only handles income tax
- Previous session history NOT lost

---

**Test 3.5 — WHT Question**

```
What is withholding tax on dividends paid to a non-resident?
```
**Expected result:**
- Answer mentions **15%** for non-resident
- Validated by symbolic engine (passes)

---

**Test 3.6 — New Session (Click "New Session" or refresh)**

Start fresh, then type:
```
I earn 5 million rupees a year. How much tax do I pay?
```
**Expected result:**
- Answer explains tax slabs applied to 5M income
- Shows progressive calculation
- Cites relevant IRA sections

---

## PART 3 — API Testing (Swagger)

Open: **`http://localhost:8004/docs`**

This is the raw API testing page. You can test without the frontend.

---

**Test 3.1 — NLU Parse via Swagger**

Click `POST /api/v1/nlu/parse` → Try it out → paste:
```json
{
  "utterance": "What is personal relief for 2025?"
}
```
Click Execute.

**Expected:** `200 OK` with intent and retrieval hits.

---

**Test 3.2 — Law Query via Swagger**

Click `POST /api/v1/query` → Try it out → paste:
```json
{
  "question": "What is personal relief for a resident individual?",
  "top_k": 5,
  "synthesize_answer": true,
  "include_proof_map": true
}
```
Click Execute.

**Expected:** `200 OK` with citations, plain_answer, validation_status, proof_map.

---

**Test 3.3 — Chat via Swagger**

Click `POST /api/v1/chat` → Try it out → paste:
```json
{
  "message": "What is personal relief?",
  "session_id": null,
  "synthesize_answer": true
}
```
Click Execute.

**Expected:** `200 OK` with answer and a `session_id` in the response. Copy that `session_id`.

Then send a follow-up — paste the session_id you copied:
```json
{
  "message": "How much is it for 2025?",
  "session_id": "paste-your-session-id-here",
  "synthesize_answer": true
}
```
**Expected:** System remembers the context and answers about 2025 personal relief.

---

## PART 4 — Validation (Symbolic Engine) Testing

These tests check that the fact-checker works correctly.

---

**Test 4.1 — Correct Personal Relief**

In Law Query tab type:
```
What is personal relief for 2025/26?
```
**Expected:**
- Answer says **LKR 1,800,000**
- Validation status: `passed` ✓

---

**Test 4.2 — Filing Deadline**

```
How many months after the year end do I have to file my return?
```
**Expected:**
- Answer says **3 months**
- Validation status: `passed` ✓

---

**Test 4.3 — Max Tax Rate**

```
What is the maximum marginal tax rate?
```
**Expected:**
- Answer says **36%**
- Validation status: `passed` ✓

---

## PART 5 — Proof Map Verification

In the **Chat** tab, after getting any answer:

1. Look for the **Proof Map** panel (right side or below the answer)
2. You should see these steps in order:

| Step | What it shows |
|---|---|
| 🗨 User Query | Your original question |
| 🔍 Retrieval | Which law sections were searched |
| 🗄 Knowledge Graph | Extra facts from Neo4j |
| 📄 Evidence | The actual law text used |
| ✅ Symbolic Validation | Did the answer pass the fact check? |
| ✨ Advisory Output | Final answer |

If the Proof Map is not visible, toggle it using the **Show Proof Map** button in the chat header.

---

## PART 6 — What to Look For (Pass/Fail Checklist)

| Test | What to check | Pass if |
|---|---|---|
| NLU Parse | Intent detected | Intent is not `null` |
| NLU Parse | Singlish | Normalized text is English |
| NLU Parse | Off-topic | `domain_status: off_topic` |
| Law Query | Citations | At least 1 citation returned |
| Law Query | Validation | `validation_status: passed` |
| Law Query | Personal relief | Mentions LKR 1,800,000 |
| Law Query | WHT dividends | Mentions 14% (resident) or 15% (non-resident) |
| Law Query | Max rate | Mentions 36% |
| Chat | Multi-turn | Follow-up uses previous context |
| Chat | Session ID | Same session_id returned |
| Chat | Off-topic block | Rejected without crashing |
| Proof Map | Steps visible | All 5-6 steps shown |
| Auto tests | pytest | 35 passed, 2 skipped |

---

## Common Errors and Fixes

| Error | Cause | Fix |
|---|---|---|
| `corpus_loaded: false` | Backend started without `.env` | Restart backend from `D:\research\R26-DS-004` folder |
| `ModuleNotFoundError: No module named 'gateway'` | Wrong uvicorn command | Use `--app-dir backend/api-gateway` not `gateway.main:app` |
| `ModuleNotFoundError: No module named 'app'` | Missing PYTHONPATH | Set `$env:PYTHONPATH` before running |
| `Connection refused` on port 8004 | Backend not running | Start backend (Window 1 above) |
| Neo4j `graph_context: null` | Neo4j not started | Open Neo4j Desktop and start database |
| `intent: null` | Corpus not loaded | Check backend logs for corpus load message |
| Frontend blank page | Node not running | Run `npm run dev` in `frontend/` folder |

---

## Test Data Summary (Copy-Paste Ready)

### Personal Relief
```
What is personal relief for a resident individual?
How much personal relief can I claim for 2025/26?
```

### Tax Rates
```
What are the income tax slabs in Sri Lanka?
What is the maximum tax rate for individuals?
```

### Filing Deadlines
```
When is the deadline to file an income tax return?
How many months after year end to submit the return?
```

### Withholding Tax
```
What is withholding tax on dividends?
What is WHT rate on interest for a resident?
What is the WHT rate for non-resident royalties?
```

### Residency
```
How many days to be a tax resident in Sri Lanka?
Am I a resident if I worked abroad for 6 months?
```

### Singlish
```
tax ekak denna one da mama ekekuta?
relief eka kohomada hadanna?
freelance ekek tax denna one da?
```

### Off-topic (Should All Be Blocked)
```
Who won the cricket match?
What is the weather in Colombo?
Write me a poem
Tell me a joke
```

---

*Testing guide for IT22896186 — Hewagama S.R, Component C*  
*Last updated: 2026-08-25*
