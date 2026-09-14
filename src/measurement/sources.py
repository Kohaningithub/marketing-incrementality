"""Download real publisher data, checksum it, and record immutable provenance."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

HF = "https://huggingface.co"
REPO = "criteo/criteo-attribution-dataset"
HILL_URLS = [
    "http://www.minethatdata.com/Kevin_Hillstrom_MineThatData_E-MailAnalytics_DataMiningChallenge_2008.03.20.csv",
]

def session():
    s = requests.Session()
    s.mount("https://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])))
    return s

def sha256(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()

def download(url, path, expected=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and (expected is None or sha256(path) == expected):
        return
    part = path.with_suffix(path.suffix + ".part")
    with session().get(url, stream=True, timeout=(20, 120)) as r:
        r.raise_for_status()
        with part.open("wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                f.write(chunk)
    actual = sha256(part)
    if expected and actual != expected:
        raise ValueError(f"Checksum mismatch: {path.name}")
    part.replace(path)

def ingest(root, include_hillstrom=True):
    root = Path(root)
    raw = root / "data/raw"
    raw.mkdir(parents=True, exist_ok=True)
    lock_path = root / "sources.lock.json"
    if lock_path.exists():
        lock = json.loads(lock_path.read_text())
    else:
        s = session()
        r = s.get(f"{HF}/api/datasets/{REPO}/revision/refs%2Fconvert%2Fparquet", timeout=30)
        r.raise_for_status()
        revision = r.json()["sha"]
        r = s.get(f"{HF}/api/datasets/{REPO}/tree/{revision}?recursive=true", timeout=30)
        r.raise_for_status()
        files = [{"path": f["path"], "sha256": f["lfs"]["oid"], "bytes": f["size"]}
                 for f in r.json() if f["path"].endswith(".parquet")]
        if len(files) != 6:
            raise ValueError("Publisher shard layout changed: review before using")
        lock = {"criteo_revision": revision, "criteo_files": files}
    def get_shard(f):
        url = f"{HF}/datasets/{REPO}/resolve/{lock['criteo_revision']}/{f['path']}"
        dest = raw / "criteo" / Path(f["path"]).name
        download(url, dest, f["sha256"])
        print(f"Verified {dest.name}: {dest.stat().st_size:,} bytes", flush=True)
        return {"dataset": "criteo", "url": url, "file": str(dest.relative_to(root)), "sha256": sha256(dest), "bytes": dest.stat().st_size}
    if include_hillstrom:
        hill = raw / "hillstrom.csv"
        errors = []
        for url in [lock["hillstrom_url"]] if "hillstrom_url" in lock else HILL_URLS:
            try:
                download(url, hill, lock.get("hillstrom_sha256"))
                if not hill.read_text(encoding="utf-8-sig").lower().startswith('recency,history_segment,history,'):
                    raise ValueError("Unexpected Hillstrom schema/content")
                lock.update(hillstrom_url=url, hillstrom_sha256=sha256(hill))
                break
            except (requests.RequestException, ValueError) as exc:
                errors.append(f"{url}: {type(exc).__name__}")
        else:
            raise RuntimeError("No verified Hillstrom download: " + "; ".join(errors))
    if not lock_path.exists():
        lock_path.write_text(json.dumps(lock, indent=2), encoding="utf-8")
    with ThreadPoolExecutor(max_workers=3) as pool:
        records = list(pool.map(get_shard, lock["criteo_files"]))
    if include_hillstrom: records.append({"dataset": "hillstrom", "url": lock["hillstrom_url"], "file": "data/raw/hillstrom.csv", "sha256": sha256(hill), "bytes": hill.stat().st_size})
    manifest = {"verified_at_utc": datetime.now(timezone.utc).isoformat(), "coverage": "all six publisher attribution shards" + ("; all Hillstrom customers" if include_hillstrom else ""), "files": records}
    (raw / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
