from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from . import fields as F

_DOMAIN = re.compile(r"^(?=.{4,253}$)([A-Za-z0-9]([A-Za-z0-9\-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,}$")
_EMAIL = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
_LINKEDIN = re.compile(r"^https://www\.linkedin\.com/(in|company|pub)/[^/]+/?$")

# Common addresses that are not a specific decision-maker contact.
_ROLE_EMAIL_LOCAL = {"info", "contact", "sales", "support", "hello", "admin", "office", "enquiry", "enquiries"}

SEVERITY_ORDER = {"error": 3, "warning": 2, "info": 1}


@dataclass
class Issue:
    field: str
    code: str
    severity: str  # "error" | "warning" | "info"
    message: str


@dataclass
class ValidationResult:
    is_valid: bool  # False only when a required field is missing/invalid
    issues: list[Issue] = field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "warning"]


def validate_lead(lead: dict[str, Any]) -> ValidationResult:
    """Validate a *cleaned* lead. Assumes clean_lead() has run (uses lead['_norm'])."""
    issues: list[Issue] = []
    norm = lead.get("_norm", {})

    # Required fields
    is_valid = True
    for req in F.REQUIRED_FIELDS:
        if not lead.get(req):
            issues.append(Issue(req, "required_missing", "error", f"Required field '{req}' is missing"))
            is_valid = False

    # Website
    site = lead.get(F.WEBSITE)
    if site and not _DOMAIN.match(site):
        issues.append(Issue(F.WEBSITE, "website_malformed", "error", f"Website '{site}' is not a valid domain"))
        is_valid = False

    # Email
    email = lead.get(F.CONTACT_EMAIL)
    if email:
        if not _EMAIL.match(email):
            issues.append(Issue(F.CONTACT_EMAIL, "email_malformed", "warning", f"Email '{email}' looks malformed"))
        else:
            local = email.split("@")[0]
            if local in _ROLE_EMAIL_LOCAL:
                issues.append(Issue(F.CONTACT_EMAIL, "email_role_based", "info", "Email is a generic/role address, not a named contact"))
            email_dom = norm.get("email_domain")
            if site and email_dom and email_dom != site and not email_dom.endswith("." + site) and not site.endswith("." + email_dom):
                issues.append(Issue(F.CONTACT_EMAIL, "email_domain_mismatch", "warning", f"Email domain '{email_dom}' does not match website '{site}'"))
    else:
        issues.append(Issue(F.CONTACT_EMAIL, "email_missing", "info", "No contact email"))

    # Founded year
    founded = lead.get(F.FOUNDED)
    if founded:
        try:
            year = int(founded)
            if year < 1800 or year > date.today().year:
                issues.append(Issue(F.FOUNDED, "founded_out_of_range", "warning", f"Founded year {year} is implausible"))
        except (TypeError, ValueError):
            issues.append(Issue(F.FOUNDED, "founded_unparseable", "warning", f"Founded '{founded}' is not a year"))

    # Revenue
    rev = norm.get("revenue")
    if rev and rev.get("raw") and rev.get("amount") is None:
        issues.append(Issue(F.REVENUE, "revenue_unparseable", "info", f"Revenue '{rev['raw']}' could not be parsed to a number"))

    # LinkedIn URLs
    for lf in (F.CEO_LINKEDIN, F.MKT_LINKEDIN):
        val = lead.get(lf)
        if val and not _LINKEDIN.match(val):
            issues.append(Issue(lf, "linkedin_malformed", "info", f"{lf} '{val}' is not a canonical LinkedIn URL"))

    # A person named but no way to reach/verify them
    if lead.get(F.CEO_NAME) and not lead.get(F.CEO_LINKEDIN) and not email:
        issues.append(Issue(F.CEO_NAME, "contact_unverifiable", "info", "CEO/Founder named but no LinkedIn or email to verify"))

    return ValidationResult(is_valid=is_valid, issues=issues)
