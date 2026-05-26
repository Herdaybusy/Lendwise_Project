"""
Unit Tests — All Transformers
------------------------------
Tests every transformation function with synthetic data.
No GCP credentials required — all tests run entirely in-memory.

Run with:
    pytest tests/unit/test_all_transforms.py -v
    pytest tests/unit/test_all_transforms.py -v --tb=short   # shorter tracebacks
"""

import numpy as np
import pandas as pd
import pytest

from etl.transform.credit_bureau import CreditBureauTransformer
from etl.transform.loan_applications import LoanApplicationsTransformer
from etl.transform.loan_repayments import LoanRepaymentsTransformer

# ── Shared fixtures ───────────────────────────────────────────────────────────


@pytest.fixture()
def loan_transformer():
    return LoanApplicationsTransformer()


@pytest.fixture()
def repay_transformer():
    return LoanRepaymentsTransformer()


@pytest.fixture()
def credit_transformer():
    return CreditBureauTransformer()


@pytest.fixture()
def sample_loans() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "application_id": [
                "APP001",
                "APP002",
                "APP003",
                "APP001",
            ],  # APP001 duplicated
            "applicant_ssn": [
                "111-22-3333",
                "444-55-6666",
                "777-88-9999",
                "111-22-3333",
            ],
            "Applicant Full Name": [
                "Alice Smith",
                "Bob Jones",
                "Charlie Brown",
                "Alice Smith",
            ],
            "applicant_date_of_birth": [
                "1985-06-15",
                "1990-03-22",
                "bad-date",
                "1985-06-15",
            ],
            "application_date": [
                "2024-01-15",
                "2024-02-20",
                "2024-03-10",
                "2024-01-15",
            ],
            "loan_type": ["Personal", "Business", "Auto", "Personal"],
            "loan_amount_requested_usd": ["10000", "25000", "not_a_number", "10000"],
            "loan_term_months": [36, 60, 24, 36],
            "interest_rate": [5.5, 7.2, 4.9, 5.5],
            "applicant_phone_number": [
                "+44 7911 123456",
                "(555) 123-4567",
                None,
                "+44 7911 123456",
            ],
            "employment_type": ["Full-time", "Self-employed", "Part-time", "Full-time"],
            "monthly_income_usd": [5000, 8000, 2500, 5000],
        }
    )


@pytest.fixture()
def sample_repayments() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "application_id": ["APP001", "APP001", "APP002", None],
            "repayment_date": ["2024-02-15", "2024-03-15", "2024-03-20", "2024-04-01"],
            "amount_paid_usd": [300.0, 300.0, 450.0, 100.0],
            "days_overdue": [0, 0, 35, 0],  # APP002 payment is delinquent (35 days)
            "payment_status": ["Paid", "Paid", "Late", "Paid"],
        }
    )


@pytest.fixture()
def sample_credit() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "application_id": ["APP001", "APP002", "APP003"],
            "credit_score": [720, 590, 680],
            "total_accounts": [8, 5, 12],
            "delinquent_accounts": [0, 2, 1],
            "credit_utilization_pct": [28.5, 62.1, 45.2],
            "bureau_pull_date": ["2024-01-10", "2024-02-18", "bad-date"],
        }
    )


# ── Loan Applications: cleaning ───────────────────────────────────────────────


