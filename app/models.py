"""Normalized data structures for the research engine."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any
from datetime import date


@dataclass
class SearchResult:
    """Normalized search result from any provider."""
    title: str | None = None
    url: str = ""
    content: str | None = None
    provider: str = ""


@dataclass
class CompanyCandidate:
    """A company identified during research."""
    name: str
    website: str | None = None
    industry: str | None = None
    location: str | None = None
    employee_count: int | None = None
    founded: str | None = None
    revenue: str | None = None
    city: str | None = None
    description: str | None = None
    evidence_ids: list[str] = field(default_factory=list)


@dataclass
class PersonCandidate:
    """A person identified during research."""
    name: str
    title: str | None = None
    role: str | None = None  # "ceo_founder" or "marketing_head"
    company_name: str | None = None
    linkedin_url: str | None = None
    evidence_ids: list[str] = field(default_factory=list)


@dataclass
class ContactCandidate:
    """Contact information for a person."""
    person_name: str
    company_name: str | None = None
    email: str | None = None
    email_verified: bool | None = None
    phone: str | None = None
    evidence_ids: list[str] = field(default_factory=list)


@dataclass
class Fact:
    """A single extracted fact from evidence."""
    field: str
    value: str


@dataclass
class Evidence:
    """Research evidence collected from providers."""
    id: str = field(default_factory=lambda: f"evidence_{uuid.uuid4().hex[:8]}")
    provider: str = ""
    source_url: str = ""
    source_title: str | None = None
    content: str | None = None
    entity: str | None = None
    facts: list[Fact] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "provider": self.provider,
            "source_url": self.source_url,
            "source_title": self.source_title,
            "content": self.content,
            "entity": self.entity,
            "facts": [{"field": f.field, "value": f.value} for f in self.facts],
        }


@dataclass
class ResearchCriteria:
    """Structured interpretation of a research request."""
    company: dict[str, Any] = field(default_factory=dict)
    person: dict[str, Any] = field(default_factory=dict)
    raw_request: str = ""


@dataclass
class ResearchPlanStep:
    """A single step in the research plan."""
    step: str
    goal: str


@dataclass
class StandardLead:
    """Final lead output matching the required template.

    Fields: LeadId, Date, Category, Segment, Industry, Company Name,
    Website, Founded, Revenue, City/Country, Ceo/Founder Name,
    CEO Linkedn, Marketing Head name, Marketing Head Linkedn, Contact email
    """
    lead_id: str = field(default_factory=lambda: f"lead_{uuid.uuid4().hex[:8]}")
    date: str = field(default_factory=lambda: date.today().isoformat())
    category: str | None = None
    segment: str | None = None
    industry: str | None = None
    company_name: str | None = None
    website: str | None = None
    founded: str | None = None
    revenue: str | None = None
    city_country: str | None = None
    ceo_founder_name: str | None = None
    ceo_linkedin: str | None = None
    marketing_head_name: str | None = None
    marketing_head_linkedin: str | None = None
    contact_email: str | None = None
    evidence_refs: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "LeadId": self.lead_id,
            "Date": self.date,
            "Category": self.category,
            "Segment": self.segment,
            "Industry": self.industry,
            "Company Name": self.company_name,
            "Website": self.website,
            "Founded": self.founded,
            "Revenue": self.revenue,
            "City/Country": self.city_country,
            "Ceo/Founder Name": self.ceo_founder_name,
            "CEO Linkedn": self.ceo_linkedin,
            "Marketing Head name": self.marketing_head_name,
            "Marketing Head Linkedn": self.marketing_head_linkedin,
            "Contact email": self.contact_email,
            "evidence_refs": self.evidence_refs,
            "missing_fields": self.missing_fields,
        }
