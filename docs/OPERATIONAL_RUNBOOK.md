# Foreclosure Intelligence — Operational Runbook

**Prepared:** 2026-10-22  
**Target Architecture:** FastAPI backend, PostgreSQL 16 database, React/Vite frontend.

---

## 1. System Overview and Health Endpoints

The service exposes separate health and readiness probes:

* **Liveness Probe**: `GET /health/live`
  * Checks application process responsiveness.
  * Expected response: HTTP 200 `{"status": "live"}`.
* **Readiness Probe**: `GET /health/ready`
  * Verifies active database connection via lightweight query.
  * Expected response: HTTP 200 `{"status": "ready", "database": "connected"}`.
  * Unhealthy response: HTTP 503 `Database connection failed`.

---

## 2. Backup and Disaster Recovery

### 2.1 Objectives
* **Recovery Point Objective (RPO)**: 24 hours (daily automated snapshots).
* **Recovery Time Objective (RTO)**: 1 hour (automated script restore drill).

### 2.2 Backup Procedure
To create an offline snapshot of all database tables:
```powershell
python scripts/backup_db.py --output-dir backups
```
Output: Timestamped JSON snapshot in `backups/foreclosure_backup_<timestamp>.json`.

### 2.3 Verification & Restore Drill
To verify an existing snapshot:
```powershell
python scripts/restore_db.py backups/foreclosure_backup_<timestamp>.json
```

For native PostgreSQL dump / restore:
```bash
# Backup
pg_dump -h localhost -U postgres -d foreclosure_db -F c -b -v -f foreclosure_db.dump

# Restore
pg_restore -h localhost -U postgres -d foreclosure_db -v -c foreclosure_db.dump
```

---

## 3. Containerized Deployment (Docker Compose)

### 3.1 Local & Staging Deployment
```bash
docker compose up -d --build
```
This starts:
1. `postgres` (port 5432) with automated healthcheck.
2. `backend` (port 8000) with poppler-utils and tesseract-ocr.
3. `frontend` (port 5173 / port 80 nginx).

### 3.2 Stopping Containers
```bash
docker compose down
```

---

## 4. Ingestion Diagnostics & Troubleshooting

### 4.1 Zero-Property Ingestion Diagnostics
When an ingestion run reports `documents_ingested_without_property` with 0 extracted properties:
1. Check `documents` table for `extracted_text`:
   ```sql
   SELECT id, source_name, source_url, length(extracted_text) FROM documents ORDER BY id DESC LIMIT 5;
   ```
2. If `length(extracted_text)` is null or 0, verify PDF text extraction or Poppler / OCR configuration:
   * Native PDF text is automatically extracted using `pypdf`.
   * Scanned PDFs fall back to `pdf2image` and `pytesseract`. Ensure `POPPLER_PATH` points to the poppler binary directory.
3. Verify that the notice contains genuine residential properties rather than vehicle tenders or non-residential land auctions.
4. Check classification via `app.services.property_classifier.is_residential_property(text)`.
5. Run the regression test suite:
   ```powershell
   python -m pytest -v tests/test_pnb_extraction.py
   ```

---

## 5. Rollback Procedures

### 5.1 Application Rollback
If a deployed build exhibits failures:
1. Revert to the prior Git commit or container tag.
2. Verify `/health/ready` responds HTTP 200.
3. Check application logs for unhandled exceptions.

### 5.2 Migration Rollback
To downgrade the database by one migration:
```powershell
python -m alembic downgrade -1
```
Always verify data consistency and table foreign keys following any schema modification.
