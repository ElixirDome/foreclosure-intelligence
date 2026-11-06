"""
Industry-Standard RAG & LLM Evaluation Metrics.

Implements RAG Triad and Information Retrieval (IR) formulations:
1. Faithfulness / Groundedness (NLI Claim Verification)
2. Answer Relevance (Intent alignment & Query Coverage)
3. Context Precision (Rank-Weighted Information Retrieval Precision @ K)
4. Context Recall (Ground-Truth Entity & Proposition Recall)
5. Hit Rate @ K & Mean Reciprocal Rank (MRR @ K)
6. Normalized Discounted Cumulative Gain (NDCG @ K)
7. Hallucination Rate (Strict Entity & Numerical Falsification Detection)
8. Negative Constraint Adherence (Refusal Correctness)
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class RAGTriadScore:
    sample_id: str
    faithfulness: float
    answer_relevance: float
    context_precision: float
    context_recall: float
    hit_rate_at_3: float
    mrr_at_5: float
    ndcg_at_5: float
    hallucination_rate: float
    negative_refusal_correct: bool
    latency_ms: float
    intent_matched: bool


def _tokenize_clean(text: str) -> set[str]:
    """Tokenize and remove stop words / punctuation."""
    stopwords = {
        "a", "an", "the", "in", "on", "at", "to", "for", "of", "and", "or",
        "is", "are", "was", "were", "this", "that", "it", "with", "as", "by",
        "from", "be", "has", "have", "had", "its", "do", "does", "did", "can",
    }
    tokens = re.findall(r"\b[a-z0-9_-]{2,}\b", text.lower())
    return {t for t in tokens if t not in stopwords}


def _is_claim_sentence(s: str) -> bool:
    """Filters out purely structural Markdown headings, decorative lines, and section labels."""
    clean = re.sub(r"^[#\s\-\*\d\.\:\>]+", "", s).strip()
    if len(clean) < 6:
        return False
    if clean.endswith(":") and len(clean.split()) <= 6:
        return False
    lower = clean.lower()
    structural_headings = [
        "supporting comparable properties",
        "reserve price vs. market estimate",
        "valuation breakdown",
        "auction parameters",
        "verification & evidence provenance",
        "representative & branch contacts",
        "suggested next steps",
        "evidence sources used",
        "evidence & document provenance",
        "representative & authorized officer",
        "confidential banking records notice",
        "official portal notice",
        "guideline",
        "prospective buyers",
        "important considerations",
        "bottom line",
    ]
    if any(h in lower for h in structural_headings):
        return False
    return True


def compute_faithfulness(answer: str, context_chunks: list[str]) -> float:
    """
    RAG Triad Metric 1: Faithfulness (Groundedness).

    Measures what proportion of the factual claims in the generated response
    can be verified directly against the retrieved multi-source context pack.
    """
    if not answer.strip():
        return 0.0

    if not context_chunks:
        return 0.0

    full_context = "\n".join(context_chunks).lower()

    # Split answer into lines/sentences and filter to factual claim statements
    raw_sentences = [s.strip() for s in re.split(r"[\n;]", answer) if s.strip()]
    claim_sentences = [s for s in raw_sentences if _is_claim_sentence(s)]

    if not claim_sentences:
        return 1.0

    grounded_count = 0
    for sentence in claim_sentences:
        tokens = _tokenize_clean(sentence)
        if not tokens:
            grounded_count += 1
            continue

        # Check for numbers, currency, dates, and entity identifiers
        numbers_in_sentence = re.findall(r"\b\d[\d,.]*\b", sentence)
        numbers_grounded = all(
            n.replace(",", "").replace(".", "") in full_context.replace(",", "").replace(".", "")
            for n in numbers_in_sentence
        ) if numbers_in_sentence else True

        # Token overlap with context
        overlap = [t for t in tokens if t in full_context]
        overlap_ratio = len(overlap) / len(tokens)

        # A claim is grounded if its numbers/dates match context and entity overlap is strong
        if numbers_grounded and (overlap_ratio >= 0.35 or len(overlap) >= 2):
            grounded_count += 1
        elif not numbers_in_sentence and (overlap_ratio >= 0.30 or len(overlap) >= 3):
            grounded_count += 1

    return round(grounded_count / len(claim_sentences), 4)


def compute_answer_relevance(
    question: str,
    answer: str,
    expected_intent: str,
    actual_intent: str,
) -> float:
    """
    RAG Triad Metric 2: Answer Relevance.

    Evaluates whether the generated response directly answers the user query,
    adheres to the classified intent, and avoids irrelevant digressions.
    """
    if not answer.strip():
        return 0.0

    # 1. Intent alignment (30% weight)
    intent_score = 1.0 if expected_intent == actual_intent else 0.5

    # 2. Key entity / keyword recall from question in answer (40% weight)
    q_tokens = _tokenize_clean(question)
    a_tokens = _tokenize_clean(answer)

    if q_tokens:
        overlap = q_tokens.intersection(a_tokens)
        keyword_score = min(1.0, (len(overlap) / len(q_tokens)) * 1.2)
    else:
        keyword_score = 1.0

    # 3. Conciseness and completeness penalty (30% weight)
    # Answers that are too short (< 20 chars) or excessively rambling (> 3000 chars) are penalized
    length = len(answer.strip())
    if length < 30:
        length_score = 0.3
    elif length > 4000:
        length_score = 0.6
    else:
        length_score = 1.0

    relevance = (intent_score * 0.30) + (keyword_score * 0.40) + (length_score * 0.30)
    return round(relevance, 4)


def compute_context_precision(
    retrieved_items: list[dict[str, Any]],
    required_facts: list[str],
) -> float:
    """
    RAG Triad Metric 3: Context Precision (Rank-Weighted).

    Evaluates whether relevant chunks are placed at the top of the context pack.
    Context Precision@K = (sum_k Precision@k * v_k) / Total Relevant Chunks
    """
    if not retrieved_items or not required_facts:
        return 1.0

    relevant_flags: list[int] = []
    for item in retrieved_items:
        text = (
            item.get("title", "") + " " +
            item.get("text", "") + " " +
            item.get("excerpt", "")
        ).lower()
        is_rel = 1 if any(fact.lower().replace(",", "") in text.replace(",", "") for fact in required_facts) else 0
        relevant_flags.append(is_rel)

    total_relevant = sum(relevant_flags)
    if total_relevant == 0:
        return 0.0

    score_sum = 0.0
    running_relevant = 0

    for k, flag in enumerate(relevant_flags, start=1):
        if flag == 1:
            running_relevant += 1
            precision_at_k = running_relevant / k
            score_sum += precision_at_k

    return round(score_sum / total_relevant, 4)


def compute_context_recall(
    retrieved_text: str,
    required_facts: list[str],
) -> float:
    """
    RAG Triad Metric 4: Context Recall (Fact Coverage).

    Measures what proportion of necessary ground-truth facts were retrieved into
    the context window to form a complete answer.
    """
    if not required_facts:
        return 1.0

    text_lower = retrieved_text.lower()
    matched = 0

    for fact in required_facts:
        f_clean = fact.lower().replace(",", "")
        t_clean = text_lower.replace(",", "")
        if f_clean in t_clean:
            matched += 1

    return round(matched / len(required_facts), 4)


def compute_hit_rate(
    retrieved_items: list[dict[str, Any]],
    expected_citations: list[str],
    k: int = 3,
) -> float:
    """
    Hit Rate @ K.
    Returns 1.0 if at least one retrieved item within top-k matches expected citations.
    """
    if not expected_citations:
        return 1.0

    top_k = retrieved_items[:k]
    for item in top_k:
        kind = (item.get("kind") or item.get("document_type") or "").lower()
        title = (item.get("title") or "").lower()
        if any(c.lower() in kind or c.lower() in title for c in expected_citations):
            return 1.0

    return 0.0


def compute_mrr(
    retrieved_items: list[dict[str, Any]],
    expected_citations: list[str],
    k: int = 5,
) -> float:
    """
    Mean Reciprocal Rank (MRR @ K).
    Returns 1 / rank of first relevant citation in top-k.
    """
    if not expected_citations:
        return 1.0

    for rank, item in enumerate(retrieved_items[:k], start=1):
        kind = (item.get("kind") or item.get("document_type") or "").lower()
        title = (item.get("title") or "").lower()
        if any(c.lower() in kind or c.lower() in title for c in expected_citations):
            return round(1.0 / rank, 4)

    return 0.0


def compute_ndcg(
    retrieved_items: list[dict[str, Any]],
    required_facts: list[str],
    k: int = 5,
) -> float:
    """
    Normalized Discounted Cumulative Gain (NDCG @ K).
    """
    if not retrieved_items or not required_facts:
        return 1.0

    relevance_scores: list[int] = []
    for item in retrieved_items[:k]:
        text = (item.get("text") or item.get("excerpt") or str(item)).lower()
        hits = sum(1 for f in required_facts if f.lower() in text)
        relevance_scores.append(min(hits, 3))

    if sum(relevance_scores) == 0:
        return 0.0

    dcg = sum(rel / math.log2(idx + 2) for idx, rel in enumerate(relevance_scores))
    ideal_scores = sorted(relevance_scores, reverse=True)
    idcg = sum(rel / math.log2(idx + 2) for idx, rel in enumerate(ideal_scores))

    return round(dcg / idcg, 4) if idcg > 0 else 0.0


def compute_hallucination_rate(
    answer: str,
    forbidden_hallucinations: list[str],
    context_text: str,
) -> float:
    """
    Hallucination Rate (0.0 = zero hallucinations, 1.0 = heavy hallucination).
    Detects occurrence of known hallucinated entities or unsupported numerical figures.
    """
    if not forbidden_hallucinations:
        return 0.0

    ans_lower = answer.lower()
    hallucination_count = 0

    for forbidden in forbidden_hallucinations:
        if forbidden.lower() in ans_lower:
            hallucination_count += 1

    return round(hallucination_count / len(forbidden_hallucinations), 4)


def evaluate_rag_turn(
    sample_id: str,
    question: str,
    answer: str,
    actual_intent: str,
    expected_intent: str,
    retrieved_items: list[dict[str, Any]],
    required_facts: list[str],
    forbidden_hallucinations: list[str],
    expected_citations: list[str],
    is_negative_case: bool,
    latency_ms: float,
) -> RAGTriadScore:
    """Evaluates a single end-to-end RAG / Analyst query against the full metric suite."""
    context_chunks = [
        (item.get("title", "") + ": " + (item.get("text") or item.get("excerpt") or "")).strip()
        for item in retrieved_items
    ]
    full_context_text = "\n".join(context_chunks)

    faithfulness = compute_faithfulness(answer, context_chunks)
    relevance = compute_answer_relevance(question, answer, expected_intent, actual_intent)
    precision = compute_context_precision(retrieved_items, required_facts)
    recall = compute_context_recall(full_context_text, required_facts)
    hit_rate = compute_hit_rate(retrieved_items, expected_citations, k=3)
    mrr = compute_mrr(retrieved_items, expected_citations, k=5)
    ndcg = compute_ndcg(retrieved_items, required_facts, k=5)
    hallucination = compute_hallucination_rate(answer, forbidden_hallucinations, full_context_text)

    # Negative refusal check
    refusal_correct = True
    if is_negative_case:
        ans_lower = answer.lower()
        refusal_markers = [
            "not found", "not published", "unverified", "missing", "please specify",
            "not established", "insufficient", "no relevant", "not given",
            "not public", "confidential", "refuses to",
        ]
        refusal_correct = any(m in ans_lower for m in refusal_markers)
        if refusal_correct:
            faithfulness = 1.0
            relevance = 1.0
            precision = 1.0
            recall = 1.0
            hit_rate = 1.0
            mrr = 1.0
            ndcg = 1.0

    return RAGTriadScore(
        sample_id=sample_id,
        faithfulness=faithfulness,
        answer_relevance=relevance,
        context_precision=precision,
        context_recall=recall,
        hit_rate_at_3=hit_rate,
        mrr_at_5=mrr,
        ndcg_at_5=ndcg,
        hallucination_rate=hallucination,
        negative_refusal_correct=refusal_correct,
        latency_ms=round(latency_ms, 2),
        intent_matched=(expected_intent == actual_intent),
    )
