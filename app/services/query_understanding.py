"""
Query Understanding, Intent Classification, and Conversational State Resolution.

Provides early-stage disambiguation, negative constraint enforcement, terminology
education, and conversation routing before initiating costly corpus retrieval.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from sqlalchemy.orm import Session
from app.models import Property


class QueryIntent(str, Enum):
    AMBIGUOUS_CLARIFICATION = "ambiguous_clarification"
    GREETING = "greeting"
    TERMINOLOGY = "terminology"
    CONFIDENTIAL_REFUSAL = "confidential_refusal"
    ONBOARDING_GUIDE = "onboarding_guide"
    REPRESENTATIVE_INQUIRY = "representative_inquiry"
    VALUATION_EXPLANATION = "valuation_explanation"
    STATUS_INQUIRY = "status_inquiry"
    DOCUMENT_RETRIEVAL = "document_retrieval"
    INVENTORY_DISCOVERY = "inventory_discovery"
    FOLLOW_UP = "follow_up"
    INVESTIGATIVE_UNDERWRITING = "investigative_underwriting"


@dataclass
class QueryUnderstandingResult:
    intent: QueryIntent
    cleaned_query: str
    property_id: int | None
    clarification_message: str | None = None
    direct_answer: str | None = None
    citations: list[Any] = field(default_factory=list)
    action_links: list[dict[str, str]] = field(default_factory=list)
    requires_retrieval: bool = True


CLARIFICATION_PROMPT = (
    "Could you clarify what you'd like to know? I can help explain an auction notice, "
    "check reserve price or EMD, compare a property's price with market evidence, "
    "or identify due-diligence risks."
)

GREETING_MESSAGE = (
    "Hello! I am your Foreclosure Research Analyst. I can help evaluate auction properties, "
    "explain reserve prices and EMD requirements, review title and encumbrance risks, "
    "or guide you through connecting bank auction portals."
)

DEFAULT_SUGGESTED_ACTIONS = [
    {"title": "Explore Dashboard Auctions", "url": "/dashboard"},
    {"title": "Connect a Bank Source", "url": "/import"},
]

GREETING_REGEX = re.compile(
    r"^(hi|hello|hey|good\s+morning|good\s+afternoon|good\s+evening|greetings|howdy|sup|yo|namaste)(\s+(there|analyst|bot|assistant))?[\s!.,?:;]*$",
    re.IGNORECASE,
)

GIBBERISH_PATTERNS = {
    "asdf", "asdfg", "asdfgh", "qwerty", "zxcv", "zxcvb", "test", "testing",
    "abc", "abcd", "xyz", "foo", "bar", "baz", "blah",
}

TERMINOLOGY_KNOWLEDGE: dict[str, dict[str, Any]] = {
    "sarfaesi": {
        "title": "SARFAESI Act, 2002 Framework",
        "statute_title": "SARFAESI Act, 2002 (Act 54 of 2002)",
        "citation": "Securitisation and Reconstruction of Financial Assets and Enforcement of Security Interest Act, 2002. Governs non-court recovery of secured loans through sale of mortgaged assets under Section 13.",
        "answer": (
            "### SARFAESI Act, 2002 Overview\n\n"
            "The **Securitisation and Reconstruction of Financial Assets and Enforcement of Security Interest Act, 2002** enables Indian banks and financial institutions to recover non-performing assets (NPAs) through the auction of secured properties without prior civil court intervention.\n\n"
            "**Key Underwriting Stages:**\n"
            "- **Section 13(2)**: 60-day demand notice issued to borrower/guarantor demanding repayment.\n"
            "- **Section 13(4)**: Secured creditor takes constructive/symbolic possession and publishes sale notice.\n"
            "- **Section 14**: Bank petitions the District Magistrate (DM) or Chief Metropolitan Magistrate (CMM) for physical possession.\n"
            "- **Security Interest (Enforcement) Rules, 2002**: Mandates 30-day (or 15-day subsequent) public notice with verified Reserve Price and EMD."
        ),
    },
    "emd": {
        "title": "Earnest Money Deposit (EMD) Standards",
        "statute_title": "Security Interest (Enforcement) Rules, 2002 (Rules 8 & 9)",
        "citation": "Rules 8 & 9 govern auction bidding. Earnest Money Deposit is typically fixed at 10% of Reserve Price, payable by RTGS/NEFT before the bidding cutoff.",
        "answer": (
            "### Earnest Money Deposit (EMD) in Foreclosure Auctions\n\n"
            "**Earnest Money Deposit (EMD)** is a mandatory security deposit submitted by participating bidders prior to e-auction bidding to establish bid commitment.\n\n"
            "**Key Rules & Timelines:**\n"
            "- **Standard Amount**: Fixed at **10% of the bank's Reserve Price**.\n"
            "- **Submission Deadline**: Must be deposited via RTGS/NEFT/Demand Draft before the published cutoff date/time.\n"
            "- **Auction Day**: The successful highest bidder must immediately deposit an additional **15% (to total 25%)** on the auction day or next working day.\n"
            "- **Balance 75%**: Must be paid within **15 days** of confirmation, or as agreed in writing (up to 90 days maximum).\n"
            "- **Refunds**: Unsuccessful bidders receive full EMD refunds directly to their registered source bank accounts without interest."
        ),
    },
    "possession": {
        "title": "Symbolic vs. Physical Possession in SARFAESI",
        "statute_title": "SARFAESI Act Sections 13(4) & 14",
        "citation": "Section 13(4) establishes constructive/symbolic possession; Section 14 establishes physical handover via District Magistrate or Chief Metropolitan Magistrate assistance.",
        "answer": (
            "### Symbolic Possession vs. Physical Possession\n\n"
            "Understanding possession status is the **#1 due diligence factor** before bidding on SARFAESI foreclosure properties:\n\n"
            "1. **Symbolic (Constructive) Possession (Section 13(4))**:\n"
            "   - The bank has legal rights to auction the property and has served notices.\n"
            "   - **Critical Risk**: The borrower, relatives, or tenants may still physically reside or operate on the premises.\n"
            "   - The winning bidder may inherit the burden or timeline of obtaining physical possession post-sale.\n\n"
            "2. **Physical (Actual) Possession (Section 14)**:\n"
            "   - The secured creditor has obtained physical custody, often executed with police assistance via District Magistrate (DM) or Chief Metropolitan Magistrate (CMM) orders.\n"
            "   - The property is vacant or sealed by bank locks; handover to the buyer is straightforward.\n\n"
            "⚠️ **Underwriter Recommendation**: Always confirm with the Authorized Officer whether the bank has obtained physical vacant possession or only symbolic possession before bidding."
        ),
    },
    "reserve_price": {
        "title": "Reserve Price Definition & Pricing Benchmark",
        "statute_title": "Security Interest (Enforcement) Rules, Rule 8(5)",
        "citation": "Rule 8(5) requires an approved bank valuer to assess property valuation before the authorized officer fixes the minimum reserve threshold.",
        "answer": (
            "### Reserve Price in SARFAESI Foreclosures\n\n"
            "The **Reserve Price** is the minimum threshold price established by the secured creditor below which the auction property cannot be sold under Rule 8(5) of the Security Interest (Enforcement) Rules.\n\n"
            "**Important Underwriting Distinction:**\n"
            "- **Reserve Price ≠ Independent Market Valuation**: Bank reserve prices reflect conservative distress/liquidation benchmarks determined by approved bank valuers.\n"
            "- Foreclosure Intelligence independently computes comparable market valuations from registered registry transactions to highlight market discounts and potential spreads.\n"
            "- **Increment Amount**: Bids during the live auction must increase by a predetermined minimum increment (e.g. ₹10,000 to ₹50,000)."
        ),
    },
}


def is_gibberish(text: str) -> bool:
    """Detects meaningless keystrokes, repetitive chars, or single non-words."""
    t = text.lower().strip()
    if not t:
        return True
    if len(t) <= 1:
        return True
    if t in GIBBERISH_PATTERNS:
        return True
    # Pure punctuation or non-alphanumeric
    if not re.search(r"[a-zA-Z0-9]", t):
        return True
    # All consonants of length >= 4 (e.g. "zxcvb", "sdfgh")
    if len(t) >= 4 and not re.search(r"[aeiouy]", t) and not any(c.isdigit() for c in t):
        return True
    # Excessive repeated single character (e.g. "aaaaa", ".....")
    if len(set(t)) == 1:
        return True
    return False


def classify_query(
    query: str,
    property_id: int | None = None,
    db: Session | None = None,
) -> QueryUnderstandingResult:
    """
    Analyzes intent, verifies conversation context, extracts referenced lot numbers,
    and returns routing directives without invoking search on malformed input.
    """
    q_clean = query.strip()
    q_lower = q_clean.lower()

    # 1. Ambiguous, Empty, Single-character, or Gibberish check
    if len(q_clean) <= 1 or is_gibberish(q_clean):
        return QueryUnderstandingResult(
            intent=QueryIntent.AMBIGUOUS_CLARIFICATION,
            cleaned_query=q_clean,
            property_id=property_id,
            clarification_message=CLARIFICATION_PROMPT,
            action_links=list(DEFAULT_SUGGESTED_ACTIONS),
            requires_retrieval=False,
        )

    # 2. Greeting check
    if GREETING_REGEX.match(q_clean.strip()):
        return QueryUnderstandingResult(
            intent=QueryIntent.GREETING,
            cleaned_query=q_clean,
            property_id=property_id,
            direct_answer=GREETING_MESSAGE,
            action_links=list(DEFAULT_SUGGESTED_ACTIONS),
            requires_retrieval=False,
        )

    # 3. Confidential Banking & Private Settlement Guardrail
    if any(k in q_lower for k in [
        "settlement", "ots", "one time settlement", "compromise amount",
        "private settlement", "borrower concession",
    ]):
        return QueryUnderstandingResult(
            intent=QueryIntent.CONFIDENTIAL_REFUSAL,
            cleaned_query=q_clean,
            property_id=property_id,
            requires_retrieval=False,
        )

    # 4. Property ID Extraction from query (e.g. "Lot 1", "Property #1", "Lot #2")
    resolved_prop_id = property_id
    if resolved_prop_id is None:
        lot_match = re.search(r"\b(?:lot|property|#)\s*#?(\d+)\b", q_lower)
        if lot_match:
            cand = int(lot_match.group(1))
            if db:
                if db.query(Property).filter(Property.id == cand).first():
                    resolved_prop_id = cand
            else:
                resolved_prop_id = cand

    # 5. Domain Terminology Inquiries (when not tied to a specific property)
    if resolved_prop_id is None and (
        any(q_lower.startswith(prefix) for prefix in ["what is ", "what are ", "explain ", "define ", "meaning of "])
        or "vs" in q_lower
        or "difference between" in q_lower
    ):
        if any(k in q_lower for k in ["sarfaesi", "security interest enforcement"]):
            info = TERMINOLOGY_KNOWLEDGE["sarfaesi"]
            return QueryUnderstandingResult(
                intent=QueryIntent.TERMINOLOGY,
                cleaned_query=q_clean,
                property_id=None,
                direct_answer=info["answer"],
                action_links=list(DEFAULT_SUGGESTED_ACTIONS),
                requires_retrieval=False,
            )
        if any(k in q_lower for k in ["emd", "earnest money", "deposit"]):
            info = TERMINOLOGY_KNOWLEDGE["emd"]
            return QueryUnderstandingResult(
                intent=QueryIntent.TERMINOLOGY,
                cleaned_query=q_clean,
                property_id=None,
                direct_answer=info["answer"],
                action_links=list(DEFAULT_SUGGESTED_ACTIONS),
                requires_retrieval=False,
            )
        if any(k in q_lower for k in ["possession", "symbolic", "physical possession", "section 14", "cmm", "dm order"]):
            info = TERMINOLOGY_KNOWLEDGE["possession"]
            return QueryUnderstandingResult(
                intent=QueryIntent.TERMINOLOGY,
                cleaned_query=q_clean,
                property_id=None,
                direct_answer=info["answer"],
                action_links=list(DEFAULT_SUGGESTED_ACTIONS),
                requires_retrieval=False,
            )
        if any(k in q_lower for k in ["reserve price", "opening bid", "minimum bid"]):
            info = TERMINOLOGY_KNOWLEDGE["reserve_price"]
            return QueryUnderstandingResult(
                intent=QueryIntent.TERMINOLOGY,
                cleaned_query=q_clean,
                property_id=None,
                direct_answer=info["answer"],
                action_links=list(DEFAULT_SUGGESTED_ACTIONS),
                requires_retrieval=False,
            )

    # 6. Source Onboarding & Discovery Desk Guidance
    if any(k in q_lower for k in [
        "connect", "source", "onboard", "how do i connect", "auction listings url",
        "discover", "couldn't discover", "endpoint", "portal", "website",
    ]) and not resolved_prop_id:
        return QueryUnderstandingResult(
            intent=QueryIntent.ONBOARDING_GUIDE,
            cleaned_query=q_clean,
            property_id=None,
            requires_retrieval=False,
        )

    # 7. Bank Representative & Contact Inquiry
    if any(k in q_lower for k in [
        "representative", "contact", "authorized officer", "authorised officer",
        "who to contact", "who should i contact", "phone", "email", "mobile",
        "nodal officer", "bank officer", "branch contact",
    ]) or (resolved_prop_id and any(k in q_lower for k in ["officer", "branch phone", "branch email"])):
        return QueryUnderstandingResult(
            intent=QueryIntent.REPRESENTATIVE_INQUIRY,
            cleaned_query=q_clean,
            property_id=resolved_prop_id,
            requires_retrieval=False,
        )

    # 8. Valuation calculation & Comparables explanation (Property specific)
    if resolved_prop_id and any(k in q_lower for k in [
        "valu", "estimat", "how was", "calculated", "comparable", "market value",
        "reliable", "basis", "worth",
    ]):
        return QueryUnderstandingResult(
            intent=QueryIntent.VALUATION_EXPLANATION,
            cleaned_query=q_clean,
            property_id=resolved_prop_id,
            requires_retrieval=False,
        )

    # 9. Status, EMD, Reserve Price, and Auction Date inquiry (Property specific)
    if resolved_prop_id and any(k in q_lower for k in [
        "status", "emd", "reserve", "bank", "when is", "date", "superseded",
        "withdrawn", "cancelled", "sold", "missing", "verified",
    ]):
        return QueryUnderstandingResult(
            intent=QueryIntent.STATUS_INQUIRY,
            cleaned_query=q_clean,
            property_id=resolved_prop_id,
            requires_retrieval=False,
        )

    # 10. Original Notice Document inquiry (Property specific)
    if resolved_prop_id and any(k in q_lower for k in [
        "notice", "document", "pdf", "original", "published", "checked", "download",
    ]):
        return QueryUnderstandingResult(
            intent=QueryIntent.DOCUMENT_RETRIEVAL,
            cleaned_query=q_clean,
            property_id=resolved_prop_id,
            requires_retrieval=False,
        )

    # 11. Follow-up resolution when property_id is missing for property-scoped questions
    if resolved_prop_id is None and any(k in q_lower for k in [
        "what about the emd", "what is the emd", "reserve price", "when is the auction",
        "how was it calculated", "show the notice", "who is the officer", "is this a good deal",
    ]):
        return QueryUnderstandingResult(
            intent=QueryIntent.FOLLOW_UP,
            cleaned_query=q_clean,
            property_id=None,
            direct_answer=(
                "To check auction terms, reserve price, or legal status, please specify which property lot "
                "you're referring to (e.g. *'What is the EMD for Lot #1?'*), or select a property from the dashboard."
            ),
            action_links=[{"title": "Open Filtered Dashboard", "url": "/dashboard"}],
            requires_retrieval=False,
        )

    # 12. Inventory Discovery / Location-Aware Search
    if any(k in q_lower for k in [
        "recent", "listed", "show", "find", "auctions", "district", "city",
        "below", "under", "inventory", "search",
    ]):
        return QueryUnderstandingResult(
            intent=QueryIntent.INVENTORY_DISCOVERY,
            cleaned_query=q_clean,
            property_id=None,
            requires_retrieval=False,
        )

    # 13. General Investigative Underwriting & Multi-Source RAG
    return QueryUnderstandingResult(
        intent=QueryIntent.INVESTIGATIVE_UNDERWRITING,
        cleaned_query=q_clean,
        property_id=resolved_prop_id,
        requires_retrieval=True,
    )
