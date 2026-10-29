# Foreclosure Intelligence — Project Handoff

**Prepared:** 2026-10-22  
**Repository:** `ElixirDome/foreclosure-intelligence`  
**Previously used local worktrees:**
- `C:\Dev\foreclosure-intelligence`
- `C:\Dev\foreclosure-ui-review`

> This is a snapshot of prior conversation context, not proof of current code, database, or runtime state. Verify the active worktree, branch, uncommitted changes, relevant implementation, and tests before acting.

## Current priority

Diagnose and fix why genuine **ARMB Pathankot property-sale notices** result in zero extracted properties. The most recent reported ingestion output was:

```python
{
    "ingestion_run_id": 132,
    "items_found": 6,
    "items_extracted": 0,
    "saved": [],
    "skipped": [],
    "documents_ingested_without_property": 6,
    "extraction_errors": []
}
```

The user confirmed that the ARMB Pathankot notices contain actual property-sale details. Do not dismiss them as non-residential or irrelevant without inspecting their OCR/native text and tracing the extraction pipeline.

## Immediate debugging procedure

1. Verify the active worktree and branch. Do not assume the local project and GitHub branch contain identical changes.
2. Inspect the current versions of:
   - `app/ingestion/pnb_source.py`
   - `app/services/pnb_extraction.py`
   - `app/services/property_classifier.py`
   - `app/ingestion/document_ingest.py`
3. Select one actual ARMB Pathankot PDF and run a read-only diagnostic: inspect native text/OCR output (bounded sample), text length, extracted candidates, classification result, address validation, and field parsing.
4. Identify the first failing stage before editing. Potential causes include OCR quality/language, document segmentation, residential classification, address parsing, or numeric/date parsing.
5. Make the smallest justified fix and add a regression test for that real notice.
6. Re-run the targeted test, then the backend suite. Only then run ingestion against the intended environment and verify persistence/API/UI.
7. Do not perform destructive database operations or migrations against a real database without explicit approval. Do not commit, push, or deploy without explicit approval.

## Technical context

Known stack:
- FastAPI, Python, SQLAlchemy, PostgreSQL, Alembic
- React/Vite frontend
- JWT authentication/admin functionality
- Ollama for local LLM inference
- PDF parsing/OCR includes `pypdf`, `pdf2image`, and `pytesseract`

Known database name: `foreclosure_db`. Frontend API base was previously `127.0.0.1:8000`.

Important files:
- `app/models.py`
- `alembic/env.py`
- `app/services/properties.py`
- `app/routes/properties.py`
- `app/ingestion/pnb_source.py`
- `app/services/pnb_extraction.py`
- `app/services/property_classifier.py`
- `app/ingestion/document_ingest.py`
- `app/services/llm.py`
- `app/services/embeddings.py`

### PNB/OCR details from prior debugging

The PNB adapter previously called `_extract_ocr_text(item["pdf_path"])`, then `extract_pnb_properties(text)`, and discarded results without a usable address. The residential classifier has historically required recognizable residential wording and may reject real notices when OCR or wording differs from expected patterns. Verify the actual current code before changing rules.

The OCR path previously used `pdf2image.convert_from_path(..., dpi=200, poppler_path=...)` followed by `pytesseract.image_to_string(page)` without an explicit language. `POPPLER_PATH` was supported; a Windows fallback previously observed was `C:\Dev\poppler-26.09.0\Library\bin`. Verify current configuration.

Eleven page candidates were reported earlier; six PDFs were downloaded. They included:
- A vehicle tender with clear OCR that was correctly rejected as not a residential property.
- A Punjabi newspaper/publication page with noisy OCR and unrelated sections.
- Three ARMB Pathankot e-auction PDFs, reported sizes approximately 640,344 bytes, 1,772,245 bytes, and 751,494 bytes.
Other notices included entities that may not be residential property sales. The actual ARMB PDFs are the priority.

### Two suspected/previously addressed bugs

**Reserve-price regex:** A pattern like `([\d,]+(?:\.\d+)?)` can match comma-only text, then cause `float("")` to raise `ValueError`. A safer numeric capture begins with a digit, for example `(\d[\d,]*(?:\.\d+)?)`. The user still saw the same error after this was suggested, so do not assume the fix was applied to the active worktree or that this is the only affected parser. Inspect all relevant regexes and add tests for malformed comma-only text and a valid price such as `Rs. 12,50,000`.

