"""
GCS Extractor
-------------
Pulls raw CSV files from Google Cloud Storage.
"""

import io
import time
from typing import Dict

import great_expectations as ge
import pandas as pd
from google.api_core.exceptions import GoogleAPIError, NotFound
from google.cloud import storage

from etl.utils.config import settings
from etl.utils.logger import get_logger

logger = get_logger("lendwise.extractor")


class ExtractionError(Exception):
    """Raised when a source file can't be retrieved after all retries."""


class GCSExtractor:
    """
    Reads CSV files from GCS (or from local disk in local mode).

    Args:
        mode: "cloud" reads from GCS. "local" reads from ./data/Raw_Data/
                Using local mode during development to avoid needing GCP credentials.
    """

    def __init__(self, mode: str = "cloud"):
        self.mode = mode
        self._client = None

        # To only initialise GCS client if we're in cloud mode.
        if mode == "cloud":
            self._client = storage.Client(project=settings.project_id)
            self._bucket = self._client.bucket(settings.bucket_name)
            logger.info(
                "GCSExtractor initialised (cloud mode) | bucket=%s",
                settings.bucket_name,
            )
        else:
            logger.info("GCSExtractor initialised (local mode)")

    def read_csv(self, filename: str) -> pd.DataFrame:
        """
        Reads a single CSV file and returns it as a DataFrame.

        In cloud mode, downloads from GCS with retry logic.
        In local mode, reads from ./data/Raw_Data/<filename>.
        """
        if self.mode == "local":
            local_path = f"data/Raw_Data/{filename}"
            logger.info("LOCAL MODE — reading from %s", local_path)

            df = pd.read_csv(local_path, low_memory=False)
            return df

    def read_all_sources(self) -> Dict[str, pd.DataFrame]:
        """
        Downloads every configured source file in one call.
        Returns a dict keyed by source name (e.g. "loan_applications").
        """
        datasets: Dict[str, pd.DataFrame] = {}
        for name, filename in settings.source_files.items():
            logger.info("Extracting source: %s (%s)", name, filename)
            datasets[name] = self.read_csv(filename)
            logger.info("Loaded %s: %d rows, %d columns", name, *datasets[name].shape)
        return datasets

    def _download_with_retry(self, gcs_path: str) -> pd.DataFrame:
        """
        Downloads a blob from GCS with exponential backoff.
        Raises ExtractionError if every attempt fails.
        """
        last_error: Exception = RuntimeError("No attempts made")

        for attempt in range(1, settings.max_retries + 1):
            try:
                blob = self._bucket.blob(gcs_path)

                if not blob.exists():
                    raise ExtractionError(
                        f"File not found in GCS: gs://{settings.bucket_name}/{gcs_path}\n"
                        "Check that the raw data has been uploaded to the correct bucket path."
                    )

                raw_bytes = blob.download_as_bytes()
                df = pd.read_csv(io.BytesIO(raw_bytes), low_memory=False)
                logger.debug(
                    "Downloaded gs://%s/%s (%d bytes)",
                    settings.bucket_name,
                    gcs_path,
                    len(raw_bytes),
                )
                return df

            except ExtractionError:
                raise
            # Catch both GoogleAPIError for GCS issues and a general Exception to cover unexpected errors.

            except (GoogleAPIError, Exception) as exc:
                last_error = exc
                wait = settings.retry_delay_seconds * (
                    2 ** (attempt - 1)
                )  # Exponential backoff
                logger.warning(
                    "Attempt %d/%d failed for %s: %s. Retrying in %.1fs...",
                    attempt,
                    settings.max_retries,
                    gcs_path,
                    exc,
                    wait,
                )
                # Only sleep if we're going to retry again.
                if attempt < settings.max_retries:
                    time.sleep(wait)

        # If all attempts failed
        raise ExtractionError(
            f"Failed to download gs://{settings.bucket_name}/{gcs_path} "
            f"after {settings.max_retries} attempts. Last error: {last_error}"
        )
