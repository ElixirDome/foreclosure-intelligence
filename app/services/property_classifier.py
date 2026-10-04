import re


STRONG_RESIDENTIAL_PATTERNS = [
    r"\bflat\b",
    r"\bapartment\b",
    r"\bresidential flat\b",
    r"\bresidential apartment\b",
    r"\bresidential property\b",
    r"\bresidential premises\b",
    r"\bresidential house\b",
    r"\bindependent house\b",
    r"\bhouse property\b",
    r"\bvilla\b",
    r"\bduplex\b",
    r"\bbungalow\b",
]


STRONG_NON_RESIDENTIAL_PATTERNS = [
    r"\bindustrial property\b",
    r"\bindustrial premises\b",
    r"\bindustrial building\b",
    r"\bfactory\b",
    r"\bwarehouse\b",
    r"\bcommercial property\b",
    r"\bcommercial building\b",
    r"\bcommercial premises\b",
    r"\bcommercial plot\b",
    r"\bagricultural land\b",
    r"\bagricultural property\b",
]


LAND_ONLY_PATTERNS = [
    r"\bbigha\b",
    r"\bbiswas\b",
    r"\bbiswansi\b",
]


def _contains_any(text: str, patterns: list[str]) -> bool:
    return any(
        re.search(pattern, text, re.IGNORECASE)
        for pattern in patterns
    )


def is_residential_property(text: str) -> bool:
    """
    Classify an auction document for our residential-property pipeline.

    We deliberately prioritize explicit residential property terminology.
    Auction notices contain legal boilerplate, so generic words elsewhere
    in the document should not automatically reject a residential property.
    """

    text_lower = text.lower()

    has_residential = _contains_any(
        text_lower,
        STRONG_RESIDENTIAL_PATTERNS,
    )

    has_non_residential = _contains_any(
        text_lower,
        STRONG_NON_RESIDENTIAL_PATTERNS,
    )

    has_land_measurement = _contains_any(
        text_lower,
        LAND_ONLY_PATTERNS,
    )

    # Explicit residential terminology is our strongest signal.
    if has_residential:
        return True

    # Explicit commercial/industrial/agricultural terminology
    # without residential terminology means reject.
    if has_non_residential:
        return False

    # Bigha/Biswas/Biswansi without residential terminology is
    # treated as land rather than a residential property.
    if has_land_measurement:
        return False

    # If we cannot establish that it is residential, reject it.
    return False