"""URL fanout from social signals to article raw_signals."""

import json
import sqlite3

import pytest
from collectors.signal_url_fanout import (
    extract_outbound_urls,
    fanout_one_signal,
    should_skip_url,
)
from db.migrations import apply_runtime_migrations


@pytest.mark.parametrize(
    "url,skip",
    [
        ("https://x.com/foo/status/1", True),
        ("https://techcrunch.com/2024/startup-raises/", False),
    ],
)
def test_should_skip_url(url: str, skip: bool) -> None:
    assert should_skip_url(url) is skip


def test_extract_outbound_urls_from_x_payload() -> None:
    data = {
        "text": "Big round https://techcrunch.com/deal and https://x.com/foo",
        "urls": ["https://venturebeat.com/story"],
        "url": "https://x.com/foo/status/99",
        "kind": "x_social",
    }
    urls = extract_outbound_urls(data)
    assert "https://techcrunch.com/deal" in urls
    assert "https://venturebeat.com/story" in urls
    assert not any("x.com" in u for u in urls)


def test_fanout_inserts_article_signal(operational_db) -> None:
    conn = sqlite3.connect(operational_db)
    apply_runtime_migrations(conn)
    cur = conn.cursor()
    payload = {
        "text": "Startup raised $10M led by Sequoia https://techcrunch.com/round",
        "urls": ["https://techcrunch.com/round"],
        "url": "https://x.com/a/status/1",
        "kind": "x_social",
    }
    cur.execute(
        """
        INSERT INTO raw_signals (company_id, source, signal_type, data_json, detected_at, processed)
        VALUES (NULL, 'x', 'x:test', ?, datetime('now'), 0)
        """,
        (json.dumps(payload),),
    )
    sid = cur.lastrowid
    assert sid is not None
    conn.commit()

    n = fanout_one_signal(cur, int(sid), "x", None, payload)
    conn.commit()

    assert n == 1
    cur.execute("SELECT source, data_json FROM raw_signals WHERE source = 'article'")
    row = cur.fetchone()
    assert row is not None
    article = json.loads(row[1])
    assert article["url"] == "https://techcrunch.com/round"
    assert article["discovered_via"] == "x"
    conn.close()
