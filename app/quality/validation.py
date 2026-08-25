"""Validation module — deterministic field validation."""

from __future__ import annotations

import re
from typing import Any

from app.models import FieldValidation


# Required fields that must not be None/empty
_REQUIRED_FIELDS = [
    "Company Name",
    "Ceo/Founder Name",
]

# Regex patterns
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
_URL_RE = re.compile(r"^https?://[^\s/$.?#].[^\s]*$")
_LINKEDIN_RE = re.compile(r"^https?://(www\.)?linkedin\.com/in/[a-zA-Z0-9._%-]+/?$")
_YEAR_RE = re.compile(r"^\d{4}$")
_PHONE_RE = re.compile(r"^[\d\s\-\+\(\)]{7,15}$")


def validate_lead(cleaned: dict[str, Any]) -> list[FieldValidation]:
    """Validate a cleaned lead dict. Returns list of field validation results."""
    validations: list[FieldValidation] = []

    # Company Name — required
    validations.append(_validate_required("Company Name", cleaned.get("Company Name")))

    # Website — URL format
    validations.append(_validate_url("Website", cleaned.get("Website")))

    # Industry — present
    validations.append(_validate_present("Industry", cleaned.get("Industry")))

    # Founded — year format
    validations.append(_validate_year("Founded", cleaned.get("Founded")))

    # Revenue — present (optional field, but validate format if present)
    validations.append(_validate_present("Revenue", cleaned.get("Revenue")))

    # City/Country — present
    validations.append(_validate_present("City/Country", cleaned.get("City/Country")))

    # Ceo/Founder Name — required
    validations.append(_validate_required("Ceo/Founder Name", cleaned.get("Ceo/Founder Name")))

    # CEO LinkedIn — URL format
    validations.append(_validate_linkedin("CEO Linkedn", cleaned.get("CEO Linkedn")))

    # Marketing Head name — present
    validations.append(_validate_present("Marketing Head name", cleaned.get("Marketing Head name")))

    # Marketing Head LinkedIn — URL format
    validations.append(_validate_linkedin("Marketing Head Linkedn", cleaned.get("Marketing Head Linkedn")))

    # Contact email — email format
    validations.append(_validate_email("Contact email", cleaned.get("Contact email")))

    return validations


def _validate_required(field: str, value: str | None) -> FieldValidation:
    """Validate that a required field is present."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return FieldValidation(field=field, value=value, status="invalid", issues=["required_field_missing"])
    return FieldValidation(field=field, value=value, status="valid", issues=[])


def _validate_present(field: str, value: str | None) -> FieldValidation:
    """Validate that a field is present (not required but recommended)."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return FieldValidation(field=field, value=value, status="missing", issues=["field_not_provided"])
    return FieldValidation(field=field, value=value, status="valid", issues=[])


def _validate_url(field: str, value: str | None) -> FieldValidation:
    """Validate URL format."""
    if value is None:
        return FieldValidation(field=field, value=None, status="missing", issues=["field_not_provided"])
    if not _URL_RE.match(str(value)):
        return FieldValidation(field=field, value=str(value), status="invalid", issues=["invalid_url_format"])
    return FieldValidation(field=field, value=str(value), status="valid", issues=[])


def _validate_email(field: str, value: str | None) -> FieldValidation:
    """Validate email format."""
    if value is None:
        return FieldValidation(field=field, value=None, status="missing", issues=["field_not_provided"])
    if not _EMAIL_RE.match(str(value)):
        return FieldValidation(field=field, value=str(value), status="invalid", issues=["invalid_email_format"])
    return FieldValidation(field=field, value=str(value), status="valid", issues=[])


def _validate_linkedin(field: str, value: str | None) -> FieldValidation:
    """Validate LinkedIn URL format."""
    if value is None:
        return FieldValidation(field=field, value=None, status="missing", issues=["field_not_provided"])
    if not _LINKEDIN_RE.match(str(value)):
        return FieldValidation(field=field, value=str(value), status="invalid", issues=["invalid_linkedin_url"])
    return FieldValidation(field=field, value=str(value), status="valid", issues=[])


def _validate_year(field: str, value: str | None) -> FieldValidation:
    """Validate year format (4-digit)."""
    if value is None:
        return FieldValidation(field=field, value=None, status="missing", issues=["field_not_provided"])
    if not _YEAR_RE.match(str(value)):
        return FieldValidation(field=field, value=str(value), status="invalid", issues=["invalid_year_format"])
    # Sanity check: year should be between 1800 and current year
    year = int(value)
    if year < 1800 or year > 2030:
        return FieldValidation(field=field, value=str(value), status="invalid", issues=["year_out_of_range"])
    return FieldValidation(field=field, value=str(value), status="valid", issues=[])
