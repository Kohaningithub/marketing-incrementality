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
        from measurement.pipeline import ingest_all
        ingest_all(ROOT)
    @task
    def validate():
        from measurement.pipeline import validate_sources
        validate_sources(ROOT)
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
        from measurement.criteo_experiment import analyze_criteo
        analyze_criteo(ROOT)
    @task
    def reporting():
        from measurement.science_report import report
        report(ROOT)
    @task
    def attribution_and_daily_metrics():
        from measurement.reconciliation import run_sql
        run_sql(ROOT)
    @task
    def measurement_health():
        from measurement.reconciliation import health
        health(ROOT)
    @task
    def uplift_evaluation():
        from measurement.uplift_model import fit_uplift
        fit_uplift(ROOT)
    # Sequential DuckDB writers avoid database locking; no credentials in XCom.
    chain=ingestion() >> validate() >> cleaning() >> sql_transformation() >> attribution_and_daily_metrics() >> quality_checks() >> measurement_health() >> experimentation() >> uplift_evaluation()
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
