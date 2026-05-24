#!/usr/bin/env python3
"""Expanded RSS & Source Feed List for private company intelligence."""

import logging

logger = logging.getLogger("sources")

TECH_NEWS = {
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "TechCrunch Startups": "https://techcrunch.com/category/startups/feed/",
    "TechCrunch Venture": "https://techcrunch.com/category/venture/feed/",
    "The Verge": "https://www.theverge.com/rss/index.xml",
    "Ars Technica": "http://feeds.arstechnica.com/arstechnica/index",
    "Wired": "https://www.wired.com/feed/rss",
    "MIT Technology Review": "https://www.technologyreview.com/feed/",
    "ZDNet": "https://www.zdnet.com/news/rss.xml",
    "CNET": "https://www.cnet.com/rss/news/",
    "Fast Company": "https://www.fastcompany.com/latest/rss",
    "Bloomberg Tech": "https://feeds.bloomberg.com/business/news.rss",
    "Reuters Tech": "https://www.reutersagency.com/feed/?best-topics=tech&post_type=reuters-best",
}

AI_NEWS = {
    "VentureBeat AI": "https://venturebeat.com/category/ai/feed/",
    "AI News": "https://www.artificialintelligence-news.com/feed/",
    "Analytics India": "https://analyticsindiamag.com/feed/",
    "Synced Review": "https://syncedreview.com/feed/",
    "TopBots": "https://www.topbots.com/feed/",
    "AI Weekly": "https://aiweekly.co/rss",
    "Datafloq": "https://datafloq.com/feed/",
    "KDnuggets": "https://www.kdnuggets.com/feed",
    "AI Trends": "https://www.ai-trends.com/feed/",
    "OpenAI Blog": "https://openai.com/blog/rss.xml",
    "Anthropic Blog": "https://www.anthropic.com/rss.xml",
    "DeepMind Blog": "https://deepmind.google/blog/rss.xml",
    "Hugging Face Blog": "https://huggingface.co/blog/feed.xml",
    "MosaicML Blog": "https://www.mosaicml.com/blog/rss.xml",
    "Scale AI Blog": "https://scale.com/blog/rss.xml",
}

VC_NEWS = {
    "PitchBook News": "https://pitchbook.com/news/articles/feed",
    "PE Hub": "https://www.pehub.com/feed/",
    "VC Journal": "https://www.vcj.news/feed/",
    "Crunchbase News": "https://news.crunchbase.com/feed/",
    "AngelList Blog": "https://angel.co/blog/feed",
    "a16z Newsletter": "https://a16z.substack.com/feed",
    "Sequoia Insights": "https://www.sequoiacap.com/feed/",
    "Bessemer Blog": "https://www.bvp.com/feed",
    "First Round Review": "https://review.firstround.com/feed",
    "Accel Insights": "https://www.accel.com/content/feed",
    "Greylock Perspectives": "https://greylock.com/greymatter/feed/",
    "Index Ventures Blog": "https://www.indexventures.com/perspectives/feed/",
}

STARTUP_DISCOVERY = {
    "Product Hunt": "https://www.producthunt.com/feed",
    "BetaList": "https://betalist.com/startups/feed",
    "Indie Hackers": "https://www.indiehackers.com/feed",
    "Starter Story": "https://www.starterstory.com/feed",
    "Failory": "https://www.failory.com/feed",
    "Hacker News Top": "https://hnrss.org/newest?points=50",
    "Hacker News Show": "https://hnrss.org/show",
    "Lobsters": "https://lobste.rs/rss",
    "GrowthHackers": "https://growthhackers.com/rss",
    "SaaS Strife": "https://saasstr.com/feed/",
    "TinySeed": "https://tinyseed.com/feed",
    "Dealroom Blog": "https://blog.dealroom.co/feed",
    "Tracxn Blog": "https://tracxn.com/blog/feed/",
    "Startup Genome": "https://startupgenome.com/feed",
}

