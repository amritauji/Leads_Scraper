"""NVIDIA Nemotron intelligence provider.

Uses the Nemotron model for all LLM-dependent reasoning:
- Interpreting research requests into structured criteria
- Creating research plans
- Generating targeted search queries
- Evaluating evidence completeness
- Building final lead JSON from evidence
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.intelligence import IntelligenceProvider
from app.providers.nvidia import NvidiaProvider


class NvidiaIntelligenceProvider(IntelligenceProvider):
    """Nemotron-powered intelligence provider.

    Uses NVIDIA's Nemotron model for reasoning tasks.
    Falls back to regex/pattern matching if JSON parsing fails.
    """

    def __init__(self, nvidia: NvidiaProvider | None = None):
        self._nvidia = nvidia or NvidiaProvider()

    def _chat(self, system: str, user: str) -> str:
        """Send a chat request and return the content. Falls back to mock on error."""
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        try:
            return self._nvidia.invoke(messages)
        except Exception as e:
            print(f"[nvidia_intelligence] LLM call failed ({e}), falling back to mock")
            from app.intelligence import MockIntelligenceProvider
            self._fallback = MockIntelligenceProvider()
            return ""

    def _chat_json(self, system: str, user: str) -> dict[str, Any] | list[Any]:
        """Send a chat request and parse JSON from the response."""
        raw = self._chat(system, user)
        return self._extract_json(raw)

    @staticmethod
    def _extract_json(text: str) -> Any:
        """Extract JSON from text that may contain markdown code blocks."""
        # Try to find JSON in code blocks
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))

        # Try to find raw JSON (object or array)
        for pattern in [r"\{.*\}", r"\[.*\]"]:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    continue

        return text

    # -- interpret_request ---------------------------------------------------

    def interpret_request(self, research_request: str) -> dict[str, Any]:
        system = """You are a research criteria parser. Given a natural language research request,
extract structured criteria as JSON. Return ONLY valid JSON with this structure:
{
  "company": {
    "industry": ["Industry1"],
    "location": ["Country1"],
    "employee_min": 100,
    "employee_max": 500
  },
  "person": {
    "target_roles": ["ceo_founder", "marketing_head"],
    "target_titles": ["CEO", "Marketing Head"]
  },
  "raw_request": "<original request>"
}

Rules:
- Extract industries from context (SaaS, FinTech, E-Commerce, etc.)
- Extract location/country names
- Extract employee size ranges
- Always include target_roles: ceo_founder and marketing_head
- Include any specific titles mentioned (CEO, CTO, CFO, Marketing Head, VP Marketing, etc.)
- Return ONLY the JSON object, no explanation."""

        user = f"Parse this research request:\n\n{research_request}"
        result = self._chat_json(system, user)

        if isinstance(result, dict):
            result["raw_request"] = research_request
            return result

        # Fallback to regex or mock
        if hasattr(self, "_fallback"):
            return self._fallback.interpret_request(research_request)
        return self._interpret_fallback(research_request)

    def _interpret_fallback(self, research_request: str) -> dict[str, Any]:
        """Regex fallback for interpret_request."""
        req = research_request.lower()
        criteria: dict[str, Any] = {
            "company": {},
            "person": {"target_roles": ["ceo_founder", "marketing_head"]},
            "raw_request": research_request,
        }

        if "saas" in req:
            criteria["company"]["industry"] = ["SaaS"]
        elif "fintech" in req or "finance" in req:
            criteria["company"]["industry"] = ["FinTech"]
        elif "ecommerce" in req or "e-commerce" in req:
            criteria["company"]["industry"] = ["E-Commerce"]

        for country in ["india", "usa", "united states", "uk", "united kingdom", "canada", "germany"]:
            if country in req:
                mapped = {"usa": "United States", "uk": "United Kingdom"}.get(country, country.title())
                criteria["company"]["location"] = [mapped]
                break

        size_match = re.search(r"(\d[\d,]*)\s*[-–to]+\s*(\d[\d,]*)\s*(?:employee|people|staff|member)", req)
        if size_match:
            criteria["company"]["employee_min"] = int(size_match.group(1).replace(",", ""))
            criteria["company"]["employee_max"] = int(size_match.group(2).replace(",", ""))

        title_keywords = {
            "cfo": ["CFO", "Chief Financial Officer"],
            "cto": ["CTO", "Chief Technology Officer"],
            "ceo": ["CEO", "Chief Executive Officer"],
            "marketing": ["Marketing Head", "VP Marketing"],
        }
        found_titles: list[str] = []
        for keyword, titles in title_keywords.items():
            if keyword in req:
                found_titles.extend(titles)
        criteria["person"]["target_titles"] = list(dict.fromkeys(found_titles)) or ["CEO", "Marketing Head"]

        return criteria

    # -- create_research_plan ------------------------------------------------

    def create_research_plan(self, criteria: dict[str, Any]) -> list[dict[str, str]]:
        system = """You are a research planning assistant. Given research criteria, create a step-by-step