class TestLoanApplicationsCleaning:

    def test_drops_exact_duplicates(self, loan_transformer, sample_loans):
        cleaned = loan_transformer.clean(sample_loans)
        assert len(cleaned) == 3  # 4 rows minus 1 duplicate

    def test_drops_rows_with_null_application_id(self, loan_transformer):
        df = pd.DataFrame(
            {
                "application_id": ["APP001", None],
                "loan_amount_requested_usd": [10000, 5000],
            }
        )
        cleaned = loan_transformer.clean(df)
        assert len(cleaned) == 1

    def test_normalises_column_names(self, loan_transformer, sample_loans):
        cleaned = loan_transformer.clean(sample_loans)
        # "Applicant Full Name" should become "applicant_full_name"
        assert "applicant_full_name" in cleaned.columns
        assert "Applicant Full Name" not in cleaned.columns

    def test_coerces_loan_amount_to_numeric(self, loan_transformer, sample_loans):
        cleaned = loan_transformer.clean(sample_loans)
        assert pd.api.types.is_numeric_dtype(cleaned["loan_amount_requested_usd"])

    def test_bad_loan_amount_becomes_nan_not_crash(
        self, loan_transformer, sample_loans
    ):
        cleaned = loan_transformer.clean(sample_loans)
        # "not_a_number" for APP003 should be NaN, not raise an exception
        app003 = cleaned[cleaned["application_id"] == "APP003"]
        assert pd.isna(app003["loan_amount_requested_usd"].values[0])

    def test_parses_application_date(self, loan_transformer, sample_loans):
        cleaned = loan_transformer.clean(sample_loans)
        assert pd.api.types.is_datetime64_any_dtype(cleaned["application_date"])

    def test_bad_date_of_birth_becomes_nat(self, loan_transformer, sample_loans):
        cleaned = loan_transformer.clean(sample_loans)
        app003 = cleaned[cleaned["application_id"] == "APP003"]
        assert pd.isna(app003["applicant_date_of_birth"].values[0])

    def test_cleans_phone_numbers(self, loan_transformer, sample_loans):
        cleaned = loan_transformer.clean(sample_loans)
        assert cleaned["applicant_phone_number"].iloc[0] == "+447911123456"
        assert cleaned["applicant_phone_number"].iloc[1] == "5551234567"

    def test_null_phone_remains_null(self, loan_transformer, sample_loans):
        cleaned = loan_transformer.clean(sample_loans)
        app003 = cleaned[cleaned["application_id"] == "APP003"]
        assert pd.isna(app003["applicant_phone_number"].values[0])

    def test_retains_all_non_key_columns(self, loan_transformer, sample_loans):
        cleaned = loan_transformer.clean(sample_loans)
        # Columns with all valid rows should still be present
        assert "loan_type" in cleaned.columns


# ── Loan Applications: dimension building ─────────────────────────────────────


class TestApplicantDimension:

    def test_applicant_ids_are_deterministic(self, loan_transformer, sample_loans):
        """
        Critical test: same SSN must always produce the same applicant_id.
        This is the core fix over the original np.random approach.
        """
        cleaned = loan_transformer.clean(sample_loans)
        dim_run1 = loan_transformer.build_applicant_dim(cleaned)
        dim_run2 = loan_transformer.build_applicant_dim(cleaned)

        assert dim_run1["applicant_id"].tolist() == dim_run2["applicant_id"].tolist()

    def test_applicant_ids_start_with_app_prefix(self, loan_transformer, sample_loans):
        cleaned = loan_transformer.clean(sample_loans)
        dim = loan_transformer.build_applicant_dim(cleaned)
        assert all(aid.startswith("APP-") for aid in dim["applicant_id"])

    def test_different_ssns_get_different_ids(self, loan_transformer, sample_loans):
        cleaned = loan_transformer.clean(sample_loans)
        dim = loan_transformer.build_applicant_dim(cleaned)
        assert dim["applicant_id"].nunique() == len(dim)

    def test_dim_has_no_duplicate_rows(self, loan_transformer, sample_loans):
        cleaned = loan_transformer.clean(sample_loans)
        dim = loan_transformer.build_applicant_dim(cleaned)
        assert len(dim) == dim.drop_duplicates().shape[0]


class TestFactTable:

    def test_fact_table_contains_applicant_id(self, loan_transformer, sample_loans):
        cleaned = loan_transformer.clean(sample_loans)
        dim = loan_transformer.build_applicant_dim(cleaned)
        fact = loan_transformer.build_fact_table(cleaned, dim)
        assert "applicant_id" in fact.columns

    def test_estimated_monthly_payment_added(self, loan_transformer, sample_loans):
        cleaned = loan_transformer.clean(sample_loans)
        dim = loan_transformer.build_applicant_dim(cleaned)
        fact = loan_transformer.build_fact_table(cleaned, dim)
        assert "estimated_monthly_payment_usd" in fact.columns

    def test_monthly_payment_positive_for_valid_rows(
        self, loan_transformer, sample_loans
    ):
        cleaned = loan_transformer.clean(sample_loans)
        dim = loan_transformer.build_applicant_dim(cleaned)
        fact = loan_transformer.build_fact_table(cleaned, dim)
        valid = fact["estimated_monthly_payment_usd"].dropna()
        assert (valid > 0).all()


# ── Loan Repayments ───────────────────────────────────────────────────────────


