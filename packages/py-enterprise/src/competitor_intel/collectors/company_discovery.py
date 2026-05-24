"""Company discovery collector — finds emerging companies automatically."""

from datetime import UTC, datetime
from typing import Any

import structlog

from competitor_intel.core.collector import BaseCollector
from competitor_intel.core.types import SignalType

logger = structlog.getLogger()


class CompanyDiscoveryCollector(BaseCollector):
    """Discover new companies to track from multiple sources.

    Sources:
    - GitHub trending repos (new orgs not yet tracked)
    - Product Hunt new launches
    - Y Combinator batch companies
    - Crunchbase recent additions
    - Hacker News "Show HN" posts
    - AngelList/Wellfound new listings
    """

    API_BASE = "https://api.github.com"

    def __init__(self):
        super().__init__("company_discovery")

    @property
    def source_type(self) -> str:
        return "company_discovery"

    async def collect(self) -> list[dict[str, Any]]:
        """Discover new companies from multiple sources."""
        signals = []

        # GitHub: find new AI orgs with high star velocity
        try:
            github_orgs = await self._discover_github_orgs()
            signals.extend(github_orgs)
        except Exception as e:
            logger.error("github_discovery_error", error=str(e))

        # Product Hunt: recent launches
        try:
            ph_launches = await self._discover_product_hunt()
            signals.extend(ph_launches)
        except Exception as e:
            logger.error("product_hunt_discovery_error", error=str(e))

        # Hacker News: Show HN with company signals
        try:
            hn_companies = await self._discover_hacker_news()
            signals.extend(hn_companies)
        except Exception as e:
            logger.error("hn_discovery_error", error=str(e))

        logger.info("discovery_complete", total_companies=len(signals))
        return signals

    async def _discover_github_orgs(self) -> list[dict[str, Any]]:
        """Find new AI/tech orgs from GitHub search."""
        signals = []

        # Search for recently created AI repos with high stars
        queries = [
            "created:>2024-01-01 topic:ai stars:>100",
            "created:>2024-01-01 topic:llm stars:>50",
            "created:>2024-01-01 topic:machine-learning stars:>200",
            "created:>2024-06-01 topic:agent stars:>50",
        ]

        for query in queries:
            url = f"{self.API_BASE}/search/repositories"
            params = {"q": query, "sort": "stars", "order": "desc", "per_page": "15"}

            headers = {"Accept": "application/vnd.github.v3+json"}
            if self.settings.rate_limit.github_token:
                headers["Authorization"] = f"token {self.settings.rate_limit.github_token}"

            response = await self.fetch(url, params=params, headers=headers)
            data = response.json()

            for repo in data.get("items", []):
                owner = repo.get("owner", {})
                if owner.get("type") != "Organization":
                    continue

                org_login = owner.get("login", "")
                signals.append(
                    {
                        "title": f"New company discovered: {org_login}",
                        "summary": (
                            f"GitHub org with {repo.get('stargazers_count', 0)} stars on "
                            f"{repo['name']}. Description: {repo.get('description', 'N/A')}"
                        ),
                        "url": f"https://github.com/{org_login}",
                        "source": "github_discovery",
                        "signal_type": SignalType.UNKNOWN.value,
                        "detected_at": datetime.now(UTC).isoformat(),
                        "metadata": {
                            "discovery_type": "github_org",
                            "org_name": org_login,
                            "org_url": f"https://github.com/{org_login}",
                            "repo_name": repo["full_name"],
                            "stars": repo.get("stargazers_count", 0),
                            "language": repo.get("language", ""),
                            "description": repo.get("description", ""),
                            "created_at": repo.get("created_at", ""),
                            "discovery_query": query,
                        },
                    }
                )

        return signals

    async def _discover_product_hunt(self) -> list[dict[str, Any]]:
        """Discover companies from Product Hunt RSS feed."""
        signals = []

        url = "https://www.producthunt.com/feed"
        response = await self.fetch(url)

        # Parse RSS manually since feedparser handles it
        import feedparser

        feed = feedparser.parse(response.text)

        for entry in feed.entries[:10]:
            title = entry.get("title", "")
            if not title:
                continue

            signals.append(
                {
                    "title": f"Product Hunt launch: {title}",
                    "summary": (entry.get("summary", "") or "")[:500],
                    "url": entry.get("link", ""),
                    "source": "product_hunt_discovery",
                    "signal_type": SignalType.UNKNOWN.value,
                    "detected_at": datetime.now(UTC).isoformat(),
                    "metadata": {
                        "discovery_type": "product_hunt",
                        "product_name": title,
                        "author": entry.get("author", ""),
                    },
                }
            )

        return signals

    async def _discover_hacker_news(self) -> list[dict[str, Any]]:
        """Find companies from Hacker News Show HN."""
        signals = []

        url = "https://hacker-news.firebaseio.com/v0/showstories.json"
        response = await self.fetch(url)
        story_ids = response.json()[:20]

        for story_id in story_ids[:10]:
            try:
                story_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
                story_resp = await self.fetch(story_url)
                story = story_resp.json()

                if not story or not story.get("url"):
                    continue

                signals.append(
                    {
                        "title": f"Show HN: {story.get('title', '')}",
                        "summary": f"Score: {story.get('score', 0)}, "
                        f"Comments: {story.get('descendants', 0)}",
                        "url": story.get("url", ""),
                        "source": "hacker_news_discovery",
                        "signal_type": SignalType.UNKNOWN.value,
                        "detected_at": datetime.now(UTC).isoformat(),
                        "metadata": {
                            "discovery_type": "hacker_news",
                            "hn_score": story.get("score", 0),
                            "hn_comments": story.get("descendants", 0),
                            "hn_by": story.get("by", ""),
                            "hn_time": story.get("time", 0),
                        },
                    }
                )
            except Exception:
                continue

        return signals
