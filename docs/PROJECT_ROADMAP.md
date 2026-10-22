# Project Roadmap

This roadmap describes intended work for Foreclosure Intelligence. It is a plan, not a statement that any phase is already complete. Reassess priorities against the current repository and test results before implementation.

## Product objective

Build a reliable foreclosure and auction property research platform that ingests notices from multiple sources, extracts property and auction details with traceable evidence, estimates value transparently, and presents useful research in a clear UI.

## Phase 0 — Baseline and safety

- [ ] Verify active branch/worktree, clean vs. modified files, recent commits, and current API/UI structure.
- [ ] Run backend tests and frontend build; record the actual baseline.
- [ ] Inspect current models, Alembic heads, and target database schema without changing production data.
- [ ] Identify the ingestion entry points and trace one source item end to end.
- [ ] Establish a reproducible test environment and document required environment variables without committing secrets.

**Exit criteria:** The current state and known failures are reproducible; production data has not been changed.

## Phase 1 — One genuine notice end to end

Immediate priority: diagnose why genuine ARMB Pathankot property-sale notices were returning zero extracted properties.

- [ ] Select one real ARMB Pathankot PDF and preserve its source URL and sample for regression testing where licensing and privacy permit.
- [ ] Inspect native PDF text and OCR output before changing extraction rules.
- [ ] Trace extraction, residential classification, address validation, field parsing, and persistence to find the first failing stage.
- [ ] Validate address/locality/city, reserve price, EMD, auction date, and other fields only when supported by the source.
- [ ] Retain source-document and page/text evidence for extracted values where feasible.
- [ ] Add focused regression tests for the genuine notice and malformed/missing fields.
- [ ] Confirm repeat ingestion is idempotent and does not create duplicate properties, listings, documents, or chunks.

**Exit criteria:** At least one genuine ARMB notice is correctly parsed, validated, persisted once, visible through the API/UI, and covered by regression tests.

## Phase 2 — Extraction quality and multilingual OCR

- [ ] Create a reviewed corpus of genuine residential notices, non-residential notices, vehicle tenders, noisy scans, multilingual documents, duplicate/revised notices, and malformed fields.
- [ ] Prefer native PDF text when reliable; use OCR as a fallback.
- [ ] Support appropriate OCR languages and preserve page boundaries.
- [ ] Detect low-quality/empty OCR and route it to retry or review rather than silently treating it as a negative classification.
- [ ] Validate numeric amounts, dates, area units, addresses, and currency conversions.
- [ ] Separate extraction confidence from classification confidence.
- [ ] Measure field-level precision and recall on reviewed examples.

**Exit criteria:** Regression suite captures known failure modes, and extraction quality is measured rather than inferred from raw item counts.

## Phase 3 — Ingestion reliability and idempotency

- [ ] Use durable job/run state with clear lifecycle statuses and error summaries.
- [ ] Add bounded retries, timeouts, checkpoints, and restart recovery.
- [ ] Track discovered, downloaded, parsed, extracted, validated, saved, skipped, and failed counts consistently.
- [ ] Add idempotency keys and database uniqueness constraints where appropriate.
- [ ] Avoid duplicate property-document links and document chunks.
- [ ] Detect document revisions and preserve source history.
- [ ] Test repeat runs, partial failures, interrupted downloads, malformed PDFs, timeouts, and concurrent ingestion.

**Exit criteria:** A run can resume safely after failure, repeat runs do not duplicate data, and operational status accurately reflects the outcome.

## Phase 4 — Data model, listings, and evidence

- [ ] Clearly distinguish canonical properties from auction listings/events and notice revisions.
- [ ] Preserve original URLs, source identifiers, document metadata, and retrieval timestamps.
- [ ] Store evidence/provenance for important fields such as address, reserve price, EMD, date, area, and title/borrower details.
- [ ] Where practical, link evidence to source document, page, and supporting text.
- [ ] Handle conflicting values and revisions explicitly; do not silently select arbitrary values.
- [ ] Validate migration chains and metadata in a scratch database before production deployment.

**Exit criteria:** Important property and auction claims can be traced to the source and conflicts are represented transparently.

## Phase 5 — Valuation and deal intelligence

- [ ] Display reserve price and EMD as distinct fields; never conflate them with estimated market value.
- [ ] Build transparent source/bank baseline valuation where data supports it.
- [ ] Select comparable properties using location, property type, area, recency, and plausible price ranges.
- [ ] Define minimum comparable requirements and show when coverage is insufficient.
- [ ] Expose assumptions, evidence, confidence, stale-data warnings, and risk factors.
- [ ] Avoid false precision and unsupported deal scores.
- [ ] Remove redundant or contradictory valuation panels and manual inputs that allow unaudited manipulation.

