"""
ETL Pipeline

Design principle: each step fails loudly so that we can get a clear error message
at step 2 than silently load half-transformed data into BigQuery.
"""

import time
from datetime import datetime, timezone
from typing import Optional

from etl.extract.gcs_extractor import GCSExtractor
from etl.transform.loan_applications import LoanApplicationsTransformer
from etl.transform.loan_repayments import LoanRepaymentsTransformer
from etl.transform.credit_bureau import CreditBureauTransformer
from etl.load.gcs_loader import GCSLoader
from etl.load.bigquery_loader import BigQueryLoader
from etl.utils.validators import (
    validate_loan_applications,
    validate_loan_repayments,
    validate_credit_bureau,
    validate_fact_loans,
    ValidationError,
)
from etl.utils.logger import get_logger
from metrics import Metrics

logger = get_logger("lendwise.pipeline")


class ETLPipeline:     # Orchestrates the full LendWise ETL run.
    

    def __init__(self, mode: str = "cloud"):
        # Store mode and generate a unique run ID for this execution.
        
        self.mode = mode
        self.run_id = f"lendwise-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

        logger.info("ETLPipeline initialised | run_id=%s | mode=%s", self.run_id, mode)

        # Wire up components
        self.extractor   = GCSExtractor(mode=mode)
        self.gcs_loader  = GCSLoader(mode=mode)
        self.bq_loader   = BigQueryLoader(mode=mode)

        # Transformers
        self.loan_t   = LoanApplicationsTransformer()
        self.repay_t  = LoanRepaymentsTransformer()
        self.credit_t = CreditBureauTransformer()

    @Metrics.time_execution
    def run(self, dry_run: bool = False) -> dict:
        # Executes the full pipeline end-to-end.

        start = time.monotonic()
        logger.info("=== LendWise ETL run started | run_id=%s ===", self.run_id)

        # Extract 
        logger.info("Step 1/5 — Extracting raw data")
        raw = self.extractor.read_all_sources()
        Metrics.log_row_counts(raw)

        # Transform
        logger.info("Step 2/5 — Transforming data")

        loans_clean     = self.loan_t.clean(raw["loan_applications"])
        repayments_clean = self.repay_t.clean(raw["loan_repayments"])
        credit_clean    = self.credit_t.clean(raw["credit_bureau"])

        applicant_dim   = self.loan_t.build_applicant_dim(loans_clean)
        employment_dim  = self.loan_t.build_employment_dim(loans_clean)
        contact_dim     = self.loan_t.build_contact_info_dim(loans_clean)
        nok_dim         = self.loan_t.build_next_of_kin_dim(loans_clean)
        fact_loans      = self.loan_t.build_fact_table(loans_clean, applicant_dim)

        # Validate 
        logger.info("Step 3/5 — Running data quality validation")
        try:
            validate_loan_applications(loans_clean)
            validate_loan_repayments(repayments_clean)
            validate_credit_bureau(credit_clean)
            validate_fact_loans(fact_loans)
        except ValidationError as exc:
            logger.error("Quality gate FAILED — aborting pipeline: %s", exc)
            raise

        # Load to GCS
        if dry_run:
            logger.info("Step 4/5 — DRY RUN: skipping GCS upload")
        else:
            logger.info("Step 4/5 — Uploading cleaned data to GCS")
            self.gcs_loader.upload(fact_loans,       "fact_loans.csv")
            self.gcs_loader.upload(applicant_dim,    "dim_applicants.csv")
            self.gcs_loader.upload(employment_dim,   "dim_employment.csv")
            self.gcs_loader.upload(contact_dim,      "dim_contact_info.csv")
            self.gcs_loader.upload(nok_dim,          "dim_next_of_kin.csv")
            self.gcs_loader.upload(repayments_clean, "fact_repayments.csv")
            self.gcs_loader.upload(credit_clean,     "dim_credit_bureau.csv")

        # Load to BigQuery 
        if dry_run:
            logger.info("Step 5/5 — DRY RUN: skipping BigQuery load")
            row_counts = {name: len(df) for name, df in {
                "fact_loans":        fact_loans,
                "dim_applicants":    applicant_dim,
                "dim_employment":    employment_dim,
                "dim_contact_info":  contact_dim,
                "dim_next_of_kin":   nok_dim,
                "fact_repayments":   repayments_clean,
                "dim_credit_bureau": credit_clean,
            }.items()}
        else:
            logger.info("Step 5/5 — Loading to BigQuery")
            row_counts = self.bq_loader.load_all({
                "fact_loans":        fact_loans,
                "dim_applicants":    applicant_dim,
                "dim_employment":    employment_dim,
                "dim_contact_info":  contact_dim,
                "dim_next_of_kin":   nok_dim,
                "fact_repayments":   repayments_clean,
                "dim_credit_bureau": credit_clean,
            })

        # Summary 
        elapsed = round(time.monotonic() - start, 2)
        result = {
            "status":          "success",
            "run_id":          self.run_id,
            "mode":            self.mode,
            "dry_run":         dry_run,
            "elapsed_seconds": elapsed,
            "tables_loaded":   row_counts,
        }
        logger.info("=== Pipeline complete | run_id=%s | elapsed=%.2fs ===", self.run_id, elapsed)
        logger.info("Tables loaded: %s", row_counts)
        return result

# Entry point for running the pipeline directly.
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--mode", choices=["local", "cloud"], default="local")
    args = parser.parse_args()

    pipeline = ETLPipeline(mode=args.mode)
    result = pipeline.run(dry_run=args.dry_run)

    for key, val in result.items():
        logger.info("%s: %s", key, val)