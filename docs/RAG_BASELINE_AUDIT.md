# Foreclosure Intelligence — RAG Baseline Audit

**Date:** October 28, 2026  
**Repository:** `ElixirDome/foreclosure-intelligence`  
**Branch:** `fix/idempotent-ingestion-unified-analysis`  
**Working Directory:** `C:\Dev\foreclosure-ui-review`  
**Baseline Test Status:** 221 / 221 passing (8.27s), 7 Vitest passing, 24 Playwright passing.

---

## 1. Current Request & Data Path Trace

```
[User Input in ChatBot.tsx]
       │
       ▼
[askRag() in frontend/src/api/rag.ts]
       │ (POST /documents/rag { question, property_id, mode, limit })
       ▼
[rag_answer() in app/routes/documents.py]
       │ (Depends(get_db))
       ▼
[process_analyst_turn() in app/services/analyst.py]
       ├── Pattern matching: connect/source -> _handle_source_onboarding_inquiry
       ├── Pattern matching: rep/officer -> _handle_representative_inquiry
       ├── Pattern matching: valuation -> _handle_valuation_explanation
       ├── Pattern matching: settlement/OTS -> Confidential refusal guardrail
       ├── Pattern matching: status/notice -> _handle_status_inquiry
       └── Fallthrough: answer_question() in app/services/rag.py
             │
             ├── If looks_like_investment_question or property_id:
             │     build_multi_source_context() in app/services/multi_retriever.py
             │     ├── Relational properties (Property)
             │     ├── Field-level evidence (Evidence)
             │     ├── Market comparables (MarketComparable)
             │     ├── Automated valuations (PropertyValuation)
             │     └── Document chunks via retrieve() in app/services/retrieval.py
             │           ├── generate_query_variants()
             │           ├── parallel_search() [BM25 + Vector concurrent]
             │           ├── reciprocal_rank_fusion() [RRF k=60]
             │           └── deduplicate_chunks()
             │
             └── Synthesis:
                   ├── Local Ollama _llm_synthesize() (if provider online)
                   └── Deterministic _format_structured_answer()
                         │
                         ▼
             [RAGAnswer -> RAGResponse in app/schemas.py]
                         │
                         ▼
             [ChatBot.tsx UI Rendering: SWOT card, citations, action pills]
```

---

## 2. Critical Reliability & Architectural Defects

### Defect 1: Single-Character & Gibberish Queries Dump Irrelevant OCR Text
- **Root Cause**: When a user inputs `"h"`, `"asdf"`, or a non-question, `process_analyst_turn()` has no conversational understanding layer. None of the static keyword matchers fire, so it falls through to `answer_question("h", mode="hybrid")`.
- **Retrieval Failure**: `parallel_search("h")` searches the BM25 index and vector store for the letter `"h"`. In an OCR document corpus, almost every chunk contains `"h"`. The top-ranked arbitrary chunk is retrieved with a low score (~0.35).
- **Answer Degradation**: In fallback/legacy mode, `_legacy_document_only_answer` formats the output as:
  `Based on document evidence (score=0.35):\n\n[1,200 chars of raw OCR bank text]`
- **Required Behavior**: Input must pass through an intent & query-understanding layer. Single-character, incomplete, or ambiguous inputs must **never** execute corpus retrieval. They must return a helpful clarification request.

### Defect 2: Duplicate Citations & Mixed Document Context
- **Root Cause**: When a document contains multiple matching chunks, or when action links are generated in `analyst.py`, multiple citations with duplicate titles, URLs, or excerpts are returned.
- **Required Behavior**: Strict citation reconciliation: deduplicate by `(document_id, page_number)`, surface the best excerpt, and keep action links cleanly separated from evidential citations.

### Defect 3: Missing Conversation-State Resolution for Follow-Ups
- **Root Cause**: Follow-up questions like *"What about the EMD?"* or *"Who is the officer?"* require `property_id` in the API payload. If the user asks a follow-up from the general chat interface, the system loses the referenced property unless explicitly stated.
- **Required Behavior**: Conversational state resolver that extracts context from recent turns or asks the user which property they mean.

### Defect 4: Exposure of Internal Pipeline Jargon
- **Root Cause**: Diagnostic terms (`"rrf_fused"`, `"hashed_vector"`, score numbers, kind labels) risk leaking into user-facing output.
- **Required Behavior**: User answers must be natural, underwriter-oriented, and free of internal pipeline mechanics. Detailed scoring belongs in telemetry/logs.

---

## 3. Retrieval Components & Provenance

| Component | Implementation File | Verification Status | Notes |
| :--- | :--- | :--- | :--- |
| **BM25 Lexical Ranker** | `app/services/bm25.py` | Verified | Okapi BM25 ($k_1=1.5, b=0.75$), non-negative RSJ IDF, exact numeric boosting. |
| **Vector Store** | `app/services/retrieval.py` | Verified | 256-dim L2-normalized feature-hashed bag-of-words vectors stored in chunk metadata. |
| **Multi-Query Expansion** | `app/services/retrieval.py` | Verified | Deterministic auction domain synonym expansion. |
| **Parallel Search** | `app/services/retrieval.py` | Verified | `ThreadPoolExecutor(max_workers=4, timeout=3.0)` with branch fallback. |
| **Fusion & Dedup** | `app/services/retrieval.py` | Verified | Reciprocal Rank Fusion ($k=60$) with deterministic tie-breaking. |
