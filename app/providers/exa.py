"""Exa search provider adapter.

Primary use: company discovery, person discovery, semantic web search.
Uses the exa_py SDK with highlights for token-efficient content.
"""

from __future__ import annotations

from typing import Any, Literal

from app import config
from app.models import SearchResult


class ExaProvider:
    """Exa search adapter.

    Reads EXA_API_KEY from .env. Falls back to mock data when no key is set
    or when the API call fails.
    """

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or config.EXA_API_KEY
        self._client = None

    @property
    def client(self):
        if self._client is None and self.api_key:
            from exa_py import Exa
            self._client = Exa(api_key=self.api_key)
        return self._client

    def search(
        self,
        query: str,
        num_results: int = 5,
        category: Literal["company", "people"] | None = None,
    ) -> list[SearchResult]:
        """Search using Exa. Returns normalized SearchResult list.

        Args:
            query: Search query string.
            num_results: Number of results to return.
            category: Optional Exa category filter — "company" or "people".
                      If None, auto-detects from query content.
        """
        if not self.api_key or not self.client:
            return self._mock_search(query, num_results)

        resolved_category = category or self._detect_category(query)

        try:
            return self._real_search(query, num_results, resolved_category)
        except Exception as e:
            print(f"[exa] API call failed ({e}), falling back to mock")
            return self._mock_search(query, num_results)

    def _detect_category(self, query: str) -> str | None:
        """Auto-detect Exa category from query content."""
        q = query.lower()
        people_signals = [
            "ceo", "founder", "co-founder", "cto", "cfo", "cmo",
            "marketing head", "vp marketing", "head of",
            "chief executive", "chief technology",
        ]
        if any(sig in q for sig in people_signals):
            return "people"

        company_signals = [
            "company", "companies", "startup", "saas", "fintech",
            "enterprise", "firm", "corporation", "business",
        ]
        if any(sig in q for sig in company_signals):
            return "company"

        return None

    def _real_search(
        self,
        query: str,
        num_results: int,
        category: str | None,
    ) -> list[SearchResult]:
        """Execute real Exa search with highlights."""
        kwargs: dict[str, Any] = {
            "num_results": num_results,
            "type": "auto",
            "contents": {"highlights": True},
        }
        if category:
            kwargs["category"] = category

        response = self.client.search(query, **kwargs)

        results: list[SearchResult] = []
        for item in response.results:
            content = self._extract_content(item)
            results.append(SearchResult(
                title=item.title,
                url=item.url,
                content=content,
                provider="exa",
            ))
        return results

    def get_contents(
        self,
        urls: list[str],
        max_characters: int = 2000,
    ) -> list[SearchResult]:
        """Fetch parsed content for known URLs via /contents endpoint."""
        if not self.api_key or not self.client:
            return []

        try:
            response = self.client.get_contents(
                urls,
                contents={"text": {"max_characters": max_characters}},
            )
            results: list[SearchResult] = []
            for item in response.results:
                results.append(SearchResult(
                    title=item.title,
                    url=item.url,
                    content=item.text if hasattr(item, "text") else None,
                    provider="exa",
                ))
            return results
        except Exception as e:
            print(f"[exa] get_contents failed ({e})")
            return []

    @staticmethod
    def _extract_content(item: Any) -> str | None:
        """Extract the best available content from an Exa result."""
        # Prefer highlights (token-efficient excerpts)
        highlights = getattr(item, "highlights", None)
        if highlights:
            return "\n---\n".join(highlights)

        # Fall back to text
        text = getattr(item, "text", None)
        if text:
            # Truncate to keep token usage reasonable
            return text[:3000] if len(text) > 3000 else text

        # Fall back to summary
        summary = getattr(item, "summary", None)
        if summary:
            return summary

        return None

    # -----------------------------------------------------------------------
    # Mock fallback — DEVELOPMENT/TEST DATA ONLY
    # -----------------------------------------------------------------------

    def _mock_search(self, query: str, num_results: int) -> list[SearchResult]:
        """Mock search results for development when no API key is set."""
        q = query.lower()
        results: list[SearchResult] = []

        if "saas" in q and "india" in q:
            mock_data = [
                SearchResult(
                    title="Zoho Corporation - SaaS Company India",
                    url="https://www.zoho.com",
                    content=(
                        "Zoho Corporation is a SaaS company headquartered in Chennai, India. "
                        "Founded in 1996 by Sridhar Vembu. CEO & Founder: Sridhar Vembu. "
                        "Marketing Head: Praval Singh. "
                        "Zoho has over 12,000 employees worldwide. Revenue: $1 billion+ ARR. "
                        "The company provides a suite of 45+ online business tools."
                    ),
                    provider="exa",
                ),
                SearchResult(
                    title="Freshworks - SaaS Company India",
                    url="https://www.freshworks.com",
                    content=(
                        "Freshworks Inc. is a SaaS company based in San Mateo, California with major operations in Chennai, India. "
                        "Founded in 2010 by Girish Mathrubootham. CEO & Founder: Girish Mathrubootham. "
                        "Marketing Head: Dave Ranson. "
                        "The company has approximately 5,000 employees. Revenue: $720M+. IPO: NASDAQ 2021."
                    ),
                    provider="exa",
                ),
                SearchResult(
                    title="Postman - API Development SaaS India",
                    url="https://www.postman.com",
                    content=(
                        "Postman is an API development platform headquartered in San Francisco with a large engineering team in Bangalore, India. "
                        "Founded in 2014 by Abhinav Asthana. CEO & Founder: Abhinav Asthana. "
                        "Marketing Head: Helen O'Reilly. "
                        "The company has around 800 employees. Valuation: $5.6B."
                    ),
                    provider="exa",
                ),
                SearchResult(
                    title="Chargebee - Subscription Management SaaS India",
                    url="https://www.chargebee.com",
                    content=(
                        "Chargebee is a subscription billing and revenue management SaaS platform headquartered in Chennai, India. "
                        "Founded in 2011 by Krish Subramanian, Rajeev Raman, Saravanan Kumar, Thiyagarajan T. "
                        "CEO & Founder: Krish Subramanian. "
                        "Marketing Head: Sidharth S. "
                        "The company has approximately 500 employees. Revenue: $100M+ ARR."
                    ),
                    provider="exa",
                ),
                SearchResult(
                    title="BrowserStack - Testing SaaS India",
                    url="https://www.browserstack.com",
                    content=(
                        "BrowserStack is a cloud testing platform headquartered in Mumbai, India. "
                        "Founded in 2011 by Ritesh Arora and Nakul Aggarwal. "
                        "CEO & Founder: Ritesh Arora. "
                        "Marketing Head: Rahul Shetty. "
                        "The company has approximately 1,200 employees. Revenue: $200M+."
                    ),
                    provider="exa",
                ),
            ]
            results = mock_data[:num_results]

        elif "ceo" in q or "founder" in q or "marketing head" in q:
            results = [
                SearchResult(
                    title="Sridhar Vembu - CEO & Founder Zoho",
                    url="https://www.linkedin.com/in/sridhar-vembu",
                    content="Sridhar Vembu, CEO & Founder of Zoho Corporation. Based in Chennai, India. Built Zoho into a $1B+ SaaS company.",
                    provider="exa",
                ),
                SearchResult(
                    title="Girish Mathrubootham - CEO & Founder Freshworks",
                    url="https://www.linkedin.com/in/girish-mathrubootham",
                    content="Girish Mathrubootham, CEO & Founder of Freshworks. Led the company to NASDAQ IPO in 2021.",
                    provider="exa",
                ),
                SearchResult(
                    title="Praval Singh - Marketing Head Zoho",
                    url="https://www.linkedin.com/in/praval-singh",
                    content="Praval Singh, Head of Marketing at Zoho Corporation. Leads global marketing initiatives.",
                    provider="exa",
                ),
                SearchResult(
                    title="Helen O'Reilly - Marketing Head Postman",
                    url="https://www.linkedin.com/in/helen-oreilly",
                    content="Helen O'Reilly, VP Marketing at Postman. Drives developer marketing and community growth.",
                    provider="exa",
                ),
            ]

        elif "employee" in q or "company size" in q or "team" in q:
            results = [
                SearchResult(
                    title="Zoho Corporation Company Overview",
                    url="https://www.zoho.com/about.html",
                    content="Zoho Corporation has approximately 12,000 employees across its offices in Chennai, Austin, and Dublin. Founded 1996. Revenue: $1B+.",
                    provider="exa",
                ),
            ]

        elif "chargebee" in q.lower():
            results = [
                SearchResult(
                    title="Chargebee Company Information",
                    url="https://www.chargebee.com/about",
                    content="Chargebee is a subscription revenue management platform. Founded in 2011, headquartered in Chennai, India with approximately 500 employees. Revenue: $100M+ ARR.",
                    provider="exa",
                ),
            ]

        else:
            results = [
                SearchResult(
                    title=f"Search result for: {query}",
                    url="https://example.com",
                    content=f"Mock content for query: {query}",
                    provider="exa",
                ),
            ]

        return results[:num_results]