research plan. Return ONLY a JSON array of objects with "step" and "goal" keys.

Example:
[
  {"step": "discover_companies", "goal": "Find companies matching the criteria"},
  {"step": "verify_companies", "goal": "Verify company details"},
  {"step": "find_people", "goal": "Find key people at companies"},
  {"step": "enrich_contacts", "goal": "Find contact information"}
]

Valid step names: discover_companies, verify_companies, find_people, enrich_contacts, evaluate_evidence.
Return ONLY the JSON array."""

        user = f"Create a research plan for these criteria:\n\n{json.dumps(criteria, indent=2)}"
        result = self._chat_json(system, user)

        if isinstance(result, list):
            return result

        # Default plan
        return [
            {"step": "discover_companies", "goal": "Find companies matching the requested criteria"},
            {"step": "verify_companies", "goal": "Verify industry, location and company size"},
            {"step": "find_people", "goal": "Find CEO/Founder and Marketing Head at identified companies"},
            {"step": "enrich_contacts", "goal": "Find available professional contact information"},
        ]

    # -- generate_search_queries ---------------------------------------------

    def generate_search_queries(
        self,
        criteria: dict[str, Any],
        plan: list[dict[str, str]],
        missing: list[str],
        known_companies: list[dict[str, Any]],
        known_people: list[dict[str, Any]],
    ) -> list[str]:
        system = """You are a search query generator. Given research criteria, missing information,
and known companies/people, generate targeted search queries to fill gaps.

Return ONLY a JSON array of query strings. Each query should be specific enough to find
relevant results. Focus on the missing fields."""

        context = {
            "criteria": criteria,
            "missing_fields": missing,
            "known_companies": [c.get("name", "") for c in known_companies],
            "known_people": [f"{p.get('name', '')} ({p.get('role', '')})" for p in known_people],
        }

        user = f"Generate search queries to fill these missing fields:\n\n{json.dumps(context, indent=2)}"
        result = self._chat_json(system, user)

        if isinstance(result, list) and all(isinstance(q, str) for q in result):
            return result

        # Fallback to simple query generation
        if hasattr(self, "_fallback"):
            return self._fallback.generate_search_queries(criteria, plan, missing, known_companies, known_people)
        return self._queries_fallback(criteria, missing, known_companies)

    def _queries_fallback(
        self,
        criteria: dict[str, Any],
        missing: list[str],
        known_companies: list[dict[str, Any]],
    ) -> list[str]:
        """Regex fallback for generate_search_queries."""
        if not missing or not known_companies:
            company = criteria.get("company", {})
            parts: list[str] = []
            industries = company.get("industry", [])
            locations = company.get("location", [])
            if industries and locations:
                parts.append(f"{' '.join(industries)} companies in {' '.join(locations)}")
            return [" ".join(parts)] if parts else [f"{criteria} research"]

        queries: list[str] = []
        for company in known_companies:
            name = company.get("name", "")
            for field in missing:
                if field == "ceo_founder" and name:
                    queries.append(f'"{name}" CEO founder')
                elif field == "marketing_head" and name:
                    queries.append(f'"{name}" marketing head')
                elif field == "contact_email" and name:
                    queries.append(f'"{name}" contact email')
                elif field == "founded" and name:
                    queries.append(f'"{name}" founded year')
                elif field == "revenue" and name:
                    queries.append(f'"{name}" revenue ARR')
        return queries or [f"research {criteria}"]

    # -- evaluate_evidence ---------------------------------------------------

    def evaluate_evidence(
        self,
        criteria: dict[str, Any],
        companies: list[dict[str, Any]],
        people: list[dict[str, Any]],
        contacts: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
    ) -> list[str]:
        system = """You are a data completeness evaluator. Given the current state of a research
