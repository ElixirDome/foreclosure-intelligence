"""
Unified Research Analyst Engine.

Provides tool-assisted, evidence-backed conversational research for foreclosure
properties, valuations, auction status, discovery, and source onboarding.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models import (
    Document,
    DocumentChunk,
    Evidence,
    MarketComparable,
    Property,
    PropertyDocument,
    PropertyValuation,
    UserPreference,
)
from app.services.deal_intelligence import build_deal_intelligence
from app.services.query_understanding import (
    CLARIFICATION_PROMPT,
    GREETING_MESSAGE,
    QueryIntent,
    TERMINOLOGY_KNOWLEDGE,
    classify_query,
)
from app.services.rag import Citation, RAGAnswer, StructuredAnalysis, answer_question
from app.services.valuation import (
    find_comparables,
    calculate_valuation_from_comparables,
)


@dataclass
class AnalystResponse:
    question: str
    answer: str
    property_id: int | None = None
    citations: list[Citation] = field(default_factory=list)
    structured: StructuredAnalysis | None = None
    action_links: list[dict[str, str]] = field(default_factory=list)
    intent: str = "general"


def process_analyst_turn(
    db: Session,
    question: str,
    property_id: int | None = None,
    user_id: int | None = None,
    provider: Any | None = None,
) -> AnalystResponse:
    """Dispatches user query to specific domain tools or multi-source RAG."""
    # Load user location preferences if available
    user_pref = None
    if user_id:
        user_pref = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()

    u_result = classify_query(question, property_id=property_id, db=db)
    q_clean = u_result.cleaned_query
    q_lower = q_clean.lower()
    resolved_prop_id = u_result.property_id

    # 1. Ambiguous, empty, single-character, or gibberish input (never hit corpus/vector search)
    if u_result.intent == QueryIntent.AMBIGUOUS_CLARIFICATION:
        return AnalystResponse(
            question=q_clean,
            answer=u_result.clarification_message or CLARIFICATION_PROMPT,
            property_id=resolved_prop_id,
            citations=[],
            structured=None,
            action_links=u_result.action_links,
            intent="ambiguous_clarification",
        )

    # 2. Conversational Greetings (never hit corpus)
    if u_result.intent == QueryIntent.GREETING:
        return AnalystResponse(
            question=q_clean,
            answer=u_result.direct_answer or GREETING_MESSAGE,
            property_id=resolved_prop_id,
            citations=[],
            structured=None,
            action_links=u_result.action_links,
            intent="greeting",
        )

    # 3. Domain Terminology Education (authoritative legal definitions without notice search)
    if u_result.intent == QueryIntent.TERMINOLOGY:
        term_citation = []
        for key, info in TERMINOLOGY_KNOWLEDGE.items():
            if info["answer"] == u_result.direct_answer:
                term_citation.append(
                    Citation(
                        kind="statute",
                        source_id=f"statute:{key}",
                        title=info["statute_title"],
                        excerpt=info["citation"],
                        score=1.0,
                    )
                )
                break
        return AnalystResponse(
            question=q_clean,
            answer=u_result.direct_answer or "",
            property_id=None,
            citations=term_citation,
            action_links=u_result.action_links,
            intent="terminology",
        )

    # 4. Confidential Banking & Settlement Refusal (Negative Constraint Adherence)
    if u_result.intent == QueryIntent.CONFIDENTIAL_REFUSAL:
        return AnalystResponse(
            question=q_clean,
            answer=(
                "### Confidential Banking Records Notice\n\n"
                "⚠️ **Private Settlement & OTS Records Are Not Public**\n"
                "- One-Time Settlement (OTS) figures, borrower compromise arrangements, and private bank concessions are confidential.\n"
                "- Official SARFAESI auction notices state only the verified Reserve Price, Earnest Money Deposit (EMD), and Auction Date.\n"
                "- Foreclosure Intelligence strictly relies on published public auction records and refuses to speculate on non-public banking matters."
            ),
            property_id=resolved_prop_id,
            citations=[
                Citation(
                    kind="system",
                    source_id="sys:confidentiality",
                    title="SARFAESI Public Disclosure Scope",
                    excerpt="Under SARFAESI Security Interest Enforcement Rules, public notices state reserve price, EMD, and auction terms. Private borrower settlements and OTS compromises are confidential non-public banking matters.",
                    score=1.0,
                )
            ],
            intent="confidential_refusal",
        )

    # 5. Follow-Up Queries missing property context
    if u_result.intent == QueryIntent.FOLLOW_UP:
        return AnalystResponse(
            question=q_clean,
            answer=u_result.direct_answer or "",
            property_id=None,
            citations=[],
            action_links=u_result.action_links,
            intent="follow_up",
        )

    # 6. Onboarding & Source Connection Guidance
    if u_result.intent == QueryIntent.ONBOARDING_GUIDE:
        return _handle_source_onboarding_inquiry(q_clean, q_lower)

    # 7. Bank Representative & Contact Inquiry
    if u_result.intent == QueryIntent.REPRESENTATIVE_INQUIRY:
        return _handle_representative_inquiry(db, resolved_prop_id, q_clean)

    # 8. Valuation calculation & Comparables explanation
    if u_result.intent == QueryIntent.VALUATION_EXPLANATION:
        return _handle_valuation_explanation(db, resolved_prop_id, q_clean)

    # 9. Status, EMD, Reserve Price, and Auction Date inquiry
    if u_result.intent == QueryIntent.STATUS_INQUIRY:
        return _handle_status_inquiry(db, resolved_prop_id, q_clean)

    # 10. Original Notice Document inquiry
    if u_result.intent == QueryIntent.DOCUMENT_RETRIEVAL:
        return _handle_original_document_inquiry(db, resolved_prop_id, q_clean)

    # 11. Inventory Discovery / Location-Aware Search
    if u_result.intent == QueryIntent.INVENTORY_DISCOVERY:
        return _handle_discovery_search(db, q_clean, q_lower, user_pref)

    # 12. Fallback to Multi-Source RAG with Deal Intelligence
    rag_result = answer_question(
        db=db,
        question=q_clean,
        property_id=resolved_prop_id,
        mode="hybrid",
        provider=provider,
    )

    action_links = []
    if resolved_prop_id:
        action_links.append({"title": f"View Property Details #{resolved_prop_id}", "url": f"/properties/{resolved_prop_id}"})
        pdoc = db.query(PropertyDocument).filter(PropertyDocument.property_id == resolved_prop_id).first()
        if pdoc:
            action_links.append({"title": "Download Original Auction Notice", "url": f"/documents/{pdoc.document_id}/file"})

    seen_citations = set()
    deduped_citations = []
    for c in rag_result.citations:
        c_key = (c.kind, c.document_id, c.page_number, c.source_id)
        if c_key not in seen_citations:
            seen_citations.add(c_key)
            deduped_citations.append(c)

    return AnalystResponse(
        question=q_clean,
        answer=rag_result.answer,
        property_id=resolved_prop_id,
        citations=deduped_citations,
        structured=rag_result.structured,
        action_links=action_links,
        intent="investment_analysis" if resolved_prop_id else "rag_general",
    )


def _handle_source_onboarding_inquiry(question: str, q_lower: str) -> AnalystResponse:
    lines = [
        "### Connecting Foreclosure & Auction Sources",
        "",
        "Foreclosure Intelligence autonomously crawls and monitors bank e-auction portals. Here is how to connect a source:",
        "",
        "1. **Autonomous Discovery**:",
        "   - Navigate to the **Admin Import Desk** (`/import`).",
        "   - Enter the bank name (e.g. `PNB`, `IBAPI`, `SBI`) or root website address.",
        "   - The autonomous crawler inspects navigation menus, sitemaps, SARFAESI auction grids, and downloadable notices.",
        "   - Review the discovered endpoint and sample preview, then click **Connect Source**.",
        "",
        "2. **Supported Auction Portals**:",
        "   - **Punjab National Bank (PNB)**: Direct listings at `https://www.pnb.bank.in/EAuction.aspx`.",
        "   - **IBAPI (e-Bkray)**: Centralized portal for public sector banks at `https://ibapi.in`.",
        "   - **Custom Bank Portals**: Any public bank portal displaying SARFAESI auction tables or notice PDFs.",
        "",
        "3. **What if endpoint discovery cannot locate listings?**",
        "   - Some bank sites use dynamic JavaScript or Cloudflare bot checks.",
        "   - **Solution**: Open the bank's site in your browser, click 'Tenders' or 'E-Auctions / SARFAESI Notices', and copy the direct URL of the auction table or PDF view page.",
        "   - Paste that exact URL into the Admin Import Desk; our validator will immediately verify tabular headers and document links.",
    ]

    action_links = [
        {"title": "Open Admin Source Connect Desk", "url": "/import"},
    ]

    citations = [
        Citation(
            kind="system",
            source_id="sys:onboarding",
            title="Foreclosure Source Connector Guide",
            excerpt="Supported Bank Portals: Punjab National Bank (PNB at https://www.pnb.bank.in/EAuction.aspx), IBAPI (e-Bkray at https://ibapi.in), Custom Bank Portals. Admin Import Desk route: /import",
            score=1.0,
        )
    ]

    return AnalystResponse(
        question=question,
        answer="\n".join(lines),
        citations=citations,
        action_links=action_links,
        intent="onboarding_guide",
    )


def _extract_representative_from_text(text: str) -> dict[str, str | None]:
    if not text:
        return {}
    res: dict[str, str | None] = {}

    # 1. Officer Designation
    m_officer = re.search(
        r"(Authori[sz]ed\s+Of[f\uFB01\uFB02]+icer(?:\s*of\s*(?:the\s*)?Bank|\s*Punjab\s*National\s*Bank|[^,\n\(\)]{0,50})?)",
        text,
        re.IGNORECASE,
    )
    if m_officer:
        off_str = re.sub(r"\s+", " ", m_officer.group(1)).strip()
        if "officerofthebank" in off_str.lower():
            off_str = "Authorised Officer of the Bank / Secured Creditor"
        res["officer"] = off_str
    else:
        m_mgr = re.search(r"((?:Chief\s+Manager|Branch\s+Manager|Nodal\s+Officer|Recovery\s+Officer)[^\n,\(]{0,40})", text, re.IGNORECASE)
        res["officer"] = re.sub(r"\s+", " ", m_mgr.group(1)).strip() if m_mgr else "Authorised Officer"

    # 2. Branch / Asset Recovery Office
    m_branch = re.search(
        r"([A-Za-z0-9\s\-]+(?:ARMB|SAMB|Asset Recovery Management Branch)[^\n\(\)]*)",
        text,
        re.IGNORECASE,
    )
    if m_branch:
        res["branch"] = re.sub(r"\s+", " ", m_branch.group(1)).strip()

    # 3. Office Address
    m_addr = re.search(r"\((Near[^\)]+?\d{6}[^\)]*)\)", text, re.IGNORECASE)
    if not m_addr:
        m_addr = re.search(r"([^\n]+(?:Saili Road|Civil Lines|Model Town|GT Road)[^\n]+)", text, re.IGNORECASE)
    if m_addr:
        res["address"] = re.sub(r"\s+", " ", m_addr.group(1)).strip()

    # 4. Phone / Mobile
    m_phone = re.search(
        r"(?:\[?Phone(?:\s*No\.?)?\]?|Contact(?:\s*No\.?)?|Mobile(?:\s*No\.?)?|Tel\.?)\s*[:\-]?\s*([+0-9\s,\-/]{8,25})",
        text,
        re.IGNORECASE,
    )
    if m_phone:
        res["phone"] = m_phone.group(1).strip()
    else:
        m_phone2 = re.search(r"\b(?:\+91[- ]?)?[6-9]\d{9}\b", text)
        if m_phone2:
            res["phone"] = m_phone2.group(0).strip()

    # 5. Email
    m_email = re.search(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", text, re.IGNORECASE)
    if m_email:
        res["email"] = m_email.group(1).strip()

    # 6. Place & Date
    m_place = re.search(r"PLACE\s*[:\-]?\s*([A-Za-z]+)", text, re.IGNORECASE)
    m_date = re.search(r"DATE\s*[:\-]?\s*(\d{2}[./-]\d{2}[./-]\d{4})", text, re.IGNORECASE)
    if m_place:
        res["place"] = m_place.group(1).strip()
    if m_date:
        res["notice_date"] = m_date.group(1).strip()

    return res


def _handle_representative_inquiry(db: Session, property_id: int | None, question: str) -> AnalystResponse:
    if property_id is None:
        return AnalystResponse(
            question=question,
            answer=(
                "### Bank Representative & Contact Inquiries\n\n"
                "To look up the authorized officer or representative for a foreclosure auction, "
                "please specify the property lot or open a property:\n"
                "- E.g.: *\"Who is the representative for Lot #40?\"*\n"
                "- Or click **Ask Analyst** on any property card from the dashboard."
            ),
            intent="representative_inquiry",
            action_links=[{"title": "Open Dashboard", "url": "/dashboard"}],
        )

    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        return AnalystResponse(
            question=question,
            answer=f"Property #{property_id} was not found in the database.",
            property_id=property_id,
            intent="representative_inquiry",
        )

    # Find associated notice document(s)
    pdocs = db.query(PropertyDocument).filter(PropertyDocument.property_id == property_id).all()
    if not pdocs:
        return AnalystResponse(
            question=question,
            answer=(
                f"### Bank Representative for Lot #{prop.id}\n"
                f"**Property**: {prop.address}\n\n"
                f"⚠️ **Notice Document Missing**\n"
                f"- No auction notice documents are currently linked to Property #{prop.id} on record.\n"
                f"- **Recommendation**: Contact the secured creditor directly or verify the auction listing in the Admin Import desk."
            ),
            property_id=property_id,
            intent="representative_inquiry",
            action_links=[{"title": f"View Property Details #{prop.id}", "url": f"/properties/{prop.id}"}],
        )

    doc_ids = [pd.document_id for pd in pdocs]
    docs = db.query(Document).filter(Document.id.in_(doc_ids)).all()

    rep_info: dict[str, str | None] = {}
    target_doc: Document | None = None
    matching_chunk: DocumentChunk | None = None

    for doc in docs:
        chunks = (
            db.query(DocumentChunk)
            .filter(DocumentChunk.document_id == doc.id)
            .order_by(DocumentChunk.chunk_index)
            .all()
        )
        full_text = doc.extracted_text or ""
        extracted = _extract_representative_from_text(full_text)
        if extracted.get("phone") or extracted.get("email") or extracted.get("branch"):
            rep_info = extracted
            target_doc = doc
            for chunk in chunks:
                c_text = chunk.text.lower()
                if (extracted.get("phone") and extracted["phone"] in chunk.text) or \
                   (extracted.get("email") and extracted["email"] in chunk.text) or \
                   ("armb" in c_text or "officer" in c_text):
                    matching_chunk = chunk
                    break
            break

    citations: list[Citation] = []
    action_links = [
        {"title": f"View Property Details #{prop.id}", "url": f"/properties/{prop.id}"}
    ]

    if rep_info and target_doc:
        bank_name = target_doc.source_name or "Punjab National Bank (PNB)"
        lines = [
            f"### Bank Representative & Authorized Officer for Lot #{prop.id}",
            f"**Property**: {prop.address} ({prop.city or 'General'})",
            f"**Secured Creditor**: {bank_name}",
            "",
            "#### Representative & Branch Contacts:",
            f"- **Official Designation**: {rep_info.get('officer', 'Authorised Officer')}",
            f"- **Branch / Recovery Office**: {rep_info.get('branch', 'Asset Recovery Management Branch')}",
            f"- **Office Address**: {rep_info.get('address') or 'Refer to auction notice'}",
            f"- **Contact Phone**: `{rep_info['phone']}`" if rep_info.get("phone") else "- **Contact Phone**: ⚠️ Not stated in notice",
            f"- **Email**: `{rep_info['email']}`" if rep_info.get("email") else "- **Email**: ⚠️ Not stated in notice",
        ]
        if rep_info.get("notice_date") or rep_info.get("place"):
            lines.append(f"- **Notice Origin**: {rep_info.get('place', 'Headquarters')} (Notice Date: {rep_info.get('notice_date', 'On file')})")

        lines.extend([
            "",
            "#### Evidence & Document Provenance:",
            f"- Extracted from official auction notice: **{target_doc.title}** (Doc #{target_doc.id}, Page {matching_chunk.page_number if matching_chunk else 1})",
            f"- **Publisher**: {target_doc.source_name}",
        ])

        if target_doc.source_url:
            lines.append(f"- **Official Portal Notice**: {target_doc.source_url}")

        citations.append(
            Citation(
                kind="document",
                source_id=f"doc:{target_doc.id}:rep",
                title=f"Bank Representative Notice: {target_doc.title}",
                excerpt=(
                    f"Authorized Officer / Contact: {rep_info.get('officer')} | "
                    f"Branch: {rep_info.get('branch')} | "
                    f"Phone: {rep_info.get('phone')} | "
                    f"Email: {rep_info.get('email')} | "
                    f"Address: {rep_info.get('address')}"
                )[:400],
                score=1.0,
                document_id=target_doc.id,
                chunk_id=matching_chunk.id if matching_chunk else None,
                page_number=matching_chunk.page_number if matching_chunk else 1,
                property_id=property_id,
                filename=target_doc.filename,
                source_name=target_doc.source_name,
            )
        )
        action_links.append({"title": "Download Original Auction Notice", "url": f"/documents/{target_doc.id}/file"})

        return AnalystResponse(
            question=question,
            answer="\n".join(lines),
            property_id=property_id,
            citations=citations,
            action_links=action_links,
            intent="representative_inquiry",
        )
    else:
        ref_doc = docs[0] if docs else None
        doc_title = ref_doc.title if ref_doc else "Auction Notice"
        doc_id = ref_doc.id if ref_doc else None
        bank_label = ref_doc.source_name if ref_doc else "Bank / Secured Creditor"

        lines = [
            f"### Bank Representative & Contact Inquiries for Lot #{prop.id}",
            f"**Property**: {prop.address}",
            "",
            "⚠️ **Representative Contact Details Not Found in Notice**",
            f"- The indexed auction notice (**{doc_title}**) does not list a direct designated authorized officer name, contact phone, or branch email for this property.",
            f"- **Secured Creditor**: {bank_label}",
            "",
            "#### Suggested Next Steps:",
            "- Review the full original auction notice PDF for unindexed fine print or addenda.",
            "- Inquire directly with the bank's nearest regional asset recovery or SARFAESI branch.",
        ]
        if ref_doc:
            citations.append(
                Citation(
                    kind="document",
                    source_id=f"doc:{ref_doc.id}",
                    title=f"Source Notice: {ref_doc.title}",
                    excerpt="No direct representative phone number or email was extracted from this notice.",
                    score=0.8,
                    document_id=ref_doc.id,
                    property_id=property_id,
                    source_name=ref_doc.source_name,
                )
            )
            action_links.append({"title": "Download Original Auction Notice", "url": f"/documents/{ref_doc.id}/file"})

        return AnalystResponse(
            question=question,
            answer="\n".join(lines),
            property_id=property_id,
            citations=citations,
            action_links=action_links,
            intent="representative_inquiry",
        )


def _handle_valuation_explanation(db: Session, property_id: int, question: str) -> AnalystResponse:
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        return AnalystResponse(
            question=question,
            answer=f"Property #{property_id} was not found in the database.",
            property_id=property_id,
        )

    comparables = find_comparables(db, prop)
    valuation_calc = None
    if prop.area_sqft and prop.area_sqft > 0 and len(comparables) >= 3:
        try:
            valuation_calc = calculate_valuation_from_comparables(prop.area_sqft, comparables)
        except Exception:
            pass

    deal = build_deal_intelligence(db, property_id)

    lines = [
        f"### Valuation Breakdown for Lot #{prop.id}",
        f"**Address**: {prop.address} ({prop.city or 'Unspecified City'})",
        f"**Asset Scope**: {prop.property_type or 'Residential Property'} · Area: {prop.area_sqft or 'Unknown'} sq.ft.",
        "",
    ]

    citations = [
        Citation(
            kind="property",
            source_id=f"prop:{prop.id}",
            title=f"Property Listing #{prop.id}: {prop.address}",
            excerpt=f"Address: {prop.address}, City: {prop.city or 'Gurdaspur'}, Reserve Price: ₹{prop.reserve_price or 0:,.2f}, Area: {prop.area_sqft} sqft, Type: {prop.property_type}",
            score=1.0,
            property_id=property_id,
        )
    ]
    if valuation_calc:
        med_psf = valuation_calc["median_price_per_sqft"]
        est_val = valuation_calc["estimated_value"]
        conf = valuation_calc["confidence"]
        citations.append(
            Citation(
                kind="valuation",
                source_id=f"val:{prop.id}",
                title=f"Automated Valuation Model for Lot #{prop.id}",
                excerpt=f"Estimated Market Value: ₹{est_val:,.2f}, Median PSF: ₹{med_psf:,.2f}, Confidence: {conf * 100:.0f}%, based on {len(comparables)} comparable sales in {prop.city}.",
                score=0.95,
                property_id=property_id,
            )
        )
        lines.extend([
            f"**Estimated Market Value**: ₹{est_val:,.2f}",
            f"- **Valuation Method**: Residential Comparable Sales Analysis (Statistical Median).",
            f"- **Median Price / Sq.Ft.**: ₹{med_psf:,.2f} / sq.ft. applied to {prop.area_sqft} sq.ft.",
            f"- **Confidence Score**: {conf * 100:.0f}% (based on sample size & price dispersion).",
            f"- **Comparables Used**: {len(comparables)} eligible sales in the same city/locality within ±30% area tolerance.",
            "",
            "#### Supporting Comparable Properties:",
        ])

        for idx, comp in enumerate(comparables[:4], start=1):
            psf = comp.sale_price / comp.area_sqft if comp.area_sqft else 0
            lines.append(
                f"{idx}. **{comp.address}** ({comp.city or ''}) — ₹{comp.sale_price:,.0f} ({comp.area_sqft} sq.ft. @ ₹{psf:,.0f}/sq.ft.) [Source: {comp.source}]"
            )
            citations.append(
                Citation(
                    kind="comparable",
                    source_id=f"comp:{comp.id}",
                    title=f"Comparable #{comp.id}: {comp.address}",
                    excerpt=f"Sold for ₹{comp.sale_price:,.0f} ({comp.area_sqft} sqft). Price/sqft: ₹{psf:,.0f}",
                    score=0.9,
                    property_id=property_id,
                )
            )

        if deal and deal.reserve_price:
            diff = est_val - deal.reserve_price
            pct = (diff / est_val) * 100
            lines.extend([
                "",
                "#### Reserve Price vs. Market Estimate:",
                f"- **Bank Reserve Price**: ₹{deal.reserve_price:,.2f}",
                f"- **Discount Amount**: ₹{diff:,.2f} ({pct:.1f}% discount to market estimate)",
                f"- **Deal Score**: {deal.deal_score:.0f}/100 ({deal.deal_rating or 'unrated'})",
            ])
    else:
        lines.extend([
            "**Valuation Status**: *No Automated Valuation Available*",
            f"- The engine requires at least **3 eligible comparable sales** within ±30% area tolerance in {prop.city or 'this district'}.",
            f"- Currently, {len(comparables)} matching sales were found in the comparable database.",
            "- **Rule**: The platform strictly refuses to guess valuations without verified evidence.",
        ])

    action_links = [
        {"title": f"View Full Property File #{prop.id}", "url": f"/properties/{prop.id}"},
    ]

    return AnalystResponse(
        question=question,
        answer="\n".join(lines),
        property_id=property_id,
        citations=citations,
        action_links=action_links,
        intent="valuation_explanation",
    )


def _handle_status_inquiry(db: Session, property_id: int, question: str) -> AnalystResponse:
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        return AnalystResponse(
            question=question,
            answer=f"Property #{property_id} was not found in the database.",
            property_id=property_id,
        )

    # Resolve source document if available
    pdoc = db.query(PropertyDocument).filter(PropertyDocument.property_id == property_id).first()
    doc = db.query(Document).filter(Document.id == pdoc.document_id).first() if pdoc else None
    bank_name = doc.source_name if doc else "Punjab National Bank (PNB)"

    # Fetch evidence records
    evidences = db.query(Evidence).filter(Evidence.property_id == property_id).all()
    evidence_by_field = {e.field: e for e in evidences}

    lines = [
        f"### Auction & Underwriting Status for Lot #{prop.id}",
        f"**Address**: {prop.address}",
        f"**Location**: {prop.city or 'Unspecified City'}{', ' + prop.locality if prop.locality else ''}",
        "",
        "#### Auction Parameters:",
        f"- **Secured Creditor / Bank**: `{bank_name}`",
        f"- **Foreclosure Status**: `{prop.foreclosure_status or 'scheduled'}`",
        f"- **Auction Date**: {prop.auction_date.strftime('%d %b %Y') if prop.auction_date else 'Not scheduled'}",
        f"- **Reserve Price**: {f'₹{prop.reserve_price:,.2f}' if prop.reserve_price else '⚠️ Missing / Not extracted'}",
        f"- **Earnest Money Deposit (EMD)**: {f'₹{prop.emd:,.2f}' if prop.emd else '⚠️ Missing / Not extracted'}",
        f"- **Revenue / Survey No**: {prop.survey_number or 'Unspecified'}",
        "",
        "#### Verification & Evidence Provenance:",
    ]

    citations = [
        Citation(
            kind="property",
            source_id=f"prop:{prop.id}",
            title=f"Property Listing #{prop.id}",
            excerpt=f"Address: {prop.address}, City: {prop.city or 'Gurdaspur'}, Reserve Price: ₹{prop.reserve_price or 0:,.2f}, EMD: ₹{prop.emd or 0:,.2f}, Auction Date: {prop.auction_date}, Status: {prop.foreclosure_status or 'scheduled'}",
            score=1.0,
            property_id=property_id,
        )
    ]
    if doc:
        citations.append(
            Citation(
                kind="document",
                source_id=f"doc:{doc.id}",
                title=doc.title or "Auction Notice",
                excerpt=(doc.extracted_text or doc.title or "Official auction notice")[:400],
                score=0.9,
                document_id=doc.id,
                property_id=property_id,
                source_name=doc.source_name,
            )
        )
    if evidences:
        for ev in evidences[:5]:
            lines.append(f"- **{ev.field.title()}**: `{ev.value}` (Verified via `{ev.extraction_method}` extraction from Doc #{ev.document_id}, Page {ev.page_number or 1})")
            citations.append(
                Citation(
                    kind="evidence",
                    source_id=f"ev:{ev.id}",
                    title=f"Field Evidence: {ev.field}",
                    excerpt=f"Field: {ev.field}, Value: {ev.value}, Extraction Method: {ev.extraction_method}, Source Text: {ev.source_text or ev.value}",
                    score=ev.confidence or 0.9,
                    document_id=ev.document_id,
                    page_number=ev.page_number,
                    property_id=property_id,
                )
            )
    else:
        lines.append("- *No field-level evidence records currently linked to this listing.*")

    action_links = [{"title": f"View Property Details #{prop.id}", "url": f"/properties/{prop.id}"}]
    if doc:
        first_seen = getattr(doc, "first_seen_at", None)
        date_str = first_seen.strftime('%d %b %Y') if first_seen else 'Recent'
        lines.append(f"\n**Auction Source**: {doc.source_name or 'Bank Auction Notice'} (Recorded: {date_str})")
        action_links.append({"title": "Download Original Auction Notice", "url": f"/documents/{doc.id}/file"})

    return AnalystResponse(
        question=question,
        answer="\n".join(lines),
        property_id=property_id,
        citations=citations,
        action_links=action_links,
        intent="status_inquiry",
    )


def _handle_original_document_inquiry(db: Session, property_id: int, question: str) -> AnalystResponse:
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        return AnalystResponse(question=question, answer=f"Property #{property_id} not found.", property_id=property_id)

    pdocs = db.query(PropertyDocument).filter(PropertyDocument.property_id == property_id).all()
    if not pdocs:
        return AnalystResponse(
            question=question,
            answer=f"No source auction notice documents are linked to Property #{property_id} on record.",
            property_id=property_id,
        )

    doc_ids = [pd.document_id for pd in pdocs]
    docs = db.query(Document).filter(Document.id.in_(doc_ids)).all()

    lines = [
        f"### Original Auction Notice for Lot #{prop.id}",
        f"**Property**: {prop.address}",
        "",
        f"Found **{len(docs)}** verified source notice document(s) on file:",
        "",
    ]

    action_links = []
    citations = [
        Citation(
            kind="property",
            source_id=f"prop:{prop.id}",
            title=f"Property Listing #{prop.id}",
            excerpt=f"Address: {prop.address}, City: {prop.city or 'Gurdaspur'}, Type: {prop.property_type}",
            score=1.0,
            property_id=property_id,
        )
    ]
    for d in docs:
        first_seen = getattr(d, "first_seen_at", None)
        last_seen = getattr(d, "last_seen_at", None)
        pub_str = first_seen.strftime("%d %b %Y") if first_seen else "Unknown"
        check_str = last_seen.strftime("%d %b %Y %H:%M UTC") if last_seen else "Recent"
        lines.extend([
            f"📄 **{d.title or 'Auction Notice Document'}**",
            f"- **Publishing Source**: {d.source_name or 'Bank Portal'}",
            f"- **Notice Type**: `{d.document_type or 'auction_notice'}`",
            f"- **Recorded at**: {pub_str} | **Last checked**: {check_str}",
            f"- **Original Source URL**: {d.source_url or 'Stored PDF'}",
            "",
        ])
        action_links.append({
            "title": f"Open Notice #{d.id} PDF",
            "url": f"/documents/{d.id}/file",
        })
        citations.append(
            Citation(
                kind="document",
                source_id=f"doc:{d.id}",
                title=d.title or f"Document #{d.id}",
                excerpt=(
                    f"Title: {d.title}, Publisher: {d.source_name}, Type: {d.document_type}, "
                    f"Recorded: {pub_str}, Checked: {check_str}, URL: {d.source_url}\n" +
                    (d.extracted_text[:300] if d.extracted_text else "")
                ),
                score=1.0,
                document_id=d.id,
                property_id=property_id,
                source_name=d.source_name,
            )
        )

    return AnalystResponse(
        question=question,
        answer="\n".join(lines),
        property_id=property_id,
        citations=citations,
        action_links=action_links,
        intent="document_retrieval",
    )


def _handle_discovery_search(
    db: Session,
    question: str,
    q_lower: str,
    user_pref: UserPreference | None,
) -> AnalystResponse:
    query = db.query(Property)

    # 1. Enforce residential scope
    query = query.filter(
        or_(
            func.lower(Property.property_type).ilike("%residential%"),
            func.lower(Property.property_type).ilike("%flat%"),
            func.lower(Property.property_type).ilike("%apartment%"),
            func.lower(Property.property_type).ilike("%house%"),
            func.lower(Property.property_type).ilike("%villa%"),
            func.lower(Property.property_type).ilike("%duplex%"),
        ),
        ~func.lower(Property.property_type).ilike("%commercial%"),
        ~func.lower(Property.property_type).ilike("%industrial%"),
    )

    # 2. Extract location constraints from query or user preferences
    target_city = None
    target_district = None

    # Check for specific known districts in query
    for candidate in ["gurdaspur", "pathankot", "amritsar", "ghaziabad", "noida", "ludhiana", "lucknow"]:
        if candidate in q_lower:
            target_city = candidate.capitalize()
            break

    # If no explicit city in question, fall back to user's onboarding district/city
    if not target_city and user_pref:
        if user_pref.city:
            target_city = user_pref.city
        elif user_pref.district:
            target_district = user_pref.district

    if target_city:
        query = query.filter(func.lower(Property.city).ilike(f"%{target_city.lower()}%"))
    elif target_district:
        query = query.filter(
            or_(
                func.lower(Property.city).ilike(f"%{target_district.lower()}%"),
                func.lower(Property.address).ilike(f"%{target_district.lower()}%"),
            )
        )

    # 3. Extract price ceiling (e.g. "below 50 lakh", "under 4000000")
    price_match = re.search(r"(?:below|under|<)\s*(?:rs\.?|inr)?\s*([\d\.,]+)\s*(lakh|cr)?", q_lower)
    if price_match:
        val_str = price_match.group(1).replace(",", "")
        unit = price_match.group(2)
        try:
            val = float(val_str)
            if unit == "lakh":
                val *= 100000
            elif unit == "cr":
                val *= 10000000
            query = query.filter(Property.reserve_price <= val)
        except ValueError:
            pass

    results = query.order_by(Property.auction_date.desc().nullslast(), Property.id.desc()).limit(6).all()

    loc_desc = target_city or target_district or "your monitored areas"
    lines = [
        f"### Latest Residential Auctions ({loc_desc})",
        f"Found **{len(results)}** active residential auction lots:",
        "",
    ]

    action_links = []
    citations = []
    if results:
        for p in results:
            rp_str = f"₹{p.reserve_price:,.0f}" if p.reserve_price else "Price pending"
            date_str = p.auction_date.strftime("%d %b %Y") if p.auction_date else "Date unannounced"
            lines.append(
                f"- **Lot #{p.id}**: {p.address} ({p.city or 'General'}) — **Reserve: {rp_str}** | Auction: `{date_str}`"
            )
            action_links.append({
                "title": f"Open Lot #{p.id}",
                "url": f"/properties/{p.id}",
            })
            citations.append(
                Citation(
                    kind="property",
                    source_id=f"prop:{p.id}",
                    title=f"Lot #{p.id}: {p.address} ({p.city or 'Gurdaspur'})",
                    excerpt=f"Address: {p.address}, City: {p.city or 'Gurdaspur'}, Reserve: {rp_str}, Status: {p.foreclosure_status or 'scheduled'}, Auction: {date_str}",
                    score=1.0,
                    property_id=p.id,
                )
            )
    else:
        lines.append(f"No properties matching your criteria were found in {loc_desc}. Try broadening your search or connecting additional auction sources in Admin.")

    action_links.append({"title": "Open Filtered Dashboard", "url": "/dashboard"})

    return AnalystResponse(
        question=question,
        answer="\n".join(lines),
        citations=citations,
        action_links=action_links,
        intent="inventory_discovery",
    )
