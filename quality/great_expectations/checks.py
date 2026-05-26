from great_expectations.dataset import PandasDataset


def validate_loans(df):

    # Basic data quality checks for loan dataset

    gdf = PandasDataset(df)

    gdf.expect_column_values_to_not_be_null("application_id")
    gdf.expect_column_values_to_not_be_null("applicant_id")

    if "loan_amount_requested_usd" in df.columns:
        gdf.expect_column_values_to_be_between(
            "loan_amount_requested_usd", min_value=0, max_value=100000
        )

    return gdf.validate()
