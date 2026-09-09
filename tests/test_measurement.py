"""Regression checks use downloaded real records. Mutations only test failure paths."""
from pathlib import Path
import json
import ast
import duckdb
import numpy as np
import pandas as pd
import pytest
import sqlglot
from measurement.experiment import effect,design,clean_hillstrom
from measurement.cloud import render,identifiers
from measurement.monitoring import event_health

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module')
def hill():
    if not (ROOT/'data/raw/hillstrom.csv').exists(): pytest.skip('Run measurement ingest for real-data tests')
    return clean_hillstrom(ROOT)

@pytest.fixture
def db():
    source=ROOT/'data/raw/criteo/0000.parquet'
    if not source.exists(): pytest.skip('Run measurement ingest for real-data tests')
    c=duckdb.connect()
    path=source.as_posix().replace("'","''")
    c.execute(f"CREATE TABLE original AS SELECT * EXCLUDE(file_row_number), '0000.parquet:'||CAST(file_row_number AS VARCHAR) event_id FROM read_parquet('{path}',file_row_number=true) LIMIT 20000")
    c.execute('CREATE TABLE raw_criteo AS SELECT * FROM original')
    yield c
    c.close()

def run_sql(c):
    for path in sorted((ROOT/'sql/local').glob('*.sql')): c.execute(path.read_text())

def test_replay_dedup_preserves_repeat_users(db):
    db.execute('INSERT INTO raw_criteo SELECT * FROM original LIMIT 100')
    run_sql(db)
    assert db.execute('SELECT COUNT(*) FROM impressions').fetchone()[0]==20000
    assert db.execute('SELECT COUNT(*)>COUNT(DISTINCT user_id) FROM impressions').fetchone()[0]

def test_bad_timeline_is_rejected(db):
    db.execute('UPDATE raw_criteo SET conversion_timestamp=timestamp-1 WHERE conversion=1')
    run_sql(db)
    assert db.execute('SELECT COUNT(*) FROM conversions').fetchone()[0]==0
    assert db.execute('SELECT COUNT(*) FROM impressions WHERE conversion=1').fetchone()[0]==0

def test_window_and_weight_conservation(db):
    run_sql(db)
    assert db.execute('SELECT COUNT(*) FROM last_click_proxy WHERE conversion_seconds-impression_seconds NOT BETWEEN 0 AND window_days*86400').fetchone()[0]==0
    assert db.execute('SELECT COUNT(*) FROM (SELECT window_days,conversion_key FROM last_click_proxy GROUP BY ALL HAVING SUM(attribution_weight)!=1)').fetchone()[0]==0
    counts=db.execute('SELECT window_days,COUNT(*) FROM last_click_proxy GROUP BY 1 ORDER BY 1').fetchall()
    assert all(a[1]<=b[1] for a,b in zip(counts,counts[1:]))
    assert db.execute('SELECT SUM(attributed_conversions) FROM campaign_daily').fetchone()[0]==db.execute('SELECT COUNT(*) FROM last_click_proxy').fetchone()[0]
    assert db.execute('SELECT COUNT(*) FROM campaign_daily WHERE attributed_roas IS NOT NULL OR incremental_roas IS NOT NULL OR geo IS NOT NULL').fetchone()[0]==0

def test_conversion_id_collisions_do_not_merge_customers():
    source=ROOT/'data/measurement.duckdb'
    if not source.exists(): pytest.skip('Run full real-data pipeline')
    c=duckdb.connect(str(source),read_only=True)
    n=c.execute('SELECT COUNT(*) FROM conversion_conflicts').fetchone()[0]
    assert n==2910
    assert c.execute('SELECT COUNT(*) FROM conversions').fetchone()[0]==c.execute('SELECT COUNT(*) FROM (SELECT DISTINCT conversion_id,user_id,conversion_seconds FROM impressions WHERE conversion_id IS NOT NULL)').fetchone()[0]
    c.close()

def test_real_experiment_estimates(hill):
    t=hill[hill.arm=='Mens E-Mail'];c=hill[hill.arm=='No E-Mail']
    r=effect(t.conversion,c.conversion,binary=True)
    assert r['effect']==pytest.approx(267/21307-122/21306)
    assert 0<r['ci_low']<r['effect']<r['ci_high']
    rev=effect(t.revenue,c.revenue)
    assert rev['effect']==pytest.approx(.7698271558945368)
    assert len(hill)==64000 and hill.participant_id.is_unique
    assert not hill.geo_class.eq('Surburban').any()

def test_mde_monotonicity(hill):
    p0=hill[hill.arm=='No E-Mail'].conversion.mean()
    a=design(p0,21307,21306);b=design(p0,42614,42612)
    assert b['mde_absolute']<a['mde_absolute']
    assert 0<a['power_at_planned_lift']<.8
    assert a['required_treatment_n']>21307

def test_unobserved_lateness_is_not_zero(db):
    data=db.execute('SELECT event_id,timestamp FROM original LIMIT 100').fetchdf()
    result=event_health(data)
    assert result['late_event_rate'] is None and result['missing_event_rate'] is None
    # Removing an actual observed record tests manifest reconciliation.
    result=event_health(data.iloc[1:],expected_event_ids=data.event_id)
    assert result['missing_events']==1

def test_bigquery_sql_rendering():
    out=render(ROOT,'measurement-demo-2026','marketing_measurement')
    for path in out.glob('*.sql'):
        text=path.read_text()
        assert sqlglot.parse(text,read='bigquery')
        assert 'isfinite(' not in text.lower()
        assert '__PROJECT__' not in text
    clean=(out/'01_clean.sql').read_text()
    assert 'PARTITION BY RANGE_BUCKET' in clean
    assert '`measurement-demo-2026.marketing_measurement.impressions`' in clean
    assert 'CAST(NULL AS TIMESTAMP)' in clean

def test_no_sql_identifier_injection():
    with pytest.raises(ValueError): identifiers('project;DROP TABLE x','valid')
    with pytest.raises(ValueError): identifiers('valid-project','dataset`')

def test_dag_python_syntax_and_stages():
    # Static only; actual Airflow DagBag test lives in tests/test_airflow_runtime.py.
    source=(ROOT/'dags/marketing_measurement.py').read_text()
    tree=ast.parse(source)
    names={n.name for n in ast.walk(tree) if isinstance(n,ast.FunctionDef)}
    assert {'ingestion','cleaning','sql_transformation','quality_checks','experimentation','reporting','bigquery_qa'}<=names
    assert 'max_active_runs=1' in source and 'schedule=None' in source