STARTUP_NEWSLETTERS = {
    "Lenny's Newsletter": "https://www.lennysnewsletter.com/feed",
    "First 1000": "https://first1000.substack.com/feed",
    "Superorganizers": "https://superorganizers.substack.com/feed",
    "Divinations": "https://divinations.substack.com/feed",
    "Not Boring": "https://www.notboring.co/feed",
    "Stratechery": "https://stratechery.com/feed/",
    "Above Avalon": "https://www.aboveavalon.com/feed",
    "Tom Tunguz": "https://tomtunguz.com/feed",
    "Jason Cohen": "https://blog.asmartbear.com/feed/",
    "David Sacks": "https://davidsacks.substack.com/feed",
    "Elad Gil": "https://blog.eladgil.com/feed",
    "Paul Graham": "http://www.paulgraham.com/rss.html",
    "Sam Altman": "https://blog.samaltman.com/rss",
}

GOVERNMENT_DEFENSE = {
    "Defense News": "https://www.defensenews.com/arc/outboundfeeds/rss/",
    "Breaking Defense": "https://breakingdefense.com/feed/",
    "Defense One": "https://www.defenseone.com/rss/all/",
    "FedScoop": "https://www.fedscoop.com/feed/",
    "NextGov": "https://www.nextgov.com/rss/",
    "DARPA News": "https://www.darpa.mil/rss/news.xml",
    "C4ISRNET": "https://www.c4isrnet.com/arc/outboundfeeds/rss/",
}

INDUSTRY = {
    "Healthcare IT News": "https://www.healthcareitnews.com/rss/xml",
    "Fintech Nexus": "https://www.fintechnexus.com/feed/",
    "BioPharma Dive": "https://www.biopharmadive.com/feeds/news/",
    "EdTech Digest": "https://edtechdigest.com/feed/",
    "Transportation Dive": "https://www.transportationdive.com/feeds/news/",
    "Retail Dive": "https://www.retaildive.com/feeds/news/",
    "Manufacturing Dive": "https://www.manufacturingdive.com/feeds/news/",
}

INTERNATIONAL = {
    "Tech in Asia": "https://www.techinasia.com/feed",
    "KrASIA": "https://kr-asia.com/feed",
    "South China Morning Post Tech": "https://www.scmp.com/rss/tech/feed",
    "EU Startups": "https://www.eu-startups.com/feed/",
    "Sifted (FT)": "https://sifted.eu/articles/feed/",
    "The Ken": "https://the-ken.com/feed/",
    "Tech.eu": "https://tech.eu/feed/",
}

STARTUP_ACCELERATORS = {
    "Y Combinator": "https://www.ycombinator.com/blog/rss.xml",
    "Techstars Blog": "https://www.techstars.com/blog/feed",
    "500 Global": "https://500.co/feed/",
    "Plug and Tech": "https://plugandtech.com/feed/",
    "MassChallenge": "https://masschallenge.org/feed/",
}

AI_RESEARCH = {
    "arXiv AI": "http://export.arxiv.org/rss/cs.AI",
    "arXiv ML": "http://export.arxiv.org/rss/cs.LG",
    "arXiv CL": "http://export.arxiv.org/rss/cs.CL",
    "arXiv CV": "http://export.arxiv.org/rss/cs.CV",
    "Papers With Code": "https://paperswithcode.com/latest.rss",
    "AI Research Blog": "https://ai.googleblog.com/feeds/posts/default",
    "OpenAI Research": "https://openai.com/research/rss.xml",
}

ALL_SOURCES: dict[str, str] = {}
ALL_SOURCES.update(TECH_NEWS)
ALL_SOURCES.update(AI_NEWS)
ALL_SOURCES.update(VC_NEWS)
ALL_SOURCES.update(STARTUP_DISCOVERY)
ALL_SOURCES.update(STARTUP_NEWSLETTERS)
ALL_SOURCES.update(GOVERNMENT_DEFENSE)
ALL_SOURCES.update(INDUSTRY)
ALL_SOURCES.update(INTERNATIONAL)
ALL_SOURCES.update(STARTUP_ACCELERATORS)
ALL_SOURCES.update(AI_RESEARCH)

