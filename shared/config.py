"""
shared/config.py
----------------
Loads all configuration from environment variables.
Never import os.getenv() anywhere else — always use `settings` from here.

Usage:
    from shared.config import settings
    print(settings.gemini_api_key)
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Immutable app settings. Built once at import time."""
    gemini_api_key: str
    app_env: str
    log_level: str
    max_file_size_mb: int
    data_retention_days: int


def _require(var: str) -> str:
    """Raise a clear error if a required env var is missing."""
    value = os.getenv(var)
    if not value:
        raise EnvironmentError(
            f"Required env var '{var}' is not set. "
            "Copy .env.example to .env and fill in the value."
        )
    return value


settings = Settings(
    gemini_api_key=_require("GEMINI_API_KEY"),
    app_env=os.getenv("APP_ENV", "development"),
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    max_file_size_mb=int(os.getenv("MAX_FILE_SIZE_MB", "10")),
    data_retention_days=int(os.getenv("DATA_RETENTION_DAYS", "0")),
)
