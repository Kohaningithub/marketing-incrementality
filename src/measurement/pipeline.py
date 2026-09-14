"""Versioned stages for the local snapshot; no analysis requires a cloud account."""
import hashlib
import json
import logging
from pathlib import Path
import pyarrow.parquet as pq

LOG = logging.getLogger(__name__)

def ingest_all(root):
    from measurement.sources import ingest
    from measurement.uplift_source import ingest_uplift
    ingest(root, include_hillstrom=False)
    ingest_uplift(root)

def validate_sources(root):
    root=Path(root)
    counts={}
    for name,expected,shards in [('criteo',16468027,6),('uplift',13979592,4)]:
        paths=sorted((root/'data/raw'/name).glob('*.parquet'))
        if len(paths)!=shards: raise ValueError(f'{name}: expected {shards} verified source files')
        counts[name]=sum(pq.ParquetFile(p).metadata.num_rows for p in paths)
        if counts[name]!=expected: raise ValueError(f'{name}: source row count changed')
    LOG.info('Validated source counts: %s',counts)
    return counts

def cached_stage(root,name,callback,inputs,outputs,force=False):
    root=Path(root);cache=root/'data/processed'/f'stage_{name}.json'
    h=hashlib.sha256()
    for rel in inputs:
        for path in sorted(root.glob(rel)):
            h.update(str(path.relative_to(root)).encode());h.update(path.read_bytes())
    # Files are checksum-verified by ingestion; metadata also invalidates accidental replacements.
    for path in sorted((root/'data/raw').glob('*/*.parquet')):
        h.update(f'{path.name}:{path.stat().st_size}:{path.stat().st_mtime_ns}'.encode())
    key=h.hexdigest()
    if not force and cache.exists() and json.loads(cache.read_text()).get('key')==key and all((root/p).exists() for p in outputs):
        LOG.info('Reusing verified %s stage',name);return False
    callback(root)
    cache.parent.mkdir(parents=True,exist_ok=True)
    cache.write_text(json.dumps({'key':key,'outputs':outputs},indent=2))
    return True

def run(root,force=False):
    from measurement.warehouse import clean,transform,qa
    from measurement.reconciliation import run_sql,health,EXPORT
    from measurement.criteo_experiment import analyze_criteo
    from measurement.uplift_model import fit_uplift
    from measurement.science_report import report
    root=Path(root);ingest_all(root);validate_sources(root)
    rebuilt=cached_stage(root,'clean',clean,['src/measurement/warehouse.py','sql/local/01_clean.sql','sources.lock.json'],['data/measurement.duckdb'],force)
    cached_stage(root,'attribution',lambda r:(transform(r),run_sql(r)),['sql/**/*.sql','src/measurement/reconciliation.py','src/measurement/warehouse.py','sources.lock.json'],['outputs/reconciliation_summary.json']+[f'outputs/tables/{n}.csv' for n in EXPORT],force or rebuilt)
    qa(root);health(root)
    cached_stage(root,'experiment',analyze_criteo,['src/measurement/criteo_experiment.py','src/measurement/experiment_design.py','uplift.lock.json'],['outputs/criteo_experiment_summary.json','outputs/tables/criteo_itt.csv','outputs/tables/experiment_readiness.csv','outputs/tables/criteo_feature_balance.csv','outputs/tables/criteo_exposure.csv'],force)
    fit_uplift(root);report(root)
