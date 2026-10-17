# Technical audit: valuation history, authorization, auction updates

## Scope

This change set addresses the valuation-history display and obvious authorization bypasses in the current FastAPI/SQLAlchemy + React implementation. It is intentionally focused; it is not a full production security review.

## Changes in this branch

- The property detail page now renders valuation history as a chronological SVG line chart, with value-axis grid lines and per-point date/value labels. The existing per-record details remain below the chart.
- Creating a valuation now requires authentication and property ownership (or the existing admin override in `require_property_owner`).
- Calculating a market valuation now requires the same property-owner/admin authorization.
- Creating or modifying shared market-comparable records now requires the admin role.
- Valuation request validation rejects non-positive estimates, non-finite values, confidence outside `0..1`, empty/oversized method labels, and oversized source strings.
- The ordinary property PATCH schema and service allowlist no longer accept `estimated_value`. That field must be changed through the valuation-recording flow, so an estimate update cannot silently bypass valuation history.
- When a property is initially created with a positive estimate, the service records an initial valuation entry with method `initial_property_value` and source `property_creation`.

## Auction-status update behavior (important)

The code does **not** currently poll an auction source to update the status of existing properties.

- `app/main.py` starts an APScheduler background scheduler in FastAPI's lifespan.
- `app/ingestion/scheduler.py` runs `run_pnb_ingestion` every six hours.
- That job fetches PNB auction notices and invokes the ingestion pipeline.
- `app/ingestion/save.py` identifies existing properties by `property_key`. For an existing match, it currently fills missing city/locality fields and records document provenance, then marks the property as a duplicate/skipped.
- It does not reconcile changed auction dates, closing dates, sold/cancelled status, or other status transitions for an existing property.

Therefore, the six-hour schedule is **source ingestion**, not auction-status polling/reconciliation. Existing statuses can become stale. A proper next step is a source-specific reconciliation policy with explicit field precedence, observed-at timestamps, provenance, and tests for transitions. Do not infer `sold` or `cancelled` solely from an expired auction date.

## Remaining technical debt / modern standards comparison

1. **Valuation authorship and immutability:** the current table has no `created_by_user_id`, provenance payload, or correction/supersession relation. Authorization is now enforced at the API route, but a stronger audit trail should persist who submitted each valuation, distinguish manual vs. system-generated values, and make corrections append-only rather than editing history.
2. **Initial values from ingestion:** the initial valuation entry is created for user-created properties that contain a positive estimate. The current ingestion save path does not create valuation history for source-ingested records; if ingestion begins supplying estimates, route those through a similarly explicit provenance-aware recording path.
3. **Scheduler deployment:** a process-local background scheduler can run once per application worker/replica. In multi-worker or multi-replica deployment, move scheduled ingestion to a dedicated worker/scheduler or use a distributed lock and idempotent jobs.
4. **Source reliability:** ingestion should retain fetch timestamps, per-source status observations, retry/backoff, rate-limit handling, and reconciliation metrics. Current duplicate handling alone does not establish that a source record is unchanged.
5. **Configuration and observability:** remove debug `print` statements and use structured logging; configure the PNB OCR/Poppler path via environment/config rather than a machine-specific Windows path.
6. **Frontend API URL:** `frontend/src/api/client.ts` hardcodes `http://127.0.0.1:8000`. Use a Vite environment variable for deployments.
7. **Testing:** add API tests proving unauthenticated users receive 401, non-owners receive 403, owners/admins can create valuations, non-admins cannot mutate comparables, and PATCH cannot alter `estimated_value`. Add chart tests for empty, one-point, same-value, and multi-date histories.

## Verification status

The edits were committed to a dedicated branch for review. This environment did not execute the Python test suite or the frontend production build, so those remain required checks before merging. No database migration is required for this branch.
