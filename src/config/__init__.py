"""Configuration management for experiments.

Provides a ``Settings`` singleton accessible via ``get_settings()``
that reads from environment variables and an optional YAML config file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional


class ConfigurationError(Exception):
    """Raised when a required configuration value is missing."""
    pass


# ─── Sub-configs ──────────────────────────────────────────────────────


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    format: str = "text"  # "text" (rich) or "json"


@dataclass
class DatabaseConfig:
    """Database connection settings."""
    url: str = ""
    pool_size: int = 5


@dataclass
class WandbConfig:
    """Weights & Biases settings."""
    project: str = "llm-quant-lab"
    entity: str = ""
    enabled: bool = True


@dataclass
class Settings:
    """Application-wide settings.

    Values are resolved from environment variables with sensible defaults.
    """
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    wandb: WandbConfig = field(default_factory=WandbConfig)

    def setup_environment(self) -> None:
        """Push key settings into environment variables so downstream
        code that reads ``os.getenv`` finds them."""
        if self.database.url:
            os.environ.setdefault("DATABASE_URL", self.database.url)

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from environment variables.

        Critical variables (database, W&B, LLM) must be set explicitly
        in the environment — they will fail fast at point of use.

        Non-critical variables (logging, pool sizes) that only affect
        operational behaviour raise warnings when missing.
        """
        import warnings

        db_url = get_database_url_optional()

        log_level = os.getenv("LOG_LEVEL")
        if not log_level:
            warnings.warn(
                "LOG_LEVEL is not set — defaulting is disabled. "
                "Set LOG_LEVEL in your .env file.",
                stacklevel=2,
            )
            raise ConfigurationError("LOG_LEVEL is not set. Set it in your .env file.")

        log_format = os.getenv("LOG_FORMAT")
        if not log_format:
            raise ConfigurationError("LOG_FORMAT is not set. Set it in your .env file.")

        wandb_project = os.getenv("WANDB_PROJECT")
        if not wandb_project:
            raise ConfigurationError("WANDB_PROJECT is not set. Set it in your .env file.")

        return cls(
            logging=LoggingConfig(
                level=log_level.upper(),
                format=log_format,
            ),
            database=DatabaseConfig(
                url=db_url,
                pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
            ),
            wandb=WandbConfig(
                project=wandb_project,
                entity=os.getenv("WANDB_ENTITY", ""),
                enabled=os.getenv("WANDB_DISABLED", "").lower() not in ("1", "true"),
            ),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the application settings singleton."""
    return Settings.from_env()


# ─── Database URL helpers ─────────────────────────────────────────────


def get_database_url_optional() -> str:
    """Return the database URL, or empty string if not configured.

    Unlike ``get_database_url`` this will NOT raise; it is used during
    settings construction so we can still run without a DB.

    Resolution order:
        1. ``DATABASE_URL`` environment variable (preferred)
        2. Constructed from ``POSTGRES_*`` variables (all must be set)
        3. Empty string (no database configured)
    """
    url = os.getenv("DATABASE_URL")
    if url:
        return url

    password = os.getenv("POSTGRES_PASSWORD", "")
    if not password:
        return ""

    # If POSTGRES_PASSWORD is set, all other POSTGRES_* vars are required
    user = os.getenv("POSTGRES_USER")
    host = os.getenv("POSTGRES_HOST")
    port = os.getenv("POSTGRES_PORT")
    db = os.getenv("POSTGRES_DB")

    missing = []
    if not user:
        missing.append("POSTGRES_USER")
    if not host:
        missing.append("POSTGRES_HOST")
    if not port:
        missing.append("POSTGRES_PORT")
    if not db:
        missing.append("POSTGRES_DB")
    if missing:
        raise ConfigurationError(
            f"POSTGRES_PASSWORD is set but the following required variables are missing: "
            f"{', '.join(missing)}.  Set them in your .env file or use DATABASE_URL instead."
        )

    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def get_database_url() -> str:
    """Build the database URL from individual environment variables.

    Falls back to DATABASE_URL if set, otherwise constructs from
    POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB.

    Raises:
        ConfigurationError: If no database configuration is available.
    """
    url = get_database_url_optional()
    if url:
        return url

    raise ConfigurationError(
        "No DATABASE_URL or POSTGRES_PASSWORD set. "
        "Please configure database connection via environment variables."
    )
