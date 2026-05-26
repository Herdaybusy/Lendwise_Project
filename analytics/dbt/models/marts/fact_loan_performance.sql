SELECT
    l.application_id,
    l.applicant_id,
    l.loan_amount_requested_usd,

    CASE
        WHEN l.loan_amount_requested_usd > 5000 THEN 'HIGH_VALUE'
        WHEN l.loan_amount_requested_usd > 1000 THEN 'MEDIUM_VALUE'
        ELSE 'LOW_VALUE'
    END AS loan_segment

FROM {{ ref('stg_loans') }} l