"""
Canonical feed catalog for RSS / Atom collectors.

Categories (private-company verticals):
  vc, pe, tech_press, fintech, neobank, ai_lab, company_blog,
  regulatory, eu_startup, general_startup

Only URLs marked enabled=True were verified (HTTP 200 + RSS/Atom body) as of
2026-05. Disabled entries document known-broken URLs — do not re-enable without
re-check via utils.http.fetch_text or HEAD.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# Canonical category slugs for private-company intel
FEED_CATEGORIES: Tuple[str, ...] = (
    "vc",
    "pe",
    "tech_press",
    "fintech",
    "neobank",
    "ai_lab",
    "company_blog",
    "regulatory",
    "eu_startup",
    "general_startup",
)

# Backward compatibility for collectors/docs that used legacy slugs
CATEGORY_ALIASES: Dict[str, str] = {
    "news": "tech_press",
    "funding": "general_startup",
    "ai": "ai_lab",
    "community": "general_startup",
    "products": "general_startup",
    "newsletter": "vc",
    "sec": "regulatory",
}


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
    # --- tech_press (verified 2026-05) ---
    FeedSource("TechCrunch", "https://techcrunch.com/feed/", "tech_press", 1),
    FeedSource("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/", "tech_press", 1),
    FeedSource("TechCrunch Startups", "https://techcrunch.com/category/startups/feed/", "tech_press", 1),
    FeedSource("TechCrunch Venture", "https://techcrunch.com/category/venture/feed/", "tech_press", 1),
    FeedSource("VentureBeat", "https://venturebeat.com/feed/", "tech_press", 1),
    FeedSource("VentureBeat AI", "https://venturebeat.com/category/ai/feed/", "tech_press", 1),
    FeedSource("Ars Technica", "http://feeds.arstechnica.com/arstechnica/index", "tech_press", 2),
    FeedSource("The Verge", "https://www.theverge.com/rss/index.xml", "tech_press", 2),
    FeedSource("Wired", "https://www.wired.com/feed/rss", "tech_press", 2),
    FeedSource("Wired Business", "https://www.wired.com/feed/category/business/latest/rss", "tech_press", 1),
    FeedSource("MIT Technology Review", "https://www.technologyreview.com/feed/", "tech_press", 2),
    FeedSource("Bloomberg Technology", "https://feeds.bloomberg.com/technology/news.rss", "tech_press", 1),
    FeedSource("Fast Company", "https://www.fastcompany.com/latest/rss", "tech_press", 2),
    FeedSource("ZDNet", "https://www.zdnet.com/news/rss.xml", "tech_press", 2),
    FeedSource("CNET News", "https://www.cnet.com/rss/news/", "tech_press", 2),
    FeedSource("GeekWire", "https://www.geekwire.com/feed/", "tech_press", 2),
    FeedSource("SiliconANGLE", "https://siliconangle.com/feed/", "tech_press", 2),
    FeedSource("Techmeme", "https://www.techmeme.com/feed.xml", "tech_press", 2),
    FeedSource("Business Insider Tech", "https://www.businessinsider.com/rss", "tech_press", 2),
    FeedSource(
        "CNBC Technology",
        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19854910",
        "tech_press",
        2,
    ),
    FeedSource("Rest of World", "https://restofworld.org/feed/latest/", "tech_press", 2),
    FeedSource("The Register", "https://www.theregister.com/headlines.atom", "tech_press", 2),
    FeedSource("InfoQ", "https://feed.infoq.com/", "tech_press", 2),
    FeedSource("TechRepublic", "https://www.techrepublic.com/rssfeeds/articles/", "tech_press", 2),
    FeedSource(
        "The Information",
        "https://www.theinformation.com/feed",
        "tech_press",
        1,
        enabled=False,
        disabled_reason="403 — paywalled; no public RSS as of 2026-05",
    ),
    FeedSource(
        "Protocol",
        "https://www.protocol.com/feeds/feed.rss",
        "tech_press",
        2,
        enabled=False,
        disabled_reason="404 — publication shut down 2022",
    ),
    FeedSource(
        "Axios Technology",
        "https://api.axios.com/feed/technology",
        "tech_press",
        2,
        enabled=False,
        disabled_reason="404 as of 2026-05",
    ),
    # --- eu_startup ---
    FeedSource("Sifted", "https://sifted.eu/feed/", "eu_startup", 1),
    FeedSource("Tech.eu", "https://tech.eu/feed/", "eu_startup", 2),
    FeedSource("EU Startups", "https://www.eu-startups.com/feed/", "eu_startup", 2),
    FeedSource("BetaKit", "https://betakit.com/feed/", "eu_startup", 2),
    FeedSource("Silicon Canals", "https://siliconcanals.com/feed/", "eu_startup", 2),
    FeedSource("The Recursive", "https://therecursive.com/feed/", "eu_startup", 2),
    FeedSource("Arctic Startup", "https://arcticstartup.com/feed/", "eu_startup", 2),
    FeedSource("StartupJuncture", "https://www.startupjuncture.com/feed/", "eu_startup", 2),
    FeedSource("FrenchWeb", "https://www.frenchweb.fr/feed", "eu_startup", 2),
    FeedSource(
        "EU Tech Loop",
        "https://www.eutechloop.com/feed/",
        "eu_startup",
        2,
        enabled=False,
        disabled_reason="TLS error as of 2026-05",
    ),
    # --- general_startup ---
    FeedSource("Crunchbase News", "https://news.crunchbase.com/feed/", "general_startup", 1),
    FeedSource("TechFundingNews", "https://techfundingnews.com/feed/", "general_startup", 2),
    FeedSource("StrictlyVC", "https://strictlyvc.com/feed/", "general_startup", 1),
    FeedSource("Fortune Term Sheet", "https://fortune.com/feed/tag/term-sheet/rss/", "general_startup", 1),
    FeedSource("Inc Magazine", "https://www.inc.com/rss/", "general_startup", 2),
    FeedSource("Entrepreneur", "https://www.entrepreneur.com/latest.rss", "general_startup", 2),
    FeedSource("SaaStr", "https://www.saastr.com/feed/", "general_startup", 2),
    FeedSource("SaaS Mag", "https://saasmag.com/feed/", "general_startup", 2),
    FeedSource("Hacker News", "https://news.ycombinator.com/rss", "general_startup", 1),
    FeedSource("HN Show", "https://hnrss.org/show", "general_startup", 2),
    FeedSource("HN High Signal", "https://hnrss.org/newest?points=50", "general_startup", 2),
    FeedSource("Product Hunt", "https://www.producthunt.com/feed", "general_startup", 1),
    FeedSource(
        "PitchBook News",
        "https://pitchbook.com/news/feed",
        "general_startup",
        1,
        enabled=False,
        disabled_reason="403 as of 2026-05",
    ),
    FeedSource(
        "TechCrunch Fundings (FeedBurner)",
        "https://feeds.feedburner.com/TechCrunch/fundings-exits",
        "general_startup",
        1,
        enabled=False,
        disabled_reason="404 as of 2026-05",
    ),
    # --- ai_lab (agent #14: labs, hyperscalers, model vendors — verified May 2026) ---
    FeedSource("OpenAI Blog", "https://openai.com/blog/rss.xml", "ai_lab", 1),
    FeedSource("Google DeepMind Blog", "https://deepmind.google/blog/rss.xml", "ai_lab", 1),
    FeedSource("Google AI Blog", "https://blog.google/technology/ai/rss/", "ai_lab", 1),
    FeedSource("Google Research Blog", "https://research.google/blog/rss/", "ai_lab", 1),
    FeedSource(
        "Google Developers Blog",
        "https://developers.googleblog.com/feeds/posts/default",
        "ai_lab",
        1,
    ),
    FeedSource("Hugging Face Blog", "https://huggingface.co/blog/feed.xml", "ai_lab", 1),
    FeedSource(
        "Meta AI News",
        "https://about.fb.com/news/category/technologies/feed/",
        "ai_lab",
        1,
    ),
    FeedSource("Meta AI Research", "https://research.facebook.com/feed/", "ai_lab", 1),
    FeedSource("Microsoft AI Blog", "https://blogs.microsoft.com/ai/feed/", "ai_lab", 1),
    FeedSource(
        "Microsoft Research",
        "https://www.microsoft.com/en-us/research/feed/",
        "ai_lab",
        1,
    ),
    FeedSource(
        "AWS Machine Learning Blog",
        "https://aws.amazon.com/blogs/machine-learning/feed/",
        "ai_lab",
        1,
    ),
    FeedSource(
        "Azure AI Blog",
        "https://azure.microsoft.com/en-us/blog/topics/artificial-intelligence/feed/",
        "ai_lab",
        1,
    ),
    FeedSource("NVIDIA AI Blog", "https://blogs.nvidia.com/feed/", "ai_lab", 1),
    FeedSource("NVIDIA Developer Blog", "https://developer.nvidia.com/blog/feed", "ai_lab", 1),
    FeedSource("Apple Machine Learning", "https://machinelearning.apple.com/rss.xml", "ai_lab", 1),
    FeedSource(
        "Anthropic News",
        "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_news.xml",
        "ai_lab",
        2,
    ),
    FeedSource(
        "Anthropic Engineering",
        "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_engineering.xml",
        "ai_lab",
        2,
    ),
    FeedSource("Cohere Blog (Substack)", "https://cohere.substack.com/feed", "ai_lab", 2),
    FeedSource("Together AI Blog", "https://www.together.ai/blog/rss.xml", "ai_lab", 1),
    FeedSource("Character.AI Blog", "https://blog.character.ai/rss", "ai_lab", 2),
    FeedSource("Midjourney Updates", "https://updates.midjourney.com/rss", "ai_lab", 2),
    FeedSource("Writer Blog", "https://writer.com/blog/feed/", "ai_lab", 2),
    FeedSource("Replicate Blog", "https://replicate.com/blog/rss", "ai_lab", 2),
    FeedSource("Databricks Blog", "https://www.databricks.com/feed", "ai_lab", 1),
    FeedSource("DataRobot Blog", "https://www.datarobot.com/blog/feed/", "ai_lab", 2),
    FeedSource("Weaviate Blog", "https://weaviate.io/blog/rss.xml", "ai_lab", 2),
    FeedSource("Habana Labs", "https://habana.ai/feed/", "ai_lab", 2),
    FeedSource("AI News", "https://www.artificialintelligence-news.com/feed/", "ai_lab", 2),
    FeedSource("Import AI", "https://jack-clark.net/feed/", "ai_lab", 2),
    FeedSource("The Gradient", "https://thegradient.pub/rss/", "ai_lab", 2),
    FeedSource("Latent Space", "https://www.latent.space/feed", "ai_lab", 2),
    FeedSource("Interconnects", "https://www.interconnects.ai/feed", "ai_lab", 2),
    FeedSource("SemiAnalysis", "https://www.semianalysis.com/feed", "ai_lab", 2),
    FeedSource(
        "Simon Willison",
        "https://simonwillison.net/atom/everything/",
        "ai_lab",
        2,
    ),
    FeedSource(
        "Anthropic News (official)",
        "https://www.anthropic.com/news/rss.xml",
        "ai_lab",
        1,
        enabled=False,
        disabled_reason="404 as of 2026-05; use Anthropic News mirror",
    ),
    FeedSource(
        "Mistral AI",
        "https://mistral.ai/news/rss.xml",
        "ai_lab",
        1,
        enabled=False,
        disabled_reason="404 as of 2026-05; no public RSS on learn.mistral.ai",
    ),
    FeedSource(
        "Cohere Blog (official)",
        "https://cohere.com/blog/rss.xml",
        "ai_lab",
        1,
        enabled=False,
        disabled_reason="200 but empty feed; use Cohere Substack",
    ),
    FeedSource(
        "Meta AI Blog",
        "https://ai.meta.com/blog/rss/",
        "ai_lab",
        1,
        enabled=False,
        disabled_reason="404; use Meta AI News (about.fb.com)",
    ),
    FeedSource(
        "xAI Blog",
        "https://x.ai/blog/rss.xml",
        "ai_lab",
        1,
        enabled=False,
        disabled_reason="404 as of 2026-05",
    ),
    FeedSource(
        "Stability AI Blog",
        "https://stability.ai/blog/rss.xml",
        "ai_lab",
        1,
        enabled=False,
        disabled_reason="404 as of 2026-05",
    ),
    FeedSource(
        "Scale AI Blog",
        "https://scale.com/blog/rss.xml",
        "ai_lab",
        1,
        enabled=False,
        disabled_reason="200 but empty feed as of 2026-05",
    ),
    FeedSource(
        "AI21 Labs Blog",
        "https://www.ai21.com/blog/rss.xml",
        "ai_lab",
        2,
        enabled=False,
        disabled_reason="200 but empty feed as of 2026-05",
    ),
    FeedSource(
        "LangChain Blog",
        "https://blog.langchain.dev/rss/",
        "ai_lab",
        2,
        enabled=False,
        disabled_reason="200 but empty feed as of 2026-05",
    ),
    FeedSource(
        "The Batch",
        "https://www.thebatch.ai/rss",
        "ai_lab",
        2,
        enabled=False,
        disabled_reason="200 but not RSS/Atom as of 2026-05",
    ),
    # --- vc (verified 2026-05 via utils.http) ---
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
    FeedSource("Union Square Ventures", "https://www.usv.com/writing/rss/", "vc", 2),
    FeedSource("Stratechery", "https://stratechery.com/feed/", "vc", 1),
    FeedSource("Lenny's Newsletter", "https://www.lennysnewsletter.com/feed", "vc", 2),
    FeedSource("Elad Gil", "https://blog.eladgil.com/feed", "vc", 2),
    FeedSource("Not Boring", "https://www.notboring.co/feed", "vc", 2),
    FeedSource("Point Nine", "https://medium.com/feed/point-nine-news", "vc", 2),
    FeedSource("AVC", "https://avc.com/feed/", "vc", 2),
    FeedSource("Hunter Walk", "https://hunterwalk.com/feed/", "vc", 2),
    FeedSource("The Generalist", "https://www.generalist.com/feed", "vc", 2),
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
    FeedSource(
        "Index Ventures",
        "https://www.indexventures.com/perspectives/rss/",
        "vc",
        1,
        enabled=False,
        disabled_reason="404 as of 2026-05",
    ),
    FeedSource(
        "Accel Noteworthy",
        "https://www.accel.com/noteworthy/rss.xml",
        "vc",
        1,
        enabled=False,
        disabled_reason="404 as of 2026-05",
    ),
    # --- pe ---
    FeedSource("PE Hub", "https://www.pehub.com/feed/", "pe", 1),
    FeedSource("Buyouts Insider", "https://www.buyoutsinsider.com/feed/", "pe", 1),
    FeedSource("Private Equity International", "https://www.privateequityinternational.com/feed/", "pe", 1),
    FeedSource("Private Equity Wire", "https://www.privateequitywire.co.uk/rss", "pe", 2),
    FeedSource("Secondaries Investor", "https://www.secondariesinvestor.com/feed/", "pe", 2),
    FeedSource("Fortune Deals", "https://fortune.com/feed/tag/deals/rss/", "pe", 2),
    FeedSource(
        "PitchBook PE RSS",
        "https://pitchbook.com/news/articles/rss",
        "pe",
        1,
        enabled=False,
        disabled_reason="403 as of 2026-05",
    ),
    FeedSource(
        "Axios Pro Rata",
        "https://www.axios.com/feeds/pro-rata.xml",
        "pe",
        1,
        enabled=False,
        disabled_reason="404 as of 2026-05",
    ),
    # --- fintech ---
    FeedSource("Finextra", "https://www.finextra.com/rss/headlines.aspx", "fintech", 1),
    FeedSource("The Fintech Times", "https://thefintechtimes.com/feed/", "fintech", 2),
    FeedSource("PYMNTS", "https://www.pymnts.com/feed/", "fintech", 1),
    FeedSource("Banking Dive", "https://www.bankingdive.com/feeds/news/", "fintech", 2),
    FeedSource("Payments Dive", "https://www.paymentsdive.com/feeds/news/", "fintech", 2),
    FeedSource("Fintech Nexus", "https://www.fintechnexus.com/feed/", "fintech", 2),
    FeedSource("Finovate", "https://finovate.com/feed/", "fintech", 2),
    FeedSource("TechCrunch Fintech", "https://techcrunch.com/category/fintech/feed/", "fintech", 1),
    FeedSource(
        "FinTech Futures",
        "https://www.fintechfutures.com/feed/",
        "fintech",
        2,
        enabled=False,
        disabled_reason="403 as of 2026-05",
    ),
    FeedSource(
        "Crowdfund Insider",
        "https://www.crowdfundinsider.com/feed/",
        "fintech",
        2,
        enabled=False,
        disabled_reason="403 as of 2026-05",
    ),
    # --- neobank (company press rooms / Medium mirrors) ---
    FeedSource("Bunq Blog", "https://medium.com/feed/bunq", "neobank", 2),
    FeedSource("Chime Blog", "https://medium.com/feed/chime", "neobank", 2),
    FeedSource("Revolut Blog", "https://medium.com/feed/revolut", "neobank", 2),
    FeedSource("SoFi Blog", "https://www.sofi.com/blog/feed/", "neobank", 2),
    FeedSource("Wise Blog", "https://wise.com/gb/blog/rss/", "neobank", 2),
    FeedSource(
        "Monzo Blog",
        "https://monzo.com/blog/feed.rss",
        "neobank",
        2,
        enabled=False,
        disabled_reason="404 as of 2026-05; no public RSS",
    ),
    FeedSource(
        "N26 Blog",
        "https://n26.com/en-eu/blog/feed",
        "neobank",
        2,
        enabled=False,
        disabled_reason="404 as of 2026-05",
    ),
    FeedSource(
        "Starling Bank",
        "https://www.starlingbank.com/blog/feed/",
        "neobank",
        2,
        enabled=False,
        disabled_reason="403 as of 2026-05",
    ),
    FeedSource(
        "Nubank Blog",
        "https://blog.nubank.com.br/feed/",
        "neobank",
        2,
        enabled=False,
        disabled_reason="404 as of 2026-05",
    ),
    # --- company_blog (engineering / product blogs — verified May 2026) ---
    FeedSource("Stripe Blog", "https://stripe.com/blog/feed.rss", "company_blog", 1),
    FeedSource("Meta Engineering", "https://engineering.fb.com/feed/", "company_blog", 1),
    FeedSource("Cloudflare Blog", "https://blog.cloudflare.com/rss/", "company_blog", 2),
    FeedSource("Datadog Blog", "https://www.datadoghq.com/blog/index.xml", "company_blog", 2),
    FeedSource("Figma Blog", "https://www.figma.com/blog/feed/atom.xml", "company_blog", 2),
    FeedSource("Vercel Blog", "https://vercel.com/atom", "company_blog", 2),
    FeedSource("GitHub Blog", "https://github.blog/feed/", "company_blog", 2),
    FeedSource("GitLab Blog", "https://about.gitlab.com/atom.xml", "company_blog", 2),
    FeedSource("Dropbox Tech Blog", "https://dropbox.tech/feed", "company_blog", 2),
    FeedSource("Spotify Engineering", "https://engineering.atspotify.com/feed/", "company_blog", 2),
    FeedSource("Slack Engineering", "https://slack.engineering/feed/", "company_blog", 2),
    FeedSource("Discord Blog", "https://discord.com/blog/rss.xml", "company_blog", 2),
    FeedSource("Palantir Blog", "https://blog.palantir.com/feed", "company_blog", 2),
    FeedSource("Square Developer Blog", "https://developer.squareup.com/blog/rss.xml", "company_blog", 2),
    FeedSource("Linear Blog", "https://linear.app/rss/blog.xml", "company_blog", 2),
    FeedSource("Supabase Blog", "https://supabase.com/rss.xml", "company_blog", 2),
    FeedSource(
        "Uber Engineering",
        "https://www.uber.com/blog/engineering/rss/",
        "company_blog",
        2,
        enabled=False,
        disabled_reason="404 as of 2026-05",
    ),
    FeedSource(
        "Netflix Tech Blog",
        "https://netflixtechblog.com/feed",
        "company_blog",
        2,
        enabled=False,
        disabled_reason="TLS verify failure from collector host May 2026",
    ),
    FeedSource(
        "Plaid Blog",
        "https://plaid.com/blog/rss/",
        "company_blog",
        2,
        enabled=False,
        disabled_reason="404 as of 2026-05",
    ),
    FeedSource(
        "Notion Blog",
        "https://www.notion.so/blog/rss.xml",
        "company_blog",
        2,
        enabled=False,
        disabled_reason="404 as of 2026-05",
    ),
    FeedSource(
        "Ramp Blog",
        "https://ramp.com/blog/rss.xml",
        "company_blog",
        2,
        enabled=False,
        disabled_reason="404 as of 2026-05",
    ),
    # --- regulatory ---
    FeedSource("EU Digital Strategy", "https://digital-strategy.ec.europa.eu/en/rss.xml", "regulatory", 2),
    FeedSource("FCA News", "https://www.fca.org.uk/news/rss.xml", "regulatory", 1),
    FeedSource("CFPB Newsroom", "https://www.consumerfinance.gov/about-us/newsroom/feed/", "regulatory", 1),
    FeedSource("ECB Press", "https://www.ecb.europa.eu/rss/press.html", "regulatory", 1),
    FeedSource("EBA News", "https://www.eba.europa.eu/news-press/news/rss.xml", "regulatory", 1),
    FeedSource("Bank of England News", "https://www.bankofengland.co.uk/rss/news", "regulatory", 1),
    FeedSource("Federal Reserve Press", "https://www.federalreserve.gov/feeds/press_all.xml", "regulatory", 1),
    FeedSource(
        "SEC Current Filings",
        "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&count=40&output=atom",
        "regulatory",
        1,
    ),
    FeedSource(
        "ESMA News",
        "https://www.esma.europa.eu/press-news/esma-news/rss.xml",
        "regulatory",
        1,
        enabled=False,
        disabled_reason="200 but HTML landing page, not RSS as of 2026-05",
    ),
    FeedSource(
        "CFTC Press",
        "https://www.cftc.gov/PressRoom/PressReleases/rss.xml",
        "regulatory",
        1,
        enabled=False,
        disabled_reason="200 but HTML landing page, not RSS as of 2026-05",
    ),
    FeedSource(
        "BaFin Press",
        "https://www.bafin.de/SharedDocs/Veroeffentlichungen/EN/RSS/RSSNewsfeed.xml",
        "regulatory",
        1,
        enabled=False,
        disabled_reason="404 as of 2026-05",
    ),
)
# fmt: on

X_MONITOR_QUERIES: Tuple[str, ...] = (
    '(\"raised seed\" OR \"raised $\" OR \"Series A\") (startup OR SaaS OR fintech) min_faves:5',
    '(\"just launched\" OR \"new startup\" OR \"stealth mode\") min_faves:10',
    '(neobank OR \"digital bank\" OR \"embedded finance\") (funding OR raised OR launch)',
    '(\"PE firm\" OR \"private equity\" OR buyout) (acquires OR acquisition) min_faves:5',
    '(\"founder of\" OR \"co-founder\") (startup OR fintech) since:2025-01-01',
    '(\"new AI startup\" OR \"AI company\") (seed OR pre-seed) min_faves:5',
    'OpenAI OR Anthropic OR Stripe OR Plaid (funding OR partnership OR launch) min_faves:20',
    '(acquires OR acquisition) (SaaS OR fintech OR AI) min_faves:10',
    'YC W25 OR YC S25 (launch OR funding) min_faves:5',
    '(Revolut OR Monzo OR N26 OR Chime OR Wise) (funding OR expansion OR launch)',
)

SEC_USER_AGENT = "Hermes Competitor Intel contact@pyro1121.dev"


def _resolve_category(category: str) -> str:
    return CATEGORY_ALIASES.get(category, category)


def enabled_feeds() -> List[FeedSource]:
    return [f for f in FEED_CATALOG if f.enabled]


def disabled_feeds() -> List[FeedSource]:
    return [f for f in FEED_CATALOG if not f.enabled]


def rss_feed_dicts() -> List[Dict[str, str]]:
    return [f.as_rss_dict() for f in enabled_feeds()]


def multi_source_tuples() -> List[Tuple[str, str]]:
    return [(f.url, f.name) for f in enabled_feeds()]


def feeds_by_category(category: str) -> List[FeedSource]:
    resolved = _resolve_category(category)
    return [f for f in enabled_feeds() if f.category == resolved]


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
