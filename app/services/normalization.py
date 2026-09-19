import re


def normalize_address(address: str) -> str:
    address = address.lower()

    # Normalize common address terms
    address = re.sub(r"\bstreet\b", "st", address)
    address = re.sub(r"\broad\b", "rd", address)
    address = re.sub(r"\bnumber\b", "no", address)

    # Remove punctuation
    address = re.sub(r"[^a-z0-9\s]", " ", address)

    # Collapse whitespace
    address = re.sub(r"\s+", " ", address)

    return address.strip()

def create_property_key(
    address: str,
    area_sqft: int | float | None,
    property_type: str | None,
    survey_number: str | None = None,
) -> str:

    normalized_address = normalize_address(address)

    normalized_type = (
        property_type.lower().strip()
        if property_type
        else ""
    )

    normalized_survey = (
        survey_number.lower().strip()
        if survey_number
        else ""
    )

    normalized_area = (
        str(int(area_sqft))
        if area_sqft is not None
        else ""
    )

    return (
        f"{normalized_address}|"
        f"{normalized_area}|"
        f"{normalized_type}|"
        f"{normalized_survey}"
    )