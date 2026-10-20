# Refactor audit: ingestion, valuation, and underwriting

## Existing components retained

- SourceAdapter and the existing registry remain the connector contract.
- ConnectedSource remains the source registry; no parallel registry/table was introduced.
- Document, DocumentChunk, and Evidence remain the document and retrieval foundation.
- MarketComparable and PropertyValuation remain the comparable and automated-valuation records.

## Changes in this branch

- Connected-source routes require admin authorization.
- Configured URLs reject non-HTTP(S), embedded credentials, local/private literal IPs, and private DNS resolutions at fetch time. Redirects are revalidated and response bodies are size-limited. Production should also restrict outbound network traffic at the network/container layer.
- Custom HTML extraction remains declarative; no user-provided Python or JavaScript is executed.
- Source syncs reuse the existing bounded worker pool instead of creating a second BackgroundTasks execution path.
- Scheduled ingestion no longer assumes user ID 1; it chooses an admin owner when available, otherwise the first existing user.
- Explicit reserve price and EMD fields are persisted separately. An opening bid is not silently treated as a reserve price.
- Deal analysis and dashboard discounts use only the latest market_comparables / residential_comparable_sales valuation record. Legacy property-entered estimates are not treated as verified market values.
- Manual valuation request fields and the manual valuation-write endpoint have been removed. property_valuations remains as the audit trail for automated estimates; there is no separate valuation_history table in the current schema.
- Deal intelligence reuses the shared comparable engine and includes reserve/EMD in the structured RAG context.
- Exact-content deduplication is guarded by the unique content hash and handles concurrent duplicate inserts. A changed document at the same URL creates a new document record instead of silently reusing stale content.

## Remaining work before calling the refactor complete

1. Add a document_sources link table so a deduplicated document can retain every source URL/name that published it. This requires a migration and reconciliation with the local corrective migration ee3edbd81818.
2. Add database-enforced evidence identity constraints and conflict-safe evidence upserts.
3. Replace the in-process worker queue with durable queued jobs and source cursors/checkpoints. The current shared thread pool is bounded but jobs can be lost if the process stops before execution.
4. Reconcile reserve/EMD conflicts using source priority and evidence provenance rather than last processed value.
5. Move CPU-heavy OCR into dedicated workers and add stage-level timing, retry, and failure metrics.
6. Add end-to-end tests for source sync, revised notices, source conflicts, valuation eligibility, and underwriting citations.

## Verification status

The changes have not been executed in a local checkout from this environment. Run the frontend production build, the backend test suite, and alembic check on the feature branch before merging. No new migration is included in this branch, so the existing schema is unchanged by these code edits.
