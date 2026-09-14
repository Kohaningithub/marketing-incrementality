# Incremental upgrade: September 2026

Inspection covered all tracked code, SQL, tests, generated aggregate/QA tables, figure assets, the HTML report generator, documentation, packaging, Docker/DAG and Pages workflow. There are no notebooks or separate frontend build. The existing standalone project and public URL are retained.

Reuse: verified six-shard attribution cache, source-row event IDs, composite conversion keys, shard-bounded DuckDB cleaning, Newcombe binary intervals, BigQuery rendering/loading, Hillstrom supplement, static artifact publishing.

Gaps: main causal example was Hillstrom; no first/linear attribution, 14-day window, reconciliation/rank diagnostics, real Criteo uplift, held-out targeting evaluation, reusable readiness interface, or daily statistical monitoring. Most original tests need downloaded data.

Plan: (1) additive attribution SQL and tests, (2) pinned full Criteo Uplift ingest and full-data diagnostics, (3) deterministic train/validation/test uplift benchmark, (4) readiness and health, (5) integrate cloud/DAG, (6) run and inspect all feasible analyses, (7) update existing report/README and publish to the same Pages URL.

Early integrity finding: all observed canonical conversion paths in the existing full release belong to one campaign. First/last/linear campaign totals may therefore agree exactly; this is a result to explain, not an invitation to invent cross-campaign paths. User-only joins could connect unrelated advertisers. Source-linked paths are preserved.

Execution boundary: BigQuery and Airflow require unavailable runtimes/credentials; local execution and offline SQL parity tests remain the verified implementation mode. The uplift publisher explicitly warns that release subsampling prevents recovery of the original business incrementality level. No A/B dataset join or exposed-only causal comparison is permitted.
