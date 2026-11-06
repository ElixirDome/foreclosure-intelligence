"""
Foreclosure Intelligence — LLM & RAG Evaluation Harness.

Provides RAG Triad and Information Retrieval (IR) evaluation metrics:
- Faithfulness / Groundedness
- Answer Relevance
- Context Precision (Rank-Weighted)
- Context Recall / Fact Coverage
- Hit Rate @ K & Mean Reciprocal Rank (MRR @ K)
- Hallucination Rate
- Negative Constraint / Honest Refusal Accuracy
- End-to-End Latency Tracking (p50, p95, p99)
"""

from evals.metrics import (
    RAGTriadScore,
    compute_faithfulness,
    compute_answer_relevance,
    compute_context_precision,
    compute_context_recall,
    compute_hit_rate,
    compute_mrr,
    compute_ndcg,
    compute_hallucination_rate,
    evaluate_rag_turn,
)
from evals.dataset import EVAL_DATASET, EvalSample

__all__ = [
    "RAGTriadScore",
    "compute_faithfulness",
    "compute_answer_relevance",
    "compute_context_precision",
    "compute_context_recall",
    "compute_hit_rate",
    "compute_mrr",
    "compute_ndcg",
    "compute_hallucination_rate",
    "evaluate_rag_turn",
    "EVAL_DATASET",
    "EvalSample",
]
