from fastapi.responses import FileResponse, RedirectResponse
from pathlib import Path
"""
Document, retrieval, extraction, and RAG API routes.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_llm_provider
from app.services.llm import LocalLLMProvider
from app.models import Document, DocumentChunk
from app.schemas import (
    DocumentResponse,
    DocumentChunkResponse,
    RAGRequest,
    RAGResponse,
    CitationResponse,
    RetrieveRequest,
    RetrievedChunkResponse,
    StructuredExtractionResponse,
    StructuredFieldEvidence,
    StructuredAnalysisResponse,
    InvestmentAnalysisRequest,
)
from app.services.rag import answer_question, analyze_investment
from app.services.analyst import process_analyst_turn
from app.services.retrieval import index_document_embeddings, retrieve
from app.services.structured_extraction import extract_from_document

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/", response_model=list[DocumentResponse])
def list_documents(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return (
        db.query(Document)
        .order_by(Document.id.desc())
        .limit(limit)
        .all()
    )


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc



@router.get("/{document_id}/file")
def download_document_file(document_id: int, db: Session = Depends(get_db)):
    """Serve stored PDF when available; otherwise redirect to source URL."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.storage_path:
        path = Path(doc.storage_path)
        if path.is_file():
            return FileResponse(
                path,
                media_type=doc.mime_type or "application/pdf",
                filename=doc.filename or path.name,
            )
    if doc.source_url:
        return RedirectResponse(url=doc.source_url, status_code=302)
    raise HTTPException(status_code=404, detail="No file or source URL")


@router.get(
    "/{document_id}/chunks",
    response_model=list[DocumentChunkResponse],
)
def list_chunks(document_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
        .all()
    )


@router.post("/{document_id}/index-embeddings")
def index_embeddings(document_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    count = index_document_embeddings(db, document_id)
    db.commit()
    return {"document_id": document_id, "chunks_indexed": count}


@router.post("/{document_id}/extract", response_model=list[StructuredExtractionResponse])
def extract_document(document_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    results = extract_from_document(db, document_id)
    payload = []
    for r in results:
        payload.append(
            StructuredExtractionResponse(
                property=r.property,
                evidence=[
                    StructuredFieldEvidence(
                        field=e.field,
                        value=e.value,
                        page_number=e.page_number,
                        source_text=e.source_text,
                        document_id=e.document_id,
                        document_chunk_id=e.document_chunk_id,
                        extraction_method=e.extraction_method,
                        confidence=e.confidence,
                    )
                    for e in r.evidence
                ],
                validation_errors=r.validation_errors,
                valid=r.valid,
                method=r.method,
            )
        )
    return payload


@router.post("/retrieve", response_model=list[RetrievedChunkResponse])
def retrieve_chunks(body: RetrieveRequest, db: Session = Depends(get_db)):
    results = retrieve(
        db,
        body.query,
        mode=body.mode,
        document_id=body.document_id,
        limit=body.limit,
    )
    return [
        RetrievedChunkResponse(
            chunk_id=r.chunk_id,
            document_id=r.document_id,
            chunk_index=r.chunk_index,
            page_number=r.page_number,
            text=r.text,
            score=r.score,
            method=r.method,
            document_title=r.document_title,
            source_name=r.source_name,
            filename=r.filename,
        )
        for r in results
    ]


def _rag_to_response(result) -> RAGResponse:
    structured = None
    if result.structured is not None:
        structured = StructuredAnalysisResponse(
            summary=result.structured.summary,
            strengths=result.structured.strengths,
            risks=result.structured.risks,
            due_diligence=result.structured.due_diligence,
            recommendation=result.structured.recommendation,
            deal_score=result.structured.deal_score,
            deal_rating=result.structured.deal_rating,
        )
    return RAGResponse(
        question=result.question,
        answer=result.answer,
        citations=[
            CitationResponse(
                kind=c.kind,
                source_id=c.source_id,
                title=c.title,
                excerpt=c.excerpt,
                score=c.score,
                document_id=c.document_id,
                chunk_id=c.chunk_id,
                page_number=c.page_number,
                property_id=c.property_id,
                filename=c.filename,
                source_name=c.source_name,
            )
            for c in result.citations
        ],
        structured=structured,
        context_kinds=result.context_kinds,
        property_ids=result.property_ids,
        document_ids=result.document_ids,
        chunks_used=result.chunks_used,
        method=result.method,
        mode=result.mode,
    )


@router.post("/rag", response_model=RAGResponse)
def rag_answer(
    body: RAGRequest,
    db: Session = Depends(get_db),
    provider: LocalLLMProvider = Depends(get_llm_provider),
):
    """
    Unified Research Analyst & Multi-source RAG.
    Handles valuation explanation, status inquiries, discovery, onboarding, and multi-source RAG.
    """
    analyst_res = process_analyst_turn(
        db=db,
        question=body.question,
        property_id=body.property_id,
        provider=provider,
    )
    structured = None
    if analyst_res.structured is not None:
        structured = StructuredAnalysisResponse(
            summary=analyst_res.structured.summary,
            strengths=analyst_res.structured.strengths,
            risks=analyst_res.structured.risks,
            due_diligence=analyst_res.structured.due_diligence,
            recommendation=analyst_res.structured.recommendation,
            deal_score=analyst_res.structured.deal_score,
            deal_rating=analyst_res.structured.deal_rating,
        )

    citations: list[CitationResponse] = []
    seen_c_keys: set[tuple] = set()
    for c in analyst_res.citations:
        c_key = (c.kind, c.document_id, c.page_number, c.source_id)
        if c_key not in seen_c_keys:
            seen_c_keys.add(c_key)
            citations.append(
                CitationResponse(
                    kind=c.kind,
                    source_id=c.source_id,
                    title=c.title,
                    excerpt=c.excerpt,
                    score=c.score,
                    document_id=c.document_id,
                    chunk_id=c.chunk_id,
                    page_number=c.page_number,
                    property_id=c.property_id,
                    filename=c.filename,
                    source_name=c.source_name,
                )
            )

    seen_action_urls: set[str] = set()
    for act in analyst_res.action_links:
        if act["url"] not in seen_action_urls:
            seen_action_urls.add(act["url"])
            citations.append(
                CitationResponse(
                    kind="action",
                    source_id=act["url"],
                    title=act["title"],
                    excerpt=act["url"],
                    score=1.0,
                    property_id=analyst_res.property_id,
                )
            )

    prop_ids = []
    if analyst_res.property_id:
        prop_ids.append(analyst_res.property_id)
    for c in analyst_res.citations:
        if c.property_id and c.property_id not in prop_ids:
            prop_ids.append(c.property_id)

    return RAGResponse(
        question=analyst_res.question,
        answer=analyst_res.answer,
        citations=citations,
        structured=structured,
        context_kinds=["analyst", analyst_res.intent],
        property_ids=prop_ids,
        document_ids=[c.document_id for c in analyst_res.citations if c.document_id],
        chunks_used=len(citations),
        method=analyst_res.intent,
        mode=body.mode,
    )


@router.post("/rag/investment", response_model=RAGResponse)
def rag_investment(body: InvestmentAnalysisRequest, db: Session = Depends(get_db)):
    """
    'Is this property a good investment?'

    Anchors retrieval on a property and synthesizes multi-source context.
    """
    result = analyze_investment(
        db,
        property_id=body.property_id,
        question=body.question,
        mode=body.mode,
        provider=None,
    )
    return _rag_to_response(result)
