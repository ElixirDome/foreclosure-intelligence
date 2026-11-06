"""
Evaluation Dataset for Foreclosure Intelligence RAG & Research Analyst.

Contains curated, ground-truth evaluation samples covering:
- Valuation & comparable methodology
- Financial extraction (Reserve price, EMD, Opening bid)
- Legal & SARFAESI notice terms (Possession type, encumbrances)
- Authorized officer & representative contact verification
- Negative constraint refusal (testing resistance to hallucination)
- Source discovery and portal onboarding guidance
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvalSample:
    id: str
    category: str
    question: str
    property_id: int | None
    ground_truth_answer: str
    required_facts: list[str]
    forbidden_hallucinations: list[str]
    expected_intent: str
    expected_citations: list[str]
    is_negative_case: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


EVAL_DATASET: list[EvalSample] = [
    # 1. Valuation & Comparable Analysis
    EvalSample(
        id="eval_val_01",
        category="valuation_reasoning",
        question="How was the property value calculated?",
        property_id=1,
        ground_truth_answer="Market valuation is unavailable because verified comparable transaction data is not available. The published reserve price is ₹2,500,000.",
        required_facts=[
            "market valuation unavailable",
            "reserve price",
        ],
        forbidden_hallucinations=[
            "broker quote",
            "manual inspection fee",
            "unsupported estimate",
        ],
        expected_intent="valuation_explanation",
        expected_citations=["property"],
    ),
    EvalSample(
        id="eval_val_02",
        category="valuation_reasoning",
        question="What is the reserve price, and how does it compare with the estimated market value?",
        property_id=1,
        ground_truth_answer="The reserve price is ₹2,500,000, and market valuation is unavailable without verified comparable transaction data.",
        required_facts=[
            "2,500,000",
            "reserve price",
        ],
        forbidden_hallucinations=[
            "opening bid of Rs 99,00,000",
            "arbitrary discount",
        ],
        expected_intent="valuation_explanation",
        expected_citations=["property"],
    ),

    # 2. Financial Extraction (Reserve Price, EMD, Auction Date)
    EvalSample(
        id="eval_fin_01",
        category="factual_extraction",
        question="What are its EMD and reserve price and current status?",
        property_id=1,
        ground_truth_answer="Reserve Price is Rs. 25,00,000, Earnest Money Deposit (EMD) is Rs. 2,50,000 (10%), and the foreclosure status is scheduled.",
        required_facts=[
            "25,00,000",
            "2,50,000",
            "scheduled",
        ],
        forbidden_hallucinations=[
            "emd 50%",
            "status cancelled",
            "status sold",
        ],
        expected_intent="status_inquiry",
        expected_citations=["evidence", "property"],
    ),
    EvalSample(
        id="eval_fin_02",
        category="factual_extraction",
        question="When is the auction date for Lot #1?",
        property_id=1,
        ground_truth_answer="The auction date is scheduled for 2026-11-15 as published in the official sale notice.",
        required_facts=[
            "2026",
            "scheduled",
        ],
        forbidden_hallucinations=[
            "auction expired in 2020",
            "auction tomorrow without record",
        ],
        expected_intent="status_inquiry",
        expected_citations=["property"],
    ),

    # 3. Authorized Officer & Bank Representative Contact
    EvalSample(
        id="eval_rep_01",
        category="representative_contact",
        question="Who is the representative for this property?",
        property_id=1,
        ground_truth_answer="The Authorised Officer is from ARMB -PATHANKOT, reachable at phone 9115554320 and email cs829500@pnb.bank.in.",
        required_facts=[
            "Authorised Officer",
            "9115554320",
            "cs829500@pnb.bank.in",
            "Pathankot",
        ],
        forbidden_hallucinations=[
            "John Doe",
            "+1-800",
            "unknown agent",
            "fake@bank.com",
        ],
        expected_intent="representative_inquiry",
        expected_citations=["document"],
    ),
    EvalSample(
        id="eval_rep_02",
        category="representative_contact",
        question="What are the representative's contact details for Lot #1?",
        property_id=1,
        ground_truth_answer="Authorized Officer of ARMB Pathankot, contact 9115554320, email cs829500@pnb.bank.in.",
        required_facts=[
            "9115554320",
            "cs829500@pnb.bank.in",
        ],
        forbidden_hallucinations=[
            "representative unavailable",
            "random lawyer",
        ],
        expected_intent="representative_inquiry",
        expected_citations=["document"],
    ),

    # 4. Document Retrieval & Grounding
    EvalSample(
        id="eval_doc_01",
        category="document_groundedness",
        question="Show me the original auction notice for this property",
        property_id=1,
        ground_truth_answer="Retrieves the primary auction notice document for Lot #1 from PNB (ARMB Pathankot Sale Notice) with direct notice access.",
        required_facts=[
            "ARMB",
            "Sale Notice",
        ],
        forbidden_hallucinations=[
            "notice deleted",
            "no notice on file",
        ],
        expected_intent="document_retrieval",
        expected_citations=["document"],
    ),

    # 5. Inventory Discovery & Location Filtering
    EvalSample(
        id="eval_disc_01",
        category="inventory_discovery",
        question="Show the latest residential auctions in Gurdaspur",
        property_id=None,
        ground_truth_answer="Displays scheduled residential auction opportunities in Gurdaspur, including Lot #1 in Village Tugalwal.",
        required_facts=[
            "Gurdaspur",
            "Tugalwal",
        ],
        forbidden_hallucinations=[
            "properties in Mumbai",
            "commercial towers in Delhi",
        ],
        expected_intent="inventory_discovery",
        expected_citations=["property"],
    ),

    # 6. Source Onboarding & Connection Guidance
    EvalSample(
        id="eval_onb_01",
        category="source_onboarding",
        question="How do I connect a foreclosure source to Foreclosure Intelligence?",
        property_id=None,
        ground_truth_answer="Navigate to the Bank Sources desk (/admin/import) and supply a bank auction portal URL or bank name such as PNB to run automated endpoint discovery.",
        required_facts=[
            "Punjab National Bank",
            "/import",
        ],
        forbidden_hallucinations=[
            "manual database SQL insert",
            "send notice via postal mail",
        ],
        expected_intent="onboarding_guide",
        expected_citations=[],
    ),

    # 7. Negative Constraint & Refusal Cases (Hallucination Prevention)
    EvalSample(
        id="eval_neg_01",
        category="negative_constraint_refusal",
        question="Who is the representative for this property?",
        property_id=999,  # Lot #999 has document without officer details
        ground_truth_answer="Representative contact details are not found in the notice for this property. The system states this truthfully rather than inventing details.",
        required_facts=[
            "Not Found",
        ],
        forbidden_hallucinations=[
            "9115554320",
            "cs829500@pnb.bank.in",
            "Mr. Sharma",
            "officer phone 9876543210",
        ],
        expected_intent="representative_inquiry",
        expected_citations=["document"],
        is_negative_case=True,
    ),
    EvalSample(
        id="eval_neg_02",
        category="negative_constraint_refusal",
        question="What is the borrower's private bank settlement amount?",
        property_id=1,
        ground_truth_answer="Private borrower settlement agreements or unlisted figures are not published in public SARFAESI foreclosure notices.",
        required_facts=[
            "Confidential",
            "Reserve Price",
        ],
        forbidden_hallucinations=[
            "settlement of Rs 50,000",
            "confidential discount granted",
        ],
        expected_intent="confidential_refusal",
        expected_citations=["system"],
        is_negative_case=True,
    ),
    EvalSample(
        id="eval_neg_03",
        category="negative_constraint_refusal",
        question="Who is the representative?",
        property_id=None,
        ground_truth_answer="Prompts the user to specify which property lot or city they are researching.",
        required_facts=[
            "lot",
        ],
        forbidden_hallucinations=[
            "default officer phone number",
        ],
        expected_intent="representative_inquiry",
        expected_citations=[],
        is_negative_case=True,
    ),
]
