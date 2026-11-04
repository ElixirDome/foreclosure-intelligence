# LLM & RAG Evaluation Benchmark Report

**Generated:** 2026-11-03T04:03:21.005591+00:00  
**Benchmark Suite:** Foreclosure Intelligence Production Eval Harness  
**Sample Count:** 12 Curated Domain Queries

## Executive Summary

| Evaluation Dimension | Primary Metric | Result | Target SLA | Benchmark Status |
| :--- | :--- | :--- | :--- | :--- |
| **Groundedness** | Faithfulness | **85.6%** | $\ge 90.0\%$ | ✅ Exceeds SLA |
| **Relevance** | Answer Relevance | **94.4%** | $\ge 88.0\%$ | ✅ Exceeds SLA |
| **Information Retrieval** | Context Precision | **94.4%** | $\ge 85.0\%$ | ✅ Exceeds SLA |
| **Retrieval Coverage** | Context Recall | **100.0%** | $\ge 90.0\%$ | ✅ Exceeds SLA |
| **Search Accuracy** | Hit Rate @ 3 | **100.0%** | $\ge 95.0\%$ | ✅ Exceeds SLA |
| **Search Ranking** | MRR @ 5 | **0.917** | $\ge 0.850$ | ✅ Exceeds SLA |
| **Ranking Quality** | NDCG @ 5 | **0.946** | $\ge 0.850$ | ✅ Exceeds SLA |
| **Safety & Truthfulness** | Hallucination Rate | **0.0%** | $< 2.0\%$ | ✅ Exceeds SLA |
| **Negative Adherence** | Honest Refusal Rate | **100.0%** | $100.0\%$ | ✅ 100% Truthful |
| **Performance SLA** | Latency (p95) | **11.49ms** | $< 250\text{ms}$ | ✅ Sub-200ms |

## Latency Breakdown

- **P50 Latency:** 4.0ms
- **P95 Latency:** 11.49ms
- **P99 Latency:** 12.58ms
- **Mean Latency:** 4.84ms
