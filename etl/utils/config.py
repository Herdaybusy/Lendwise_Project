"""
Configuration
"""

import os
from dotenv import load_dotenv
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

# Variables that MUST be present — no defaults, no silent fallback
_REQUIRED = ("GCP_PROJECT", "BUCKET_NAME", "BQ_DATASET")

load_dotenv()  # Load .env file in local dev; in cloud


@dataclass(frozen=True)
class Settings:
    """Immutable config. Built once at startup, shared everywhere."""

    # GCP identifiers
    project_id: str
    bucket_name: str
    dataset_id: str

    # GCS path prefixes
    raw_prefix: str = "Raw_Data/"
    cleaned_prefix: str = "Cleaned_Data/"

    # BigQuery load settings
    bq_write_disposition: str = "WRITE_TRUNCATE"

    # Retry settings for GCS reads
    max_retries: int = 3
    retry_delay_seconds: float = 2.0

    # Source file names — override via env if your filenames differ
    source_files: dict = field(
        default_factory=lambda: {
            "loan_applications": "loan_applications.csv",
            "loan_repayments": "loan_repayments.csv",
            "credit_bureau": "credit_bureau_data.csv",
        }
    )

    # Run mode: "local" skips GCS/BQ and uses local CSV files
    run_mode: str = "cloud"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Build and cache the Settings object. Called once — subsequent calls
    return the same instance.

    Raises EnvironmentError with a clear message if required vars are missing.
    """
    missing = [var for var in _REQUIRED if not os.environ.get(var)]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            "Copy .env.example to .env and fill in your GCP project details."
        )

    return Settings(
        project_id=os.environ["GCP_PROJECT"],
        bucket_name=os.environ["BUCKET_NAME"],
        dataset_id=os.environ["BQ_DATASET"],
        raw_prefix=os.environ.get("RAW_PREFIX", "Raw_Data/"),
        cleaned_prefix=os.environ.get("CLEANED_PREFIX", "Cleaned_Data/"),
        bq_write_disposition=os.environ.get("BQ_WRITE_DISPOSITION", "WRITE_TRUNCATE"),
        max_retries=int(os.environ.get("MAX_RETRIES", "3")),
        retry_delay_seconds=float(os.environ.get("RETRY_DELAY_SECONDS", "2.0")),
        run_mode=os.environ.get("RUN_MODE", "cloud"),
    )


# Module-level settings instance. Access via `from etl.utils.config import settings`.
def _get_settings_lazy() -> Settings:
    return get_settings()


settings: Settings = None  # type: ignore  # populated on first access via __getattr__ trick


class _LazySettings:
    """Defers Settings construction until first attribute access."""

    def __getattr__(self, name):
        global settings
        s = get_settings()

        # Cache onto the module-level name so future accesses are direct
        import sys

        sys.modules[__name__].settings = s
        return getattr(s, name)


# Initialize the lazy settings proxy.
settings = _LazySettings()  # type: ignore
