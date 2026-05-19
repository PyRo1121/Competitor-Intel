"""
Canonical feed catalog for RSS / Atom collectors.
Only URLs marked enabled=True were verified (HTTP 200 + RSS/Atom body) or are
long-standing defaults in production collectors. Disabled entries document
known-broken URLs (e.g. Sequoia /blog/rss/ 404) — do not re-enable without re-check.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class FeedSource:
    name: str
    url: str
    category: str
    trust_tier: int = 2
    enabled: bool = True
    disabled_reason: Optional[str] = None

    def as_rss_dict(self) -> Dict[str, str]:
        return {"name": self.name, "url": self.url, "category": self.category}


# fmt: off
FEED_CATALOG: Tuple[FeedSource, ...] = (
    # --- Tech / startup press (verified HTTP 200 + RSS/Atom, 2026-05) ---
    FeedSource("TechCrunch", "https://techcrunch.com/feed/", "news", 1),
    FeedSource("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/", "news", 1),
    FeedSource("TechCrunch Startups", "https://techcrunch.com/category/startups/feed/", "news", 1),
    FeedSource("TechCrunch Venture", "https://techcrunch.com/category/venture/feed/", "news", 1),
    FeedSource("VentureBeat", "https://venturebeat.com/feed/", "news", 1),
    FeedSource("VentureBeat AI", "https://venturebeat.com/category/ai/feed/", "news", 1),
    FeedSource("Ars Technica", "http://feeds.arstechnica.com/arstechnica/index", "news", 2),
    FeedSource("The Verge", "https://www.theverge.com/rss/index.xml", "news", 2),
    FeedSource("Wired", "https://www.wired.com/feed/rss", "news", 2),
    FeedSource(
        "Wired Business",
        "https://www.wired.com/feed/category/business/latest/rss",
        "news",
        1,
    ),
    FeedSource("MIT Technology Review", "https://www.technologyreview.com/feed/", "news", 2),
    FeedSource("Bloomberg Technology", "https://feeds.bloomberg.com/technology/news.rss", "news", 1),
    FeedSource("Fast Company", "https://www.fastcompany.com/latest/rss", "news", 2),
    FeedSource("ZDNet", "https://www.zdnet.com/news/rss.xml", "news", 2),
    FeedSource("CNET News", "https://www.cnet.com/rss/news/", "news", 2),
    FeedSource("GeekWire", "https://www.geekwire.com/feed/", "news", 2),
    FeedSource("SiliconANGLE", "https://siliconangle.com/feed/", "news", 2),
    FeedSource("Techmeme", "https://www.techmeme.com/feed.xml", "news", 2),
    FeedSource("Business Insider Tech", "https://www.businessinsider.com/rss", "news", 2),
    FeedSource(
        "CNBC Technology",
        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19854910",
        "news",
        2,
    ),
    FeedSource("Crunchbase News", "https://news.crunchbase.com/feed/", "funding", 1),
    FeedSource("TechFundingNews", "https://techfundingnews.com/feed/", "funding", 2),
    FeedSource("AI News", "https://www.artificialintelligence-news.com/feed/", "ai", 2),
    # --- EU / regional startup press ---
    FeedSource("Sifted", "https://sifted.eu/feed/", "news", 1),
    FeedSource("Tech.eu", "https://tech.eu/feed/", "news", 2),
    FeedSource("EU Startups", "https://www.eu-startups.com/feed/", "news", 2),
    FeedSource("BetaKit", "https://betakit.com/feed/", "news", 2),
    FeedSource(
        "Protocol",
        "https://www.protocol.com/feeds/feed.rss",
        "news",
        2,
        enabled=False,
        disabled_reason="404 — publication shut down 2022",
    ),
    FeedSource(
        "The Information",
        "https://www.theinformation.com/feed",
        "news",
        1,
        enabled=False,
        disabled_reason="403 — paywalled; no public RSS as of 2026-05",
    ),
    FeedSource(
        "PitchBook News",
        "https://pitchbook.com/news/feed",
        "funding",
        1,
        enabled=False,
        disabled_reason="403 as of 2026-05",
    ),
    FeedSource(
        "Axios Technology",
        "https://api.axios.com/feed/technology",
        "news",
        2,
        enabled=False,
        disabled_reason="404 as of 2026-05",
    ),
    # --- AI labs & research (verified) ---
    FeedSource("OpenAI Blog", "https://openai.com/blog/rss.xml", "ai", 1),
    FeedSource("Google DeepMind Blog", "https://deepmind.google/blog/rss.xml", "ai", 1),
    FeedSource("Google AI Blog", "https://blog.google/technology/ai/rss/", "ai", 1),
    FeedSource("Hugging Face Blog", "https://huggingface.co/blog/feed.xml", "ai", 1),
  # Anthropic / Meta public RSS paths change often — disabled until re-verified
    FeedSource(
        "Anthropic News",
        "https://www.anthropic.com/news/rss.xml",
        "ai",
        1,
        enabled=False,
        disabled_reason="404 as of 2026-05; check anthropic.com for current feed URL",
    ),
    # --- VC / growth (verified 2026-05 via utils.http) ---
    FeedSource("Lightspeed", "https://lsvp.com/feed/", "vc", 1),
    FeedSource("Y Combinator Blog", "https://www.ycombinator.com/blog/rss", "vc", 1),
    FeedSource("a16z", "https://a16z.substack.com/feed", "vc", 1),
    FeedSource("Sequoia Capital", "https://www.sequoiacap.com/feed/", "vc", 1),
    FeedSource("Benchmark", "https://medium.com/feed/benchmark", "vc", 1),
    FeedSource("Kleiner Perkins", "https://www.kleinerperkins.com/feed/", "vc", 1),
    FeedSource("Founders Fund", "https://foundersfund.com/feed/", "vc", 1),
    FeedSource("Menlo Ventures", "https://www.menlovc.com/feed/", "vc", 2),
    FeedSource("Battery Ventures", "https://www.battery.com/feed/", "vc", 2),
    FeedSource("Insight Partners", "https://www.insightpartners.com/feed/", "vc", 2),
    FeedSource("Redpoint Ventures", "https://medium.com/feed/redpoint-ventures", "vc", 2),
    FeedSource("Craft Ventures", "https://medium.com/feed/craft-ventures", "vc", 2),
    FeedSource("Union Square Ventures", "https://www.usv.com/feed/", "vc", 2),
    FeedSource(
        "a16z (a16z.com)",
        "https://a16z.com/feed/",
        "vc",
        1,
        enabled=False,
        disabled_reason="404 as of 2026-05; use a16z Substack feed",
    ),
    FeedSource(
        "Sequoia (/blog/rss/)",
        "https://www.sequoiacap.com/blog/rss/",
        "vc",
        1,
        enabled=False,
        disabled_reason="404; canonical feed is https://www.sequoiacap.com/feed/",
    ),
    FeedSource(
        "Sequoia Stories",
        "https://www.sequoiacap.com/stories/rss/",
        "vc",
        1,
        enabled=False,
        disabled_reason="403 as of 2026-05; use /feed/ instead",
    ),
    FeedSource(
        "Benchmark (benchmark.com)",
        "https://www.benchmark.com/feed",
        "vc",
        1,
        enabled=False,
        disabled_reason="404 as of 2026-05; use Medium feed",
    ),
    FeedSource(
        "Greylock Greymatter",
        "https://greylock.com/greymatter/feed/",
        "vc",
        2,
        enabled=False,
        disabled_reason="Returns HTML not RSS as of 2026-05",
    ),
    FeedSource(
        "First Round Review",
        "https://review.firstround.com/feed",
        "vc",
        2,
        enabled=False,
        disabled_reason="404 as of 2026-05",
    ),
    FeedSource(
        "Bessemer",
        "https://www.bvp.com/feed",
        "vc",
        2,
        enabled=False,
        disabled_reason="404 as of 2026-05",
    ),
    # --- Community / launches ---
    FeedSource("Hacker News", "https://news.ycombinator.com/rss", "community", 1),
    FeedSource("HN Show", "https://hnrss.org/show", "community", 2),
    FeedSource("HN High Signal", "https://hnrss.org/newest?points=50", "community", 2),
    FeedSource("Product Hunt", "https://www.producthunt.com/feed", "products", 1),
    # --- Newsletters / analysis ---
    FeedSource("Stratechery", "https://stratechery.com/feed/", "newsletter", 1),
    FeedSource("Lenny's Newsletter", "https://www.lennysnewsletter.com/feed", "newsletter", 2),
    FeedSource("Elad Gil", "https://blog.eladgil.com/feed", "newsletter", 2),
    # --- Corporate / infra signals ---
    FeedSource("Stripe Blog", "https://stripe.com/blog/feed.rss", "news", 2),
    # --- Regulatory ---
    FeedSource("EU Digital Strategy", "https://digital-strategy.ec.europa.eu/en/rss.xml", "regulatory", 2),
    FeedSource(
        "SEC Current Filings",
        "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&count=40&output=atom",
        "sec",
        1,
    ),
    # --- Legacy / optional (disabled) ---
    FeedSource(
        "The Batch",
        "https://www.thebatch.ai/rss",
        "ai",
        2,
        enabled=False,
        disabled_reason="200 but not RSS/Atom as of 2026-05",
    ),
    FeedSource(
        "TechCrunch Fundings (FeedBurner)",
        "https://feeds.feedburner.com/TechCrunch/fundings-exits",
        "funding",
        1,
        enabled=False,
        disabled_reason="404 as of 2026-05",
    ),
)
# fmt: on

X_MONITOR_QUERIES: Tuple[str, ...] = (
    '(\"raised seed\" OR \"raised $\" OR \"Series A\") (AI OR agent OR LLM) min_faves:5',
    '(\"just launched\" OR \"new AI tool\" OR \"AI agent\") min_faves:10',
    '(Cursor OR Perplexity OR LangChain OR CrewAI) (funding OR raised OR launch)',
    '(\"founder of\" OR \"co-founder\") (AI OR agent) since:2025-01-01',
    '(\"new AI startup\" OR \"AI company\") (seed OR pre-seed) min_faves:5',
    'OpenAI OR Anthropic OR xAI (funding OR partnership OR launch) min_faves:20',
    '(acquires OR acquisition) (AI OR LLM) min_faves:10',
    'YC W25 OR YC S25 (launch OR funding) min_faves:5',
)

SEC_USER_AGENT = "Hermes Competitor Intel contact@pyro1121.dev"


def enabled_feeds() -> List[FeedSource]:
    return [f for f in FEED_CATALOG if f.enabled]


def disabled_feeds() -> List[FeedSource]:
    return [f for f in FEED_CATALOG if not f.enabled]


def rss_feed_dicts() -> List[Dict[str, str]]:
    return [f.as_rss_dict() for f in enabled_feeds()]


def multi_source_tuples() -> List[Tuple[str, str]]:
    return [(f.url, f.name) for f in enabled_feeds()]


def feeds_by_category(category: str) -> List[FeedSource]:
    return [f for f in enabled_feeds() if f.category == category]


def catalog_summary() -> Dict[str, int]:
    enabled = enabled_feeds()
    disabled = disabled_feeds()
    by_cat: Dict[str, int] = {}
    for f in enabled:
        by_cat[f.category] = by_cat.get(f.category, 0) + 1
    return {
        "enabled": len(enabled),
        "disabled": len(disabled),
        "total": len(FEED_CATALOG),
        "by_category": by_cat,
    }


def get_x_monitor_queries() -> List[str]:
    return list(X_MONITOR_QUERIES)
