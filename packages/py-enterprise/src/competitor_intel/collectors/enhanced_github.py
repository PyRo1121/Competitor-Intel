"""Enhanced GitHub collector — deep repo analysis with language detection."""

from datetime import UTC, datetime
from typing import Any

import structlog

from competitor_intel.core.collector import BaseCollector
from competitor_intel.core.types import SignalType

logger = structlog.getLogger()


class EnhancedGitHubCollector(BaseCollector):
    """Deep GitHub analysis for tracked companies.

    Tracks:
    - Repository health metrics (commit frequency, contributor activity)
    - Language and framework detection
    - Release velocity and changelog analysis
    - Star/fork growth trends
    - Issue resolution time
    - Dependency analysis (package.json, requirements.txt, Cargo.toml)
    """

    API_BASE = "https://api.github.com"

    def __init__(self):
        super().__init__("enhanced_github")

    @property
    def source_type(self) -> str:
        return "enhanced_github"

    async def collect(self) -> list[dict[str, Any]]:
        """Collect deep GitHub signals."""
        signals = []

        # Track known company repos
        company_repos = [
            ("cursor", "comet-ide/comet"),
            ("anthropic", "anthropics/anthropic-cookbook"),
            ("perplexity", "perplexity-ai/perplexity"),
            ("langchain", "langchain-ai/langchain"),
            ("llama", "run-llama/llama_index"),
        ]

        for company, repo in company_repos:
            try:
                repo_signals = await self._analyze_repo(company, repo)
                signals.extend(repo_signals)
            except Exception as e:
                logger.error("repo_analysis_error", repo=repo, error=str(e))

        # Also collect trending AI repos
        try:
            trending = await self._collect_trending_detailed()
            signals.extend(trending)
        except Exception as e:
            logger.error("trending_error", error=str(e))

        logger.info("enhanced_github_complete", total_signals=len(signals))
        return signals

    async def _analyze_repo(self, company: str, repo_path: str) -> list[dict[str, Any]]:
        """Deep analysis of a single repository."""
        signals = []
        owner, repo = repo_path.split("/")

        # Get repo details
        url = f"{self.API_BASE}/repos/{owner}/{repo}"
        headers = self._get_headers()
        response = await self.fetch(url, headers=headers)
        repo_data = response.json()

        # Get languages
        lang_url = f"{self.API_BASE}/repos/{owner}/{repo}/languages"
        lang_response = await self.fetch(lang_url, headers=headers)
        languages = lang_response.json()

        # Get recent commits
        commits_url = f"{self.API_BASE}/repos/{owner}/{repo}/commits"
        commits_response = await self.fetch(commits_url, headers=headers, params={"per_page": "30"})
        commits = commits_response.json()

        # Get releases
        releases_url = f"{self.API_BASE}/repos/{owner}/{repo}/releases"
        releases_response = await self.fetch(
            releases_url, headers=headers, params={"per_page": "10"}
        )
        releases = releases_response.json()

        # Get contributors
        contrib_url = f"{self.API_BASE}/repos/{owner}/{repo}/contributors"
        contrib_response = await self.fetch(contrib_url, headers=headers, params={"per_page": "20"})
        contributors = contrib_response.json()

        # Build signal
        signals.append(
            {
                "title": f"GitHub analysis: {repo_path}",
                "summary": f"Stars: {repo_data.get('stargazers_count', 0)}, "
                f"Forks: {repo_data.get('forks_count', 0)}, "
                f"Open issues: {repo_data.get('open_issues_count', 0)}, "
                f"Contributors: {len(contributors)}, "
                f"Languages: {', '.join(list(languages.keys())[:5])}",
                "url": repo_data.get("html_url", ""),
                "source": "enhanced_github",
                "signal_type": SignalType.GITHUB_ACTIVITY.value,
                "detected_at": datetime.now(UTC).isoformat(),
                "metadata": {
                    "company": company,
                    "repo": repo_path,
                    "stars": repo_data.get("stargazers_count", 0),
                    "forks": repo_data.get("forks_count", 0),
                    "open_issues": repo_data.get("open_issues_count", 0),
                    "languages": languages,
                    "primary_language": repo_data.get("language"),
                    "description": repo_data.get("description", ""),
                    "updated_at": repo_data.get("updated_at"),
                    "pushed_at": repo_data.get("pushed_at"),
                    "recent_commits": len(commits),
                    "recent_releases": len(releases),
                    "contributor_count": len(contributors),
                    "top_contributors": [
                        {"login": c.get("login"), "contributions": c.get("contributions")}
                        for c in contributors[:5]
                    ],
                    "latest_release": releases[0].get("tag_name") if releases else None,
                    "is_archived": repo_data.get("archived", False),
                    "license": repo_data.get("license", {}).get("spdx_id")
                    if repo_data.get("license")
                    else None,
                },
            }
        )

        return signals

    async def _collect_trending_detailed(self) -> list[dict[str, Any]]:
        """Collect detailed trending repo data."""
        signals = []

        queries = [
            "created:>2025-01-01 topic:llm stars:>500",
            "created:>2025-01-01 topic:ai-agent stars:>200",
            "created:>2025-06-01 topic:rag stars:>100",
        ]

        for query in queries:
            url = f"{self.API_BASE}/search/repositories"
            params = {"q": query, "sort": "stars", "order": "desc", "per_page": "10"}

            response = await self.fetch(url, params=params, headers=self._get_headers())
            data = response.json()

            for repo in data.get("items", [])[:5]:
                signals.append(
                    {
                        "title": f"Trending repo: {repo['full_name']}",
                        "summary": f"⭐ {repo.get('stargazers_count', 0)} | "
                        f"🍴 {repo.get('forks_count', 0)} | "
                        f"{repo.get('language', 'N/A')} | "
                        f"{repo.get('description', '')[:100]}",
                        "url": repo["html_url"],
                        "source": "enhanced_github_trending",
                        "signal_type": SignalType.GITHUB_ACTIVITY.value,
                        "detected_at": datetime.now(UTC).isoformat(),
                        "metadata": {
                            "repo": repo["full_name"],
                            "stars": repo.get("stargazers_count", 0),
                            "forks": repo.get("forks_count", 0),
                            "language": repo.get("language", ""),
                            "description": repo.get("description", ""),
                            "created_at": repo.get("created_at"),
                            "updated_at": repo.get("updated_at"),
                            "topics": repo.get("topics", []),
                            "license": repo.get("license", {}).get("spdx_id")
                            if repo.get("license")
                            else None,
                        },
                    }
                )

        return signals

    def _get_headers(self) -> dict:
        """Get API headers with optional auth."""
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self.settings.rate_limit.github_token:
            headers["Authorization"] = f"token {self.settings.rate_limit.github_token}"
        return headers
