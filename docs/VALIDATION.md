# Execution and validation record

Run date: 2026-09-14. Local Windows / Python 3.14.3. Package snapshot: `environment-packages.json`.

## Executed

- Official attribution six-shard SHA-256 verification; all 16,468,027 impressions cleaned. 6,142,256 users, 5,947,563 clicked-impression indicators, 675 campaigns, 438,730 canonical conversions.
- Four attribution windows and all seven `sql/analysis/` modules executed in DuckDB. Per-model conversion credits conserve to tolerance 1e-8. 2,910 reused raw IDs handled by canonical user/time keys. Zero replay IDs, canonical duplicates, join loss, window errors and mart mismatch.
- Full four-shard uplift release verified: 13,979,592 records. Full ITT, SMD, missing, exposure and readiness outputs written. No invalid assignment/outcome rows or missing/nonfinite features.
- Actual T-learner fit: 2,797,402 retained real records; train 1,678,633; validation 559,705; test 559,064. Tested 60/120 iterations on validation only; selected 60. Test Qini .0004094591274, AUUC .001086762266. Real fitted models/predictions retained locally.
- Unified `python -m measurement.cli run` completed end to end; source hash verification and all completed-stage/model caches reused on a subsequent pass (about 10 seconds in this environment).
- `python -m pytest -q`: **19 passed, 1 skipped**. The skipped test requires Airflow DagBag; Airflow is absent. Eight new offline tests cover eligibility boundaries, first/last/linear, identity collisions/replays, daily aggregation, binary intervals, power inputs, anomaly leakage, Qini math, SQL round-trip parity and DAG stages. Legacy tests additionally use actual local source rows; they skip cleanly if raw data are absent. No test downloads data.
- GoogleSQL rendering parsed successfully; local → GoogleSQL → DuckDB round-trip results match on hand-authored unit fixtures for all seven analytical SQL modules, including exact quantiles. This is a portability check, not a remote BigQuery dry run.
- `python scripts/validate_artifacts.py` passed: aggregate totals, rate/CI identities, split accounting, campaign credit reconciliation, curve identities and every local report resource link.
- Static report, eight PNG figure groups and downloadable aggregate CSVs generated. Browser campaign filtering, publisher switch and empty result checked. Desktop and 390px mobile layout inspected; no browser console errors observed during the interaction checks.

## Not executed

- **BigQuery service execution: no.** No configured GCP credentials; no load/query jobs claimed.
- **Airflow scheduler / Docker deployment: no.** No local Airflow/Docker runtime. Python AST checks pass; the runtime DagBag test is explicitly skipped.
- No advertiser targeting rollout, budget allocation experiment or production streaming event monitoring.

## Re-run commands

```bash
python -m measurement.cli run
python -m pytest -q
python -m measurement.cli render-cloud --project measurement-demo-2026
python scripts/save_artifacts.py
```

`measurement-demo-2026` is a render-only example identifier. For real cloud jobs, follow `DEPLOYMENT.md` with your own project and ADC. The report's execution-status labels deliberately stay unverified until actual service evidence is available.
