"""
GCS Loader
----------
Uploads cleaned DataFrames to Google Cloud Storage as CSV files.

Serves as the intermediate landing zone between transformation and
BigQuery — cleaned data is persisted to GCS so it can be reloaded
into BQ without re-running the full ETL if needed.
"""

import io
from typing import Optional

import pandas as pd
from google.cloud import storage
from google.api_core.exceptions import GoogleAPIError

from etl.utils.config import settings
from etl.utils.logger import get_logger

logger = get_logger("lendwise.loader.gcs")


class GCSUploadError(Exception):
    """Raised when a GCS upload fails."""


class GCSLoader:
    """
    Uploads DataFrames to GCS as CSV files.
    """

    def __init__(self, mode: str = "cloud"):
        # Store mode and initialise GCS client only if in cloud mode.
        self.mode = mode
        self._client: Optional[storage.Client] = None

        if mode == "cloud":
            self._client = storage.Client(project=settings.project_id)
            self._bucket = self._client.bucket(settings.bucket_name)
            logger.info(
                "GCSLoader initialised | bucket=%s | prefix=%s",
                settings.bucket_name,
                settings.cleaned_prefix,
            )
        else:
            logger.info(
                "GCSLoader initialised (local mode — saves to ./data/Cleaned_Data/)"
            )

    def upload(self, df: pd.DataFrame, filename: str) -> str:
        """
        Uploads a DataFrame as a CSV to GCS (or saves locally in local mode).
        """
        if self.mode == "local":
            local_path = f"data/Cleaned_Data/{filename}"
            df.to_csv(local_path, index=False)
            logger.info(
                "[LOCAL MODE] Saved %s (%d rows) → %s", filename, len(df), local_path
            )
            return local_path

        # In cloud mode, upload to GCS with retry logic.
        gcs_path = f"{settings.cleaned_prefix}{filename}"
        gcs_uri = f"gs://{settings.bucket_name}/{gcs_path}"
        logger.info("Uploading %s (%d rows) → %s", filename, len(df), gcs_uri)

        # Convert DataFrame to CSV bytes in memory.
        try:
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_bytes = csv_buffer.getvalue().encode("utf-8")

            blob = self._bucket.blob(gcs_path)
            blob.upload_from_string(csv_bytes, content_type="text/csv")

            logger.info("Uploaded %s: %d bytes written", gcs_uri, len(csv_bytes))
            return gcs_uri

        except GoogleAPIError as exc:
            raise GCSUploadError(
                f"GCS API error uploading '{gcs_path}': {exc}"
            ) from exc
        except Exception as exc:
            raise GCSUploadError(
                f"Unexpected error uploading '{gcs_path}': {exc}"
            ) from exc
