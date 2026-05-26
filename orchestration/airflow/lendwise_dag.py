"""
Airflow DAG — lendwise_etl_pipeline
-------------------------------------
Schedules the LendWise ETL to run daily at 02:00 UTC.

The pipeline runs as a single PythonOperator task. If it fails,
Airflow retries up to 3 times with 5-minute delays before marking
the run as failed and sending an alert.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago


# Default task args

default_args = {
    "owner":            "lendwise-data-team",
    "depends_on_past":  False,
    "email_on_failure": True,
    "email_on_retry":   False,
    "retries":          3,
    "retry_delay":      timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
}


# Task functions

def run_etl_pipeline(**context) -> dict:

    # This is the main task function that Airflow will execute. It initializes and runs the ETL pipeline.

    from etl.pipelines.etl_pipeline import ETLPipeline

    dag_run_conf = context.get("dag_run").conf or {}
    dry_run: bool = dag_run_conf.get("dry_run", False)

    pipeline = ETLPipeline(mode="cloud")
    result = pipeline.run(dry_run=dry_run)

    # Push result to XCom so downstream tasks or monitoring can read it
    context["ti"].xcom_push(key="pipeline_result", value=result)
    return result


def on_failure_callback(context):
    """
    Called by Airflow when a task fails after all retries.
    Add alerting here (Slack, PagerDuty, email) as needed.
    """
    task_id = context.get("task_instance").task_id
    dag_id  = context.get("dag").dag_id
    run_id  = context.get("run_id")
    error   = context.get("exception")

    print(
        f"[ALERT] Task failed: {dag_id}.{task_id} | run_id={run_id} | error={error}\n"
        "Add Slack/PagerDuty notification here."
    )


# DAG definition

with DAG(
    dag_id="lendwise_etl_pipeline",
    description="Daily ETL pipeline: GCS raw data → transforms → BigQuery",
    default_args=default_args,
    start_date=datetime(2025, 1, 1),
    schedule_interval="0 2 * * *",  # 02:00 UTC daily
    catchup=False,
    max_active_runs=1,              # Prevent overlapping runs
    tags=["lendwise", "etl", "finance", "gcp"],
) as dag:

    run_pipeline = PythonOperator(
        task_id="run_full_etl_pipeline",
        python_callable=run_etl_pipeline,
        on_failure_callback=on_failure_callback,
        provide_context=True,
        doc_md="""
        ### Run LendWise ETL Pipeline

        Extracts raw loan data from GCS, transforms it through the dimensional
        model, validates with Great Expectations, and loads to BigQuery.

        **Config options (via DAG run conf):**
        - `dry_run: true` — runs transforms and validation but skips all loads
        """,
    )

    # Single task for now. The natural next step is breaking this into
    # extract → transform → validate → load tasks for finer retry granularity.
    run_pipeline
