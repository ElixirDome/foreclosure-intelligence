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

## Phase 10 — Production architecture, security, and operations

This phase defines production readiness requirements; it does not imply that any infrastructure is currently implemented. Select components based on deployment needs, threat model, expected traffic, budget, and operator capacity. Prefer the simplest architecture that meets the defined reliability and security objectives.

### 10.1 Deployment architecture and containers

- [ ] Document development, test, staging, and production environments; architecture, trust boundaries, dependencies, and data flows.
- [ ] Containerize backend and frontend where appropriate using reproducible, multi-stage Docker builds.
- [ ] Use minimal trusted base images, pinned dependencies, non-root runtime users, explicit health checks, and sensible CPU/memory limits.
- [ ] Keep secrets and environment-specific configuration out of images, source control, and build logs.
- [ ] Add .dockerignore, image labels/versioning, and a documented image lifecycle and patching policy.
- [ ] Build images in CI, scan images and dependencies, and publish immutable versioned artifacts to a controlled registry.
- [ ] Use Docker Compose for reproducible local development and integration testing when it fits the stack.
- [ ] Evaluate a managed container service or VM-based deployment before adopting Kubernetes; document the decision and trade-offs.
- [ ] If Kubernetes is justified, provide maintained manifests or Helm/Kustomize configuration, environment isolation, readiness/liveness/startup probes, resource requests/limits, disruption strategy, autoscaling policy, and controlled rolling deployments.
- [ ] Do not run stateful databases or durable job state in ephemeral containers without an explicit persistence, backup, and recovery design.

**Exit criteria:** A new environment can deploy a versioned build reproducibly from documented instructions, and the selected platform has an explicit operational rationale.

### 10.2 Application and infrastructure security

- [ ] Create and maintain a threat model covering authentication, authorization, custom source URLs, downloaded documents, OCR/PDF processing, stored property data, admin actions, and LLM/RAG prompt injection.
- [ ] Define role-based authorization and least privilege for users, administrators, service identities, database accounts, and CI/CD.
- [ ] Validate token/session expiry, secret rotation, CORS, cookie/session settings where applicable, and administrative flows.
- [ ] Enforce TLS in transit and encryption at rest using platform-supported controls for databases, backups, and object storage.
- [ ] Use a managed secret store where available; otherwise document access controls, rotation, and incident procedures.
- [ ] Defend custom-source fetching against SSRF: allowlist schemes, validate DNS and resolved IPs, block loopback/private/link-local/metadata ranges, re-check redirects, and enforce connection/read timeouts.
- [ ] Apply download byte/page limits, content-type and file-signature validation, PDF/OCR process isolation, concurrency limits, and resource/time budgets.
- [ ] Validate external inputs and enforce request/body limits, rate limits, and abuse protections at application and edge layers.
- [ ] Prevent tokens, credentials, sensitive personal data, and full document contents from leaking into logs or error responses.
- [ ] Add dependency/SCA, secret, static-analysis, container-image, and infrastructure-configuration scanning to CI where relevant.
- [ ] Produce an SBOM for release artifacts where practical, pin and regularly update dependencies, and define vulnerability triage and patch SLAs.
- [ ] Set a security verification target using a named standard such as OWASP ASVS; select and document the appropriate verification level rather than claiming blanket compliance.
- [ ] Establish incident response, credential revocation, disclosure, and audit-log retention procedures.
- [ ] Treat source PDFs and extracted text as untrusted data. Isolate parsers, avoid executing embedded content, and do not allow document instructions to override system/tool permissions.

**Exit criteria:** Threats and controls are documented, high-risk paths have automated tests, critical security findings block release, and the selected verification scope has evidence.

### 10.3 Identity, network, and Kubernetes controls (if Kubernetes is selected)

- [ ] Use least-privilege RBAC, dedicated service accounts, and restricted workload permissions.
- [ ] Apply network policies to limit pod-to-pod and outbound traffic to required destinations.
- [ ] Enforce Pod Security Standards or equivalent controls; prohibit privileged containers and unnecessary host access.
- [ ] Run containers as non-root with read-only filesystems and dropped Linux capabilities where compatible.
- [ ] Store secrets through a supported secret-management integration; restrict secret access and enable encryption at rest for cluster secrets.
- [ ] Set CPU/memory requests and limits, ephemeral-storage limits where supported, and namespace quotas.
- [ ] Scan images and manifests, pin image digests for controlled releases, and restrict deployment credentials.
- [ ] Configure control-plane, audit, and workload monitoring appropriate to the managed or self-managed cluster.
- [ ] Document cluster upgrades, node patching, certificate rotation, recovery, and access review.

**Exit criteria:** A cluster security review confirms controls are enforced, tested, and owned. If Kubernetes is not selected, this subsection is not a requirement to introduce it.

### 10.4 Observability, monitoring, and alerting

