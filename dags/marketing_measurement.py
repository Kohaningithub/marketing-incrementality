"""Historical snapshot pipeline. Manual by default; no fake live-event schedule."""
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
from airflow.sdk import dag, task

ROOT=Path(os.getenv('MEASUREMENT_ROOT','/opt/project'))
BACKEND=os.getenv('MEASUREMENT_BACKEND','local')
if BACKEND not in ('local','bigquery'):
    raise ValueError('MEASUREMENT_BACKEND must be local or bigquery')

def cloud_args():
    return dict(root=ROOT,project=os.environ['GCP_PROJECT_ID'],dataset=os.getenv('BQ_DATASET','marketing_measurement'),location=os.getenv('BQ_LOCATION','US'))

@dag(dag_id='marketing_incrementality',schedule=None,
     start_date=datetime(2026,1,1,tzinfo=timezone.utc),catchup=False,max_active_runs=1,
     default_args={'retries':2,'retry_delay':timedelta(minutes=2),'execution_timeout':timedelta(hours=1)},
     tags=['real-data','attribution','experimentation'])
def marketing_measurement():
    @task
    def ingestion():
        from measurement.sources import ingest
        ingest(ROOT)
    @task
    def cleaning():
        from measurement.warehouse import clean
        clean(ROOT)
    @task
    def sql_transformation():
        from measurement.warehouse import transform
        transform(ROOT)
    @task
    def quality_checks():
        from measurement.warehouse import qa
        qa(ROOT)
    @task
    def experimentation():
        from measurement.experiment import analyze
        analyze(ROOT)
    @task
    def reporting():
        from measurement.reporting import report
        report(ROOT)
    chain=ingestion() >> cleaning() >> sql_transformation() >> quality_checks() >> experimentation()
    if BACKEND=='bigquery':
        @task
        def bigquery_ingestion():
            from measurement.cloud import upload
            upload(**cloud_args())
        @task
        def bigquery_transformation():
            from measurement.cloud import execute
            execute(**cloud_args())
        @task
        def bigquery_qa():
            from measurement.cloud import execute
            execute(**cloud_args(),qa_only=True)
        chain=chain >> bigquery_ingestion() >> bigquery_transformation() >> bigquery_qa()
    chain >> reporting()

marketing_measurement()
