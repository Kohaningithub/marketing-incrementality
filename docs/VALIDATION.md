# Validation record — 2026-09-09

## Executed locally

- Downloaded all six Criteo publisher Parquet files, verified each against its pinned SHA-256, and downloaded the complete Hillstrom CSV from the original publisher. Exact source revision, URLs and checksums: `sources.lock.json` and `data/raw/manifest.json`.
- Ran ingestion, full SQL cleaning, conversion canonicalization, attribution, campaign marts, QA, experiment analysis and report generation on Windows / Python 3.14.3. Installed package versions: `docs/environment-packages.json`. `pip check`: no broken requirements.
- Whole-release cardinalities: **16,468,027 impressions; 6,142,256 distinct released user IDs; 5,947,563 click indicators; 675 campaign IDs; 438,730 canonical conversion keys**.
- Detected **2,910 source conversion IDs reused across different user/time combinations**. Preserved them in an audit table and avoided cross-user/time merging with the composite conversion key. Canonical key duplicate count is zero.
- Zero duplicate ingestion event IDs, conversion join loss, attribution weight errors, out-of-window winners or mart reconciliation differences. All source rows passed the implemented row-validity rules. This does not imply the source contains no other data-quality problems.
- Eligible unique conversion counts by window: **228,025** at 1 day; **326,433** at 7 days; **438,730** at 30 days. These are alternative attribution specifications and must not be added together.
- Full experiment: control 21,306; Mens email 21,307; Womens email 21,387. Sample-ratio mismatch p = 0.9037; maximum absolute pre-treatment SMD = 0.01636.
- Mens conversion lift: +0.6805 percentage points, marginal 95% CI [0.5014, 0.8641]. Womens: +0.3111 percentage points, CI [0.1502, 0.4745]. Revenue effects and secondary tests are in the generated results.
- **11 automated tests passed; 1 skipped**. Coverage includes replay handling on real source rows, invalid timelines, window and weight conservation, actual ID collisions, experimental estimates, MDE monotonicity, missing-vs-unobservable monitoring, SQL identifier validation, rendered GoogleSQL syntax, local/GoogleSQL round-trip parity on real records, and DAG static structure.
- Inspected both generated chart artifacts and the HTML report. Verified campaign filtering and the 7-to-30-day window switch in the in-app browser; campaign 10341182 changes from 15,356 to 21,877 attributed conversions.

The tests intentionally alter a small set of real records to test error handling. Those modified test inputs are never used in analytical outputs. No simulated observations appear in the project results.

## Not executed

- BigQuery dataset creation, file uploads, query execution, cost billing and service-side SQL validation. The generated SQL passed parsing and a DuckDB semantic round-trip check; this is not equivalent to BigQuery execution.
- Docker image build and actual Airflow scheduling/DagBag runtime. The Airflow runtime test is explicitly skipped when Airflow is unavailable. Windows alone is not used as a substitute for its Linux runtime.
- Original late-arrival rates, missing-source event rates, true-click-time last-click attribution, campaign iROAS or optimized spend allocation: required observational fields are not in the public data.

## Practical limitations

The initial full-table window sort exceeded a 4 GB local memory budget. Cleaning now runs independently by source shard, whose names are part of the event identity, then combines records before computing conversion keys and attribution. All six shards remain included.

The event mart is a publisher-subsampled historical snapshot. The experiment is a separate randomized email test. Their estimates cannot be joined to claim campaign causal attribution, and their economics cannot be mixed. Per-source limitations and statistical assumptions are documented in `DATA.md` and `METHODOLOGY.md`.
