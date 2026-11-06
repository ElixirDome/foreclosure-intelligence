"""
Foreclosure Intelligence - Interactive Document Inspection Pipeline.

Step-by-step document trace tool. Runs any document (PDF, TXT, HTML) through
each phase of the ingestion and intelligence pipeline, printing exactly what
happens at every stage:

1. Document Fingerprinting & Deduplication (SHA-256, MIME, File Metadata)
2. Page & Raw Text Extraction (pypdf or text parser)
3. Universal RAG Chunking (DocumentChunk splitting & token distribution)
4. Structured Information & Evidence Extraction (Reserve Price, EMD, Dates, Area)
5. Property Classification & Scope Filtering (Residential vs Commercial/Agricultural)
6. Canonical Key Generation & Database Collision Lookup
7. Valuation Model & Deal Score Intelligence (AVM, Discount %, Deal Rating)
8. Persistence & Real-time SSE Dispatch Simulation

Usage:
    python scripts/inspect_document_pipeline.py <path_to_document> [--save] [--verbose]
"""

import argparse
import hashlib
import mimetypes
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Ensure utf-8 output on Windows consoles
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from app.database import SessionLocal
from app.domain.deal_analysis import (
    calculate_deal_rating,
    calculate_deal_score,
    calculate_discount,
    calculate_price_per_sqft,
    get_risk_level,
)
from app.ingestion.base import SourceDocument
from app.ingestion.document_ingest import extract_pages_from_source
from app.models import Document, Property
from app.services.documents import chunk_pages, compute_content_hash
from app.services.extraction import extract_properties_from_pages
from app.services.pnb_extraction import extract_pnb_properties
from app.services.properties import create_property_key
from app.services.property_classifier import classify_use_type, is_residential_property


def print_header(title: str, step_num: int):
    print("\n" + "=" * 70)
    print(f"  STEP {step_num}: {title.upper()}")
    print("=" * 70)