COMPETITOR_INTEL_SOURCES = {
    "TechCrunch AI": TECH_NEWS["TechCrunch AI"],
    "TechCrunch Startups": TECH_NEWS["TechCrunch Startups"],
    "TechCrunch Venture": TECH_NEWS["TechCrunch Venture"],
    "The Verge": TECH_NEWS["The Verge"],
    "VentureBeat AI": AI_NEWS["VentureBeat AI"],
    "AI News": AI_NEWS["AI News"],
    "Analytics India": AI_NEWS["Analytics India"],
    "Crunchbase News": VC_NEWS["Crunchbase News"],
    "PitchBook News": VC_NEWS["PitchBook News"],
    "a16z Newsletter": VC_NEWS["a16z Newsletter"],
    "Sequoia Insights": VC_NEWS["Sequoia Insights"],
    "Product Hunt": STARTUP_DISCOVERY["Product Hunt"],
    "Hacker News Top": STARTUP_DISCOVERY["Hacker News Top"],
    "Indie Hackers": STARTUP_DISCOVERY["Indie Hackers"],
    "Lenny's Newsletter": STARTUP_NEWSLETTERS["Lenny's Newsletter"],
    "Not Boring": STARTUP_NEWSLETTERS["Not Boring"],
    "Stratechery": STARTUP_NEWSLETTERS["Stratechery"],
    "Defense News": GOVERNMENT_DEFENSE["Defense News"],
    "Breaking Defense": GOVERNMENT_DEFENSE["Breaking Defense"],
    "Sifted (FT)": INTERNATIONAL["Sifted (FT)"],
    "Tech.eu": INTERNATIONAL["Tech.eu"],
}

X_MONITORING_QUERIES = [
    "raised funding AI",
    "billion dollar deal",
    "strategic investment AI",
    "acquires AI company",
    "venture capital AI",
    "series A series B",
    "seed round startup",
    "pre-seed funding",
    "bootstrapped SaaS",
    "indie hacker launch",
    "Product Hunt launch",
    "YC demo day",
    "startup acquired",
    "startup shutdown",
    "OpenAI funding",
    "Anthropic funding",
    "xAI investment",
    "Cursor deal",
    "Perplexity funding",
    "Cohere funding",
    "Stability AI deal",
    "Midjourney funding",
    "Microsoft AI acquisition",
    "Google AI acquisition",
    "NVIDIA AI deal",
    "Amazon AI investment",
    "Meta AI acquisition",
    "Anduril contract",
    "Palantir defense",
    "AI defense contract",
    "DARPA AI",
    "YC W25 startup",
    "YC S25 startup",
    "YC startup launch",
    "Techstars startup",
    "500 startups",
    "startup hiring spree",
    "startup layoffs",
    "startup pivot",
    "new AI tool launch",
    "AI API launch",
    "SaaS startup funding",
    "developer tools funding",
    "AI startup valuation",
    "unicorn AI startup",
    "AI startup IPO",
    "SPAC AI merger",
    "AI startup acquisition",
    "corporate venture AI",
    "sovereign AI fund",
    "AI infrastructure funding",
    "GPU startup funding",
    "AI chip startup",
    "AI agent startup funding",
    "LLM startup raise",
    "generative AI funding",
    "AI startup partnership",
    "enterprise AI deal",
    "AI startup Series C",
    "AI startup growth round",
]


def get_sources() -> dict[str, str]:
    return ALL_SOURCES


def get_priority_sources() -> dict[str, str]:
    return COMPETITOR_INTEL_SOURCES


def get_x_monitoring_queries() -> list[str]:
    return X_MONITORING_QUERIES


def print_source_summary():
    print(f"Total RSS sources: {len(ALL_SOURCES)}")
    print(f"  Tech News: {len(TECH_NEWS)}")
    print(f"  AI News: {len(AI_NEWS)}")
    print(f"  VC/PE: {len(VC_NEWS)}")
    print(f"  Startup Discovery: {len(STARTUP_DISCOVERY)}")
    print(f"  Startup Newsletters: {len(STARTUP_NEWSLETTERS)}")
    print(f"  Government/Defense: {len(GOVERNMENT_DEFENSE)}")
    print(f"  Industry: {len(INDUSTRY)}")
    print(f"  International: {len(INTERNATIONAL)}")
    print(f"Priority sources for intel: {len(COMPETITOR_INTEL_SOURCES)}")
    print(f"X/Twitter monitoring queries: {len(X_MONITORING_QUERIES)}")


if __name__ == "__main__":
    print_source_summary()
