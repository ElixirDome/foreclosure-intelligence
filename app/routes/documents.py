"""
Document, retrieval, extraction, and RAG API routes.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
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
def rag_answer(body: RAGRequest, db: Session = Depends(get_db)):
    """
    Multi-source RAG.

    Investment-style questions (or property_id) automatically pull
    documents + properties + evidence + comparables + valuations + deal signals.
    """
    result = answer_question(
        db,
        body.question,
        mode=body.mode,
        document_id=body.document_id,
        property_id=body.property_id,
        limit=body.limit,
        multi_source=body.multi_source,
        provider=None,
    )
    return _rag_to_response(result)


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
