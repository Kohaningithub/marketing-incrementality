"""Run in the Airflow container; explicitly skipped when Airflow is absent."""
from pathlib import Path
import pytest

def test_dagbag_import():
    pytest.importorskip('airflow')
    from airflow.models.dagbag import DagBag
    root=Path(__file__).resolve().parents[1]
    bag=DagBag(dag_folder=str(root/'dags'),include_examples=False)
    assert not bag.import_errors
    dag=bag.get_dag('marketing_incrementality')
    assert dag is not None and dag.max_active_runs==1
    assert {'ingestion','quality_checks','reporting'}<=set(dag.task_ids)
