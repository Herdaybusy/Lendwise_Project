import pandas as pd

from etl.transform.loan_applications import LoanApplicationsTransformer


def sample_data():
    return pd.DataFrame(
        {
            "application_id": ["APP001", "APP002"],
            "applicant_full_name": ["John Doe", "Jane Smith"],
            "applicant_ssn": ["123", "456"],
            "application_date": ["2023-01-01", "2023-02-01"],
            "applicant_date_of_birth": ["1990-01-01", "1985-05-10"],
            "loan_amount_requested_usd": [1000, 5000],
        }
    )


def test_cleaning_removes_duplicates():
    df = sample_data()
    df = pd.concat([df, df])

    transformer = LoanApplicationsTransformer()
    cleaned = transformer.clean(df)

    assert len(cleaned) == 2


def test_column_standardisation():
    df = sample_data()
    transformer = LoanApplicationsTransformer()

    cleaned = transformer.clean(df)

    assert "application_date" in cleaned.columns
    assert "applicant_full_name" in cleaned.columns
