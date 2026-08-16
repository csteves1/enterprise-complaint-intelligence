# Power BI Build Guide

## Goal

Build an executive report that answers structured questions while the Streamlit bot handles narrative investigation.

Recommended pages:

1. Executive Overview
2. Product and Issue Analysis
3. Company and Geography
4. Data Quality and Pipeline Operations
5. Record Drill-through

## Option A: Import the included CSV exports

This is the fastest learning path.

In Power BI Desktop:

1. Get Data -> Text/CSV.
2. Import:
   - `powerbi/exports/complaints_detail.csv`
   - `powerbi/exports/monthly_metrics.csv`
   - `powerbi/exports/product_metrics.csv`
   - `powerbi/exports/ingestion_runs.csv`
   - `powerbi/exports/rejected_records.csv`
3. Open Power Query.
4. Confirm data types, especially date, decimal, boolean, and whole-number fields.
5. Rename the detail query to `Complaints`.
6. Build the date table and measures from `DAX_MEASURES.md`.

The aggregated CSVs are useful for checking your DAX results. A polished report should calculate most business metrics from the detail table and use the operational extracts on the data-quality page.

## Option B: Connect directly to MySQL

Prerequisites:

- Docker enterprise profile running
- MySQL healthy on `127.0.0.1:3306`
- `python scripts/apply_mysql_views.py` completed
- Oracle MySQL Connector/NET installed on the Windows computer

In Power BI Desktop:

1. Get Data -> MySQL database.
2. Server: `127.0.0.1:3306`
3. Database: `eci`
4. Choose Import mode.
5. Sign in with the read-only `POWERBI_USER` and `POWERBI_PASSWORD` from your local `.env`.
6. Select these views:
   - `vw_powerbi_complaints`
   - `vw_ingestion_runs`
   - `vw_rejected_records`
7. Do not use the MySQL root or application account.

The default complaint view deliberately excludes the pseudonymized customer reference and complaint narrative. The Power BI report needs metrics, not unrestricted text access.

## Model

Suggested names:

- Fact table: `Complaints`
- Operational fact: `Ingestion Runs`
- Operational fact: `Rejected Records`
- Dimension: `Date`

Create a one-to-many relationship:

```text
Date[Date] 1 -> many Complaints[date_received]
```

For a larger model, create Product, Company, State, Issue, and Status dimensions. For this capstone dataset, a clean single fact table plus Date is acceptable, provided you can explain the star-schema direction.

## Page 1: Executive Overview

KPI cards:

- Complaint Count
- Timely Response Rate
- Disputed Amount
- Company Count
- Rejection Rate

Visuals:

- Line chart: complaint count by month
- Bar chart: complaint count by product
- Bar chart: top issues
- Slicers: date, product, state, company, status

## Page 2: Product and Issue Analysis

- Matrix: product -> issue with count, timely rate, disputed amount
- 100 percent stacked bar: status by product
- Trend chart filtered by product
- Drill-through button to record detail

## Page 3: Company and Geography

- Company ranking by complaint count
- Timely response rate by company
- State bar chart or filled map
- Tooltip page showing product mix and amount

Use a bar chart instead of a map when state coverage is sparse or when location ambiguity reduces clarity.

## Page 4: Data Quality and Operations

KPI cards:

- Last Run Status
- Rows Read
- Rows Valid
- Rows Rejected
- Vectors Upserted

Visuals:

- Run history table
- Rejections by validation type
- Rejection trend over time
- Data acceptance rate

This page is a major differentiator. It shows that the project is an operated data product, not only a dashboard.

## Page 5: Record Drill-through

Display:

- Complaint ID
- Date
- Product and issue
- Company and state
- Status and timely response
- Disputed amount

The narrative remains in Streamlit, where retrieval and source evidence are controlled.

## Formatting

- Use the included `theme.json` as a starting point.
- Keep one consistent date granularity.
- Use percentage formatting for rates.
- Use currency formatting for disputed amount.
- Add meaningful titles that change with filters.
- Include an information box explaining that the dataset is synthetic.
- Include the latest refresh timestamp.

## Validation checklist

Before recording the demonstration:

- Complaint Count equals the SQL/CSV row count.
- Timely Response Rate matches a manual calculation.
- Every slicer affects the intended visuals.
- No relationship is many-to-many without a deliberate reason.
- Date sorting is chronological, not alphabetical.
- Blank amounts do not become misleading zeros at record level.
- The data-quality page displays the seven deliberate rejected rows in the reference run.
- Credentials do not appear in screenshots or the `.pbix` parameters.

## Publishing note

Power BI Desktop can demonstrate the complete report locally. Scheduled refresh from a local MySQL instance requires an on-premises gateway and additional configuration. Treat publishing and scheduled refresh as a stretch goal after the desktop report is correct.
