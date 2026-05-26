from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
from etl.pipelines.etl_pipeline import ETLPipeline


def run_etl():
    pipeline = ETLPipeline()
    pipeline.run()


with DAG(
    dag_id="lendwise_etl_pipeline",
    start_date=datetime(2025, 1, 1),
    schedule_interval="@daily",
    catchup=False,
    tags=["lendwise", "etl", "finance"],
) as dag:

    etl_task = PythonOperator(task_id="run_full_etl_pipeline", python_callable=run_etl)

    etl_task
