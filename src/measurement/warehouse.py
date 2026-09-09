from pathlib import Path
import json
import duckdb

def connect(root):
    root = Path(root)
    (root / "data/processed").mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(root / "data/measurement.duckdb"))
    con.execute("SET memory_limit = '4GB'")
    con.execute("SET threads = 1")
    con.execute("SET enable_progress_bar = false")
    con.execute("SET preserve_insertion_order = false")
    return con

def clean(root):
    root = Path(root)
    paths = [str(p.resolve()) for p in sorted((root / 'data/raw/criteo').glob('*.parquet'))]
    if len(paths) != 6:
        raise ValueError("All six verified Criteo shards required; incomplete paths bias attribution")
    con = connect(root)
    # Source file + row ordinal preserves genuine repeated users and exact-value rows.
    paths_sql = '[' + ','.join("'" + p.replace("'", "''") + "'" for p in paths) + ']'
    con.execute(f"""CREATE OR REPLACE VIEW raw_criteo AS
      SELECT * EXCLUDE(filename, file_row_number),
        regexp_extract(replace(filename, chr(92), '/'), '[^/]+$') || ':' || CAST(file_row_number AS VARCHAR) AS event_id
      FROM read_parquet({paths_sql}, filename=true, file_row_number=true)""")
    first,rest=(root / 'sql/local/01_clean.sql').read_text().split(';',1)
    # Bound window-sort memory by publisher shard. Event IDs include the shard,
    # so a replay key cannot straddle two different shards.
    for index,path in enumerate(paths):
        escaped=path.replace("'", "''")
        name=Path(path).name
        con.execute(f"""CREATE OR REPLACE VIEW raw_criteo_shard AS
          SELECT * EXCLUDE(file_row_number), '{name}:' || CAST(file_row_number AS VARCHAR) AS event_id
          FROM read_parquet('{escaped}', file_row_number=true)""")
        con.execute(first.replace('TABLE impressions AS','TABLE impressions_part AS').replace('FROM raw_criteo','FROM raw_criteo_shard'))
        if index==0:
            con.execute('CREATE OR REPLACE TABLE impressions AS SELECT * FROM impressions_part')
        else:
            con.execute('INSERT INTO impressions SELECT * FROM impressions_part')
        print(f'Cleaned source shard {index+1}/6',flush=True)
    con.execute('DROP TABLE impressions_part')
    con.execute(rest)
    print('Cleaned impressions and deduplicated conversions', flush=True)
    con.close()

def transform(root):
    root = Path(root)
    con = connect(root)
    con.execute((root / 'sql/local/02_attribution.sql').read_text())
    for table in ['conversions', 'last_click_proxy', 'campaign_daily', 'attribution_qa']:
        dest = (root / f'data/processed/{table}.parquet').resolve().as_posix().replace("'", "''")
        con.execute(f"COPY {table} TO '{dest}' (FORMAT PARQUET)")
    print('Built 1/7/30-day attribution marts', flush=True)
    con.close()

def qa(root):
    root = Path(root)
    con = connect(root)
    def scalar(q): return con.execute(q).fetchone()[0]
    raw = scalar('SELECT COUNT(*) FROM raw_criteo')
    cleaned = scalar('SELECT COUNT(*) FROM impressions')
    nconv = scalar('SELECT COUNT(*) FROM conversions')
    checks = {
        'raw_impressions': raw, 'clean_impressions': cleaned,
        'rejected_or_replayed_rows': raw - cleaned,
        'unique_users': scalar('SELECT COUNT(DISTINCT user_id) FROM impressions'),
        'campaigns': scalar('SELECT COUNT(DISTINCT campaign_id) FROM impressions'),
        'click_indicators': scalar('SELECT COUNT(*) FROM clicks'),
        'unique_conversions': nconv,
        'conversion_identity_conflicts': scalar('SELECT COUNT(*) FROM conversion_conflicts'),
        'conversion_identity_policy': 'Source conversion_id is reused across distinct users/times. Canonical key is (conversion_id,user_id,conversion_seconds); ambiguous source IDs retained in conversion_conflicts for audit.',
        'canonical_conversion_key_duplicates': scalar('SELECT COUNT(*)-COUNT(DISTINCT conversion_key) FROM conversions'),
        'source_min_seconds': scalar('SELECT MIN(impression_seconds) FROM impressions'),
        'source_max_seconds': scalar('SELECT MAX(impression_seconds) FROM impressions'),
        'duplicate_event_ids': scalar('SELECT COUNT(*) - COUNT(DISTINCT event_id) FROM impressions'),
        'conversion_join_loss': scalar('SELECT COUNT(*) FROM last_click_proxy p LEFT JOIN conversions c USING(conversion_key) WHERE c.conversion_key IS NULL'),
        'attribution_weight_errors': scalar('SELECT COUNT(*) FROM (SELECT window_days, conversion_key FROM last_click_proxy GROUP BY ALL HAVING SUM(attribution_weight) <> 1)'),
        'window_errors': scalar('SELECT COUNT(*) FROM last_click_proxy WHERE conversion_seconds - impression_seconds NOT BETWEEN 0 AND window_days * 86400'),
        'mart_conservation_error': scalar('SELECT ABS((SELECT SUM(attributed_conversions) FROM campaign_daily) - (SELECT COUNT(*) FROM last_click_proxy))'),
        'conversion_labels_after_impression_coverage': scalar('SELECT COUNT(*) FROM conversions WHERE conversion_seconds > (SELECT MAX(impression_seconds) FROM impressions)'),
        'late_event_rate': None,
        'late_event_status': 'Not observable: publisher has no arrival timestamps; local download time is not event arrival time',
        'missing_event_rate': None,
        'missing_event_status': 'Not identifiable in a publisher-subsampled historical release',
        'attribution_windows': con.execute('SELECT * FROM attribution_qa ORDER BY window_days').fetchdf().to_dict('records'),
    }
    # Save diagnostics before failing so the failed task remains inspectable.
    out = root / 'outputs'
    out.mkdir(exist_ok=True)
    (out / 'qa.json').write_text(json.dumps(checks, indent=2), encoding='utf-8')
    con.close()
    fatal = ['duplicate_event_ids', 'conversion_join_loss', 'attribution_weight_errors', 'window_errors', 'mart_conservation_error', 'canonical_conversion_key_duplicates']
    failed = [k for k in fatal if checks[k] != 0]
    if cleaned == 0 or nconv == 0: failed.append('empty_source')
    if failed: raise ValueError(f'QA failed: {failed}; see outputs/qa.json')
    print(f'QA passed: {cleaned:,} impressions; {nconv:,} unique conversions', flush=True)
    return checks
