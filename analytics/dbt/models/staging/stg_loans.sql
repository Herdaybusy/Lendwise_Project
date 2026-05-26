-- analytics/dbt/models/staging/stg_loans.sql

-- Staging model: loan applications


-- Pulls directly from the BigQuery raw table and applies only
-- lightweight renaming and type casting. No business logic here —
-- that belongs in the mart layer (fact_loan_performance).
--
-- Staging models are the "single source of truth" for column names.
-- If the source changes a column name, fix it here and nowhere else.

with source as (

    select * from {{ source('lendwise_data', 'fact_loans') }}

),

renamed as (

    select
        -- Keys
        application_id,
        applicant_id,

        -- Loan details
        loan_type,
        loan_amount_requested_usd,
        loan_term_months,
        interest_rate,
        loan_purpose,
        estimated_monthly_payment_usd,

        -- Dates
        cast(application_date as date) as application_date,

        -- Metadata
        current_timestamp() as _loaded_at

    from source

)

select * from renamed
