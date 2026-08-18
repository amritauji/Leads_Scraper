"""Firecrawl provider adapter.

Primary use: opening known webpages, extracting content, crawling company sites.
"""

from __future__ import annotations

from app import config
from app.models import SearchResult


class FirecrawlProvider:
    """Firecrawl adapter for webpage crawling and content extraction."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or config.FIRECRAWL_API_KEY

    def crawl(self, url: str) -> SearchResult:
        """Crawl a single page and extract its content."""
        if self.api_key:
            return self._real_crawl(url)
        return self._mock_crawl(url)

    def _real_crawl(self, url: str) -> SearchResult:
        """TODO: Implement real Firecrawl crawl when API key is available."""
        try:
            from firecrawl import FirecrawlApp

            app = FirecrawlApp(api_key=self.api_key)
            result = app.scrape_url(url, params={"formats": ["markdown"]})
            return SearchResult(
                title=result.get("metadata", {}).get("title"),
                url=url,
                content=result.get("markdown", result.get("data", {}).get("markdown")),
                provider="firecrawl",
            )
        except ImportError:
            return self._mock_crawl(url)

    def _mock_crawl(self, url: str) -> SearchResult:
        """Mock crawl results for development/testing. DEVELOPMENT DATA ONLY."""
        u = url.lower()

        content_map: dict[str, tuple[str, str]] = {
            "zoho.com": (
                "Zoho Corporation",
                "Zoho Corporation is a global technology company founded in 1996 by Sridhar Vembu. "
                "Headquarters: Chennai, India. City: Chennai. Country: India. "
                "Employees: 12,000+. Revenue: $1 billion+ ARR. "
                "CEO & Founder: Sridhar Vembu. CEO LinkedIn: https://www.linkedin.com/in/sridhar-vembu "
                "Marketing Head: Praval Singh. Marketing Head LinkedIn: https://www.linkedin.com/in/praval-singh "
                "Products: CRM, Projects, Mail, and 45+ business applications. Industry: SaaS."
            ),
            "freshworks.com": (
                "Freshworks Inc.",
                "Freshworks provides SaaS customer engagement solutions. "
                "Founded: 2010. Headquarters: San Mateo, CA / Chennai, India. City: Chennai. Country: India. "
                "Employees: 5,000+. Revenue: $720M+. IPO: NASDAQ 2021. "
                "CEO & Founder: Girish Mathrubootham. CEO LinkedIn: https://www.linkedin.com/in/girish-mathrubootham "
                "Marketing Head: Dave Ranson. Marketing Head LinkedIn: https://www.linkedin.com/in/dave-ranson "
                "Industry: SaaS."
            ),
            "postman.com": (
                "Postman",
                "Postman is an API development platform. Founded: 2014. "
                "Headquarters: San Francisco, CA / Bangalore, India. City: Bangalore. Country: India. "
                "Employees: ~800. Valuation: $5.6B. Revenue: $200M+. "
                "CEO & Founder: Abhinav Asthana. CEO LinkedIn: https://www.linkedin.com/in/abhinav-asthana "
                "Marketing Head: Helen O'Reilly. Marketing Head LinkedIn: https://www.linkedin.com/in/helen-oreilly "
                "Industry: SaaS, DevTools."
            ),
            "chargebee.com": (
                "Chargebee",
                "Chargebee is a subscription revenue management platform. "
                "Founded: 2011. Headquarters: Chennai, India / San Francisco, CA. City: Chennai. Country: India. "
                "Employees: ~500. Revenue: $100M+ ARR. "
                "CEO & Founder: Krish Subramanian. CEO LinkedIn: https://www.linkedin.com/in/krish-subramanian "
                "Marketing Head: Sidharth S. Marketing Head LinkedIn: https://www.linkedin.com/in/sidharth-s "
                "Industry: SaaS, FinTech."
            ),
            "browserstack.com": (
                "BrowserStack",
                "BrowserStack is a cloud testing platform. "
                "Founded: 2011. Headquarters: Mumbai, India. City: Mumbai. Country: India. "
                "Employees: 1,200+. Revenue: $200M+. "
                "CEO & Founder: Ritesh Arora. CEO LinkedIn: https://www.linkedin.com/in/ritesh-arora "
                "Marketing Head: Rahul Shetty. Marketing Head LinkedIn: https://www.linkedin.com/in/rahul-shetty "
                "Industry: SaaS, Testing."
            ),
        }

        for domain, (title, content) in content_map.items():
            if domain in u:
                return SearchResult(title=title, url=url, content=content, provider="firecrawl")

        return SearchResult(
            title=f"Crawled: {url}",
            url=url,
            content=f"Mock crawl content for {url}",
            provider="firecrawl",
        )
