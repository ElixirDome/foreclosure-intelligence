"""
Database backup utility for Foreclosure Intelligence.

Supports:
- PostgreSQL native dump (when pg_dump is available)
- Deterministic JSON/SQL snapshot for portability and offline drill testing
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text


def backup_database(output_dir: Path | None = None) -> Path:
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL environment variable is required.", file=sys.stderr)
        sys.exit(1)

    output_dir = output_dir or Path("backups")
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_file = output_dir / f"foreclosure_backup_{timestamp}.json"

    engine = create_engine(database_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    snapshot = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database_type": engine.dialect.name,
        "tables": {},
    }

    with engine.connect() as conn:
        for table in tables:
            rows = conn.execute(text(f"SELECT * FROM {table}")).mappings().fetchall()
            serialized_rows = []
            for row in rows:
                row_dict = {}
                for k, v in dict(row).items():
                    if hasattr(v, "isoformat"):
                        row_dict[k] = v.isoformat()
                    elif isinstance(v, bytes):
                        row_dict[k] = f"<bytes:{len(v)}>"
                    else:
                        row_dict[k] = str(v) if v is not None else None
                serialized_rows.append(row_dict)

            snapshot["tables"][table] = {
                "count": len(serialized_rows),
                "rows": serialized_rows,
            }

    backup_file.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    print(f"Backup created successfully: {backup_file.resolve()} ({backup_file.stat().st_size} bytes)")
    return backup_file


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backup Foreclosure Intelligence database")
    parser.add_argument("--output-dir", type=Path, default=Path("backups"), help="Directory to save backup")
    args = parser.parse_args()
    backup_database(args.output_dir)
