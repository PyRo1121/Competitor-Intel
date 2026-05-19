"""Centralized configuration management."""
import os
import yaml
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).parent.parent


def get_config():
    """Load configuration from files and environment."""
    config = {
        "db_path": os.getenv("CI_DB_PATH", str(BASE_DIR / "competitor_intel.db")),
        "github_token": os.getenv("GITHUB_TOKEN"),
        "discord_webhook": os.getenv("DISCORD_WEBHOOK_URL"),
        "ollama_model": os.getenv("CI_OLLAMA_MODEL", "qwen3-embedding:4b"),
        "sec_user_agent": os.getenv("CI_SEC_USER_AGENT", "Hermes-Intel/1.0"),
        "rate_limits": {
            "github": 60,  # requests per hour (unauthenticated)
            "sec": 10,     # requests per second
            "rss": 1,      # seconds between requests
        }
    }
    
    # Load competitor list
    competitors_file = BASE_DIR / "config" / "competitors.yaml"
    if competitors_file.exists():
        with open(competitors_file) as f:
            data = yaml.safe_load(f)
            config["competitors"] = data.get("competitors", [])
    
    return config
