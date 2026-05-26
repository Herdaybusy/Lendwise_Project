"""
Loan Repayments Transformer
---------------------------
Cleans repayment data and prepares it for analytics and reporting.
Focus is on clarity, not over-engineering.
"""

import pandas as pd
from etl.utils.logger import get_logger

logger = get_logger("lendwise.transform.loan_repayments")


class LoanRepaymentsTransformer:

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        logger.info("Cleaning loan repayments: %d rows", len(df))

        df = df.copy()

        # Standardise column names
        df.columns = (
            df.columns
            .str.strip()
            .str.lower()
            .str.replace(r"[\s\-\(\)]+", "_", regex=True)
            .str.strip("_")
        )

        # Remove duplicates
        df = df.drop_duplicates()

        # Identify the key ID column (application_id or loan_application_id) and ensure it exists.
        id_col = "loan_application_id" if "loan_application_id" in df.columns else "application_id"

        if id_col not in df.columns:
            raise KeyError(f"Missing required column: {id_col}")

        # Drop rows without key fields
        df = df.dropna(subset=[id_col, "repayment_date"])

        # Convert date safely
        df["repayment_date"] = pd.to_datetime(df["repayment_date"], errors="coerce")

        # Convert amounts safely
        if "amount_paid_usd" in df.columns:
            df["amount_paid_usd"] = pd.to_numeric(df["amount_paid_usd"], errors="coerce")

        # Ensure days_overdue exists
        if "days_overdue" in df.columns:
            df["days_overdue"] = pd.to_numeric(df["days_overdue"], errors="coerce").fillna(0)

            df["is_delinquent"] = df["days_overdue"] > 30
        else:
            df["is_delinquent"] = False

        # Future date check
        df["is_future_dated"] = df["repayment_date"] > pd.Timestamp.now()

        if df["is_future_dated"].any():
            logger.warning(
                "%d records have future repayment dates",
                df["is_future_dated"].sum()
            )

        logger.info("Finished cleaning repayments: %d rows", len(df))
        return df