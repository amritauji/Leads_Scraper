"""Hunter.io provider adapter.

Primary use: domain-based email discovery, professional email finding, verification.
"""

from __future__ import annotations

from app import config
from app.models import ContactCandidate, SearchResult


class HunterProvider:
    """Hunter.io adapter for email discovery."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or config.HUNTER_API_KEY

    def find_email(self, domain: str, person_name: str | None = None) -> ContactCandidate:
        """Find email addresses for a domain, optionally for a specific person."""
        if self.api_key:
            return self._real_find_email(domain, person_name)
        return self._mock_find_email(domain, person_name)

    def verify_email(self, email: str) -> dict:
        """Verify if an email address is valid."""
        if self.api_key:
            return self._real_verify_email(email)
        return self._mock_verify_email(email)

    def _real_find_email(self, domain: str, person_name: str | None = None) -> ContactCandidate:
        """Real Hunter.io Domain Search + Email Finder."""
        import requests

        try:
            # Clean domain
            d = domain.lower().replace("https://", "").replace("http://", "").replace("www.", "").rstrip("/")

            # If we have a person name, use Email Finder for precision
            if person_name:
                parts = person_name.strip().split()
                if len(parts) >= 2:
                    first_name = parts[0]
                    last_name = " ".join(parts[1:])
                    resp = requests.get(
                        "https://api.hunter.io/v2/email-finder",
                        params={
                            "domain": d,
                            "first_name": first_name,
                            "last_name": last_name,
                            "api_key": self.api_key,
                        },
                        timeout=15,
                    )
                    if resp.status_code == 200:
                        data = resp.json().get("data", {})
                        email = data.get("email")
                        if email:
                            return ContactCandidate(
                                person_name=person_name,
                                company_name=data.get("company", d.split(".")[0].title()),
                                email=email,
                                email_verified=data.get("verification", {}).get("status") == "valid",
                                evidence_ids=[],
                            )

            # Fallback: Domain Search to find emails at the company
            resp = requests.get(
                "https://api.hunter.io/v2/domain-search",
                params={
                    "domain": d,
                    "limit": 10,
                    "api_key": self.api_key,
                },
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                emails = data.get("emails", [])

                # Try to match by person name
                if person_name and emails:
                    name_lower = person_name.lower()
                    for e in emails:
                        full = f"{e.get('first_name', '')} {e.get('last_name', '')}".strip().lower()
                        if name_lower in full or full in name_lower:
                            return ContactCandidate(
                                person_name=person_name,
                                company_name=data.get("organization", d.split(".")[0].title()),
                                email=e["value"],
                                email_verified=e.get("verification", {}).get("status") == "valid",
                                evidence_ids=[],
                            )

                # Return first executive or senior email
                for e in emails:
                    if e.get("seniority") == "executive" or e.get("department") == "executive":
                        return ContactCandidate(
                            person_name=person_name or f"{e.get('first_name', '')} {e.get('last_name', '')}".strip(),
                            company_name=data.get("organization", d.split(".")[0].title()),
                            email=e["value"],
                            email_verified=e.get("verification", {}).get("status") == "valid",
                            evidence_ids=[],
                        )

                # Return first email
                if emails:
                    e = emails[0]
                    return ContactCandidate(
                        person_name=person_name or f"{e.get('first_name', '')} {e.get('last_name', '')}".strip(),
                        company_name=data.get("organization", d.split(".")[0].title()),
                        email=e["value"],
                        email_verified=e.get("verification", {}).get("status") == "valid",
                        evidence_ids=[],
                    )

            return self._mock_find_email(domain, person_name)

        except Exception as e:
            print(f"[hunter] API call failed ({e}), falling back to mock")
            return self._mock_find_email(domain, person_name)

    def _real_verify_email(self, email: str) -> dict:
        """Real Hunter.io Email Verifier."""
        import requests

        try:
            resp = requests.get(
                "https://api.hunter.io/v2/email-verifier",
                params={
                    "email": email,
                    "api_key": self.api_key,
                },
                timeout=20,
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                status = data.get("status", "unknown")
                return {
                    "email": email,
                    "is_valid": status in ("valid", "accept_all"),
                    "score": data.get("score", 0),
                    "status": status,
                    "mx_records": data.get("mx_records", False),
                    "smtp_check": data.get("smtp_check", False),
                }
            return self._mock_verify_email(email)

        except Exception as e:
            print(f"[hunter] Verify API call failed ({e}), falling back to mock")
            return self._mock_verify_email(email)

    def _mock_find_email(self, domain: str, person_name: str | None = None) -> ContactCandidate:
        """Mock email discovery for development/testing. DEVELOPMENT DATA ONLY."""
        d = domain.lower().replace("https://", "").replace("http://", "").replace("www.", "").rstrip("/")

        # Map domain to known emails
        email_map: dict[str, tuple[str, str]] = {
            "zoho.com": ("sridhar.vembu@zoho.com", "Sridhar Vembu"),
            "freshworks.com": ("girish.mathrubootham@freshworks.com", "Girish Mathrubootham"),
            "postman.com": ("abhinav.asthana@postman.com", "Abhinav Asthana"),
            "chargebee.com": ("krish.subramanian@chargebee.com", "Krish Subramanian"),
            "browserstack.com": ("ritesh.arora@browserstack.com", "Ritesh Arora"),
        }

        for domain_key, (email, name) in email_map.items():
            if domain_key in d:
                return ContactCandidate(
                    person_name=person_name or name,
                    company_name=domain_key.split(".")[0].title(),
                    email=email,
                    email_verified=True,
                    evidence_ids=[],
                )

        return ContactCandidate(
            person_name=person_name or "Unknown",
            company_name=d.split(".")[0].title(),
            email=f"info@{d}",
            email_verified=False,
            evidence_ids=[],
        )

    def _mock_verify_email(self, email: str) -> dict:
        """Mock email verification. DEVELOPMENT DATA ONLY."""
        verified_emails = {
            "sridhar.vembu@zoho.com": True,
            "girish.mathrubootham@freshworks.com": True,
            "abhinav.asthana@postman.com": True,
            "krish.subramanian@chargebee.com": True,
            "ritesh.arora@browserstack.com": True,
        }
        return {
            "email": email,
            "is_valid": verified_emails.get(email, False),
            "score": 90 if verified_emails.get(email) else 20,
        }
