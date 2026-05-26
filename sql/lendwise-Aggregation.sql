-- Total Repayment
SELECT 
    application_id, 
    SUM(loan_amount_requested_usd) AS total_repayment 
FROM `lendwise-financials.lendwise_data.loan_application_fact_data`
GROUP BY application_id LIMIT 10;


-- Default Rate by Credit Band
SELECT 
    CASE 
        WHEN cb.credit_score < 580 THEN 'Poor' 
        WHEN cb.credit_score BETWEEN 580 AND 669 THEN 'Fair' 
        WHEN cb.credit_score BETWEEN 670 AND 739 THEN 'Good' 
        WHEN cb.credit_score BETWEEN 740 AND 799 THEN 'Very Good' 
        ELSE 'Excellent' END AS credit_band, 
    COUNT(DISTINCT laft.application_id) AS total_loans,
    SUM(CASE WHEN lr.payment_status != 'Paid' THEN 1 ELSE 0 END) AS defaults 
FROM `lendwise-financials.lendwise_data.Credit_Bureau` cb 
JOIN `lendwise-financials.lendwise_data.applicant_data` a 
    ON cb.applicant_ssn = a.applicant_ssn 
JOIN `lendwise-financials.lendwise_data.loan_application_fact_data` laft 
    ON a.applicant_id = laft.applicant_id 
JOIN `lendwise-financials.lendwise_data.loan_repayments_data` lr 
    ON laft.application_id = lr.loan_application_id 
GROUP BY credit_band;


-- APPLICANT EDUCATION COUNT
SELECT 
    applicant_level_of_education, 
    COUNT(*) AS total_applicants 
FROM `lendwise-financials.lendwise_data.applicant_data` 
GROUP BY applicant_level_of_education;


-- Average Income Employmment
SELECT 
    employment_type, 
    AVG(monthly_income_usd) AS avg_income 
FROM `lendwise-financials.lendwise_data.employment_data` 
GROUP BY employment_type;


-- Applications per month
SELECT 
    EXTRACT(YEAR FROM application_date) AS year, 
    EXTRACT(MONTH FROM application_date) AS month, 
    COUNT(*) AS total_applications 
FROM `lendwise-financials.lendwise_data.loan_application_fact_data` 
GROUP BY year, month 
ORDER BY year, month;

-- Total Repayment vs income
SELECT 
    e.monthly_income_usd, 
    SUM(lr.amount_paid_usd) AS total_repaid 
FROM `lendwise-financials.lendwise_data.employment_data` e 
JOIN `lendwise-financials.lendwise_data.loan_application_fact_data` laft 
    ON e.employment_id = laft.employment_id 
JOIN `lendwise-financials.lendwise_data.loan_repayments_data` lr 
    ON laft.application_id = lr.loan_application_id 
GROUP BY e.monthly_income_usd;

-- Geo Distribution
SELECT 
      ci.applicant_state, 
      COUNT(*) AS total_applicants 
FROM `lendwise-financials.lendwise_data.contact_info_data` ci 
GROUP BY ci.applicant_state 
ORDER BY total_applicants DESC;

-- Common Next of Kin
SELECT 
    next_of_kin_relationship, 
    COUNT(*) AS frequency 
FROM `lendwise-financials.lendwise_data.next_of_kin_data` 
GROUP BY next_of_kin_relationship 
ORDER BY frequency DESC;

