# Technical audit: valuation history, authorization, auction updates

## Target branch

This change set is based on `wip/current-state` (not `main`). It preserves the existing WIP page, RAG/evidence UI, and `ValuationChart` component.

## Changes

- The property detail page refreshes valuation history after a successful market-valuation calculation. Previously, the backend created a valuation record but the frontend only refreshed the market-valuation result and analysis, so the history graph could remain stale until a reload.
- Chart points use the valuation record ID as their React key, so separate records with the same date and amount do not collide.
- Creating a valuation requires property-owner/admin authorization.
- Calculating a market valuation requires the same property-owner/admin authorization.
- Creating shared market-comparable records requires the admin role.
- Valuation input validation rejects non-positive/non-finite estimates, invalid confidence values outside `0..1`, empty or oversized method labels, and oversized source strings.
- The property PATCH schema and service allowlist no longer accept `estimated_value`. Estimate changes should go through the valuation-recording flow so the history is maintained.
- Creating a property with a positive initial estimate creates an initial valuation record (`initial_property_value`, source `property_creation`).

## Auction-status update behavior

The current code does **not** poll an auction source to update the status of existing properties.

- `app/main.py` starts APScheduler in the FastAPI lifespan.
- `app/ingestion/scheduler.py` runs `run_pnb_ingestion` every six hours.
- The job fetches PNB auction notices and invokes the ingestion pipeline.
- `app/ingestion/save.py` identifies existing properties by `property_key`. Existing matches are treated as duplicates/skipped, with limited metadata/provenance handling; auction dates and statuses are not reconciled.

The schedule is therefore source ingestion, not auction-status polling/reconciliation. Existing statuses can become stale. A proper follow-up should define source-specific field precedence, store observation timestamps and provenance, and test status transitions. Do not infer `sold` or `cancelled` solely from an expired auction date.

## Remaining technical debt

1. **Valuation authorship/immutability:** persist who submitted each valuation, distinguish manual from system-generated records, and make corrections append-only or explicitly superseding.
2. **Ingestion estimates:** if source ingestion starts supplying estimates, route them through a provenance-aware valuation-recording path.
3. **Scheduler deployment:** a process-local scheduler can run once per worker/replica. Use a dedicated scheduler/worker or a distributed lock in multi-worker deployments.
4. **Source reliability:** add retry/backoff, rate-limit handling, observation timestamps, and reconciliation metrics.
5. **Configuration/observability:** replace debug prints with structured logging and configure OCR/Poppler paths through environment/config.
6. **Frontend API URL:** replace the hardcoded `http://127.0.0.1:8000` with a Vite environment variable.
7. **Tests:** cover authentication (401), non-owner access (403), owner/admin valuation creation, admin-only comparable mutation, PATCH rejection of `estimated_value`, initial valuation history, and chart refresh after market valuation.

## Verification status

The changes are committed to a review branch based on `wip/current-state`. Python tests and the frontend production build have not been executed in this environment; run them before merging. No database migration is required for these changes.
