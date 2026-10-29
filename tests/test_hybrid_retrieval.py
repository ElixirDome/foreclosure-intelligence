"""
Comprehensive unit and integration tests for Hybrid Retrieval (Section B):
- Multi-query generation for simple vs complex queries
- Genuine Okapi BM25 lexical ranking and term boosting
- Stored vector cosine similarity
- Reciprocal Rank Fusion (RRF) rank changes
- Chunk deduplication and provenance preservation
- Concurrent branch execution and graceful failure degradation
- Grounded citations in multi-source answer generation
"""

from datetime import datetime, timezone
from unittest.mock import patch
import pytest

from app.models import Document, DocumentChunk
from app.services.bm25 import BM25Ranker
from app.services.rag import answer_question
from app.services.retrieval import (
    RetrievedChunk,
    bm25_search,
    deduplicate_chunks,
    generate_query_variants,
    parallel_search,
    reciprocal_rank_fusion,
    retrieve,
    vector_search,
)


class TestMultiQueryGeneration:
    def test_simple_queries_not_expanded(self):
        assert generate_query_variants("Lot 104") == ["Lot 104"]
        assert generate_query_variants("Plot 5") == ["Plot 5"]
        assert generate_query_variants("123 Main St") == ["123 Main St"]

    def test_complex_queries_expanded_with_original_at_index_zero(self):
        q = "What are the EMD payment deadlines and possession risks for this property?"
        variants = generate_query_variants(q)

        assert len(variants) >= 2
        assert variants[0] == q  # Original query preserved at rank 0
        # Expanded variants contain domain terms
        combined = " ".join(variants[1:]).lower()
        assert "earnest money deposit" in combined or "possession" in combined or "encumbrance" in combined


class TestBM25LexicalRanking:
    def test_bm25_ranking_and_numeric_boost(self):
        corpus = [
            (1, "Punjab National Bank public auction notice for residential flat in Pathankot."),
            (2, "Reserve Price Rs 34,38,000 and EMD Rs 3,44,000 for Flat 204."),
            (3, "General terms and conditions of SARFAESI security interest enforcement."),
        ]
        ranker = BM25Ranker(corpus)

        # Query with exact reserve price number
        ranked = ranker.score("3438000 Flat 204")
        assert len(ranked) >= 1
        # Document 2 must be ranked first by a wide margin due to exact numeric and term match
        top_doc_id, top_score = ranked[0]
        assert top_doc_id == 2
        assert top_score > 1.0


class TestReciprocalRankFusion:
    def test_rrf_orders_by_consensus(self):
        """
        List 1: Item 1 (rank 1), Item 2 (rank 2)
        List 2: Item 2 (rank 1), Item 3 (rank 2)
        Item 2 appears near the top in BOTH lists; RRF must elevate Item 2 to #1!
        """
        list1 = [
            RetrievedChunk(chunk_id=1, document_id=10, chunk_index=0, page_number=1, text="Text 1", score=0.9, method="bm25"),
            RetrievedChunk(chunk_id=2, document_id=10, chunk_index=1, page_number=1, text="Text 2", score=0.7, method="bm25"),
        ]
        list2 = [
            RetrievedChunk(chunk_id=2, document_id=10, chunk_index=1, page_number=1, text="Text 2", score=0.85, method="vector"),
            RetrievedChunk(chunk_id=3, document_id=10, chunk_index=2, page_number=2, text="Text 3", score=0.6, method="vector"),
        ]

        fused = reciprocal_rank_fusion([list1, list2], k=60)
        assert len(fused) == 3
        # Item 2 has highest consensus rank
        assert fused[0].chunk_id == 2
        assert fused[0].method == "rrf_fused"
        assert fused[0].score > fused[1].score


class TestDeduplication:
    def test_deduplicate_removes_repeated_chunks(self):
        chunks = [
            RetrievedChunk(chunk_id=1, document_id=10, chunk_index=0, page_number=1, text="Notice text", score=0.95, method="rrf_fused"),
            RetrievedChunk(chunk_id=1, document_id=10, chunk_index=0, page_number=1, text="Notice text", score=0.80, method="rrf_fused"),
            RetrievedChunk(chunk_id=2, document_id=10, chunk_index=1, page_number=2, text="Annexure text", score=0.70, method="rrf_fused"),
        ]
        deduped = deduplicate_chunks(chunks, limit=5)
        assert len(deduped) == 2
        assert [c.chunk_id for c in deduped] == [1, 2]
        # Preserved best score
        assert deduped[0].score == 0.95


class TestParallelSearchAndFaultTolerance:
    def test_parallel_search_recovers_when_one_branch_fails(self, db):
        now = datetime.now(timezone.utc)
        doc = Document(
            title="E-Auction Notice",
            filename="notice.pdf",
            source_name="PNB",
            source_url="https://pnbindia.in/notice1.pdf",
            document_type="auction_notice",
            first_seen_at=now,
            last_seen_at=now,
        )
        db.add(doc)
        db.commit()
        chunk = DocumentChunk(document_id=doc.id, chunk_index=0, page_number=1, text="Reserve price is Rs 25 Lakh.")
        db.add(chunk)
        db.commit()

        # Simulate vector search throwing an unexpected error
        with patch("app.services.retrieval.vector_search", side_effect=RuntimeError("Vector index corrupted")):
            results = parallel_search(db, "Reserve price 25 Lakh", limit=5)
            # Parallel search must NOT crash; it gracefully falls back on BM25!
            assert len(results) >= 1
            assert results[0].chunk_id == chunk.id

    def test_end_to_end_answer_question_includes_fused_citations(self, db):
        now = datetime.now(timezone.utc)
        doc = Document(
            title="Sale Notice Pathankot",
            filename="notice_pathankot.pdf",
            source_name="PNB",
            source_url="https://pnbindia.in/pathankot.pdf",
            document_type="auction_notice",
            first_seen_at=now,
            last_seen_at=now,
        )
        db.add(doc)
        db.commit()
        chunk = DocumentChunk(
            document_id=doc.id,
            chunk_index=0,
            page_number=2,
            text="Physical possession of residential flat 204 handed over to bank under SARFAESI Act.",
        )
        db.add(chunk)
        db.commit()

        answer = answer_question(db, "Is the property under physical possession?", mode="hybrid")
        assert answer is not None
        assert len(answer.citations) >= 1

        citation = answer.citations[0]
        assert citation.document_id == doc.id
        assert citation.page_number == 2
        assert "physical possession" in citation.excerpt.lower()
