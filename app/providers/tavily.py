"""Tavily search provider adapter.

Primary use: broader web research, supporting sources, verification.
"""

from __future__ import annotations

from app import config
from app.models import SearchResult


class TavilyProvider:
    """Tavily search adapter."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or config.TAVILY_API_KEY

    def search(self, query: str, num_results: int = 5) -> list[SearchResult]:
        if self.api_key:
            return self._real_search(query, num_results)
        return self._mock_search(query, num_results)

    def _real_search(self, query: str, num_results: int) -> list[SearchResult]:
        """Real Tavily search with advanced depth."""
        try:
            from tavily import TavilyClient

            client = TavilyClient(api_key=self.api_key)
            response = client.search(
                query=query,
                max_results=num_results,
                search_depth="advanced",
            )
            results: list[SearchResult] = []
            for item in response.get("results", []):
                results.append(SearchResult(
                    title=item.get("title"),
                    url=item.get("url", ""),
                    content=item.get("content"),
                    provider="tavily",
                ))
            return results
        except ImportError:
            print("[tavily] tavily-python not installed, falling back to mock")
            return self._mock_search(query, num_results)
        except Exception as e:
            print(f"[tavily] API call failed ({e}), falling back to mock")
            return self._mock_search(query, num_results)

    def _mock_search(self, query: str, num_results: int) -> list[SearchResult]:
        """Mock search results for development/testing. DEVELOPMENT DATA ONLY."""
        q = query.lower()
        results: list[SearchResult] = []

        if "saas" in q and "india" in q:
            results = [
                SearchResult(
                    title="Top SaaS Companies in India 2024",
                    url="https://techcrunch.com/top-saas-india",
                    content="India's SaaS ecosystem has grown rapidly. Key players include Zoho, Freshworks, Postman, and Chargebee. Many of these companies have 100-500 employees in their India offices.",
                    provider="tavily",
                ),
                SearchResult(
                    title="India SaaS Landscape Report",
                    url="https://nasscom.in/saas-report",
                    content="The Indian SaaS industry employs over 100,000 professionals. Companies range from bootstrapped startups to publicly traded enterprises.",
                    provider="tavily",
                ),
            ]
        elif "zoho" in q and ("ceo" in q or "founder" in q):
            results = [
                SearchResult(
                    title="Sridhar Vembu - Founder & CEO of Zoho",
                    url="https://en.wikipedia.org/wiki/Sridhar_Vembu",
                    content="Sridhar Vembu is the CEO and founder of Zoho Corporation. He founded the company in 1996 in Chennai, India. LinkedIn: https://www.linkedin.com/in/sridhar-vembu",
                    provider="tavily",
                ),
            ]
        elif "zoho" in q and ("marketing" in q or "cmo" in q):
            results = [
                SearchResult(
                    title="Praval Singh - Marketing Head at Zoho",
                    url="https://www.zoho.com/marketing",
                    content="Praval Singh leads marketing at Zoho Corporation. Marketing Head LinkedIn: https://www.linkedin.com/in/praval-singh",
                    provider="tavily",
                ),
            ]
        elif "freshworks" in q and ("ceo" in q or "founder" in q):
            results = [
                SearchResult(
                    title="Girish Mathrubootham - Founder & CEO of Freshworks",
                    url="https://en.wikipedia.org/wiki/Girish_Mathrubootham",
                    content="Girish Mathrubootham is the CEO and founder of Freshworks. He founded the company in 2010 in Chennai, India. LinkedIn: https://www.linkedin.com/in/girish-mathrubootham",
                    provider="tavily",
                ),
            ]
        elif "freshworks" in q and ("marketing" in q or "cmo" in q):
            results = [
                SearchResult(
                    title="Dave Ranson - Marketing Head at Freshworks",
                    url="https://www.freshworks.com/about",
                    content="Dave Ranson leads marketing at Freshworks. Marketing Head LinkedIn: https://www.linkedin.com/in/dave-ranson",
                    provider="tavily",
                ),
            ]
        elif "postman" in q and ("ceo" in q or "founder" in q):
            results = [
                SearchResult(
                    title="Abhinav Asthana - Founder & CEO of Postman",
                    url="https://en.wikipedia.org/wiki/Abhinav_Asthana",
                    content="Abhinav Asthana is the CEO and founder of Postman. He founded the company in 2014 in Bangalore, India. LinkedIn: https://www.linkedin.com/in/abhinav-asthana",
                    provider="tavily",
                ),
            ]
        elif "postman" in q and ("marketing" in q or "cmo" in q):
            results = [
                SearchResult(
                    title="Helen O'Reilly - Marketing Head at Postman",
                    url="https://www.postman.com/about",
                    content="Helen O'Reilly leads marketing at Postman. Marketing Head LinkedIn: https://www.linkedin.com/in/helen-oreilly",
                    provider="tavily",
                ),
            ]
        elif "chargebee" in q and ("ceo" in q or "founder" in q):
            results = [
                SearchResult(
                    title="Krish Subramanian - Founder & CEO of Chargebee",
                    url="https://en.wikipedia.org/wiki/Krish_Subramanian",
                    content="Krish Subramanian is the CEO and co-founder of Chargebee. He founded the company in 2011 in Chennai, India. LinkedIn: https://www.linkedin.com/in/krish-subramanian",
                    provider="tavily",
                ),
            ]
        elif "chargebee" in q and ("marketing" in q or "cmo" in q):
            results = [
                SearchResult(
                    title="Sidharth S - Marketing Head at Chargebee",
                    url="https://www.chargebee.com/about",
                    content="Sidharth S leads marketing at Chargebee. Marketing Head LinkedIn: https://www.linkedin.com/in/sidharth-s",
                    provider="tavily",
                ),
            ]
        elif "browserstack" in q and ("ceo" in q or "founder" in q):
            results = [
                SearchResult(
                    title="Ritesh Arora - Founder & CEO of BrowserStack",
                    url="https://en.wikipedia.org/wiki/Ritesh_Arora",
                    content="Ritesh Arora is the CEO and co-founder of BrowserStack. He founded the company in 2011 in Mumbai, India. LinkedIn: https://www.linkedin.com/in/ritesh-arora",
                    provider="tavily",
                ),
            ]
        elif "browserstack" in q and ("marketing" in q or "cmo" in q):
            results = [
                SearchResult(
                    title="Rahul Shetty - Marketing Head at BrowserStack",
                    url="https://www.browserstack.com/about",
                    content="Rahul Shetty leads marketing at BrowserStack. Marketing Head LinkedIn: https://www.linkedin.com/in/rahul-shetty",
                    provider="tavily",
                ),
            ]
        elif "zoho" in q:
            results = [
                SearchResult(
                    title="Zoho Corporation - Complete Profile",
                    url="https://en.wikipedia.org/wiki/Zoho",
                    content="Zoho Corporation is an Indian multinational technology company. Founded in 1996 by Sridhar Vembu. CEO & Founder: Sridhar Vembu. Marketing Head: Praval Singh. Headquarters in Chennai, Tamil Nadu. Over 12,000 employees.",
                    provider="tavily",
                ),
            ]
        else:
            results = [
                SearchResult(
                    title=f"Web results for: {query}",
                    url="https://example.com/research",
                    content=f"Mock Tavily content for query: {query}",
                    provider="tavily",
                ),
            ]

        return results[:num_results]
