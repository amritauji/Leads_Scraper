"""Intelligence provider interface and mock implementation.

The intelligence provider handles all LLM-dependent reasoning:
- Interpreting research requests into structured criteria
- Creating research plans
- Generating targeted search queries
- Evaluating evidence completeness
- Building final lead JSON from evidence

Currently implemented as a mock for testing the graph end-to-end.
Later, this will connect to ChatGPT, an MCP server, or another model API.

Do NOT automate the ChatGPT website or use browser session tokens.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.models import Evidence, Fact


class IntelligenceProvider:
    """Interface for the intelligence layer.

    Replace this with a real implementation once the API connection is decided.
    """

    def interpret_request(self, research_request: str) -> dict[str, Any]:
        raise NotImplementedError

    def create_research_plan(self, criteria: dict[str, Any]) -> list[dict[str, str]]:
        raise NotImplementedError

    def generate_search_queries(
        self,
        criteria: dict[str, Any],
        plan: list[dict[str, str]],
        missing: list[str],
        known_companies: list[dict[str, Any]],
        known_people: list[dict[str, Any]],
    ) -> list[str]:
        raise NotImplementedError

    def evaluate_evidence(
        self,
        criteria: dict[str, Any],
        companies: list[dict[str, Any]],
        people: list[dict[str, Any]],
        contacts: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
    ) -> list[str]:
        raise NotImplementedError

    def build_lead(
        self,
        criteria: dict[str, Any],
        companies: list[dict[str, Any]],
        people: list[dict[str, Any]],
        contacts: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
    ) -> dict[str, Any]:
        raise NotImplementedError


class MockIntelligenceProvider(IntelligenceProvider):
    """Deterministic mock intelligence provider for testing the full graph.

    Contains example data for: SaaS companies in India with 100-500 employees.
    This is DEVELOPMENT/TEST data only.
    """

    # -- interpret_request ---------------------------------------------------

    def interpret_request(self, research_request: str) -> dict[str, Any]:
        req = research_request.lower()

        criteria: dict[str, Any] = {
            "company": {},
            "person": {},
            "raw_request": research_request,
        }

        # ── Industry detection ──
        industry_map = {
            "saas": ["SaaS"],
            "software": ["Software"],
            "fintech": ["FinTech"],
            "finance": ["FinTech"],
            "financial": ["FinTech"],
            "ecommerce": ["E-Commerce"],
            "e-commerce": ["E-Commerce"],
            "e commerce": ["E-Commerce"],
            "retail": ["Retail"],
            "electronics": ["Electronics"],
            "hardware": ["Hardware"],
            "ai": ["AI/ML"],
            "artificial intelligence": ["AI/ML"],
            "machine learning": ["AI/ML"],
            "ml": ["AI/ML"],
            "deep learning": ["AI/ML"],
            "healthtech": ["HealthTech"],
            "healthcare": ["HealthTech"],
            "edtech": ["EdTech"],
            "education": ["EdTech"],
            "proptech": ["PropTech"],
            "real estate": ["PropTech"],
            "agritech": ["AgriTech"],
            "agriculture": ["AgriTech"],
            "logistics": ["Logistics"],
            "supply chain": ["Logistics"],
            "manufacturing": ["Manufacturing"],
            "manufacture": ["Manufacturing"],
            "automotive": ["Automotive"],
            "auto": ["Automotive"],
            "telecom": ["Telecom"],
            "telecommunication": ["Telecom"],
            "media": ["Media"],
            "entertainment": ["Entertainment"],
            "gaming": ["Gaming"],
            "game": ["Gaming"],
            "travel": ["Travel"],
            "hospitality": ["Hospitality"],
            "food": ["Food & Beverage"],
            "beverage": ["Food & Beverage"],
            "energy": ["Energy"],
            "renewable": ["Energy"],
            "solar": ["Energy"],
            "consulting": ["Consulting"],
            "marketing": ["Marketing"],
            "advertising": ["Advertising"],
            "b2b": ["B2B"],
            "b2c": ["B2C"],
            "cybersecurity": ["Cybersecurity"],
            "security": ["Cybersecurity"],
            "cloud": ["Cloud"],
            "devops": ["DevOps"],
            "data": ["Data Analytics"],
            "analytics": ["Data Analytics"],
            "iot": ["IoT"],
            "internet of things": ["IoT"],
            "blockchain": ["Blockchain"],
            "crypto": ["Crypto"],
            "insurance": ["InsurTech"],
            "insurtech": ["InsurTech"],
            "legal": ["LegalTech"],
            "hr": ["HRTech"],
            "human resource": ["HRTech"],
            "recruitment": ["Staffing"],
            "staffing": ["Staffing"],
        }

        detected_industries: list[str] = []
        for keyword, industries in industry_map.items():
            if keyword in req:
                detected_industries.extend(industries)
        criteria["company"]["industry"] = list(dict.fromkeys(detected_industries)) or None

        # ── Location detection ──
        city_map = {
            "bangalore": "Bangalore",
            "bengaluru": "Bangalore",
            "mumbai": "Mumbai",
            "bombay": "Mumbai",
            "delhi": "Delhi",
            "new delhi": "Delhi",
            "hyderabad": "Hyderabad",
            "chennai": "Chennai",
            "madras": "Chennai",
            "pune": "Pune",
            "kolkata": "Kolkata",
            "calcutta": "Kolkata",
            "ahmedabad": "Ahmedabad",
            "jaipur": "Jaipur",
            "lucknow": "Lucknow",
            "chandigarh": "Chandigarh",
            "coimbatore": "Coimbatore",
            "kochi": "Kochi",
            "cochin": "Kochi",
            "indore": "Indore",
            "nagpur": "Nagpur",
            "surat": "Surat",
            "san francisco": "San Francisco",
            "sf": "San Francisco",
            "new york": "New York",
            "nyc": "New York",
            "los angeles": "Los Angeles",
            "la": "Los Angeles",
            "chicago": "Chicago",
            "seattle": "Seattle",
            "austin": "Austin",
            "boston": "Boston",
            "london": "London",
            "berlin": "Berlin",
            "paris": "Paris",
            "toronto": "Toronto",
            "singapore": "Singapore",
            "dubai": "Dubai",
            "sydney": "Sydney",
        }

        detected_cities: list[str] = []
        for city_key, city_name in city_map.items():
            if city_key in req:
                detected_cities.append(city_name)

        country_map = {
            "india": "India",
            "usa": "United States",
            "united states": "United States",
            "us": "United States",
            "uk": "United Kingdom",
            "united kingdom": "United Kingdom",
            "canada": "Canada",
            "germany": "Germany",
            "australia": "Australia",
            "singapore": "Singapore",
            "uae": "UAE",
            "dubai": "UAE",
            "japan": "Japan",
            "china": "China",
            "france": "France",
        }
        detected_countries: list[str] = []
        for country_key, country_name in country_map.items():
            if country_key in req:
                detected_countries.append(country_name)

        locations = detected_cities + list(dict.fromkeys(detected_countries))
        criteria["company"]["location"] = locations or None

        # ── Employee size extraction ──
        size_match = re.search(r"(\d[\d,]*)\s*[-–to]+\s*(\d[\d,]*)\s*(?:employee|people|staff|member|team)", req)
        if size_match:
            criteria["company"]["employee_min"] = int(size_match.group(1).replace(",", ""))
            criteria["company"]["employee_max"] = int(size_match.group(2).replace(",", ""))
        else:
            single_match = re.search(r"(\d[\d,]*)\s*(?:employee|people|staff|member|team)", req)
            if single_match:
                val = int(single_match.group(1).replace(",", ""))
                criteria["company"]["employee_min"] = val
                criteria["company"]["employee_max"] = val

        # ── Person role detection ──
        criteria["person"]["target_roles"] = ["ceo_founder", "marketing_head"]

        title_keywords = {
            "cfo": ["CFO", "Chief Financial Officer"],
            "cto": ["CTO", "Chief Technology Officer"],
            "ceo": ["CEO", "Chief Executive Officer"],
            "founder": ["Founder", "Co-Founder"],
            "co-founder": ["Co-Founder"],
            "cofounder": ["Co-Founder"],
            "marketing": ["Marketing Head", "VP Marketing", "CMO"],
            "cmo": ["CMO", "Chief Marketing Officer"],
            "vp marketing": ["VP Marketing"],
            "head of marketing": ["Head of Marketing"],
        }
        found_titles: list[str] = []
        for keyword, titles in title_keywords.items():
            if keyword in req:
                found_titles.extend(titles)
        criteria["person"]["target_titles"] = list(dict.fromkeys(found_titles)) or ["CEO", "Founder", "Marketing Head"]

        return criteria

    # -- create_research_plan ------------------------------------------------

    def create_research_plan(self, criteria: dict[str, Any]) -> list[dict[str, str]]:
        plan: list[dict[str, str]] = [
            {"step": "discover_companies", "goal": "Find companies matching the requested criteria"},
            {"step": "verify_companies", "goal": "Verify industry, location and company size"},
            {"step": "find_people", "goal": "Find CEO/Founder and Marketing Head at identified companies"},
            {"step": "enrich_contacts", "goal": "Find available professional contact information"},
        ]
        return plan

    # -- generate_search_queries ---------------------------------------------

    def generate_search_queries(
        self,
        criteria: dict[str, Any],
        plan: list[dict[str, str]],
        missing: list[str],
        known_companies: list[dict[str, Any]],
        known_people: list[dict[str, Any]],
    ) -> list[str]:
        # If missing information exists, generate targeted queries
        if missing and known_companies:
            queries: list[str] = []
            for company in known_companies:
                name = company.get("name", "")
                website = company.get("website", "")
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
                    elif website and field in ("founded", "revenue"):
                        queries.append(f"site:{website} about")
            return queries or [f"{criteria} research"]

        # Initial queries based on criteria
        company = criteria.get("company", {})
        parts: list[str] = []

        industries = company.get("industry") or []
        locations = company.get("location") or []
        emp_min = company.get("employee_min")
        emp_max = company.get("employee_max")

        if industries and locations:
            parts.append(f"{' '.join(industries)} companies in {' '.join(locations)}")
        elif industries:
            parts.append(f"{' '.join(industries)} companies")
        elif locations:
            parts.append(f"companies in {' '.join(locations)}")

        if emp_min and emp_max:
            parts.append(f"{emp_min}-{emp_max} employees")

        main_query = " ".join(parts) if parts else "top companies"
        queries = [main_query]

        # Add people discovery queries using the detected industries
        industry_str = " ".join(industries) if industries else "companies"
        if locations:
            queries.append(f"CEO founder at {' '.join(locations)} {industry_str}")
            queries.append(f"marketing head at {' '.join(locations)} {industry_str}")
        else:
            queries.append(f"CEO founder at {industry_str}")
            queries.append(f"marketing head at {industry_str}")

        return queries

    # -- evaluate_evidence ---------------------------------------------------

    def evaluate_evidence(
        self,
        criteria: dict[str, Any],
        companies: list[dict[str, Any]],
        people: list[dict[str, Any]],
        contacts: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
    ) -> list[str]:
        missing: list[str] = []

        if not companies:
            missing.append("company_identification")
            return missing

        # Check company fields
        if not any(c.get("name") for c in companies):
            missing.append("company_name")
        if not any(c.get("website") for c in companies):
            missing.append("website")
        if not any(c.get("industry") for c in companies):
            missing.append("industry")
        if not any(c.get("location") or c.get("city") for c in companies):
            missing.append("location")
        if not any(c.get("founded") for c in companies):
            missing.append("founded")
        if not any(c.get("revenue") for c in companies):
            missing.append("revenue")

        # Check people — need CEO/Founder and Marketing Head
        ceo_founders = [p for p in people if p.get("role") == "ceo_founder"]
        marketing_heads = [p for p in people if p.get("role") == "marketing_head"]

        if not ceo_founders:
            missing.append("ceo_founder")
        if not marketing_heads:
            missing.append("marketing_head")

        # Check contacts
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

        # Find CEO/Founder and Marketing Head from people list
        ceo_founder = next((p for p in people if p.get("role") == "ceo_founder"), {})
        marketing_head = next((p for p in people if p.get("role") == "marketing_head"), {})

        # Find email from contacts
        contact = contacts[0] if contacts else {}
        email = contact.get("email") if contact else None

        # Collect evidence refs
        evidence_refs: list[str] = []
        for c in companies:
            evidence_refs.extend(c.get("evidence_ids", []))
        for p in people:
            evidence_refs.extend(p.get("evidence_ids", []))
        for ct in contacts:
            evidence_refs.extend(ct.get("evidence_ids", []))

        # Build city/country string
        city = company.get("city", "")
        location = company.get("location", "")
        city_country = ", ".join(filter(None, [city, location]))

        # Determine missing fields
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
            category=company.get("industry"),  # Same as industry for now
            segment=None,  # TODO: Determine segment from company data
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
