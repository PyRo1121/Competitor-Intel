"""
Lightweight Ollama API client
Uses HTTP API to bare-metal Ollama (localhost:11434)
No pip dependency needed.
"""

import logging
import os
from typing import Optional

from utils.http import post_json

logger = logging.getLogger("ollama_client")

OLLAMA_BASE = os.getenv("CI_OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_GENERATE_URL = f"{OLLAMA_BASE}/api/generate"


def generate(
    prompt: str,
    model: str = "qwen3.5:9b",
    temperature: float = 0.1,
    num_predict: int = 350,
) -> Optional[str]:
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
