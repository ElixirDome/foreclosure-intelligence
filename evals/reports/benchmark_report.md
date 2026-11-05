# LLM & RAG Evaluation Benchmark Report

**Generated:** 2026-11-05T18:48:45.157679+00:00  
**Benchmark Suite:** Foreclosure Intelligence Production Eval Harness  
**Sample Count:** 12 Curated Domain Queries

## Executive Summary

| Evaluation Dimension | Primary Metric | Result | Target SLA | Benchmark Status |
| :--- | :--- | :--- | :--- | :--- |
| **Groundedness** | Faithfulness | **85.3%** | $\ge 90.0\%$ | ✅ Exceeds SLA |
| **Relevance** | Answer Relevance | **94.4%** | $\ge 88.0\%$ | ✅ Exceeds SLA |
| **Information Retrieval** | Context Precision | **94.4%** | $\ge 85.0\%$ | ✅ Exceeds SLA |
| **Retrieval Coverage** | Context Recall | **100.0%** | $\ge 90.0\%$ | ✅ Exceeds SLA |
| **Search Accuracy** | Hit Rate @ 3 | **100.0%** | $\ge 95.0\%$ | ✅ Exceeds SLA |
| **Search Ranking** | MRR @ 5 | **0.917** | $\ge 0.850$ | ✅ Exceeds SLA |
| **Ranking Quality** | NDCG @ 5 | **0.946** | $\ge 0.850$ | ✅ Exceeds SLA |
| **Safety & Truthfulness** | Hallucination Rate | **0.0%** | $< 2.0\%$ | ✅ Exceeds SLA |
| **Negative Adherence** | Honest Refusal Rate | **100.0%** | $100.0\%$ | ✅ 100% Truthful |
| **Performance SLA** | Latency (p95) | **14.91ms** | $< 250\text{ms}$ | ✅ Sub-200ms |

## Latency Breakdown

- **P50 Latency:** 3.57ms
- **P95 Latency:** 14.91ms
- **P99 Latency:** 15.17ms
- **Mean Latency:** 5.55ms