project, identify which required fields are missing.

Required fields: company_name, industry, website, founded, revenue, city_country,
ceo_founder, marketing_head, contact_email.

Return ONLY a JSON array of missing field names. If nothing is missing, return an empty array []."""

        context = {
            "required_fields": [
                "company_name", "industry", "website", "founded", "revenue",
                "city_country", "ceo_founder", "marketing_head", "contact_email"
            ],
            "companies": companies[:3],
            "people": people[:5],
            "contacts": contacts[:3],
        }

        user = f"Identify missing fields:\n\n{json.dumps(context, indent=2, default=str)}"
        result = self._chat_json(system, user)

        if isinstance(result, list):
            return result

        if hasattr(self, "_fallback"):
            return self._fallback.evaluate_evidence(criteria, companies, people, contacts, evidence)
        return self._evaluate_fallback(companies, people, contacts)

    def _evaluate_fallback(
        self,
        companies: list[dict[str, Any]],
        people: list[dict[str, Any]],
        contacts: list[dict[str, Any]],
    ) -> list[str]:
        """Regex fallback for evaluate_evidence."""
        missing: list[str] = []
        if not companies:
            return ["company_identification"]
        if not any(c.get("name") for c in companies):
            missing.append("company_name")
        if not any(c.get("industry") for c in companies):
            missing.append("industry")
        if not any(c.get("website") for c in companies):
            missing.append("website")
        if not any(c.get("founded") for c in companies):
            missing.append("founded")
        if not any(c.get("revenue") for c in companies):
            missing.append("revenue")
        if not any(c.get("location") or c.get("city") for c in companies):
            missing.append("city_country")
        if not any(p.get("role") == "ceo_founder" for p in people):
            missing.append("ceo_founder")
        if not any(p.get("role") == "marketing_head" for p in people):
            missing.append("marketing_head")
        if not contacts or not any(c.get("email") for c in contacts):
            missing.append("contact_email")
        return missing

    # -- build_lead ----------------------------------------------------------

    def build_lead(
        self,
        criteria: dict[str, Any],
        companies: list[dict[str, Any]],
        people: list[dict[str, Any]],
        contacts: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
    ) -> dict[str, Any]:
        from app.models import StandardLead

        company = companies[0] if companies else {}
        ceo_founder = next((p for p in people if p.get("role") == "ceo_founder"), {})
        marketing_head = next((p for p in people if p.get("role") == "marketing_head"), {})
        contact = contacts[0] if contacts else {}
        email = contact.get("email") if contact else None

        evidence_refs: list[str] = []
        for c in companies:
            evidence_refs.extend(c.get("evidence_ids", []))
        for p in people:
            evidence_refs.extend(p.get("evidence_ids", []))
        for ct in contacts:
            evidence_refs.extend(ct.get("evidence_ids", []))

        city = company.get("city", "")
        location = company.get("location", "")
        city_country = ", ".join(filter(None, [city, location]))

        missing_fields: list[str] = []
        if not company.get("name"):
            missing_fields.append("Company Name")
        if not company.get("industry"):
            missing_fields.append("Industry")
        if not company.get("website"):
            missing_fields.append("Website")
        if not company.get("founded"):
            missing_fields.append("Founded")
        if not company.get("revenue"):
            missing_fields.append("Revenue")
        if not city_country:
            missing_fields.append("City/Country")
        if not ceo_founder.get("name"):
            missing_fields.append("Ceo/Founder Name")
        if not marketing_head.get("name"):
            missing_fields.append("Marketing Head name")
        if not email:
            missing_fields.append("Contact email")

        lead = StandardLead(
            category=company.get("industry"),
            segment=None,
            industry=company.get("industry"),
            company_name=company.get("name"),
            website=company.get("website"),
            founded=company.get("founded"),
            revenue=company.get("revenue"),
            city_country=city_country or None,
            ceo_founder_name=ceo_founder.get("name"),
            ceo_linkedin=ceo_founder.get("linkedin_url"),
            marketing_head_name=marketing_head.get("name"),
            marketing_head_linkedin=marketing_head.get("linkedin_url"),
            contact_email=email,
            evidence_refs=list(dict.fromkeys(evidence_refs)),
            missing_fields=missing_fields,
        )
        return lead.to_dict()
