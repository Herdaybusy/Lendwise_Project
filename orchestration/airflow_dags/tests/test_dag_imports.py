from airflow.models import DagBag
import os
import pytest


@pytest.mark.skipif(os.name == "nt", reason="Airflow not supported on Windows")
def test_dags_load_without_errors():
    from airflow.models import DagBag

    dag_bag = DagBag()
    assert len(dag_bag.import_errors) == 0
