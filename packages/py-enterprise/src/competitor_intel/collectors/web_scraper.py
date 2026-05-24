"""Web scraper collector — extracts structured intelligence from company websites."""

import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin

import structlog
from bs4 import BeautifulSoup

from competitor_intel.core.collector import BaseCollector
from competitor_intel.core.types import SignalType

logger = structlog.getLogger()


class WebScraperCollector(BaseCollector):
    """Scrape company websites for structured intelligence.

    Extracts:
    - Pricing pages (plan changes, new tiers)
    - Blog posts (product announcements)
    - About pages (team size, location, mission)
    - Careers pages (hiring signals)
    - Documentation (API changes, new features)
    - Press pages (partnerships, awards)
    """

    def __init__(self):
        super().__init__("web_scraper")

    @property
    def source_type(self) -> str:
        return "web_scraper"

    async def collect(self) -> list[dict[str, Any]]:
        """Scrape tracked company websites."""
        signals = []

        companies = [
            {"name": "Cursor", "url": "https://cursor.com", "blog": "https://cursor.com/blog"},
            {
                "name": "Anthropic",
                "url": "https://anthropic.com",
                "blog": "https://www.anthropic.com/news",
            },
            {
                "name": "Perplexity",
                "url": "https://perplexity.ai",
                "blog": "https://blog.perplexity.ai",
            },
            {"name": "Linear", "url": "https://linear.app", "blog": "https://linear.app/blog"},
            {"name": "Notion", "url": "https://notion.so", "blog": "https://www.notion.so/blog"},
            {
                "name": "ElevenLabs",
                "url": "https://elevenlabs.io",
                "blog": "https://elevenlabs.io/blog",
            },
            {"name": "Runway", "url": "https://runwayml.com", "blog": "https://runwayml.com/blog"},
        ]

        for company in companies:
            try:
                # Scrape blog for announcements
                blog_signals = await self._scrape_blog(company)
                signals.extend(blog_signals)

                # Scrape pricing for changes
                pricing_signals = await self._scrape_pricing(company)
                signals.extend(pricing_signals)

                # Scrape about page for company info
                about_signals = await self._scrape_about(company)
                signals.extend(about_signals)

            except Exception as e:
                logger.error("scraper_error", company=company["name"], error=str(e))

        logger.info("web_scraper_complete", total_signals=len(signals))
        return signals

    async def _scrape_blog(self, company: dict) -> list[dict[str, Any]]:
        """Scrape company blog for recent announcements."""
        signals = []

        blog_url = company.get("blog", company["url"] + "/blog")
        response = await self.fetch(blog_url)
        soup = BeautifulSoup(response.text, "html.parser")

        # Find blog post links
        links = soup.find_all("a", href=True)
        posts = []

        for link in links:
            href = link.get("href") or ""
            if not isinstance(href, str):
                continue
            text = link.get_text(strip=True)

            # Match blog post patterns
            if (
                any(p in href for p in ["/blog/", "/news/", "/post/", "/article/"])
                and text
                and len(text) > 10
            ):
                full_url = urljoin(blog_url, href)
                posts.append(
                    {
                        "title": text,
                        "url": full_url,
                    }
                )

        # Deduplicate and limit
        seen = set()
        for post in posts[:10]:
            if post["title"] not in seen:
                seen.add(post["title"])
                signals.append(
                    {
                        "title": f"{company['name']} blog: {post['title']}",
                        "summary": f"New post on {company['name']} blog",
                        "url": post["url"],
                        "source": "web_scraper",
                        "signal_type": SignalType.PRODUCT_UPDATE.value,
                        "detected_at": datetime.now(UTC).isoformat(),
                        "metadata": {
                            "company": company["name"],
                            "scrape_type": "blog",
                            "post_title": post["title"],
                        },
                    }
                )

        return signals

    async def _scrape_pricing(self, company: dict) -> list[dict[str, Any]]:
        """Scrape pricing page for plan information."""
        signals = []

        pricing_url = urljoin(company["url"], "/pricing")
        try:
            response = await self.fetch(pricing_url)
            soup = BeautifulSoup(response.text, "html.parser")

            # Extract pricing text
            text = soup.get_text()

            # Look for pricing patterns
            price_patterns = [
                r"\$(\d+)/",
                r"\$(\d+)\s*per",
                r"(\d+)\s*dollars",
            ]

            prices_found = []
            for pattern in price_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                prices_found.extend(matches)

            if prices_found:
                signals.append(
                    {
                        "title": f"{company['name']} pricing detected",
                        "summary": (
                            f"Price points found: {', '.join(f'${p}' for p in prices_found[:5])}"
                        ),
                        "url": pricing_url,
                        "source": "web_scraper",
                        "signal_type": SignalType.PRODUCT_UPDATE.value,
                        "detected_at": datetime.now(UTC).isoformat(),
                        "metadata": {
                            "company": company["name"],
                            "scrape_type": "pricing",
                            "prices": prices_found[:10],
                        },
                    }
                )
        except Exception:
            pass

        return signals

    async def _scrape_about(self, company: dict) -> list[dict[str, Any]]:
        """Scrape about page for company information."""
        signals = []

        about_url = urljoin(company["url"], "/about")
        try:
            response = await self.fetch(about_url)
            soup = BeautifulSoup(response.text, "html.parser")

            text = soup.get_text()

            # Look for team size indicators
            team_patterns = [
                r"(\d+)\+?\s*(?:employees|team members|people)",
                r"team of (\d+)",
                r"(\d+)\s*person\s*team",
            ]

            team_size = None
            for pattern in team_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    team_size = int(match.group(1))
                    break

            # Look for location
            location_patterns = [
                r"(?:based|headquartered|located)\s*(?:in\s*)?([A-Z][a-z]+(?:,\s*[A-Z][a-z]+)*)",
            ]

            location = None
            for pattern in location_patterns:
                match = re.search(pattern, text)
                if match:
                    location = match.group(1)
                    break

            if team_size or location:
                signals.append(
                    {
                        "title": f"{company['name']} company info",
                        "summary": (
                            f"Team size: {team_size or 'N/A'}, Location: {location or 'N/A'}"
                        ),
                        "url": about_url,
                        "source": "web_scraper",
                        "signal_type": SignalType.UNKNOWN.value,
                        "detected_at": datetime.now(UTC).isoformat(),
                        "metadata": {
                            "company": company["name"],
                            "scrape_type": "about",
                            "team_size": team_size,
                            "location": location,
                        },
                    }
                )
        except Exception:
            pass

        return signals
