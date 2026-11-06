"""
Autonomous auction source endpoint discovery and candidate verification.

Inspects bank websites and auction portals to discover listing endpoints,
pagination patterns, notice documents, and sample listings.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup

from app.ingestion.source_security import UnsafeSourceURL, validate_source_url


KNOWN_BANK_DIRECTORY = {
    "pnb": {
        "name": "Punjab National Bank (PNB) E-Auction Portal",
        "primary_url": "https://www.pnb.bank.in/EAuction.aspx",
        "adapter_key": "pnb",
        "guidance": "PNB hosts public SARFAESI auction notices at EAuction.aspx with searchable zones and branches.",
    },
    "punjab national bank": {
        "name": "Punjab National Bank (PNB) E-Auction Portal",
        "primary_url": "https://www.pnb.bank.in/EAuction.aspx",
        "adapter_key": "pnb",
        "guidance": "PNB hosts public SARFAESI auction notices at EAuction.aspx with searchable zones and branches.",
    },
    "banknet": {
        "name": "BaankNet Auction Listings Portal",
        "primary_url": "https://baanknet.com",
        "adapter_key": "banknet",
        "guidance": "BaankNet (baanknet.com) direct listing API for public sector and private bank foreclosure auctions.",
    },
    "baanknet": {
        "name": "BaankNet Auction Listings Portal",
        "primary_url": "https://baanknet.com",
        "adapter_key": "banknet",
        "guidance": "BaankNet (baanknet.com) direct listing API for public sector and private bank foreclosure auctions.",
    },
    "ibapi": {
        "name": "IBAPI Portal (e-Bkray)",
        "primary_url": "https://ibapi.in",
        "adapter_key": "banknet",
        "guidance": "Public portal for 12 public sector banks' SARFAESI auctions.",
    },
    "sbi": {
        "name": "State Bank of India (SBI) Mega E-Auctions",
        "primary_url": "https://bankauctions.in/sbi",
        "adapter_key": "custom_html",
        "guidance": "SBI lists SARFAESI notices across regional STressed Assets Management branches (SAMB).",
    },
}

AUCTION_LINK_KEYWORDS = [
    "eauction",
    "e-auction",
    "sarfaesi",
    "sale notice",
    "auction notice",
    "property auction",
    "tender",
    "mega auction",
    "possession notice",
]


def discover_auction_source(url_or_name: str) -> dict[str, Any]:
    """
    Autonomously discovers auction listing endpoints, validates candidate routes,
    and returns evidence and preview listings.
    """
    raw_query = url_or_name.strip()
    query_lower = raw_query.lower()

    # 1. Match against known bank portals if a bank name or alias is supplied
    for key, info in KNOWN_BANK_DIRECTORY.items():
        if key in query_lower:
            return _inspect_and_verify_endpoint(
                target_url=info["primary_url"],
                suggested_name=info["name"],
                adapter_key=info["adapter_key"],
                initial_query=raw_query,
            )

    # 2. If it's a URL or domain, normalize it
    if not query_lower.startswith(("http://", "https://")):
        if "." in query_lower:
            target_url = "https://" + raw_query
        else:
            return {
                "status": "failed",
                "source_name": raw_query,
                "candidate_url": None,
                "adapter_key": "custom_html",
                "confidence": "none",
                "evidence": ["Input does not appear to be a recognized bank name or valid URL."],
                "sample_listings": [],
                "failure_reason": f"Could not match '{raw_query}' to any known banking portal or parseable web address.",
                "guidance": "Enter a recognized bank name (e.g. 'PNB', 'IBAPI', 'SBI') or a direct website address (e.g. 'https://www.pnb.bank.in').",
                "suggested_urls": [
                    "https://www.pnb.bank.in/EAuction.aspx",
                    "https://ibapi.in",
                ],
            }
    else:
        target_url = raw_query

    # Validate against SSRF restrictions
    try:
        validated_url = validate_source_url(target_url)
    except UnsafeSourceURL as err:
        return {
            "status": "failed",
            "source_name": target_url,
            "candidate_url": None,
            "adapter_key": "custom_html",
            "confidence": "none",
            "evidence": [f"Security rejection: {err}"],
            "sample_listings": [],
            "failure_reason": f"Security restriction: {err}",
            "guidance": "Please provide a publicly accessible, external bank or auction portal URL.",
            "suggested_urls": [],
        }

    parsed = urlparse(validated_url)
    domain_name = parsed.netloc.replace("www.", "")
    suggested_name = f"{domain_name.capitalize()} Auction Source"

    adapter_key = "custom_html"
    if "pnb" in domain_name:
        adapter_key = "pnb"
        suggested_name = "Punjab National Bank (PNB) Auctions"
    elif "ibapi" in domain_name or "banknet" in domain_name or "baanknet" in domain_name:
        adapter_key = "banknet"
        suggested_name = "BaankNet Auction Listings"

    return _inspect_and_verify_endpoint(
        target_url=validated_url,
        suggested_name=suggested_name,
        adapter_key=adapter_key,
        initial_query=raw_query,
    )


def _inspect_and_verify_endpoint(
    target_url: str,
    suggested_name: str,
    adapter_key: str,
    initial_query: str,
) -> dict[str, Any]:
    """Inspects the webpage, discovers sub-links, and validates auction listings."""
    evidence: list[str] = []
    sample_listings: list[dict[str, Any]] = []

    try:
        with httpx.Client(
            timeout=10.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ForeclosureIntelligence/1.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            verify=False,
        ) as client:
            resp = client.get(target_url)
            resp.raise_for_status()
            html_text = resp.text
    except Exception as exc:
        return {
            "status": "failed",
            "source_name": suggested_name,
            "candidate_url": target_url,
            "adapter_key": adapter_key,
            "confidence": "none",
            "evidence": [f"Connection attempt failed: {str(exc)}"],
            "sample_listings": [],
            "failure_reason": f"Unable to reach website endpoint at {target_url} ({exc}).",
            "guidance": (
                f"The portal at {target_url} could not be crawled automatically. "
                "Steps to connect manually:\n"
                "1. Open the portal in your browser.\n"
                "2. Navigate to 'Auctions', 'SARFAESI Notices', or 'Property Sales'.\n"
                "3. Copy the URL of the listings table or PDF view page.\n"
                "4. Paste the direct listings URL below."
            ),
            "suggested_urls": [
                f"{target_url.rstrip('/')}/EAuction.aspx",
                f"{target_url.rstrip('/')}/eauction",
                f"{target_url.rstrip('/')}/tenders",
            ],
        }

    soup = BeautifulSoup(html_text, "html.parser")
    page_title = soup.title.string.strip() if soup.title and soup.title.string else suggested_name
    evidence.append(f"HTTP 200 OK received from {target_url} (Page title: '{page_title[:60]}').")

    # Detect tables with auction indicators
    tables = soup.find_all("table")
    has_auction_table = False
    for table in tables:
        tbl_text = table.get_text().lower()
        if any(w in tbl_text for w in ["reserve price", "emd", "property description", "borrower", "khasra", "date of auction"]):
            has_auction_table = True
            evidence.append("Discovered active tabular auction grid with reserve price and EMD headers.")
            break

    # Discover candidate auction links
    candidate_links: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        link_text = (a.get_text() or "").lower()
        combined = f"{href.lower()} {link_text}"
        if any(kw in combined for kw in AUCTION_LINK_KEYWORDS):
            full_link = urljoin(target_url, href)
            if full_link not in candidate_links and full_link != target_url:
                candidate_links.append(full_link)

    # Detect PDF document attachments
    pdf_links = [
        urljoin(target_url, a["href"])
        for a in soup.find_all("a", href=True)
        if a["href"].lower().endswith(".pdf") or "viewtendereauction" in a["href"].lower()
    ]
    if pdf_links:
        evidence.append(f"Found {len(pdf_links)} downloadable auction notice PDF/document links.")

    # Detect pagination patterns
    pagination_params = []
    for form in soup.find_all("form"):
        action = form.get("action", "")
        if "auction" in action.lower():
            evidence.append(f"Discovered server-side auction query form: {action}")

    # Build representative samples
    if has_auction_table:
        for row in soup.find_all("tr")[:6]:
            cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
            if len(cells) >= 3 and any("rs" in c.lower() or "lakh" in c.lower() or "bank" in c.lower() for c in cells):
                sample_listings.append({
                    "title": cells[0][:80] if len(cells) > 0 else "Auction Item",
                    "details": " | ".join(cells[1:4]),
                    "document_url": pdf_links[0] if pdf_links else None,
                })

    if not sample_listings and pdf_links:
        for idx, pdf in enumerate(pdf_links[:3], start=1):
            sample_listings.append({
                "title": f"Auction Notice Document #{idx}",
                "details": f"Direct SARFAESI Sale Notice PDF ({urlparse(pdf).path.split('/')[-1]})",
                "document_url": pdf,
            })

    # Determine confidence and best candidate URL
    best_url = target_url
    if candidate_links and not has_auction_table:
        best_url = candidate_links[0]
        evidence.append(f"Discovered specific auction section route: {best_url}")

    if has_auction_table or len(pdf_links) >= 2 or adapter_key == "pnb":
        status = "discovered"
        confidence = "high"
    elif candidate_links or pdf_links:
        status = "partial"
        confidence = "medium"
    else:
        status = "partial"
        confidence = "low"
        evidence.append("No explicit SARFAESI tables found on top-level page; sub-routing may be required.")

    return {
        "status": status,
        "source_name": page_title if len(page_title) < 80 else suggested_name,
        "candidate_url": best_url,
        "adapter_key": adapter_key,
        "confidence": confidence,
        "evidence": evidence,
        "sample_listings": sample_listings,
        "candidate_sub_links": candidate_links[:5],
        "failure_reason": None if status == "discovered" else "Listing table could not be fully identified on top-level page without query filters.",
        "guidance": (
            "Source endpoint discovered and ready for activation."
            if status == "discovered"
            else "Ensure the URL points directly to the bank's active auction / tender notices listings page."
        ),
        "suggested_urls": candidate_links[:3] if candidate_links else [best_url],
    }
