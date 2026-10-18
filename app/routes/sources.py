"""Connect and run listing sources."""

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.ingestion.pipeline import run_ingestion
from app.ingestion.registry import adapter_for_connected
from app.models import ConnectedSource

router = APIRouter(prefix="/sources", tags=["sources"])


class ConnectSourceRequest(BaseModel):
    name: str
    base_url: str
    adapter_key: str = "custom_html"
    rules: dict = Field(default_factory=dict)


class SourceResponse(BaseModel):
    id: int
    name: str
    base_url: str
    adapter_key: str
    enabled: bool
    last_run_at: datetime | None
    last_status: str | None

    model_config = {"from_attributes": True}


def _run_one(source_id: int) -> None:
    db = SessionLocal()
    try:
        source = db.query(ConnectedSource).filter(ConnectedSource.id == source_id).first()
        if source is None or not source.enabled:
            return
        adapter = adapter_for_connected(source)
        result = run_ingestion(db=db, adapter=adapter, user_id=1)
        source.last_run_at = datetime.now(timezone.utc)
        source.last_status = "error" if result.get("error") else "ok"
        db.commit()
    except Exception as exc:
        source = db.query(ConnectedSource).filter(ConnectedSource.id == source_id).first()
        if source:
            source.last_run_at = datetime.now(timezone.utc)
            source.last_status = str(exc)[:240]
            db.commit()
    finally:
        db.close()


@router.get("/", response_model=list[SourceResponse])
def list_sources(db: Session = Depends(get_db)):
    return db.query(ConnectedSource).order_by(ConnectedSource.id).all()


@router.post("/", response_model=SourceResponse, status_code=201)
def connect_source(body: ConnectSourceRequest, db: Session = Depends(get_db)):
    existing = (
        db.query(ConnectedSource)
        .filter(ConnectedSource.base_url == body.base_url)
        .first()
    )
    if existing:
        existing.name = body.name
        existing.adapter_key = body.adapter_key
        existing.config_json = {"rules": body.rules}
        existing.enabled = True
        db.commit()
        db.refresh(existing)
        return existing
    row = ConnectedSource(
        name=body.name,
        base_url=body.base_url,
        adapter_key=body.adapter_key,
        config_json={"rules": body.rules},
        enabled=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.post("/{source_id}/run")
def run_source(
    source_id: int,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    source = db.query(ConnectedSource).filter(ConnectedSource.id == source_id).first()
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    background.add_task(_run_one, source_id)
    return {"status": "queued", "source_id": source_id}
