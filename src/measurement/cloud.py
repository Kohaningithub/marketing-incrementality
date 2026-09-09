"""Optional BigQuery execution. No network requests occur during render/validation."""
import json
import re
import uuid
from pathlib import Path

TABLES = ['raw_criteo','impressions','conversion_conflicts','conversions','clicks','events','attribution_candidates','last_click_proxy','campaign_daily','attribution_qa']

def identifiers(project, dataset):
    if not re.fullmatch(r'[a-z][a-z0-9-]{4,61}[a-z0-9]',project): raise ValueError('Invalid GCP project ID')
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,1023}',dataset): raise ValueError('Invalid BigQuery dataset')

def render(root, project, dataset):
    import sqlglot
    from sqlglot import exp
    identifiers(project,dataset)
    root=Path(root)
    out=root/'outputs/bigquery'
    out.mkdir(parents=True,exist_ok=True)
    for source in sorted((root/'sql/local').glob('*.sql')):
        statements=[]
        for tree in sqlglot.parse(source.read_text(),read='duckdb'):
            for table in tree.find_all(exp.Table):
                if table.name in TABLES:
                    table.set('catalog', exp.to_identifier(project, quoted=True))
                    table.set('db',exp.to_identifier(dataset,quoted=True))
            sql=tree.sql(dialect='bigquery',pretty=True)
            sql=re.sub(r'isfinite\(cost\)', '(NOT IS_NAN(cost) AND NOT IS_INF(cost))',sql,flags=re.I)
            sql=sql.replace('CAST(NULL AS DATETIME)','CAST(NULL AS TIMESTAMP)')
            sql=sql.replace(f'`{project}`.`{dataset}`.',f'`{project}.{dataset}.')
            # Close the single fully-qualified BigQuery identifier at the table name.
            for name in TABLES:
                sql=re.sub(r'`'+re.escape(project+'.'+dataset+'.'+name)+r'\b(?![\w`])',f'`{project}.{dataset}.{name}`',sql)
            if isinstance(tree,exp.Create) and tree.this.name in ['impressions','campaign_daily']:
                sql=sql.replace(' AS\n','\nPARTITION BY RANGE_BUCKET(relative_day, GENERATE_ARRAY(0, 32, 1))\nCLUSTER BY campaign_id, context_segment\nAS\n',1)
            statements.append(sql+';')
        (out/source.name).write_text('\n\n'.join(statements),encoding='utf-8')
    for source in sorted((root/'sql/bigquery').glob('*.sql')):
        (out/source.name).write_text(source.read_text().replace('__PROJECT__',project).replace('__DATASET__',dataset),encoding='utf-8')
    return out

def client_for(project, location):
    from google.cloud import bigquery
    return bigquery.Client(project=project,location=location)

def upload(root,project,dataset,location='US'):
    """Idempotent full snapshot loads per shard; stable source row IDs included."""
    from google.cloud import bigquery
    import pyarrow as pa
    import pyarrow.parquet as pq
    from measurement.sources import sha256
    root=Path(root)
    identifiers(project,dataset)
    lock=json.loads((root/'sources.lock.json').read_text())
    client=client_for(project,location)
    ds=bigquery.Dataset(f'{project}.{dataset}'); ds.location=location
    client.create_dataset(ds,exists_ok=True)
    paths=sorted((root/'data/raw/criteo').glob('*.parquet'))
    if len(paths)!=6: raise ValueError('All six source shards required')
    job_records=[]
    for path,meta in zip(paths,sorted(lock['criteo_files'],key=lambda f:f['path'])):
        if sha256(path)!=meta['sha256']: raise ValueError(f'Checksum changed: {path}')
        temp=root/'data/processed/cloud_upload.parquet'
        writer=None; offset=0
        try:
            for batch in pq.ParquetFile(path).iter_batches(batch_size=100000):
                tab=pa.Table.from_batches([batch])
                tab=tab.append_column('event_id',pa.array([f'{path.name}:{i}' for i in range(offset,offset+len(tab))]))
                if writer is None: writer=pq.ParquetWriter(temp,tab.schema,compression='snappy')
                writer.write_table(tab); offset+=len(tab)
        finally:
            if writer is not None: writer.close()
        table_id=f'{project}.{dataset}.raw_criteo_{path.stem}'
        config=bigquery.LoadJobConfig(source_format=bigquery.SourceFormat.PARQUET,write_disposition='WRITE_TRUNCATE')
        with temp.open('rb') as f:
            job=client.load_table_from_file(f,table_id,job_config=config,job_id='measurement_load_'+uuid.uuid4().hex)
            job.result()
        job_records.append({'table':table_id,'job_id':job.job_id,'rows':offset})
    union=' UNION ALL '.join(f'SELECT * FROM `{project}.{dataset}.raw_criteo_{p.stem}`' for p in paths)
    client.query(f'CREATE OR REPLACE VIEW `{project}.{dataset}.raw_criteo` AS {union}').result()
    participant=root/'data/processed/experiment_participants.parquet'
    if not participant.exists(): raise ValueError('Run experiment cleaning before upload')
    with participant.open('rb') as f:
        job=client.load_table_from_file(f,f'{project}.{dataset}.experiment_participants',job_config=config)
        job.result()
    (root/'outputs/bigquery_load_jobs.json').write_text(json.dumps(job_records,indent=2),encoding='utf-8')

def execute(root,project,dataset,location='US',qa_only=False,maximum_bytes_billed=5_000_000_000,dry_run=False):
    from google.cloud import bigquery
    import sqlglot
    root=Path(root)
    directory=render(root,project,dataset)
    client=client_for(project,location)
    files=[directory/'03_qa.sql'] if qa_only else [directory/'01_clean.sql',directory/'02_attribution.sql',directory/'04_experiment.sql']
    results=[]
    for path in files:
        # Sequential statements preserve dependencies and record actual query job IDs.
        for stmt in sqlglot.parse(path.read_text(),read='bigquery'):
            config=bigquery.QueryJobConfig(maximum_bytes_billed=maximum_bytes_billed,dry_run=dry_run,use_query_cache=not dry_run)
            job=client.query(stmt.sql(dialect='bigquery'),job_config=config)
            if not dry_run: job.result()
            results.append({'file':path.name,'job_id':job.job_id,'bytes_processed':job.total_bytes_processed,'dry_run':dry_run})
    name='bigquery_qa_jobs.json' if qa_only else 'bigquery_transform_jobs.json'
    (root/'outputs'/name).write_text(json.dumps(results,indent=2),encoding='utf-8')
    return results
