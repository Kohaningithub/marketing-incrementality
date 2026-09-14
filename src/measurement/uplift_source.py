"""Complete publisher release; checksummed files and bounded-memory scans."""
import json
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from measurement.sources import session, download, sha256, HF

LOG=logging.getLogger(__name__)
REPO='criteo/criteo-uplift'

def ingest_uplift(root):
    root=Path(root); path=root/'uplift.lock.json'
    if path.exists(): lock=json.loads(path.read_text())
    else:
        s=session()
        r=s.get(f'{HF}/api/datasets/{REPO}/revision/refs%2Fconvert%2Fparquet',timeout=30);r.raise_for_status()
        rev=r.json()['sha']
        r=s.get(f'{HF}/api/datasets/{REPO}/tree/{rev}?recursive=true',timeout=30);r.raise_for_status()
        files=[{'path':f['path'],'sha256':f['lfs']['oid'],'bytes':f['size']} for f in r.json() if f['path'].endswith('.parquet')]
        if len(files)!=4: raise ValueError('Uplift publisher layout changed; review before ingest')
        lock={'repo':REPO,'revision':rev,'expected_rows':13979592,'files':files}
        path.write_text(json.dumps(lock,indent=2)+'\n')
    def fetch(f):
        dest=root/'data/raw/uplift'/Path(f['path']).name
        download(f"{HF}/datasets/{REPO}/resolve/{lock['revision']}/{f['path']}",dest,f['sha256'])
        LOG.info('Verified uplift %s (%s bytes)',dest.name,dest.stat().st_size)
    with ThreadPoolExecutor(max_workers=2) as pool: list(pool.map(fetch,lock['files']))
    return lock

def register_uplift(con,root):
    root=Path(root); lock=json.loads((root/'uplift.lock.json').read_text())
    paths=[root/'data/raw/uplift'/Path(f['path']).name for f in lock['files']]
    if any(not p.exists() for p in paths): raise FileNotFoundError('Run ingest-uplift; all four shards are required')
    literals=','.join("'"+p.resolve().as_posix().replace("'","''")+"'" for p in paths)
    con.execute(f'''CREATE OR REPLACE VIEW uplift_raw AS SELECT * EXCLUDE(filename,file_row_number),
      regexp_extract(replace(filename,chr(92),'/'),'[^/]+$')||':'||CAST(file_row_number AS VARCHAR) AS row_id
      FROM read_parquet([{literals}],filename=true,file_row_number=true)''')
