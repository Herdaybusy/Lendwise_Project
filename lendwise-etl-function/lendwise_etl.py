import pandas as pd
import numpy as np
import io
from google.cloud import storage, bigquery
import functions_framework
from flask import jsonify
import traceback
import os

@functions_framework.http
def etl_pipeline(request):
    try:
        # Define GCS bucket for raw data
        bucket_name = 'lendwise-bucket'
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        
        # Extract data from GCS
        def read_csv_from_gcs(blob_path):
            try:
                blob = bucket.blob(blob_path)
                content = blob.download_as_string()
                return pd.read_csv(io.BytesIO(content))
            except Exception as e:
                print(f"Error reading {blob_path}: {str(e)}")
                raise
        
        # Load the CSV files into DataFrames
        print("Starting data extraction...")
        loan_repayments = read_csv_from_gcs('Raw_Data/loan_repayments.csv')
        loan_applications = read_csv_from_gcs('Raw_Data/loan_applications.csv')  
        credit_bureau = read_csv_from_gcs('Raw_Data/credit_bureau_data.csv')
        print("Data Extracted Successfully")

        # Data Cleaning and Transformation
        print("Starting data cleaning and transformation...")
        
        # LOAN REPAYMENTS DATA
        print("Processing loan repayments data...")
        # Check for duplicates in the DataFrame
        loan_repayments = loan_repayments.drop_duplicates()
        
        # Drop missing values
        loan_repayments = loan_repayments.dropna()
        
        # Clean the column names by replacing spaces with underscores and converting to lowercase
        loan_repayments.columns = loan_repayments.columns\
                                    .str.replace(' ', '_')\
                                    .str.replace('(', '', regex=False)\
                                    .str.replace(')', '', regex=False)\
                                    .str.lower()
        
        # Convert the 'repayment_date' column to datetime format
        if 'repayment_date' in loan_repayments.columns:
            loan_repayments['repayment_date'] = pd.to_datetime(loan_repayments['repayment_date'], format='%Y-%m-%d', errors='coerce')
        
        # LOAN APPLICATIONS DATA
        print("Processing loan applications data...")
        # Check for duplicates in the DataFrame
        loan_applications = loan_applications.drop_duplicates()
        
        # Drop missing values
        loan_applications = loan_applications.dropna()
        
        # Clean the column names by replacing spaces with underscores and converting to lowercase
        loan_applications = loan_applications.rename(columns=lambda x: x.strip().lower().replace(' ', '_').replace('(', '').replace(')', ''))
        
        # Convert date columns to datetime format
        date_columns = ['application_date', 'applicant_date_of_birth']
        for date_col in date_columns:
            if date_col in loan_applications.columns:
                loan_applications[date_col] = pd.to_datetime(loan_applications[date_col], format='%Y-%m-%d', errors='coerce')
        
        # Convert phone numbers to numeric
        phone_columns = ['applicant_phone_number', 'next_of_kin_phone_number']
        for phone_col in phone_columns:
            if phone_col in loan_applications.columns:
                loan_applications[phone_col] = loan_applications[phone_col].astype(str).str.replace(r'\D', '', regex=True)

        # TRANSFORMATION (CREATING TABLES)
        print("Creating dimension tables...")
        
        # APPLICANT TABLE
        required_applicant_cols = ['applicant_ssn', 'applicant_full_name', 'applicant_date_of_birth', 
                                 'applicant_gender', 'applicant_marital_status', 'applicant_level_of_education']
        
        # Check if all required columns exist
        missing_cols = [col for col in required_applicant_cols if col not in loan_applications.columns]
        if missing_cols:
            print(f"Warning: Missing columns for applicant table: {missing_cols}")
            # Use available columns only
            available_cols = [col for col in required_applicant_cols if col in loan_applications.columns]
            applicant_table = loan_applications[available_cols].drop_duplicates().reset_index(drop=True)
        else:
            applicant_table = loan_applications[required_applicant_cols].drop_duplicates().reset_index(drop=True)

        np.random.seed(42)  # Seed set for reproducibility
        # Random applicant IDs
        applicant_table['applicant_id'] = ['Ap' + str(i) for i in np.random.randint(100000, 999999, size=len(applicant_table))]
        print('Applicant table created successfully')
        
        # EMPLOYMENT TABLE 
        print("Creating employment table...")
        # Merge the loan_applications DataFrame with the applicant_table DataFrame to get the applicant_id
        merge_cols = [col for col in required_applicant_cols if col in applicant_table.columns]
        employment_merged = loan_applications.merge(
            applicant_table,
            on=merge_cols,
            how='left'
        )
        
        # Define employment columns
        employment_cols = ['employment_type', 'employer_name', 'duration_of_employment_years', 
                          'monthly_income_usd', 'bank_account_number', 'applicant_id']
        
        # Check which columns exist and use available ones
        available_employment_cols = [col for col in employment_cols if col in employment_merged.columns]
        if 'applicant_id' not in available_employment_cols:
            available_employment_cols.append('applicant_id')
            
        employment_table = employment_merged[available_employment_cols].drop_duplicates()

        np.random.seed(42)  # Seed set for reproducibility
        # Random employment IDs
        employment_table['employment_id'] = ['Em' + str(i) for i in np.random.randint(100000, 999999, size=len(employment_table))]
        
        # Reorder columns
        cols = ['applicant_id', 'employment_id'] + [col for col in employment_table.columns if col not in ['applicant_id', 'employment_id']]
        employment_table = employment_table[cols]
        print('Employment table created successfully')   
                        
        # CONTACT INFO TABLE
        print("Creating contact info table...")
        contact_info_merged = loan_applications.merge(
            applicant_table,
            on=merge_cols,
            how='left'
        )

        contact_cols = ['applicant_street_address', 'applicant_city', 'applicant_state', 
                       'applicant_zip_code', 'applicant_phone_number', 'applicant_email_address', 'applicant_id']
        
        available_contact_cols = [col for col in contact_cols if col in contact_info_merged.columns]
        contact_info_table = contact_info_merged[available_contact_cols].drop_duplicates()

        np.random.seed(42)  # Seed set for reproducibility
        # Random contact_info IDs
        contact_info_table['contact_info_id'] = ['Ci' + str(i) for i in np.random.randint(100000, 999999, size=len(contact_info_table))]
        
        # Reorder columns
        cols = ['contact_info_id', 'applicant_id'] + [col for col in contact_info_table.columns if col not in ['contact_info_id', 'applicant_id']]
        contact_info_table = contact_info_table[cols]
        print('Contact info table created successfully')        
                
        # NEXT OF KIN TABLE
        print("Creating next of kin table...")
        next_of_kin_merged = loan_applications.merge(
            applicant_table,
            on=merge_cols,
            how='left'
        )
        
        kin_cols = ['applicant_id', 'next_of_kin_full_name', 'next_of_kin_relationship', 'next_of_kin_phone_number']
        available_kin_cols = [col for col in kin_cols if col in next_of_kin_merged.columns]
        next_of_kin_table = next_of_kin_merged[available_kin_cols].drop_duplicates()

        np.random.seed(42)  # Seed set for reproducibility
        # Random next of kin IDs
        next_of_kin_table['next_of_kin_id'] = ['Nk' + str(i) for i in np.random.randint(100000, 999999, size=len(next_of_kin_table))]
        
        # Reorder columns
        cols = ['next_of_kin_id', 'applicant_id'] + [col for col in next_of_kin_table.columns if col not in ['next_of_kin_id', 'applicant_id']]
        next_of_kin_table = next_of_kin_table[cols]
        print('Next of kin table created successfully')
        
        # LOAN APPLICATION FACT TABLE
        print("Creating loan application fact table...")
        loan_application_fact_table = loan_applications.merge(
            applicant_table, on=merge_cols, how='left'
        )
        
        # Add other dimension table IDs through merges (simplified approach)
        fact_cols = ['application_id', 'applicant_id', 'application_date', 'loan_type', 
                    'loan_amount_requested_usd', 'loan_purpose', 'repayment_tenure_months']
        
        available_fact_cols = [col for col in fact_cols if col in loan_application_fact_table.columns]
        loan_application_fact_table = loan_application_fact_table[available_fact_cols]
        print('Loan application fact table created successfully')
        
        # CREDIT BUREAU DATA 
        print("Processing credit bureau data...")
        # Check for duplicates in the DataFrame
        credit_bureau = credit_bureau.drop_duplicates()
        
        # Drop missing values
        credit_bureau = credit_bureau.dropna()
        
        # Clean the column names by replacing spaces with underscores and converting to lowercase
        credit_bureau.columns = credit_bureau.columns.str.replace(' ', '_').str.lower()
        print('Credit bureau data cleaned successfully')
        
        # Create a function to save transformed data to GCS
        def upload_to_gcs(df, blob_path):
            try:
                blob = bucket.blob(blob_path)
                csv_data = df.to_csv(index=False)
                blob.upload_from_string(csv_data, content_type='text/csv')
                print(f"Uploaded {blob_path} to GCS")
            except Exception as e:
                print(f"Error uploading {blob_path}: {str(e)}")
                raise
            
        # Save all tables to GCS
        print("Uploading cleaned data to GCS...")
        upload_to_gcs(loan_repayments, 'Cleaned_Data/loan_repayments_cleaned.csv')
        upload_to_gcs(loan_applications, 'Cleaned_Data/loan_applications_cleaned.csv')
        upload_to_gcs(applicant_table, 'Cleaned_Data/applicant_table.csv')
        upload_to_gcs(employment_table, 'Cleaned_Data/employment_table.csv')
        upload_to_gcs(contact_info_table, 'Cleaned_Data/contact_info_table.csv')
        upload_to_gcs(next_of_kin_table, 'Cleaned_Data/next_of_kin_table.csv')
        upload_to_gcs(loan_application_fact_table, 'Cleaned_Data/loan_application_fact_table.csv')
        upload_to_gcs(credit_bureau, 'Cleaned_Data/credit_bureau_cleaned.csv')
        
        # Load to BigQuery if needed
        project_id = os.environ.get('GCP_PROJECT', 'lendwise-financials')
        dataset_id = 'lendwise_data'
        
        print("Loading data to BigQuery...")
        bq_client = bigquery.Client(project=project_id)
        
        # Function to load data to BigQuery
        def load_to_bigquery(df, table_name):
            try:
                table_id = f"{project_id}.{dataset_id}.{table_name}"
                job_config = bigquery.LoadJobConfig(
                    write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
                    autodetect=True
                )
                job = bq_client.load_table_from_dataframe(df, table_id, job_config=job_config)
                job.result()  # Wait for the job to complete
                print(f"Loaded {table_name} to BigQuery")
            except Exception as e:
                print(f"Error loading {table_name} to BigQuery: {str(e)}")
                # Don't raise here, continue with other tables
        
        # Load all tables to BigQuery
        load_to_bigquery(loan_repayments, 'loan_repayments')
        load_to_bigquery(loan_applications, 'loan_applications')
        load_to_bigquery(applicant_table, 'applicant')
        load_to_bigquery(employment_table, 'employment')
        load_to_bigquery(contact_info_table, 'contact_info')
        load_to_bigquery(next_of_kin_table, 'next_of_kin')
        load_to_bigquery(loan_application_fact_table, 'loan_application_fact')
        load_to_bigquery(credit_bureau, 'credit_bureau')
        
        print("ETL Pipeline Completed Successfully")
        
        # Return success response
        response_data = {
            "status": "success",
            "message": "ETL pipeline completed successfully",
            "tables_processed": {
                "loan_repayments": len(loan_repayments),
                "loan_applications": len(loan_applications),
                "applicant": len(applicant_table),
                "employment": len(employment_table),
                "contact_info": len(contact_info_table),
                "next_of_kin": len(next_of_kin_table),
                "loan_application_fact": len(loan_application_fact_table),
                "credit_bureau": len(credit_bureau)
            }
        }
        
        return (jsonify(response_data), 200, headers)
    
    except Exception as e:
        error_message = f"ETL pipeline failed: {str(e)}"
        print(f"ERROR: {error_message}")
        print(traceback.format_exc())
        
        error_response = {
            "status": "error",
            "message": error_message,
            "traceback": traceback.format_exc()
        }
        
        return (jsonify(error_response), 500, headers)