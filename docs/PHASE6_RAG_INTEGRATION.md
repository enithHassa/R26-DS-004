# Phase 6: RAG Relief System Integration with Relief Interview UI

**Status:** Planning  
**Date:** 2026-08-24  
**Objective:** Connect RAG extraction system with Relief Interview & Catalog Admin UIs for dynamic relief discovery

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Relief Interview UI (Frontend)            │
│  - Show reliefs for selected year                            │
│  - Merge hardcoded + RAG-generated reliefs                   │
│  - Track relief source (static vs. dynamic)                  │
└──────────────────────────┬──────────────────────────────────┘
                           │
                    ┌──────▼─────┐
                    │  API Route  │
                    │  :8000/rag  │
                    └──────┬──────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│              Catalog Admin - RAG Review (Frontend)            │
│  - Show RAG-extracted reliefs awaiting approval              │
│  - Display confidence scores & audit decision UI             │
│  - Approve / Reject / Flag for manual review                 │
│  - Once approved, add to approved catalog                    │
└──────────────────────────┬──────────────────────────────────┘
                           │
          ┌────────────────▼────────────────┐
          │   RAG Component (Port 8007)     │
          │  - Extract reliefs from PDFs    │
          │  - Confidence scoring           │
          │  - Database storage & audit log │
          └────────────────┬────────────────┘
                           │
          ┌────────────────▼────────────────┐
          │  PostgreSQL (Azure)             │
          │  - rag_relief_chunks            │
          │  - rag_relief_extractions       │
          │  - rag_relief_audit_log         │
          └─────────────────────────────────┘
```

---

## Phase 6 Milestones

### Milestone 1: API Gateway Integration (Backend)
**Goal:** Expose RAG endpoints through the API Gateway

**Tasks:**
1. Register `/api/v1/rag-relief/**` routes in API Gateway
   - POST `/api/v1/rag-relief/ingest/pdf` → forward to :8007/ingest/pdf
   - POST `/api/v1/rag-relief/retrieve/search` → forward to :8007/retrieve/search
   - POST `/api/v1/rag-relief/extract/relief` → forward to :8007/extract/relief
   - GET `/api/v1/rag-relief/*/status` → health checks

2. Add database views/stored procedures
   - View: `rag_relief_extracted_by_year` (join extractions with chunks)
   - View: `rag_relief_pending_approval` (status = 'pending')
   - Procedure: `approve_rag_extraction(extraction_id, auditor_email)`
   - Procedure: `reject_rag_extraction(extraction_id, rejection_reason)`

**Deliverable:** 
- API Gateway forwards all /api/v1/rag-relief/* routes to RAG component
- Database ready for auditor approval workflow

---

### Milestone 2: Catalog Admin - RAG Review UI (Frontend)
**Goal:** Allow auditors to review & approve RAG-extracted reliefs

**New Pages:**
1. **Catalog Admin → RAG Review**
   - Tab: "Pending RAG Extractions"
   - Shows: relief name, confidence score, extracted amount, section ref, quote
   - Actions: Approve (→ add to approved catalog) | Reject (with reason) | Flag for manual review
   - Displays confidence breakdown: relief_name, cap_amount, effective_date, overall
   - Red/yellow/green indicators based on confidence

2. **Query for:** 
   ```
   GET /api/v1/rag-relief/extractions/pending
   GET /api/v1/rag-relief/extractions/pending?assessment_year=2023_24
   ```

3. **Actions:**
   ```
   POST /api/v1/rag-relief/extractions/{extraction_id}/approve
   POST /api/v1/rag-relief/extractions/{extraction_id}/reject
   ```

**Deliverable:**
- Catalog Admin has new "RAG Review" section
- Auditors can see, filter, approve/reject RAG extractions
- Approved extractions become part of that year's relief catalog

---

### Milestone 3: Relief Interview Integration (Frontend)
**Goal:** Show RAG-generated reliefs in the interview when they're confidence-approved

**Approach:**
1. **Fetch Strategy:**
   - Current: `GET /relief-interview/approved/{year}` (hardcoded)
   - **New:** Merge two sources:
     - Hardcoded approved reliefs (current)
     - RAG-approved extractions for that year (new)

2. **Data Transformation:**
   - Convert RAG extraction → ApprovedEntry type
   ```typescript
   {
     entry_id: extraction_id (from RAG),
     compare_group_id: "rag_relief_" + sanitize(relief_name),
     display_name: relief_name,
     question_prompt: "How much can you claim for {relief_name}?",
     cap_amount: cap_amount (from extraction),
     section_ref: section_ref,
     quote: quote,
     source_doc_id: source_act,
     needs_manual_verification: confidence_overall < 0.85,
     engine_binding: { kind: "none" } // RAG reliefs don't auto-affect tax yet
   }
   ```

3. **Display Indicators:**
   - Badge: "RAG" for RAG-extracted reliefs
   - Tooltip: "Extracted from {source_act}, Section {section_ref}, Confidence {score}%"
   - Warning icon if `needs_manual_verification` is true

4. **API Changes:**
   - Keep existing `/relief-interview/approved/{year}` endpoint
   - **New:** Merge logic can be in frontend (React Query) or backend (simpler)
   - **Recommendation:** Merge in frontend to keep backend stateless

**Deliverable:**
- Relief Interview shows both hardcoded + RAG-approved reliefs for selected year
- Clear visual distinction between sources
- Users see most up-to-date relief information

---

## Implementation Strategy

### Option A: Frontend-Driven Merge (Recommended)
```typescript
// frontend/src/features/adaptive-tax/api.ts

