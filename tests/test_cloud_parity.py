"""Check rendered GoogleSQL round-trip against the local SQL on real rows.

This is semantic portability coverage, not BigQuery service validation.
"""
from pathlib import Path
import duckdb
import pytest
import sqlglot
from sqlglot import exp
from measurement.cloud import render

ROOT=Path(__file__).resolve().parents[1]

def test_rendered_sql_matches_local_on_real_rows():
    source=ROOT/'data/raw/criteo/0000.parquet'
    if not source.exists(): pytest.skip('Run ingest first')
    path=source.as_posix().replace("'","''")
    setup=f"CREATE TABLE raw_criteo AS SELECT * EXCLUDE(file_row_number), '0000.parquet:'||CAST(file_row_number AS VARCHAR) event_id FROM read_parquet('{path}',file_row_number=true) LIMIT 20000"
    a=duckdb.connect();b=duckdb.connect();a.execute(setup);b.execute(setup)
    out=render(ROOT,'measurement-demo-2026','marketing_measurement')
    for filename in ['01_clean.sql','02_attribution.sql']:
        a.execute((ROOT/'sql/local'/filename).read_text())
        for tree in sqlglot.parse((out/filename).read_text(),read='bigquery'):
            if isinstance(tree,exp.Create): tree.set('properties',None)
            for table in tree.find_all(exp.Table):
                table.set('catalog',None);table.set('db',None)
            b.execute(tree.sql(dialect='duckdb'))
    for table in ['impressions','conversions','last_click_proxy','campaign_daily','attribution_qa']:
        assert a.execute(f'SELECT COUNT(*) FROM {table}').fetchone()==b.execute(f'SELECT COUNT(*) FROM {table}').fetchone()
    assert a.execute('SELECT window_days,conversion_key,event_id FROM last_click_proxy ORDER BY ALL').fetchall()==b.execute('SELECT window_days,conversion_key,event_id FROM last_click_proxy ORDER BY ALL').fetchall()
    assert a.execute('SELECT * FROM attribution_qa ORDER BY window_days').fetchall()==b.execute('SELECT * FROM attribution_qa ORDER BY window_days').fetchall()
    a.close();b.close()
