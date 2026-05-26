# LendWise Financial Data Pipeline

An end-to-end ETL system built on GCP that moves raw loan data through a cleaning, validation, and dimensional modelling layer before landing it in BigQuery for analysis.

The pipeline handles data quality issues in financial datasets — duplicate records, inconsistent column names, nullable fields that shouldn't kill a whole row, and IDs that need to be stable across runs. It runs daily on a Cloud Scheduler trigger and can also be managed through an Airflow DAG for environments that want finer orchestration control.

---

## Architecture

![LendWise pipeline architecture](images/Lendwise_Architecture.png)

## Data model

![LendWise data model](images/data_model.png)

The star schema centres on `Loan_Application_Fact_Table`, which holds the
core loan metrics and four foreign keys linking out to the dimension tables.
Each dimension captures a distinct subject — who the applicant is, where they
work, how to contact them, and who their next of kin is.


**Data flow:**

```
GCS (raw CSV files)
  └── Cloud Function (HTTP / Airflow DAG / Cloud Scheduler)
        ├── Extract   → GCSExtractor (retry + backoff)
        ├── Transform → Star schema: 7 tables
        ├── Validate  → Great Expectations quality gate
        └── Load      → BigQuery (lendwise_data) + GCS cleaned/
              └── dbt → stg_loans, fact_loan_performance, SQL analysis
```

---

## Output tables

| Table | Description |
|---|---|
| `fact_loans` | One row per application — amounts, terms, rates, estimated monthly payment |
| `fact_repayments` | Payment events with delinquency flags (>30 days overdue) |
| `dim_applicants` | Demographics, deterministic applicant ID derived from SSN hash |
| `dim_employment` | Employment type, employer, income |
| `dim_contact_info` | Address, cleaned phone number, email |
| `dim_next_of_kin` | Emergency contact details |
| `dim_credit_bureau` | FICO score, credit band (Poor → Exceptional), utilisation |

---

## Project structure

```
Lendwise_Project/
├── etl/
│   ├── extract/
│   │   └── gcs_extractor.py        # GCS downloads with retry logic
│   ├── transform/
│   │   ├── loan_applications.py    # Cleaning + all dim/fact builders
│   │   ├── loan_repayments.py      # Repayment cleaning + delinquency flag
│   │   └── credit_bureau.py        # Credit data cleaning + FICO band
│   ├── load/
│   │   ├── bigquery_loader.py      # BQ write with row count verification
│   │   └── gcs_loader.py           # Cleaned CSV upload back to GCS
│   ├── pipelines/
│   │   └── etl_pipeline.py         # Main orchestrator
│   └── utils/
│       ├── config.py               # Env var config — no hardcoded values
│       ├── logger.py               # Named loggers per module
│       └── validators.py           # Great Expectations validation suite
├── orchestration/
│   └── airflow/
│       └── lendwise_dag.py         # Airflow DAG, daily at 02:00 UTC
├── quality/
│   └── great_expectation.py/
│       └── checks.py         # Airflow DAG, daily at 02:00 UTC
├── analytics/
│   └── dbt/
│       ├── models/
│       │   ├── staging/stg_loans.sql
│       │   └── fact_loan_performance.sql
│       └── loan_tests.yml
├── tests/
│   ├── unit/
│   │   └── test_all_transforms.py  # 36 unit tests, no GCP needed
│   └── integration/
│       └── test_etl_pipeline.py
├── images/
│   ├── Lendwise_Architecture.png
│   └── data_model.png
├── sql/
│   └── lendwise_aggregation.sql
├── metrics.py
├── main.py                         # Cloud Function entry point
├── requirements.txt
├── Makefile
├── pytest.ini
└── .env.example
```

---

## Getting started

### Prerequisites

- Python 3.11+
- A GCP project with Cloud Storage and BigQuery enabled
- Service account with `Storage Object Viewer` and `BigQuery Data Editor` roles

### Setup

```bash
git clone https://github.com/Herdaybusy/Lendwise_Project.git
cd Lendwise_Project

pip install -r requirements.txt

cp .env.example .env
# fill in your GCP_PROJECT, BUCKET_NAME, BQ_DATASET

export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
```

### Run locally (no GCP credentials needed)

Set `RUN_MODE=local` in your `.env` — reads from `./data/Raw_Data/`, writes to `./data/Cleaned_Data/`.

```bash
# Dry run: transforms + validation only, nothing gets written
python -m etl.pipelines.etl_pipeline --dry-run

# Full local run
python -m etl.pipelines.etl_pipeline --mode local
```