class TestLoanRepaymentsCleaning:

    def test_drops_rows_missing_application_id(
        self, repay_transformer, sample_repayments
    ):
        cleaned = repay_transformer.clean(sample_repayments)
        assert cleaned["application_id"].notna().all()

    def test_does_not_drop_rows_with_optional_nulls(self, repay_transformer):
        """
        A row with a null in a non-essential column (like notes)
        should NOT be dropped.
        """
        df = pd.DataFrame(
            {
                "application_id": ["APP001"],
                "repayment_date": ["2024-01-15"],
                "amount_paid_usd": [500.0],
                "notes": [None],  # Optional — should not trigger a row drop
            }
        )
        cleaned = repay_transformer.clean(df)
        assert len(cleaned) == 1

    def test_parses_repayment_date(self, repay_transformer, sample_repayments):
        cleaned = repay_transformer.clean(sample_repayments)
        assert pd.api.types.is_datetime64_any_dtype(cleaned["repayment_date"])

    def test_delinquent_flag_set_correctly(self, repay_transformer, sample_repayments):
        cleaned = repay_transformer.clean(sample_repayments)
        # APP002 has days_overdue=35 → should be delinquent
        app002 = cleaned[cleaned["application_id"] == "APP002"]
        assert app002["is_delinquent"].values[0] == True

    def test_non_delinquent_flag_correct(self, repay_transformer, sample_repayments):
        cleaned = repay_transformer.clean(sample_repayments)
        app001 = cleaned[cleaned["application_id"] == "APP001"]
        assert not app001["is_delinquent"].any()

    def test_drops_duplicates(self, repay_transformer, sample_repayments):
        duped = pd.concat([sample_repayments, sample_repayments])
        cleaned = repay_transformer.clean(duped)
        assert len(cleaned) < len(duped)


# ── Credit Bureau ─────────────────────────────────────────────────────────────


class TestCreditBureauCleaning:

    def test_drops_rows_missing_application_id(self, credit_transformer, sample_credit):
        df = sample_credit.copy()
        df.loc[0, "application_id"] = None
        cleaned = credit_transformer.clean(df)
        assert cleaned["application_id"].notna().all()

    def test_coerces_credit_score_to_numeric(self, credit_transformer, sample_credit):
        cleaned = credit_transformer.clean(sample_credit)
        assert pd.api.types.is_numeric_dtype(cleaned["credit_score"])

    def test_bad_bureau_pull_date_becomes_nat(self, credit_transformer, sample_credit):
        cleaned = credit_transformer.clean(sample_credit)
        app003 = cleaned[cleaned["application_id"] == "APP003"]
        assert pd.isna(app003["bureau_pull_date"].values[0])

    def test_credit_band_added(self, credit_transformer, sample_credit):
        cleaned = credit_transformer.clean(sample_credit)
        assert "credit_band" in cleaned.columns

    def test_credit_band_correct_for_720(self, credit_transformer, sample_credit):
        cleaned = credit_transformer.clean(sample_credit)
        app001 = cleaned[cleaned["application_id"] == "APP001"]
        assert str(app001["credit_band"].values[0]) == "Good"  # 720 → Good

    def test_credit_band_correct_for_590(self, credit_transformer, sample_credit):
        cleaned = credit_transformer.clean(sample_credit)
        app002 = cleaned[cleaned["application_id"] == "APP002"]
        assert str(app002["credit_band"].values[0]) == "Fair"  # 590 → Fair

    def test_does_not_drop_rows_with_null_optional_fields(self, credit_transformer):
        """
        The original code did dropna() which would drop this row.
        We only require application_id to be non-null.
        """
        df = pd.DataFrame(
            {
                "application_id": ["APP001"],
                "credit_score": [700],
                "bankruptcy_flag": [None],  # Optional — no bankruptcy on record
            }
        )
        cleaned = credit_transformer.clean(df)
        assert len(cleaned) == 1

    def test_credit_utilization_coerced_to_numeric(
        self, credit_transformer, sample_credit
    ):
        cleaned = credit_transformer.clean(sample_credit)
        assert pd.api.types.is_numeric_dtype(cleaned["credit_utilization_pct"])


# ── Column normalisation edge cases ───────────────────────────────────────────


class TestColumnNormalisation:
    """Tests the _normalise_columns helper via the transformer."""

    def test_uppercase_becomes_lowercase(self, loan_transformer):
        df = pd.DataFrame({"application_id": ["APP001"], "LOAN_TYPE": ["Personal"]})
        cleaned = loan_transformer.clean(df)
        assert "loan_type" in cleaned.columns

    def test_spaces_replaced_with_underscores(self, loan_transformer):
        df = pd.DataFrame({"application_id": ["APP001"], "Loan Amount USD": [10000]})
        cleaned = loan_transformer.clean(df)
        assert "loan_amount_usd" in cleaned.columns

    def test_parentheses_stripped(self, loan_transformer):
        df = pd.DataFrame({"application_id": ["APP001"], "income (usd)": [5000]})
        cleaned = loan_transformer.clean(df)
        assert "income_usd" in cleaned.columns
