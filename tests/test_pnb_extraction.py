from app.services.pnb_extraction import _parse_area_sqft


def test_pnb_area_parser_ignores_punctuation_without_digits():
    assert _parse_area_sqft("Area: , Sq Ft") is None
    assert _parse_area_sqft("Area: . Sq Mtr") is None
    assert _parse_area_sqft("Area: , Square Yards") is None


def test_pnb_area_parser_still_converts_valid_measurements():
    assert _parse_area_sqft("Area: 1,250 Sq Ft") == 1250
    assert _parse_area_sqft("Area: 100 Sq Mtr") == 1076
    assert _parse_area_sqft("Area: 100 Sq Yards") == 900
