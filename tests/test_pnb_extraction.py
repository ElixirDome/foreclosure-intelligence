from app.services.pnb_extraction import (
    _parse_area_sqft,
    _parse_emd,
    _parse_opening_bid,
    extract_pnb_property,
    extract_pnb_properties,
)


def test_pnb_area_parser_ignores_punctuation_without_digits():
    assert _parse_area_sqft("Area: , Sq Ft") is None
    assert _parse_area_sqft("Area: . Sq Mtr") is None
    assert _parse_area_sqft("Area: , Square Yards") is None


def test_pnb_area_parser_still_converts_valid_measurements():
    assert _parse_area_sqft("Area: 1,250 Sq Ft") == 1250
    assert _parse_area_sqft("Area: 100 Sq Mtr") == 1076
    assert _parse_area_sqft("Area: 100 Sq Yards") == 900



def test_pnb_reserve_price_is_not_misreported_as_opening_bid():
    extracted = extract_pnb_property(
        "Reserve Price: Rs. 30,00,000/- EMD: Rs. 3,00,000/-"
    )
    assert extracted["reserve_price"] == 3000000.0
    assert extracted["opening_bid"] is None


def test_pnb_opening_bid_is_parsed_only_when_explicitly_labelled():
    assert _parse_opening_bid("Opening Bid: Rs. 25,00,000/-") == 2500000.0
    assert _parse_opening_bid("Starting Bid: ₹ 12.5 lakh") == 1250000.0
    assert _parse_opening_bid("Reserve Price: Rs. 30,00,000/-") is None


def test_pnb_emd_is_extracted_independently_from_reserve_price():
    extracted = extract_pnb_property(
        "Reserve Price: Rs. 30,00,000/- EMD: Rs. 3,00,000/-"
    )
    assert extracted["reserve_price"] == 3000000.0
    assert extracted["emd"] == 300000.0
    assert _parse_emd("Earnest Money Deposit: Rs. 2.5 lakh") == 250000.0
    assert _parse_emd("Reserve Price: Rs. 30,00,000/-") is None


def test_pnb_extraction_repairs_ocr_typos_and_recognizes_residential_plot():
    text = (
        "Auction Notice\n"
        "All that piece and parcel of Res1dentia1 Plot situated at "
        "Plot No. 14, Sector 8, Chandigarh measuring 120 Sq Yards. "
        "Reserve Price: Rs. 45,00,000/-"
    )
    properties = extract_pnb_properties(text)
    assert len(properties) == 1
    assert properties[0]["address"]
    assert properties[0]["reserve_price"] == 4500000.0