- [ ] Emit structured, timestamped logs with correlation/request IDs and ingestion-run/document IDs; redact secrets and sensitive data.
- [ ] Instrument API and background jobs with metrics and traces; use OpenTelemetry-compatible instrumentation where appropriate.
- [ ] Monitor request rate, errors, latency (including p95/p99), resource saturation, database connection/slow-query health, queue/job age, retries, and dependency failures.
- [ ] Monitor product/data signals: source freshness, source fetch failures, discovered/downloaded/parsed/extracted/validated/saved counts, extraction yield, OCR quality, duplicate rates, missing critical fields, and valuation/evidence coverage.
- [ ] Expose separate liveness and readiness checks; readiness must verify required dependencies without triggering expensive work.
- [ ] Define actionable alerts, severity, owner, runbook, and escalation path; avoid alerting on noisy metrics without a response action.
- [ ] Create dashboards for service health, ingestion reliability, extraction quality, database/storage, and security events.
- [ ] Define retention, access control, and cost limits for logs, metrics, traces, and audit events.
- [ ] Establish service-level indicators/objectives and error budgets where appropriate, based on measured baselines.
- [ ] Test alerts with controlled failures and verify that they reach the intended responder.

**Exit criteria:** Operators can detect and diagnose both service outages and silent data-quality failures, and each critical alert has a tested response procedure.

### 10.5 Data protection, backups, and disaster recovery

- [ ] Classify data and document collection purpose, retention, deletion, and access requirements.
- [ ] Define backup coverage for PostgreSQL, documents, source configuration, and required operational metadata.
- [ ] Encrypt and restrict backup access; keep recovery copies isolated from ordinary application credentials where feasible.
- [ ] Define recovery point objective (RPO) and recovery time objective (RTO) based on product needs.
- [ ] Perform scheduled restore tests in an isolated environment and record measured recovery results.
- [ ] Define migration/rollback compatibility and backup requirements before risky schema changes.
- [ ] Document outage, data corruption, credential compromise, and failed-ingestion recovery procedures.

**Exit criteria:** Recovery objectives are agreed, backups are current, and a restore drill demonstrates that critical data can be recovered within the defined objectives.

### 10.6 CI/CD and release governance

- [ ] Run backend unit/integration tests, frontend type-check/build, migration checks, and applicable security scans in CI.
- [ ] Test migrations against a disposable database and staging-like schema before release; detect multiple or unexpected Alembic heads.
- [ ] Build once and promote the same immutable artifact through environments rather than rebuilding differently per environment.
- [ ] Use short-lived, least-privilege CI identities and protected deployment environments; require approval for production changes as appropriate.
- [ ] Deploy through a documented, repeatable pipeline with versioned configuration and an auditable release record.
- [ ] Add smoke tests and post-deployment health verification; define automatic or operator-triggered rollback conditions.
- [ ] Use backward-compatible expand/contract database migrations when zero/low-downtime deployment requires them.
- [ ] Test that rollback does not destroy data or leave application and schema versions incompatible.
- [ ] Maintain dependency update automation and a process for reviewing generated changes.

**Exit criteria:** A release is reproducible, traceable, tested, and recoverable; deployment does not depend on undocumented manual steps.

### 10.7 Reliability, capacity, and background work

- [ ] Apply explicit connect/read/total timeouts to outbound requests and bounded retries with exponential backoff and jitter.
- [ ] Make ingestion jobs idempotent; persist progress and errors so workers can restart safely.
- [ ] Separate web request handling from long-running OCR/ingestion work when load or latency requires a durable queue and worker process.
- [ ] Bound queue depth, concurrency, file size, PDF pages, OCR time, memory, and per-source request rate.
- [ ] Add graceful shutdown, job leases/visibility timeouts, stale-job detection, and a defined retry/dead-letter or manual-review path.
- [ ] Run realistic load and soak tests for API traffic, PDF/OCR throughput, database access, and ingestion backlogs.
- [ ] Define capacity assumptions and scaling thresholds; test degradation and recovery when dependencies are unavailable.
- [ ] Document maintenance windows and external source availability assumptions.

**Exit criteria:** Failure, restart, and load tests show bounded resource use, no duplicate side effects, and recoverable job processing.

### 10.8 Runbooks and operational ownership

- [ ] Document deployment, rollback, migration, restore, credential rotation, and source-adapter troubleshooting runbooks.
- [ ] Define who owns production alerts, security findings, dependency updates, and incident decisions.
- [ ] Maintain an architecture decision record for material choices such as container platform, queue, monitoring stack, and database hosting.
- [ ] Document environment bootstrap, required configuration, health endpoints, backup schedules, and known operational limitations.
- [ ] Conduct a pre-release review that checks monitoring, backups, access controls, vulnerability findings, capacity, and recovery readiness.

**Exit criteria:** Another engineer can operate, diagnose, deploy, and recover the service using documented procedures without relying on undocumented knowledge.

### Production release gate

A production release is not approved merely because the app starts or containers build. Before real production use, demonstrate at minimum:

- [ ] Automated tests and build checks pass on the release candidate.
- [ ] No unresolved critical/high security findings without an explicitly documented, approved risk decision.
- [ ] Secrets are not committed or embedded in artifacts; production access is least-privilege.
- [ ] TLS, input/download limits, SSRF controls, and admin authorization are verified.
- [ ] Health checks, dashboards, actionable alerts, and operational runbooks work.
- [ ] Database/document backups and a restore drill are verified against the chosen RPO/RTO.
- [ ] Migrations, smoke tests, and rollback procedures are exercised in staging.
- [ ] Ingestion data-quality monitoring detects failures even when the API itself remains healthy.
- [ ] Deployment target, scaling approach, costs, and operational ownership are documented.
- [ ] Known risks, residual limitations, and release approval are recorded.

**Phase 10 exit criteria:** The above release gate is satisfied with evidence, and production operations have an assigned owner.

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
