"""
BigQuery Loader
---------------
Handles writing transformed DataFrames to BigQuery.
"""

from typing import Dict, Optional

import pandas as pd
from google.cloud import bigquery
from google.api_core.exceptions import GoogleAPIError

from etl.utils.config import settings
from etl.utils.logger import get_logger

logger = get_logger("lendwise.loader.bigquery")


class LoadError(Exception):
    """Raised when a BigQuery load fails."""


class BigQueryLoader:
    """
    Loads DataFrames into BigQuery tables.

    Args:
        mode: "cloud" performs actual BQ loads. "local" skips the load
              and just logs — used for local testing without GCP credentials.
    """

    def __init__(self, mode: str = "cloud"):
        # Store mode and initialise BigQuery client only if in cloud mode.

        self.mode = mode
        self._client: Optional[bigquery.Client] = None

        if mode == "cloud":
            self._client = bigquery.Client(project=settings.project_id)
            logger.info(
                "BigQueryLoader initialised | project=%s | dataset=%s",
                settings.project_id,
                settings.dataset_id,
            )
        else:
            logger.info("BigQueryLoader initialised (local mode — loads skipped)")

    def load(self, df: pd.DataFrame, table_name: str) -> int:

        # Loads a DataFrame into a BigQuery table.

        if self.mode == "local":
            logger.info(
                "[LOCAL MODE] Skipping BigQuery load for: %s (%d rows)",
                table_name,
                len(df),
            )
            return 0

        table_id = f"{settings.project_id}.{settings.dataset_id}.{table_name}"
        logger.info("Loading %s → %s (%d rows)", table_name, table_id, len(df))

        # Configure the load job to overwrite the table and auto-detect the schema.
        job_config = bigquery.LoadJobConfig(
            write_disposition=settings.bq_write_disposition,
            autodetect=True,  # Infer schema from the DataFrame
        )

        # Implementing retry logic for transient errors.
        try:
            job = self._client.load_table_from_dataframe(
                df, table_id, job_config=job_config
            )
            job.result()  # Block until the job completes

            # Verify by reading the row count back from BQ
            table = self._client.get_table(table_id)
            rows_written = table.num_rows
            logger.info("Loaded %s: %d rows in BigQuery", table_name, rows_written)
            return rows_written

        except GoogleAPIError as exc:
            raise LoadError(
                f"BigQuery API error loading '{table_name}': {exc}"
            ) from exc
        except Exception as exc:
            raise LoadError(f"Unexpected error loading '{table_name}': {exc}") from exc

    def load_all(self, tables: Dict[str, pd.DataFrame]) -> Dict[str, int]:
        """
        Loads multiple tables. Continues on failure and reports all errors
        at the end, rather than stopping at the first one.
        """

        row_counts: Dict[str, int] = {}
        errors: list = []

        for table_name, df in tables.items():
            try:
                row_counts[table_name] = self.load(df, table_name)
            except LoadError as exc:
                logger.error("Failed to load '%s': %s", table_name, exc)
                errors.append(str(exc))

        if errors:
            raise LoadError(
                f"{len(errors)} table(s) failed to load:\n" + "\n".join(errors)
            )

        return row_counts
