"""RSS feed collector using async HTTP and proper parsing."""

import asyncio
from datetime import UTC, datetime
from typing import Any

import feedparser
import structlog

from competitor_intel.core.collector import BaseCollector
from competitor_intel.core.types import SignalType

logger = structlog.get_logger()


class RSSCollector(BaseCollector):
    """Collect signals from RSS feeds.

    Sources:
    - TechCrunch
    - VentureBeat
    - Axios
    - Reuters
    - a16z
    - Sequoia
    - Y Combinator
    - Product Hunt
    """

    SOURCES = [
        ("https://techcrunch.com/feed/", "TechCrunch"),
        ("https://venturebeat.com/feed/", "VentureBeat"),
        ("https://feeds.feedburner.com/TechCrunch/fundings-exits", "TechCrunch Fundings"),
        ("https://www.axios.com/feeds/technology.xml", "Axios Tech"),
        ("https://a16z.com/feed/", "a16z"),
        ("https://www.sequoiacap.com/blog/rss/", "Sequoia Capital"),
        ("https://www.ycombinator.com/blog/rss", "Y Combinator"),
        ("https://news.ycombinator.com/rss", "Hacker News"),
        ("https://news.crunchbase.com/feed/", "Crunchbase News"),
        ("https://www.producthunt.com/feed", "Product Hunt"),
    ]

    def __init__(self):
        super().__init__("rss")

    @property
    def source_type(self) -> str:
        return "rss"

    async def collect(self) -> list[dict[str, Any]]:
        """Collect signals from RSS feeds."""
        signals = []

        for feed_url, source_name in self.SOURCES:
            try:
                feed_signals = await self._parse_feed(feed_url, source_name)
                signals.extend(feed_signals)

                # Rate limiting delay between feeds
                await asyncio.sleep(self.settings.rate_limit.rss_delay_seconds)

            except Exception as e:
                logger.error(
                    "rss_feed_error",
                    url=feed_url,
                    source=source_name,
                    error=str(e),
                )

        logger.info("rss_collection_complete", total_signals=len(signals))
        return signals

    async def _parse_feed(self, feed_url: str, source_name: str) -> list[dict[str, Any]]:
        """Parse a single RSS feed."""
        # feedparser is sync, so run in thread pool
        loop = asyncio.get_event_loop()
        feed = await loop.run_in_executor(None, feedparser.parse, feed_url)

        if feed.bozo:
            logger.warning(
                "rss_parse_warning",
                url=feed_url,
                error=feed.get("bozo_exception", "Unknown"),
            )

        signals = []
        for entry in feed.entries[:15]:  # Limit to top 15 entries
            signal = self._entry_to_signal(entry, source_name)
            if signal:
                signals.append(signal)

        logger.debug(
            "rss_feed_parsed",
            url=feed_url,
            source=source_name,
            entries=len(signals),
        )

        return signals

    def _entry_to_signal(self, entry: Any, source_name: str) -> dict[str, Any] | None:
        """Convert feed entry to normalized signal."""
        title = entry.get("title", "").strip()
        if not title or len(title) < 10:
            return None

        # Extract published date
        published = entry.get("published_parsed") or entry.get("updated_parsed")
        if published:
            detected_at = datetime(*published[:6]).isoformat()
        else:
            detected_at = datetime.now(UTC).isoformat()

        return {
            "title": title,
            "summary": (entry.get("summary", "") or entry.get("description", ""))[:800],
            "url": entry.get("link", ""),
            "source": source_name,
            "signal_type": SignalType.RSS_ITEM.value,
            "detected_at": detected_at,
            "metadata": {
                "feed_source": source_name,
                "author": entry.get("author", ""),
            },
        }
