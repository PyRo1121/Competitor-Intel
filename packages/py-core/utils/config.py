"""Centralized configuration management."""

import os
from pathlib import Path
from typing import Any

import yaml

from ci_paths import CONFIG_DIR, db_path


def get_config() -> dict[str, Any]:
    """Load configuration from files and environment."""
    config: dict[str, Any] = {
        "db_path": str(db_path()),
        "github_token": os.getenv("GITHUB_TOKEN"),
        "discord_webhook": os.getenv("DISCORD_WEBHOOK_URL"),
        "ollama_model": os.getenv("CI_OLLAMA_MODEL", "qwen3-embedding:4b"),
        "sec_user_agent": os.getenv("CI_SEC_USER_AGENT", "Competitor-Intel/2.1"),
        "rate_limits": {
            "github": 60,
            "sec": 10,
            "rss": 1,
        },
    }

    competitors_file = CONFIG_DIR / "competitors.yaml"
    if competitors_file.exists():
        with open(competitors_file) as f:
            data = yaml.safe_load(f)
            config["competitors"] = data.get("competitors", [])

    return config
