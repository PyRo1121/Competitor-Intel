"""
Lightweight Ollama HTTP client (localhost:11434).

Use only for embedding/rerank. Do not call generate() for X ingest or funding
extraction — use Grok/xAI (see grok_x_fetcher.py).
"""

import logging
import os

from utils.http import post_json

logger = logging.getLogger("ollama_client")


def _ollama_base() -> str:
    host = os.getenv("CI_OLLAMA_HOST") or os.getenv("OLLAMA_HOST", "http://localhost:11434")
    return host.rstrip("/")


OLLAMA_BASE = _ollama_base()
OLLAMA_GENERATE_URL = f"{OLLAMA_BASE}/api/generate"


def generate(
    prompt: str,
    model: str = "qwen3.5:9b",
    temperature: float = 0.1,
    num_predict: int = 350,
) -> str | None:
    """Generate text using the local Ollama /api/generate endpoint."""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": num_predict,
        },
    }

    data = post_json(OLLAMA_GENERATE_URL, payload, timeout=120.0)
    if data is None:
        logger.error("Ollama not reachable at %s", OLLAMA_BASE)
        return None
    return data.get("response", "")
