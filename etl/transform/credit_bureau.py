import pandas as pd
from etl.utils.logger import get_logger

logger = get_logger("lendwise.transform.credit_bureau")


class CreditBureauTransformer: # Transformer for credit bureau data. Cleans and standardises the credit bureau DataFrame

    
    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        
        logger.info("Cleaning credit bureau data: %d rows", len(df))
        # Make a copy to avoid modifying the original DataFrame
        df = df.copy()

        # 1. Normalise column names
        df.columns = (
            df.columns
            .str.strip()
            .str.lower()
            .str.replace(r"[\s\-\(\)]+", "_", regex=True)
            .str.strip("_")
        )

        # 2. Identifier handling
        if "application_id" in df.columns:
            pass
        elif "applicant_ssn" in df.columns:
            df["application_id"] = df["applicant_ssn"]
        else:
            raise ValueError(
                f"credit_bureau must contain 'application_id' or 'applicant_ssn'. "
                f"Found columns: {list(df.columns)}"
            )

        if "applicant_ssn" not in df.columns:
            df["applicant_ssn"] = df["application_id"]

        # 3. Clean identifiers
        df = df.dropna(subset=["application_id"])
        df = df.drop_duplicates()

        # 4. Numeric conversion
        numeric_cols = [
            "credit_score",
            "number_of_credit_accounts",
            "number_of_derogatory_marks",
            "credit_utilization_pct",
        ]

        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # 5. Date parsing
        if "bureau_pull_date" in df.columns:
            df["bureau_pull_date"] = pd.to_datetime(
                df["bureau_pull_date"],
                errors="coerce"
            )

        # 6. Credit band
        if "credit_score" in df.columns:
            df["credit_band"] = pd.cut(
                df["credit_score"],
                bins=[299, 579, 669, 739, 799, 850],
                labels=["Poor", "Fair", "Good", "Very Good", "Exceptional"],
            )

            logger.info(
                "Credit band distribution: %s",
                df["credit_band"].value_counts(dropna=True).to_dict()
            )

        logger.info("Finished cleaning credit bureau data: %d rows", len(df))
        return df