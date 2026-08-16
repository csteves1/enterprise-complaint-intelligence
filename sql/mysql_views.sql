-- Run after the Python application has created the ORM tables.
-- These views contain no customer_ref or free-text narrative, which keeps the
-- default Power BI connection on the minimum data necessary for analytics.

CREATE OR REPLACE VIEW vw_powerbi_complaints AS
SELECT
    complaint_id,
    date_received,
    product,
    sub_product,
    issue,
    company,
    state,
    channel,
    amount_disputed,
    timely_response,
    status,
    created_at,
    updated_at
FROM complaints;

CREATE OR REPLACE VIEW vw_monthly_metrics AS
SELECT
    DATE_FORMAT(date_received, '%Y-%m-01') AS month_start,
    COUNT(*) AS complaint_count,
    AVG(CASE WHEN timely_response THEN 1.0 ELSE 0.0 END) AS timely_response_rate,
    COALESCE(SUM(amount_disputed), 0) AS disputed_amount,
    COUNT(DISTINCT company) AS company_count
FROM complaints
GROUP BY DATE_FORMAT(date_received, '%Y-%m-01');

CREATE OR REPLACE VIEW vw_product_metrics AS
SELECT
    product,
    COUNT(*) AS complaint_count,
    AVG(CASE WHEN timely_response THEN 1.0 ELSE 0.0 END) AS timely_response_rate,
    COALESCE(SUM(amount_disputed), 0) AS disputed_amount,
    COUNT(DISTINCT company) AS company_count
FROM complaints
GROUP BY product;

CREATE OR REPLACE VIEW vw_ingestion_runs AS
SELECT
    run_id,
    source_file,
    source_sha256,
    status,
    started_at,
    completed_at,
    rows_read,
    rows_valid,
    rows_rejected,
    rows_inserted,
    rows_updated,
    vectors_upserted,
    error_message,
    app_version
FROM ingestion_runs;

CREATE OR REPLACE VIEW vw_rejected_records AS
SELECT
    rejection_id,
    run_id,
    source_row_number,
    complaint_id,
    validation_errors,
    rejected_at
FROM rejected_records;
