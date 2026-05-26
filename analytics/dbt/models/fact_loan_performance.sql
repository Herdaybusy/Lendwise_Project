-- analytics/dbt/models/fact_loan_performance.sql

-- Mart model: loan performance

-- Joins the loan staging model with repayments and credit bureau data
-- to produce a denormalised analytical table ready for dashboards and reporting.

-- Grain: one row per loan application.

with loans as (

    select * from {{ ref('stg_loans') }}

),

repayments_summary as (

    -- Aggregate repayment events to one row per application
    select
        application_id,
        count(*)                                                    as total_payments_made,
        sum(amount_paid_usd)                                        as total_amount_paid_usd,
        max(repayment_date)                                         as last_payment_date,
        sum(case when is_delinquent then 1 else 0 end)              as delinquent_payment_count,
        max(case when payment_status = 'Defaulted' then 1 else 0 end) as has_defaulted

    from {{ source('lendwise_data', 'fact_repayments') }}
    group by application_id

),

credit as (

    select
        application_id,
        credit_score,
        credit_band,
        credit_utilization_pct,
        delinquent_accounts

    from {{ source('lendwise_data', 'dim_credit_bureau') }}

),

final as (

    select
        -- Keys
        l.application_id,
        l.applicant_id,

        -- Loan facts
        l.loan_type,
        l.loan_amount_requested_usd,
        l.loan_term_months,
        l.interest_rate,
        l.loan_purpose,
        l.estimated_monthly_payment_usd,
        l.application_date,

        -- Loan value segment — useful for portfolio slicing
        case
            when l.loan_amount_requested_usd > 50000 then 'LARGE'
            when l.loan_amount_requested_usd > 10000 then 'MEDIUM'
            when l.loan_amount_requested_usd > 1000  then 'SMALL'
            else 'MICRO'
        end as loan_segment,

        -- Repayment performance
        coalesce(r.total_payments_made, 0)          as total_payments_made,
        coalesce(r.total_amount_paid_usd, 0)        as total_amount_paid_usd,
        r.last_payment_date,
        coalesce(r.delinquent_payment_count, 0)     as delinquent_payment_count,
        coalesce(r.has_defaulted, 0) = 1            as has_defaulted,

        -- Derived: outstanding balance
        l.loan_amount_requested_usd
            - coalesce(r.total_amount_paid_usd, 0)  as outstanding_balance_usd,

        -- Credit profile
        c.credit_score,
        c.credit_band,
        c.credit_utilization_pct,
        c.delinquent_accounts,

        -- Risk flag: delinquent payments OR poor credit
        (
            coalesce(r.delinquent_payment_count, 0) > 0
            or c.credit_band in ('Poor', 'Fair')
        ) as is_high_risk

    from loans l
    left join repayments_summary r using (application_id)
    left join credit c using (application_id)

)

select * from final
