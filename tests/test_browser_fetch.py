"""Browser fetch helpers (challenge detection, enable flag)."""

from __future__ import annotations

from utils import browser_fetch as bf


def test_challenge_detection_cloudflare_interstitial():
    html = """
    <html><head><title>Just a moment...</title></head>
    <body>Enable JavaScript and cookies to continue. Ray ID: abc. challenge-platform</body>
    </html>
    """
    assert bf._looks_like_challenge_page(html) is True


def test_challenge_detection_real_page():
    html = "<html><body>" + ("x" * 6000) + "<h1>About our team</h1></body></html>"
    assert bf._looks_like_challenge_page(html) is False


def test_fetch_disabled_returns_none(monkeypatch):
    monkeypatch.setenv("CI_BROWSER_FETCH", "0")
    assert bf.fetch_browser_text("https://example.com") is None


def test_fetch_uses_curl_cffi(monkeypatch):
    import sys
    import types
    from typing import Any

    monkeypatch.setenv("CI_BROWSER_FETCH", "1")
    monkeypatch.setenv("CI_SCRAPE_DELAY_SEC", "0")

    class FakeResp:
        status_code = 200
        text = "<html><body>" + "ok " * 2000 + "</body></html>"

    requests_mod: Any = types.ModuleType("curl_cffi.requests")

    def fake_get(*_a, **_k):
        return FakeResp()

    requests_mod.get = fake_get
    pkg: Any = types.ModuleType("curl_cffi")
    pkg.requests = requests_mod
    monkeypatch.setitem(sys.modules, "curl_cffi", pkg)
    monkeypatch.setitem(sys.modules, "curl_cffi.requests", requests_mod)

    html = bf.fetch_browser_text("https://example.com/about")
    assert html is not None
    assert "ok" in html