**Windows PDF temp files:** `app/ingestion/document_ingest.py` previously used a temporary PDF file that could remain open while `PdfReader` attempted to open it, causing a Windows `PermissionError`. A proposed fix was to write to a `delete=False` temporary file, close it before parsing, then unlink it in `finally`. The user later reported tests passing and the latest ingestion output no longer showed that error. Verify current implementation and regression coverage.

## Historical branch, PR, tests, and database notes

Previously observed branch: `fix/idempotent-ingestion-unified-analysis`. Draft PR #6 was:
https://github.com/ElixirDome/foreclosure-intelligence/pull/6

A technical audit was previously at:
https://github.com/ElixirDome/foreclosure-intelligence/blob/fix/idempotent-ingestion-unified-analysis/TECHNICAL_AUDIT.md

Previously observed commits/branches included:
- `52b8e0a Fix migration chain and align model metadata`
- `a394900 Remove empty root files`
- `f3e451e Refactor source ingestion and enforce evidence-based valuation`
- `9440d92 feat: pluggable sources, reserve/EMD cards, incremental ingest, underwriter RAG` on an earlier branch
- `881ea67e2433` was a migration-chain cleanup/merge point in earlier testing
- `66c1710f4924` restored a document-chunk composite index in earlier history

Most recent backend checks reported before this handoff:
- `python -m compileall app` passed.
- `python -m pytest -q`: 39 passed in 0.70s.

Earlier frontend checks reported:
- `npm audit`: 0 vulnerabilities.
- `npm run build`: succeeded with Vite 8.3.5, 90 modules, JS bundle about 340.98 kB (gzip 107.99 kB).

These results are historical and must be re-run before relying on them.

Historical database notes:
- Alembic revision `ee3edbd81818`.
- `connected_sources` and `document_chunks` existed.
- Evidence foreign key `evidence_document_chunk_id_fkey` existed.
- At that time, the production `properties` table did not have EMD/reserve columns.
- A scratch database `foreclosure_migration_test` had been advanced to a state around `881ea67e2433` with EMD/reserve fields and indexes.
- Duplicate property/document and document/chunk pairs had reportedly been cleaned at the time.
- `.gitignore` had been updated to ignore `backups/`.
- `alembic/env.py` had been changed to support offline URL handling via `config.attributes['database_url']`.

Do not change production schema or data based on these notes. Inspect current migrations and schema first.

## Product and architecture goals

- Pluggable source adapters for PNB and BAANKNET/Banknet, with a configurable source-connection workflow.
- Incremental, restart-safe, idempotent ingestion with durable job status, retries, checkpoints, and meaningful error reporting.
- A clear distinction between canonical properties and auction listings/events/revisions.
- Evidence-backed extraction with original source URLs and, where feasible, page/text provenance.
- EMD and reserve price shown separately from estimated market value.
- Transparent comparable-based valuation with confidence and risk, avoiding false precision.
- RAG answers grounded in stored documents and citations, with abstention when evidence is missing.
- Measured LLM comparisons before changing models or adding hosted inference.
- A professional BAANKNET-inspired UI that consolidates duplicate analysis panels and separates end-user research from admin operations.
- Production security, observability, backup/restore, migration validation, and deployment recovery.

Prior notes stated `app/services/llm.py` used Ollama `llama3.2:3b`. `app/services/embeddings.py` previously used a 256-dimensional hashed bag-of-words vector based on Python's built-in `hash(token)`, which can vary across processes. Verify whether this is still current; if so, make embeddings deterministic and test persisted/query-vector consistency.

## Useful baseline commands

Run only after verifying the active worktree and environment. Tests can have side effects if configured against a real database.

```powershell
git status --short
git branch --show-current
git log -5 --oneline
git diff --stat
git diff -- app/services/pnb_extraction.py app/ingestion/pnb_source.py app/ingestion/document_ingest.py app/services/property_classifier.py

.\.venv\Scripts\python.exe -m compileall app
.\.venv\Scripts\python.exe -m pytest -q
```

From the actual frontend directory:

```powershell
npm audit
npm run build
```

## Roadmap

Use `docs/PROJECT_ROADMAP.md` for the phased plan and exit criteria:
1. Baseline and safety checks.
2. One genuine ARMB notice end to end.
3. Extraction quality and multilingual OCR.
4. Ingestion reliability and idempotency.
5. Data model, listings, and evidence.
6. Valuation and deal intelligence.
7. RAG evaluation.
8. LLM comparison.
9. Agentic workflow only if justified.
10. UI integration.
11. Security and production readiness.

**Immediate objective:** determine exactly why a genuine ARMB Pathankot notice yields zero extracted properties, fix it with a regression test, and preserve all current work.