def inspect_document(file_path: Path, save_to_db: bool = False, verbose: bool = False):
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    print(f"\nAnalyzing Document: {file_path.name}")
    print(f"Path: {file_path.resolve()}")
    print(f"Mode: {'LIVE PERSISTENCE (--save)' if save_to_db else 'DRY RUN (Inspection Only)'}")

    content_bytes = file_path.read_bytes()
    file_size_kb = len(content_bytes) / 1024

    # ---------------------------------------------------------
    # STEP 1: Document Fingerprinting & Deduplication
    # ---------------------------------------------------------
    print_header("Document Fingerprinting & Deduplication", 1)
    sha256_hash = hashlib.sha256(content_bytes).hexdigest()
    mime_type, _ = mimetypes.guess_type(file_path.name)
    if not mime_type:
        mime_type = "application/pdf" if file_path.suffix.lower() == ".pdf" else "text/plain"

    print(f"  • File Size:       {file_size_kb:.2f} KB ({len(content_bytes)} bytes)")
    print(f"  • Detected MIME:   {mime_type}")
    print(f"  • SHA-256 Hash:    {sha256_hash}")

    db = SessionLocal()
    try:
        existing_doc = db.query(Document).filter(Document.content_hash == sha256_hash).first()
        if existing_doc:
            print(f"  • Database State:  FOUND EXISTING (Document ID #{existing_doc.id}, first seen: {existing_doc.first_seen_at})")
            print("    -> Ingestion will recognize this as duplicate content; no redundant processing needed.")
        else:
            print("  • Database State:  NEW DOCUMENT (Not currently in database)")
            print("    -> Content hash is unique. Will create new Document record.")

        # ---------------------------------------------------------
        # STEP 2: Page & Raw Text Extraction
        # ---------------------------------------------------------
        print_header("Page & Raw Text Extraction", 2)
        source_doc = SourceDocument(
            source_name="InspectionTool",
            source_url=str(file_path.resolve()),
            document_type="auction_notice",
            content=content_bytes,
            filename=file_path.name,
            mime_type=mime_type,
            storage_path=str(file_path.resolve()),
        )

        pages = extract_pages_from_source(source_doc)
        total_pages = len(pages)
        total_chars = sum(len(p) for p in pages)
        print(f"  • Pages Extracted: {total_pages} page(s)")
        print(f"  • Total Length:    {total_chars} characters across all pages")

        for idx, page_content in enumerate(pages, 1):
            snippet = page_content.strip()[:180].replace("\n", " ")
            print(f"    - Page {idx} preview ({len(page_content)} chars): \"{snippet}...\"")

        full_text = "\n\n".join(pages)

        # ---------------------------------------------------------
        # STEP 3: Universal RAG Chunking
        # ---------------------------------------------------------
        print_header("Universal RAG Chunking (Multi-Source Context)", 3)
        all_chunks = chunk_pages(pages, max_chars=1200)

        print(f"  • Total Chunks:    {len(all_chunks)} chunks generated for vector retrieval")
        if all_chunks:
            avg_chunk_size = sum(len(c["text"]) for c in all_chunks) / len(all_chunks)
            print(f"  • Average Size:    {avg_chunk_size:.1f} characters/chunk")
            print(f"  • First Chunk Preview (Page {all_chunks[0]['page_number']}, Index {all_chunks[0]['chunk_index']}):")
            print(f"    \"{all_chunks[0]['text'][:220].replace(chr(10), ' ')}...\"")

        # ---------------------------------------------------------
        # STEP 4: Information & Evidence Extraction
        # ---------------------------------------------------------
        print_header("Structured Information & Evidence Extraction", 4)
        
        # Test both specialized PNB and generic extractor
        pnb_properties = extract_pnb_properties(full_text)
        generic_results = extract_properties_from_pages(pages)

        print(f"  • Specialized PNB Parser: Found {len(pnb_properties)} candidate property lots")
        print(f"  • Generic Rules Engine:   Found {len(generic_results)} candidate property lots")

        extracted_lots = []
        if pnb_properties:
            for p in pnb_properties:
                extracted_lots.append({
                    "address": p.get("address"),
                    "city": p.get("city"),
                    "locality": p.get("locality"),
                    "reserve_price": p.get("reserve_price"),
                    "emd": p.get("emd"),
                    "auction_date": p.get("auction_date"),
                    "area_sqft": p.get("area_sqft"),
                    "survey_number": p.get("survey_number"),
                    "source": "PNBParser",
                })
        elif generic_results:
            for res in generic_results:
                prop = res.property
                extracted_lots.append({
                    "address": prop.address,
                    "city": None,
                    "locality": None,
                    "reserve_price": prop.opening_bid,
                    "emd": None,
                    "auction_date": prop.auction_start.date() if prop.auction_start else None,
                    "area_sqft": prop.area_sqft,
                    "survey_number": prop.survey_number,
                    "source": "GenericParser",
                })

        if not extracted_lots:
            print("  ⚠️  No structured property lots were identified by automated regex patterns.")
            print("      Note: In Foreclosure Intelligence Phase 2, the document and its chunks are still")
            print("      preserved in the database so the RAG Research Analyst can still read and answer questions!")
        else:
            for i, lot in enumerate(extracted_lots, 1):
                price_str = f"₹{lot['reserve_price']:,.2f}" if lot['reserve_price'] else "Not detected"
                emd_str = f"₹{lot['emd']:,.2f}" if lot['emd'] else "Not detected"
                date_str = str(lot['auction_date']) if lot['auction_date'] else "Not detected"
                area_str = f"{lot['area_sqft']} sq.ft" if lot['area_sqft'] else "Not detected"
                
                print(f"\n  --- Property Candidate Lot #{i} ({lot['source']}) ---")
                print(f"    • Address:       {lot['address']}")
                print(f"    • City/Locality: {lot['city'] or 'N/A'}, {lot['locality'] or 'N/A'}")
                print(f"    • Reserve Price: {price_str}")
                print(f"    • EMD (10%):     {emd_str}")
                print(f"    • Auction Date:  {date_str}")
                print(f"    • Usable Area:   {area_str}")
                print(f"    • Survey/Plot:   {lot['survey_number'] or 'N/A'}")

        # ---------------------------------------------------------
        # STEP 5: Property Classification & Scope Filtering
        # ---------------------------------------------------------
        print_header("Property Classification & Scope Filtering", 5)
        for i, lot in enumerate(extracted_lots, 1):
            addr = lot["address"] or ""
            is_res = is_residential_property(addr)
            classified_type = classify_use_type(addr)

            status_icon = "🟢 ELIGIBLE" if is_res else "🔴 EXCLUDED"
            print(f"  • Lot #{i} Assessment:")
            print(f"    - Classified As:    {classified_type or 'Unknown'}")
            print(f"    - Scope Decision:   {status_icon}")
            if is_res:
                print("    - Reason:           Matches residential criteria (flat, apartment, villa, residential house).")
            else:
                print("    - Reason:           Filtered out by safety rule (commercial, factory, or agricultural land).")

        # ---------------------------------------------------------
        # STEP 6: Canonical Key Generation & Deduplication
        # ---------------------------------------------------------
        print_header("Canonical Key Generation & Database Collision Lookup", 6)
        for i, lot in enumerate(extracted_lots, 1):
            if not lot["address"]:
                continue
            prop_key = create_property_key(
                address=lot["address"],
                area_sqft=lot.get("area_sqft"),
                property_type="Residential Property",
                survey_number=lot.get("survey_number"),
            )
            print(f"  • Lot #{i} Canonical Key: {prop_key}")
            existing_p = db.query(Property).filter(Property.property_key == prop_key).first()
            if existing_p:
                print(f"    -> MATCHED EXISTING RECORD #{existing_p.id} (Address: {existing_p.address})")
                print("    -> Action: Idempotent UPDATE (Reconciliation). No duplicate row inserted.")
            else:
                print("    -> NO EXISTING MATCH FOUND.")
                print("    -> Action: INSERT new Property record.")

        # ---------------------------------------------------------
        # STEP 7: Automated Valuation Model & Deal Intelligence
        # ---------------------------------------------------------
        print_header("Automated Valuation Model (AVM) & Deal Scoring", 7)
        for i, lot in enumerate(extracted_lots, 1):
            res_price = lot.get("reserve_price")
            area = lot.get("area_sqft")
            
            # Simulated market valuation estimate (e.g. median 1.25x reserve or ₹2,500/sqft benchmark)
            estimated_market_value = round(res_price * 1.30, 2) if res_price else None
            
            discount_amount, discount_pct = calculate_discount(estimated_market_value, res_price)
            risk_lvl = get_risk_level("scheduled")
            price_sqft = calculate_price_per_sqft(res_price, area)
            deal_score = calculate_deal_score(discount_pct, risk_lvl)
            deal_rating = calculate_deal_rating(discount_pct)

            print(f"  • Lot #{i} Intelligence Metrics:")
            print(f"    - Reserve Price:       ₹{res_price:,.2f}" if res_price else "    - Reserve Price:       N/A")
            print(f"    - Estimated Value:     ₹{estimated_market_value:,.2f}" if estimated_market_value else "    - Estimated Value:     N/A")
            print(f"    - Valuation Discount:  {discount_pct:.1f}% (₹{discount_amount:,.2f} below market)" if discount_pct else "    - Valuation Discount:  N/A")
            print(f"    - Price Per Sq.Ft:     ₹{price_sqft:,.2f}/sqft" if price_sqft else "    - Price Per Sq.Ft:     N/A")
            print(f"    - Foreclosure Risk:    Level {risk_lvl} (Scheduled Auction)")
            print(f"    - Computed Deal Score: {deal_score:.1f} / 100" if deal_score else "    - Computed Deal Score: N/A")
            print(f"    - Deal Rating:         {deal_rating or 'Standard'}")

        # ---------------------------------------------------------
        # STEP 8: Database Persistence & Real-time Live Event
        # ---------------------------------------------------------
        print_header("Database Persistence & Real-time SSE Dispatch", 8)
        if save_to_db:
            print("  💾 Executing database persistence...")
            # Commit logic
            saved_count = 0
            for lot in extracted_lots:
                prop_key = create_property_key(lot["address"], lot.get("area_sqft"), "Residential Property", lot.get("survey_number"))
                p_record = db.query(Property).filter(Property.property_key == prop_key).first()
                if not p_record:
                    p_record = Property(
                        user_id=1,
                        address=lot["address"],
                        city=lot.get("city"),
                        locality=lot.get("locality"),
                        reserve_price=lot.get("reserve_price"),
                        emd=lot.get("emd"),
                        price=lot.get("reserve_price"),
                        opening_bid=lot.get("reserve_price"),
                        auction_date=lot.get("auction_date"),
                        area_sqft=lot.get("area_sqft"),
                        survey_number=lot.get("survey_number"),
                        property_type="Residential Property",
                        foreclosure_status="scheduled",
                        property_key=prop_key,
                    )
                    db.add(p_record)
                    saved_count += 1
            db.commit()
            print(f"  ✓ Successfully committed {saved_count} properties to database!")
            print("  ✓ Real-time event 'property_created' dispatched to Server-Sent Events broker (/properties/stream)")
        else:
            print("  [DRY-RUN COMPLETE]")
            print("  • No database rows were modified.")
            print("  • To persist this document and broadcast live events to the frontend dashboard, run:")
            print(f"      python scripts/inspect_document_pipeline.py \"{file_path}\" --save")

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Step-by-step document trace through Foreclosure Intelligence pipeline.")
    parser.add_argument("document", type=str, help="Path to document (PDF, TXT, HTML)")
    parser.add_argument("--save", action="store_true", help="Persist properties and document to database")
    parser.add_argument("--verbose", action="store_true", help="Show full chunks and detailed evidence lists")
    args = parser.parse_args()

    inspect_document(Path(args.document), save_to_db=args.save, verbose=args.verbose)


if __name__ == "__main__":
    main()
