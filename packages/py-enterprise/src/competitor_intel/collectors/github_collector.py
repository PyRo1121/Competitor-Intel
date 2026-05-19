"""GitHub API collector for tracking repository activity."""

from datetime import datetime
from typing import Any

import structlog

from competitor_intel.core.collector import BaseCollector
from competitor_intel.core.types import SignalType

logger = structlog.get_logger()


class GitHubCollector(BaseCollector):
    """Collect GitHub activity signals.
    
    Tracks:
    - Trending AI repositories
    - Organization activity
    - Star velocity
    """
    
    API_BASE = "https://api.github.com"
    
    def __init__(self):
        super().__init__("github")
    
    @property
    def source_type(self) -> str:
        return "github"
    
    @property
    def timeout(self) -> int:
        return 15
    
    async def collect(self) -> list[dict[str, Any]]:
        """Collect GitHub signals."""
        signals = []
        
        try:
            trending = await self._collect_trending()
            signals.extend(trending)
        except Exception as e:
            logger.error("github_trending_error", error=str(e))
        
        try:
            org_activity = await self._collect_org_activity()
            signals.extend(org_activity)
        except Exception as e:
            logger.error("github_org_error", error=str(e))
        
        logger.info("github_collection_complete", total_signals=len(signals))
        return signals
    
    async def _collect_trending(self) -> list[dict[str, Any]]:
        """Collect trending AI repositories."""
        url = f"{self.API_BASE}/search/repositories"
        params = {
            "q": "topic:ai language:python",
            "sort": "stars",
            "order": "desc",
            "per_page": "10",
        }
        
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self.settings.rate_limit.github_token:
            headers["Authorization"] = f"token {self.settings.rate_limit.github_token}"
        
        response = await self.fetch(url, params=params, headers=headers)
        data = response.json()
        
        signals = []
        for repo in data.get("items", []):
            signal = {
                "title": repo["full_name"],
                "summary": repo.get("description", "") or "No description",
                "url": repo["html_url"],
                "source": "github",
                "signal_type": SignalType.GITHUB_ACTIVITY.value,
                "detected_at": datetime.utcnow().isoformat(),
                "metadata": {
                    "stars": repo.get("stargazers_count", 0),
                    "forks": repo.get("forks_count", 0),
                    "language": repo.get("language", ""),
                    "repo_type": "trending",
                },
            }
            signals.append(signal)
        
        return signals
    
    async def _collect_org_activity(self) -> list[dict[str, Any]]:
        """Collect activity from tracked GitHub organizations."""
        # TODO: Load from database or config
        orgs = ["cursor", "langchain-ai", "run-llama", "e2b-dev"]
        
        signals = []
        for org in orgs:
            try:
                url = f"{self.API_BASE}/orgs/{org}/repos"
                params = {"per_page": "5", "sort": "updated"}
                
                headers = {"Accept": "application/vnd.github.v3+json"}
                if self.settings.rate_limit.github_token:
                    headers["Authorization"] = f"token {self.settings.rate_limit.github_token}"
                
                response = await self.fetch(url, params=params, headers=headers)
                data = response.json()
                
                for repo in data:
                    signal = {
                        "title": f"{org}/{repo['name']}",
                        "summary": f"Updated: {repo.get('updated_at', 'N/A')}",
                        "url": repo["html_url"],
                        "source": "github",
                        "signal_type": SignalType.GITHUB_ACTIVITY.value,
                        "detected_at": datetime.utcnow().isoformat(),
                        "metadata": {
                            "org": org,
                            "stars": repo.get("stargazers_count", 0),
                            "repo_type": "org_activity",
                        },
                    }
                    signals.append(signal)
                    
            except Exception as e:
                logger.warning("github_org_error", org=org, error=str(e))
        
        return signals
