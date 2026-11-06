"""
Integration Tests for LLM & RAG Evaluation Harness.

Validates that the production system meets strict RAG Triad, IR,
and Safety SLA thresholds on the curated domain evaluation dataset.
"""

import pytest
from evals.runner import run_evaluations
from evals.metrics import (
    compute_faithfulness,
    compute_answer_relevance,
    compute_context_precision,
    compute_context_recall,
    compute_hit_rate,
    compute_mrr,
    compute_ndcg,
    compute_hallucination_rate,
)


def test_rag_triad_benchmark_suite_thresholds():
    """Asserts that aggregate benchmark metrics exceed production SLAs."""
    summary = run_evaluations()
    metrics = summary["metrics"]

    rag_triad = metrics["rag_triad"]
    ir_perf = metrics["retrieval_performance"]
    safety = metrics["safety_and_alignment"]
    latency = metrics["latency_sla"]

    # 1. RAG Triad Groundedness & Relevance
    assert rag_triad["faithfulness"] >= 0.80, f"Faithfulness {rag_triad['faithfulness']} must be >= 80%"
    assert rag_triad["answer_relevance"] >= 0.90, f"Answer relevance {rag_triad['answer_relevance']} must be >= 90%"
    assert rag_triad["context_precision"] >= 0.85, f"Context precision {rag_triad['context_precision']} must be >= 85%"
    assert rag_triad["context_recall"] >= 0.95, f"Context recall {rag_triad['context_recall']} must be >= 95%"

    # 2. Retrieval & Ranking
    assert ir_perf["hit_rate_at_3"] >= 0.95, f"Hit@3 {ir_perf['hit_rate_at_3']} must be >= 95%"
    assert ir_perf["mrr_at_5"] >= 0.85, f"MRR@5 {ir_perf['mrr_at_5']} must be >= 0.85"
    assert ir_perf["ndcg_at_5"] >= 0.85, f"NDCG@5 {ir_perf['ndcg_at_5']} must be >= 0.85"

    # 3. Safety & Hallucination Resistance
    assert safety["hallucination_rate"] <= 0.02, f"Hallucination rate {safety['hallucination_rate']} must be <= 2%"
    assert safety["negative_refusal_accuracy"] == 1.0, "Negative constraint refusal accuracy must be 100%"

    # 4. Latency SLA
    assert latency["p95_latency_ms"] < 250.0, f"P95 latency {latency['p95_latency_ms']}ms must be < 250ms"


def test_standalone_metric_computations():
    """Unit test individual metric mathematical formulations."""
    context = [
        "Reserve price of Lot 1 is Rs. 25,00,000.",
        "Auction date is scheduled for 15 Nov 2026.",
    ]
    grounded_answer = "The reserve price is Rs. 25,00,000 and the auction is scheduled for 15 Nov 2026."
    hallucinated_answer = "The reserve price is Rs. 99,00,000 and auction is tomorrow."

    # Faithfulness
    f_score_good = compute_faithfulness(grounded_answer, context)
    f_score_bad = compute_faithfulness(hallucinated_answer, context)
    assert f_score_good > f_score_bad

    # Relevance
    rel = compute_answer_relevance("What is the reserve price?", grounded_answer, "status_inquiry", "status_inquiry")
    assert rel >= 0.80

    # Context Precision
    items = [
        {"text": "Reserve price is Rs. 25,00,000."},
        {"text": "Unrelated terms and conditions."},
    ]
    prec = compute_context_precision(items, ["25,00,000"])
    assert prec == 1.0

    # Context Recall
    rec = compute_context_recall(context[0], ["25,00,000"])
    assert rec == 1.0

    # Hit Rate & MRR
    hit = compute_hit_rate([{"kind": "property"}], ["property"], k=3)
    mrr = compute_mrr([{"kind": "document"}, {"kind": "property"}], ["property"], k=5)
    assert hit == 1.0
    assert mrr == 0.5

    # Hallucination
    hal_zero = compute_hallucination_rate("Reserve is 25 lakh", ["99 lakh"], context[0])
    hal_detected = compute_hallucination_rate("Reserve is 99 lakh", ["99 lakh"], context[0])
    assert hal_zero == 0.0
    assert hal_detected == 1.0
