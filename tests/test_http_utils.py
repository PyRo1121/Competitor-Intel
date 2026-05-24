"""HTTP helper tests (retries, JSON POST)."""

from __future__ import annotations

import httpx
import pytest
import respx
from utils import http as http_utils


@pytest.fixture(autouse=True)
def reset_http_client():
    http_utils.close_http_client()
    yield
    http_utils.close_http_client()


@pytest.mark.operational
@respx.mock
def test_safe_request_succeeds():
    respx.get("https://example.com/feed").mock(return_value=httpx.Response(200, text="<rss/>"))
    resp = http_utils.safe_request("https://example.com/feed")
    assert resp is not None
    assert resp.text == "<rss/>"


@pytest.mark.operational
@respx.mock
def test_safe_request_retries_then_fails():
    route = respx.get("https://example.com/fail").mock(return_value=httpx.Response(503))
    assert http_utils.safe_request("https://example.com/fail", timeout=1.0) is None
    assert route.call_count == http_utils.MAX_RETRIES


@pytest.mark.operational
@respx.mock
def test_post_json_parses_body():
    respx.post("https://ollama.example/api/embed").mock(
        return_value=httpx.Response(200, json={"embeddings": [[0.1, 0.2]]})
    )
    data = http_utils.post_json("https://ollama.example/api/embed", {"model": "x", "input": "hi"})
    assert data == {"embeddings": [[0.1, 0.2]]}


@pytest.mark.operational
@respx.mock
def test_fetch_text_returns_none_on_failure():
    respx.get("https://example.com/missing").mock(return_value=httpx.Response(404))
    assert http_utils.fetch_text("https://example.com/missing", timeout=1.0) is None


@pytest.mark.operational
@respx.mock
def test_post_json_handles_errors():
    respx.post("https://ollama.example/timeout").mock(side_effect=httpx.TimeoutException("slow"))
    assert http_utils.post_json("https://ollama.example/timeout", {"x": 1}, timeout=0.1) is None

    respx.post("https://ollama.example/badjson").mock(
        return_value=httpx.Response(200, content=b"not-json")
    )
    assert http_utils.post_json("https://ollama.example/badjson", {"x": 1}) is None
