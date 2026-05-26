"""
Validators
----------

Reliable data quality checks
"""

import pandas as pd

from etl.utils.logger import get_logger

logger = get_logger("lendwise.validators")


# Loan Applications


class ValidationError(Exception):
    pass


# Each validation function checks a specific table's DataFrame for expected columns and value ranges.
def validate_loan_applications(df: pd.DataFrame) -> dict:
    logger.info("Validating loan applications: %d rows", len(df))

    # Check for required column
    if "loan_amount_requested_usd" not in df.columns:
        logger.warning("loan_amount_requested_usd column missing")
        return {}

    # Convert safely
    df["loan_amount_requested_usd"] = pd.to_numeric(
        df["loan_amount_requested_usd"], errors="coerce"
    )

    # Detect invalids
    invalid_mask = (
        (df["loan_amount_requested_usd"] <= 0)
        | (df["loan_amount_requested_usd"] > 500_000)
        | (df["loan_amount_requested_usd"].isna())
    )

    invalid_count = invalid_mask.sum()

    # Log summary of invalids
    if invalid_count > 0:
        logger.warning(
            "Invalid loan amounts detected: %d rows (%.2f%%)",
            invalid_count,
            invalid_count / len(df) * 100,
        )

    # Optional: decide policy instead of crashing
    if invalid_count > len(df) * 0.2:
        # only crash if dataset is really bad (>20%)
        raise ValidationError("Too many invalid loan amounts")

    logger.info("Loan applications validation passed")
    return {"invalid_rows": int(invalid_count)}


# Loan Repayments


def validate_loan_repayments(df: pd.DataFrame):
    logger.info("Validating loan repayments: %d rows", len(df))

    # Check for required columns
    if "loan_application_id" not in df.columns:
        raise ValidationError("Missing loan_application_id")

    if "amount_paid_usd" in df.columns:
        if (df["amount_paid_usd"] < 0).any():
            raise ValidationError("Negative repayment detected")

    logger.info("Loan repayments validation passed")


# Credit Bureau


def validate_credit_bureau(df: pd.DataFrame):
    logger.info("Validating credit bureau: %d rows", len(df))

    if "applicant_ssn" not in df.columns:
        raise ValidationError("Missing applicant_ssn")

    if "credit_score" in df.columns:
        invalid = df[(df["credit_score"] < 300) | (df["credit_score"] > 850)]
        if len(invalid) > 0:
            raise ValidationError("Invalid credit scores found")

    logger.info("Credit bureau validation passed")


# Fact Table


def validate_fact_loans(df: pd.DataFrame):
    logger.info("Validating fact loans: %d rows", len(df))

    if "application_id" not in df.columns:
        raise ValidationError("Missing application_id")

    logger.info("Fact loans validation passed")
