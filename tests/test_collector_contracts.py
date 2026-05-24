"""HTTP contract tests for priority ingest collectors (P3-5, respx)."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import respx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "py-core"))
sys.path.insert(0, str(ROOT / "packages" / "py-collectors"))

from collectors.hackernews_collector import fetch_story, fetch_story_ids  # noqa: E402
from collectors.signal_text import extract_company_mentions  # noqa: E402
from utils.http import fetch_text  # noqa: E402

SAMPLE_RSS = """<?xml version="1.0"?>
<rss><channel><item>
<title>Acme Corp raises Series B</title>
<link>https://example.com/acme-series-b</link>
<description>Acme Corp announced funding today.</description>
</item></channel></rss>"""


@respx.mock
def test_fetch_text_rss_contract():
    respx.get("https://feeds.example.com/tech.xml").mock(
        return_value=httpx.Response(200, text=SAMPLE_RSS)
    )
    body = fetch_text("https://feeds.example.com/tech.xml", timeout=5.0)
    assert body is not None
    assert "Acme Corp" in body


@respx.mock
def test_hackernews_story_ids_contract():
    respx.get("https://hacker-news.firebaseio.com/v0/topstories.json").mock(
        return_value=httpx.Response(200, json=[1, 2, 3])
    )
    ids = fetch_story_ids("https://hacker-news.firebaseio.com/v0/topstories.json", limit=2)
    assert ids == [1, 2]


@respx.mock
def test_hackernews_story_item_contract():
    payload = {
        "id": 1,
        "type": "story",
        "title": "Show HN: Demo",
        "url": "https://example.com",
        "by": "user",
        "score": 10,
        "descendants": 0,
    }
    respx.get("https://hacker-news.firebaseio.com/v0/item/1.json").mock(
        return_value=httpx.Response(200, json=payload)
    )
    story = fetch_story(1)
    assert story.get("title") == "Show HN: Demo"


def test_rss_company_mention_extraction():
    mentions = extract_company_mentions(
        "Acme Corp raises $10M from Beta Ventures",
        ["Acme Corp", "OtherCo"],
    )
    assert "Acme Corp" in mentions


@respx.mock
def test_rss_parse_feed_body_contract():
    from collectors.rss_collector import parse_feed_body

    entries = parse_feed_body(SAMPLE_RSS, "Test Feed", "vc", ["Acme Corp"])
    assert len(entries) == 1
    assert entries[0]["title"] == "Acme Corp raises Series B"
    assert "Acme Corp" in entries[0]["mentioned_companies"]


@respx.mock
def test_rss_fetch_and_parse_feed_contract():
    from collectors.rss_collector import fetch_and_parse_feed

    respx.get("https://feeds.example.com/t.xml").mock(
        return_value=httpx.Response(200, text=SAMPLE_RSS)
    )
    name, entries = fetch_and_parse_feed(
        {"name": "Test", "url": "https://feeds.example.com/t.xml", "category": "vc"},
        ["Acme Corp"],
    )
    assert name == "Test"
    assert entries[0]["link"] == "https://example.com/acme-series-b"