export async function getReliefInterviewApprovedWithRag(
  assessmentYear: string
): Promise<ReliefInterviewApprovedYear> {
  // Fetch hardcoded reliefs
  const hardcodedResponse = await adaptiveTaxApi.get(
    `/relief-interview/approved/${encodeURIComponent(assessmentYear)}`
  );
  
  // Fetch RAG-approved extractions for this year
  const ragResponse = await adaptiveTaxApi.get(
    `/rag-relief/extractions/approved-by-year/${encodeURIComponent(assessmentYear)}`
  );
  
  // Transform RAG extractions to ApprovedEntry format
  const ragEntries = (ragResponse.data.extractions || []).map(
    (extraction) => ragExtractionToApprovedEntry(extraction)
  );
  
  // Merge (avoid duplicates by compare_group_id)
  const existingGroupIds = new Set(
    hardcodedResponse.data.entries.map(e => e.compare_group_id)
  );
  const uniqueRagEntries = ragEntries.filter(
    e => !existingGroupIds.has(e.compare_group_id)
  );
  
  return {
    ...hardcodedResponse.data,
    entries: [...hardcodedResponse.data.entries, ...uniqueRagEntries],
  };
}
```

### Option B: Backend-Driven Merge
- Modify Adaptive Tax component to call RAG API
- Merge reliefs server-side before returning
- Simpler frontend, but adds coupling

**Decision:** Go with **Option A** (frontend merge) for cleaner separation.

---

## Database Schema Updates

### New Views

```sql
-- View: RAG reliefs approved for each year
CREATE VIEW rag_relief_extracted_by_year AS
SELECT 
  e.extraction_id,
  e.relief_name,
  e.cap_amount,
  e.source_act,
  e.section_ref,
  e.confidence_overall,
  e.status,
  e.approved_by,
  e.approved_at,
  -- Extract year from source_act (e.g., "2017", "2022", "2023")
  COALESCE(
    (regexp_matches(e.source_act, '\d{4}'))[1],
    '2023'
  ) AS act_year
FROM rag_relief_extractions e
WHERE e.status = 'approved';
```

### New Stored Procedures

```sql
-- Approve an extraction and create audit log entry
CREATE OR REPLACE FUNCTION approve_rag_extraction(
  extraction_id UUID,
  auditor_email VARCHAR,
  auditor_notes TEXT DEFAULT NULL
)
RETURNS VOID AS $$
BEGIN
  UPDATE rag_relief_extractions
  SET 
    status = 'approved',
    approved_by = auditor_email,
    approved_at = NOW(),
    auditor_notes = auditor_notes,
    updated_at = NOW()
  WHERE extraction_id = extraction_id;
  
  INSERT INTO rag_relief_audit_log 
    (operation, user_email, pdf_filename, success, details)
  SELECT
    'approve',
    auditor_email,
    e.source_act,
    true,
    jsonb_build_object(
      'extraction_id', extraction_id,
      'relief_name', e.relief_name,
      'confidence', e.confidence_overall
    )
  FROM rag_relief_extractions e
  WHERE e.extraction_id = extraction_id;
END;
$$ LANGUAGE plpgsql;
```

---

## API Endpoints

### Backend: RAG Component (Port 8007)

**Already Implemented:**
- `POST /ingest/pdf` - Upload & process PDF
- `POST /retrieve/search` - Hybrid search
- `POST /extract/relief` - Extract relief with confidence

### New: API Gateway (Port 8000)

Register these routes:
```
POST   /api/v1/rag-relief/ingest/pdf
GET    /api/v1/rag-relief/ingest/status
POST   /api/v1/rag-relief/retrieve/search
GET    /api/v1/rag-relief/retrieve/keyword
GET    /api/v1/rag-relief/retrieve/semantic
POST   /api/v1/rag-relief/extract/relief
GET    /api/v1/rag-relief/extract/status
GET    /api/v1/rag-relief/extractions/pending
GET    /api/v1/rag-relief/extractions/approved-by-year/{year}
POST   /api/v1/rag-relief/extractions/{id}/approve
POST   /api/v1/rag-relief/extractions/{id}/reject
```

---

## Frontend: New Types

```typescript
// frontend/src/features/adaptive-tax/pages/catalog-admin/rag-types.ts

