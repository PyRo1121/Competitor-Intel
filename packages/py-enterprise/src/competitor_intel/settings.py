"""Application settings with validation."""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database configuration."""
    
    model_config = SettingsConfigDict(env_prefix="CI_DB_")
    
    path: Path = Field(
        default=Path(__file__).resolve().parents[4] / "data" / "competitor_intel.db"
    )
    echo: bool = Field(default=False)
    pool_size: int = Field(default=5)
    max_overflow: int = Field(default=10)
    
    @field_validator("path")
    @classmethod
    def ensure_parent_exists(cls, v: Path) -> Path:
        v.parent.mkdir(parents=True, exist_ok=True)
        return v


class RateLimitSettings(BaseSettings):
    """Rate limiting configuration."""
    
    model_config = SettingsConfigDict(env_prefix="CI_RATE_")
    
    github_requests_per_hour: int = Field(default=60)
    github_token: Optional[str] = Field(default=None)
    sec_requests_per_second: int = Field(default=10)
    sec_user_agent: str = Field(default="Hermes-Intel/2.0 contact@example.com")
    rss_delay_seconds: float = Field(default=1.0)
    default_timeout: int = Field(default=30)


class DiscordSettings(BaseSettings):
    """Discord webhook configuration."""
    
    model_config = SettingsConfigDict(env_prefix="DISCORD_")
    
    webhook_url: Optional[str] = Field(default=None)
    timeout: int = Field(default=10)


class OllamaSettings(BaseSettings):
    """Ollama LLM configuration."""
    
    model_config = SettingsConfigDict(env_prefix="CI_OLLAMA_")
    
    host: str = Field(default="http://localhost:11434")
    model: str = Field(default="qwen3-embedding:4b")
    timeout: int = Field(default=60)


class CollectorSettings(BaseSettings):
    """Collector-specific settings."""
    
    model_config = SettingsConfigDict(env_prefix="CI_COLLECTOR_")
    
    max_concurrent: int = Field(default=5)
    batch_size: int = Field(default=100)
    dedup_window_days: int = Field(default=30)


class Settings(BaseSettings):
    """Application settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    app_name: str = Field(default="competitor-intel")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    
    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    discord: DiscordSettings = Field(default_factory=DiscordSettings)
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    collector: CollectorSettings = Field(default_factory=CollectorSettings)
    
    # Data paths
    config_dir: Path = Field(default=Path(__file__).parent.parent / "config")
    exports_dir: Path = Field(default=Path(__file__).parent.parent / "exports")
    obsidian_dir: Path = Field(default=Path.home() / "Obsidian/Competitor Intelligence")
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v.upper()
    
    @field_validator("exports_dir", "obsidian_dir")
    @classmethod
    def ensure_dir_exists(cls, v: Path) -> Path:
        v.mkdir(parents=True, exist_ok=True)
        return v


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
