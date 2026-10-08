"""
Deterministic validation of extracted property fields (Phase 8).

LLM / regex extraction can be wrong. This layer decides whether a
value is safe to write into the database.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FieldValidation:
    field: str
    value: Any
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ExtractionValidationResult:
    valid: bool
    fields: list[FieldValidation]
    errors: list[str] = field(default_factory=list)

    @property
    def valid_fields(self) -> dict[str, Any]:
        return {
            f.field: f.value
            for f in self.fields
            if f.valid and f.value is not None
        }


def _evidence_contains_number(evidence: str | None, value: float) -> bool:
    if not evidence:
        return False
    # Accept 109, 109.0, 109.00, 1.09 crore-style is out of scope
    candidates = {
        str(int(value)) if value == int(value) else str(value),
        f"{value:.2f}",
        f"{value:.1f}",
        f"{value / 100000:.2f}",  # lakhs
        f"{value / 100000:.1f}",
        f"{value / 100000:.0f}",
    }
    text = evidence.lower().replace(",", "")
    return any(c.lower() in text for c in candidates if c)


def validate_opening_bid(
    value: Any,
    *,
    source_text: str | None = None,
    require_evidence: bool = False,
) -> FieldValidation:
    errors: list[str] = []
    warnings: list[str] = []

    if value is None:
        return FieldValidation("opening_bid", None, True, [], ["missing"])

    try:
        number = float(value)
    except (TypeError, ValueError):
        return FieldValidation(
            "opening_bid", value, False, ["not numeric"], []
        )

    if number <= 0:
        errors.append("must be positive")
    if number > 1e12:
        errors.append("unrealistically large")

    if require_evidence and source_text:
        if not _evidence_contains_number(source_text, number):
            warnings.append("evidence text does not contain the number")
    elif require_evidence and not source_text:
        warnings.append("no source evidence provided")

    return FieldValidation(
        "opening_bid",
        number,
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


def validate_area_sqft(value: Any) -> FieldValidation:
    if value is None:
        return FieldValidation("area_sqft", None, True, [], ["missing"])
    try:
        number = float(value)
    except (TypeError, ValueError):
        return FieldValidation("area_sqft", value, False, ["not numeric"], [])
    errors = []
    if number <= 0:
        errors.append("must be positive")
    if number > 1_000_000:
        errors.append("unrealistically large")
    return FieldValidation("area_sqft", number, len(errors) == 0, errors, [])


def validate_address(value: Any) -> FieldValidation:
    if value is None or str(value).strip() == "":
        return FieldValidation(
            "address", value, False, ["address is required"], []
        )
    text = str(value).strip()
    if len(text) < 5:
        return FieldValidation(
            "address", text, False, ["address too short"], []
        )
    return FieldValidation("address", text, True, [], [])


def validate_lot_number(value: Any) -> FieldValidation:
    if value is None:
        return FieldValidation("lot_number", None, True, [], ["missing"])
    text = str(value).strip()
    if not text:
        return FieldValidation("lot_number", value, False, ["empty"], [])
    return FieldValidation("lot_number", text, True, [], [])


def validate_extraction(
    data: dict[str, Any],
    *,
    evidence_by_field: dict[str, str | None] | None = None,
    require_evidence: bool = False,
) -> ExtractionValidationResult:
    """
    Validate a structured extraction dict.

    Invalid required fields mark the whole result invalid.
    Optional fields can fail individually without rejecting everything.
    """
    evidence_by_field = evidence_by_field or {}
    fields: list[FieldValidation] = []

    fields.append(validate_address(data.get("address")))
    fields.append(
        validate_opening_bid(
            data.get("opening_bid"),
            source_text=evidence_by_field.get("opening_bid"),
            require_evidence=require_evidence,
        )
    )
    fields.append(validate_area_sqft(data.get("area_sqft")))
    fields.append(validate_lot_number(data.get("lot_number")))

    # Pass-through optional string fields with light checks
    for optional in (
        "city",
        "state",
        "pincode",
        "survey_number",
        "property_type",
        "seller_name",
    ):
        val = data.get(optional)
        if val is None:
            fields.append(
                FieldValidation(optional, None, True, [], ["missing"])
            )
        else:
            fields.append(
                FieldValidation(optional, str(val).strip(), True, [], [])
            )

    required_ok = all(
        f.valid for f in fields if f.field in {"address"}
    )
    errors = []
    for f in fields:
        errors.extend(f"{f.field}: {e}" for e in f.errors)

    return ExtractionValidationResult(
        valid=required_ok and not any(
            f.field == "address" and not f.valid for f in fields
        ),
        fields=fields,
        errors=errors,
    )


def lakh_to_inr(value: float) -> float:
    """Convert amount expressed in lakhs to INR."""
    return value * 100_000


def parse_money_token(text: str) -> float | None:
    """Parse strings like '109.00 lakh', 'Rs. 83,00,000', '8300000'."""
    if not text:
        return None
    cleaned = text.lower().replace(",", "").strip()
    m = re.search(
        r"(\d+(?:\.\d+)?)\s*(lakh|lac|lacs|lakhs)?",
        cleaned,
    )
    if not m:
        return None
    try:
        number = float(m.group(1))
    except ValueError:
        return None
    if m.group(2):
        return lakh_to_inr(number)
    # Heuristic: small numbers in auction context often mean lakhs
    if number < 1000:
        return lakh_to_inr(number)
    return number