export type RagReliefsResponse = {
  extractions: RagExtraction[];
  total_pending: number;
  total_approved: number;
};

export type RagExtraction = {
  extraction_id: string;
  relief_name: string;
  cap_amount: string;
  currency: string;
  effective_from: string;
  assessment_years: string[];
  section_ref: string;
  quote: string;
  source_act: string;
  
  // Confidence scores
  confidence_name: number;
  confidence_amount: number;
  confidence_date: number;
  confidence_overall: number;
  
  // Auditor workflow
  status: 'pending' | 'approved' | 'rejected' | 'needs_review';
  auditor_notes?: string;
  approved_by?: string;
  approved_at?: string;
  created_at: string;
};
```

---

## User Workflows

### Auditor Workflow: Review RAG Extraction

1. **Access:** Catalog Admin → "RAG Review" tab
2. **See:** List of pending extractions with confidence badges
3. **Inspect:** Click to view extracted JSON, quote, source section
4. **Decide:**
   - ✅ Approve → Moved to "Approved" catalog for that year
   - ❌ Reject → Excluded, reason logged
   - ⚠️ Flag → Marked `needs_manual_verification`, stays in interview with warning
5. **Result:** Approved reliefs appear in Relief Interview for that year

### Taxpayer Workflow: Relief Interview with RAG Reliefs

1. **Current:** Interview shows hardcoded reliefs (e.g., Personal Relief, Employment Relief)
2. **Future:** Interview also shows RAG-approved reliefs
   - If new relief was extracted & auditor-approved
   - Taxpayer can now claim it in the interview
   - All relief calculations work same as hardcoded

---

## Testing Strategy

### Manual Testing

1. **Catalog Admin RAG Review:**
   - Upload a new act PDF via `/ingest/pdf`
   - Verify extractions appear in pending list
   - Approve one extraction
   - Reject another with reason
   - Verify status changes in database

2. **Relief Interview:**
   - Select a year that has approved RAG extractions
   - Verify both hardcoded + RAG reliefs appear
   - Test claiming both types
   - Verify tax calculation includes RAG reliefs

### Automated Testing

- Unit tests for RAG extraction → ApprovedEntry transformation
- Integration tests for approval workflow
- E2E tests for full auditor + taxpayer flow

---

## Phase 6 Deliverables Checklist

- [ ] API Gateway registers /api/v1/rag-relief/** routes
- [ ] Database views & procedures for approval workflow
- [ ] Catalog Admin → RAG Review page (list, approve, reject)
- [ ] Confidence score display with visual indicators
- [ ] Frontend merge logic: hardcoded + RAG reliefs
- [ ] Relief Interview shows RAG-approved reliefs
- [ ] RAG badge/indicator on Relief Interview items
- [ ] Manual verification flag on low-confidence extractions
- [ ] Audit log records all RAG operations
- [ ] E2E test: Upload PDF → Extract → Approve → Show in Interview
- [ ] Documentation & runbook

---

## Success Criteria

✅ **Accuracy:** Auditor-approved RAG reliefs match act text  
✅ **Usability:** Relief Interview seamlessly shows dynamic reliefs  
✅ **Traceability:** All RAG operations logged & auditable  
✅ **Performance:** Retrieval & extraction <5s per relief  
✅ **Cost:** Stay within OpenAI API credit budget  

---

## Known Limitations

1. **Confidence Scores:** Machine-calculated (not perfect)
   - Always require auditor review before taxpayer sees
   - Low confidence (<0.7) flagged for extra scrutiny

2. **Timescales:** No automatic extraction when act uploaded
   - Manual audit required before relief becomes active
   - Auditors control rollout timing

3. **Coverage:** Only works for reliefs in uploaded acts
   - Hardcoded reliefs still available as fallback
   - Hybrid approach ensures no data loss

---

## Next Steps

1. **Milestone 1:** Set up API Gateway routes
2. **Milestone 2:** Build Catalog Admin RAG Review UI
3. **Milestone 3:** Integrate with Relief Interview
4. **Testing:** Full E2E validation with real acts
5. **Deployment:** Ship with documentation

