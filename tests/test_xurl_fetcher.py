"""Unit tests for xurl_fetcher (no live xurl binary required)."""

from __future__ import annotations

import json
from pathlib import Path

from collectors.xurl_fetcher import _users_by_id, map_xurl_tweet, parse_xurl_search_payload

FIXTURE = Path(__file__).parent / "fixtures" / "xurl_search_sample.json"


def test_parse_xurl_search_sample() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    posts = parse_xurl_search_payload(payload)
    assert len(posts) == 1
    post = posts[0]
    assert post["post_id"] == "2056871280599847054"
    assert post["likes"] == 42
    assert post["retweets"] == 8
    assert post["replies"] == 3
    assert post["url"] == "https://x.com/XDevelopers/status/2056871280599847054"
    assert "https://techcrunch.com/example" in post["urls"]
    assert post["source_provider"] == "xurl"


def test_map_xurl_tweet_without_includes() -> None:
    tweet = {
        "id": "1",
        "text": "hello",
        "author_id": "99",
        "public_metrics": {"like_count": 1, "retweet_count": 0, "reply_count": 0},
    }
    post = map_xurl_tweet(tweet, {})
    assert post["url"] == "https://x.com/i/status/1"


def test_users_by_id_empty() -> None:
    assert _users_by_id({}) == {}
    assert (
        _users_by_id({"includes": {"users": [{"id": "1", "username": "a"}]}})["1"]["username"]
        == "a"
    )