**Exit criteria:** A user can understand what a valuation means, how it was derived, which evidence supports it, and where uncertainty remains.

## Phase 6 — RAG and retrieval evaluation

- [ ] Audit embedding generation and persistence for deterministic consistency across processes.
- [ ] Build a reviewed benchmark of roughly 50–100 questions when enough documents are available.
- [ ] Include answerable, ambiguous, conflicting-evidence, and unanswerable questions.
- [ ] Require citations for factual claims and abstention when the corpus lacks support.
- [ ] Evaluate retrieval Recall@5, answer accuracy, groundedness, citation correctness, abstention, latency, and schema validity.
- [ ] Treat source documents as untrusted content and defend against prompt injection.

Suggested initial targets to measure—not existing results:
- Recall@5 ≥ 90% on the reviewed benchmark.
- Citations on 100% of critical factual claims.
- Groundedness/faithfulness ≥ 95%.
- Answer accuracy ≥ 90% on answerable benchmark questions.
- Correct abstention on 100% of intentionally unanswerable critical questions.
- Valid schema-constrained output on 100% of evaluated cases.

**Exit criteria:** Benchmark results and failure analysis demonstrate whether retrieval and answers are reliable enough for the intended use.

## Phase 7 — LLM comparison

- [ ] Establish the current model as a baseline before changing it.
- [ ] Compare candidate local and optional hosted models on the same benchmark and prompt/tool conditions.
- [ ] Measure accuracy, groundedness, citation correctness, hallucinations, abstention, structured-output validity, latency/p95, memory, cost, and operational complexity.
- [ ] Use deterministic validators for amounts, dates, required fields, and source references where possible.
- [ ] Adopt a larger or hosted model only when measured gains justify the cost and risk.

**Exit criteria:** Model selection is supported by reproducible comparative results.

## Phase 8 — Agentic workflow, only if justified

- [ ] Start with one controlled orchestrator and narrow, testable tools.
- [ ] Potential tools: evidence retrieval, deterministic valuation, risk checklist, and answer synthesis with citations.
- [ ] Keep tools read-only by default.
- [ ] Do not allow arbitrary SQL, unrestricted shell access, open-ended network access, or autonomous database mutations.
- [ ] Add multiple agents only if evaluation shows a meaningful improvement over a simpler workflow.

**Exit criteria:** Each tool has clear permissions, validation, tests, and a measurable reason to exist.

## Phase 9 — UI and product integration

- [ ] Create a clear discovery experience and coherent property detail view.
- [ ] Separate end-user research from source configuration, ingestion status, and administration.
- [ ] Consolidate overlapping Deal Intelligence, Market Valuation, “worth a closer look,” and evidence content.
- [ ] Keep internal RAG/agent implementation details out of the user-facing interface unless useful.
- [ ] Show reserve price, EMD, estimated value, confidence, risk, valuation assumptions, and source evidence distinctly.
- [ ] Preserve original auction notice links.
- [ ] Test loading, empty, error, stale-data, responsive, keyboard, and accessibility states.
- [ ] Preserve API contracts unless changes are planned and tested.

**Exit criteria:** The UI presents evidence-backed information coherently and handles missing or failed data gracefully.

## Phase 10 — Security and production readiness

- [ ] Review authentication, authorization, role boundaries, and session handling.
- [ ] Protect custom-source URL fetching against SSRF, redirects to private networks, and unsafe protocols.
- [ ] Apply download size limits, content-type validation, timeouts, concurrency limits, and resource limits for PDF/OCR work.
- [ ] Protect secrets and use explicit environment configuration.
- [ ] Add rate limiting and abuse protections.
- [ ] Add structured logs, metrics, alerts, health checks, and durable worker monitoring.
- [ ] Test backups and restoration.
- [ ] Validate migrations in CI and staging with a rollback plan.
- [ ] Add smoke, integration, failure-recovery, and realistic load tests.
- [ ] Establish staged deployment and rollback procedures.

**Exit criteria:** The application can be deployed, monitored, restored, and rolled back with documented procedures.

## Cross-phase definition of done

Every meaningful change should include:
1. A clearly identified problem and expected behavior.
2. A minimal implementation that fits existing architecture.
3. Regression tests for the bug or feature.
4. Relevant backend tests and/or frontend build checks.
5. Evidence that the intended behavior was actually verified.
6. Updated documentation where architecture or operations changed.
7. A concise summary of changed files, results, and remaining limitations.

Do not mark a phase complete based only on implementation; require its exit criteria to be demonstrated.
