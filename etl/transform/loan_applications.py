"""
Loan Applications Transformer
------------------------------
Cleans raw loan application data and builds the star schema
dimension and fact tables.

"""

import hashlib
import re
from typing import Tuple

import numpy as np
import pandas as pd

from etl.utils.logger import get_logger

logger = get_logger("lendwise.transform.loan_applications")


class LoanApplicationsTransformer:
    # Transformer for loan applications data. Cleans the raw source and builds the dimension and fact tables.
    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Cleans the raw loan applications CSV.
        """
        logger.info("Cleaning loan applications: %d rows", len(df))

        # Make a copy to avoid modifying the original DataFrame
        df = df.copy()

        # 1. Normalise column names
        df.columns = self._normalise_columns(df.columns)

        # 2. Drop duplicates
        df = df.drop_duplicates()

        # 3. Drop only rows missing the anchor key
        before = len(df)
        df = df.dropna(subset=["application_id"])
        dropped = before - len(df)

        if dropped:
            logger.warning("Dropped %d rows with null application_id", dropped)

        # 4. Date parsing
        for col in ["application_date", "applicant_date_of_birth"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")

        # 5. Numeric columns
        for col in [
            "loan_amount_requested_usd",
            "monthly_income_usd",
            "annual_income_usd",
        ]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # 6. strip everything except digits and leading +
        for col in ["applicant_phone_number"]:
            if col in df.columns:
                df[col] = df[col].apply(self._clean_phone)

        logger.info("Cleaned loan applications: %d rows retained", len(df))
        return df

    def build_applicant_dim(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Builds the applicant dimension table.
        """
        logger.info("Building applicant dimension table")

        # Only keep relevant columns for the dimension, and drop duplicates to get unique applicants.
        cols = [
            "applicant_ssn",
            "applicant_full_name",
            "applicant_date_of_birth",
            "applicant_gender",
            "applicant_marital_status",
            "applicant_level_of_education",
        ]
        available = [c for c in cols if c in df.columns]
        dim = df[available].drop_duplicates().copy()

        # Deterministic ID: SHA-256 of SSN, truncated to 8 hex chars → "APP-4a3f2b1c"
        key_col = "applicant_ssn" if "applicant_ssn" in dim.columns else None
        if key_col:
            dim["applicant_id"] = dim[key_col].apply(
                lambda ssn: (
                    "APP-" + hashlib.sha256(str(ssn).encode()).hexdigest()[:8]
                    if pd.notna(ssn)
                    else "APP-UNKNOWN"
                )
            )
        else:

            # Fallback to sequential IDs if no SSN column is available.
            dim["applicant_id"] = [f"APP-{str(i).zfill(6)}" for i in range(len(dim))]
            logger.warning(
                "applicant_ssn column not found. Using sequential IDs — "
                "these will break on re-runs. Add SSN data to fix this."
            )

        logger.info("Applicant dimension built: %d unique applicants", len(dim))
        return dim

    def build_employment_dim(self, df: pd.DataFrame) -> pd.DataFrame:
        """Builds the employment dimension table."""
        logger.info("Building employment dimension table")

        # Only keep relevant columns for the dimension, and drop duplicates to get unique employment records.
        cols = [
            "application_id",
            "employment_type",
            "employer_name",
            "monthly_income_usd",
            "employment_duration_months",
        ]
        available = [c for c in cols if c in df.columns]
        return df[available].drop_duplicates(subset=["application_id"]).copy()

    def build_contact_info_dim(self, df: pd.DataFrame) -> pd.DataFrame:
        """Builds the contact information dimension table."""
        logger.info("Building contact info dimension table")

        cols = [
            "application_id",
            "applicant_email",
            "applicant_phone_number",
            "applicant_state",
            "applicant_city",
            "applicant_address",
        ]
        available = [c for c in cols if c in df.columns]
        return df[available].drop_duplicates(subset=["application_id"]).copy()

    def build_next_of_kin_dim(self, df: pd.DataFrame) -> pd.DataFrame:
        """Builds the next-of-kin dimension table."""
        logger.info("Building next-of-kin dimension table")

        cols = [
            "application_id",
            "next_of_kin_name",
            "next_of_kin_relationship",
            "next_of_kin_phone",
            "next_of_kin_email",
        ]
        available = [c for c in cols if c in df.columns]
        return df[available].drop_duplicates(subset=["application_id"]).copy()

    def build_fact_table(self, df: pd.DataFrame, dim: pd.DataFrame) -> pd.DataFrame:
        """
        Builds the loan application fact table by joining the cleaned source
        with the applicant dimension to pick up applicant_id.
        """
        logger.info("Building fact_loans table")

        # Only merge on columns that exist in both DataFrames
        merge_cols = [c for c in dim.columns if c in df.columns and c != "applicant_id"]
        merged = df.merge(dim[["applicant_id"] + merge_cols], on=merge_cols, how="left")

        fact_cols = [
            "application_id",
            "applicant_id",
            "application_date",
            "loan_type",
            "loan_amount_requested_usd",
            "loan_purpose",
            "loan_term_months",
            "interest_rate",
        ]
        available = [c for c in fact_cols if c in merged.columns]
        fact = merged[available].copy()

        # Derived column: estimated monthly payment using standard amortisation formula
        if all(
            c in fact.columns
            for c in ["loan_amount_requested_usd", "interest_rate", "loan_term_months"]
        ):
            fact["estimated_monthly_payment_usd"] = self._monthly_payment(
                fact["loan_amount_requested_usd"],
                fact["interest_rate"],
                fact["loan_term_months"],
            )

        logger.info("Fact loans built: %d rows", len(fact))
        return fact

    # Utilities

    @staticmethod
    def _normalise_columns(columns) -> list:
        """
        Lowercases, strips whitespace, replaces spaces/hyphens/brackets
        with underscores. "First Name" → "first_name".
        """
        return [
            re.sub(r"[\s\-\(\)]+", "_", col.strip().lower()).strip("_")
            for col in columns
        ]

    @staticmethod
    def _clean_phone(value) -> str:
        """Strips all non-digit characters except a leading +."""
        if pd.isna(value):
            return np.nan
        cleaned = re.sub(r"[^\d+]", "", str(value).strip())
        return cleaned if cleaned else np.nan

    @staticmethod
    def _monthly_payment(
        principal: pd.Series,
        annual_rate_pct: pd.Series,
        term_months,
    ) -> pd.Series:
        """
        Standard amortising loan payment:  M = P * r(1+r)^n / ((1+r)^n - 1)
        Returns NaN where inputs are missing or invalid.
        """
        monthly_rate = annual_rate_pct / 100 / 12
        n = pd.to_numeric(term_months, errors="coerce").fillna(60)

        mask = monthly_rate > 0
        payment = pd.Series(np.nan, index=principal.index)
        payment[mask] = principal[mask] * (
            monthly_rate[mask]
            * (1 + monthly_rate[mask]) ** n[mask]
            / ((1 + monthly_rate[mask]) ** n[mask] - 1)
        )
        payment[~mask] = principal[~mask] / n[~mask]
        return payment.round(2)