> Always run from the project root (`Lendwise_Project/`), not from inside any subdirectory.

---

## Tests

```bash
# All tests
pytest -v

# Unit tests only (fast, no GCP)
pytest tests/unit/ -v

# With coverage
pytest tests/unit/ --cov=etl --cov-report=term-missing
```

Expected: **39 passed, 2 skipped** — the 2 skipped are Airflow tests that don't run on Windows by design.

---

## Deployment

### Cloud Function

```bash
gcloud functions deploy lendwise-etl \
  --runtime python311 \
  --trigger-http \
  --entry-point etl_pipeline \
  --source . \
  --region europe-west2 \
  --set-env-vars GCP_PROJECT=your-project,BUCKET_NAME=your-bucket,BQ_DATASET=lendwise_data
```

### Cloud Scheduler (daily at 02:00 UTC)

```bash
gcloud scheduler jobs create http lendwise-daily \
  --schedule="0 2 * * *" \
  --uri="https://your-function-url" \
  --http-method=POST \
  --location=europe-west2
```

Trigger a dry run manually:

```bash
curl -X POST https://your-function-url \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true}'
```

### BigQuery

```sql
CREATE SCHEMA `your-project.lendwise_data` OPTIONS (location = 'EU');
```

---

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GCP_PROJECT` | ✅ | — | GCP project ID |
| `BUCKET_NAME` | ✅ | — | GCS bucket name |
| `BQ_DATASET` | ✅ | — | BigQuery dataset (e.g. `lendwise_data`) |
| `RUN_MODE` | — | `cloud` | `local` or `cloud` |
| `BQ_WRITE_DISPOSITION` | — | `WRITE_TRUNCATE` | `WRITE_TRUNCATE` or `WRITE_APPEND` |
| `LOG_LEVEL` | — | `INFO` | `DEBUG` for local dev |
| `MAX_RETRIES` | — | `3` | GCS download retries |

If any required variable is missing the pipeline raises a clear `EnvironmentError` at startup — no silent fallback to a wrong GCP project.

---

## Data quality

Every run goes through a validation gate before anything reaches BigQuery. Implemented with Great Expectations:

- `application_id` non-null and unique in all dimension tables
- `loan_amount_requested_usd` positive, within $100–$500k
- FICO scores in the valid 300–850 range
- Payment amounts non-negative
- No future-dated repayment records
- Referential integrity between fact and dimension tables

Critical check failures abort the pipeline. Warnings are logged but don't block the load.

---

## Two decisions worth explaining

### Deterministic applicant IDs

The original code generated applicant IDs using `np.random.seed(42) + randint`. That produces a different ID for the same applicant on every pipeline run — which silently breaks any join using `applicant_id` as a foreign key.

Fixed by deriving the ID from a SHA-256 hash of the SSN:

```python
applicant_id = "APP-" + hashlib.sha256(ssn.encode()).hexdigest()[:8]
```

Same SSN always produces the same ID. No database lookup needed.

### Targeted null handling

`df.dropna()` with no arguments drops any row with a null in *any* column — including optional fields like `bankruptcy_flag` (no record = null, not a data error). Replaced with:

```python
df = df.dropna(subset=["application_id"])
```

Everything else is handled per-column with `errors="coerce"`, turning bad values into `NaN` instead of crashing.

---

## SQL analytics

`sql/lendwise_aggregation.sql` contains ready-to-run BigQuery queries:

- Default rate by FICO credit band
- Applications per month
- Average income by employment type
- Total repayments vs income
- Geographic distribution of applicants
- Most common next-of-kin relationships

---

## Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| Data processing | Pandas, NumPy, PyArrow |
| Cloud | Google Cloud Platform |
| Storage | Google Cloud Storage |
| Warehouse | BigQuery |
| Orchestration | Cloud Functions + Cloud Scheduler / Apache Airflow |
| Data quality | Great Expectations |
| Analytics | dbt (BigQuery adapter) |
| Testing | pytest, pytest-cov |
| CI | GitHub Actions |

---

## CI/CD

Every push to `main` or `develop` runs three GitHub Actions jobs:

1. Lint — black, isort, flake8
2. Unit tests — 80% coverage gate
3. Integration tests — full pipeline smoke test in local mode

---

Ahmed Adebisi — [Herdaybusy@gmail.com](mailto:Herdaybusy@gmail.com) — [github.com/Herdaybusy](https://github.com/Herdaybusy)