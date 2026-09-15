# Marketing Measurement & Incrementality

[Live case study](https://kohaningithub.github.io/marketing-incrementality/) · [Methods](docs/METHODOLOGY.md) · [Validation](docs/VALIDATION.md) · [Resume / interview](docs/RESUME.md)

## Business problem

How much credit does advertising receive, what changes with treatment assignment, and why can measurement definitions disagree? Two **independent real Criteo datasets** answer complementary questions. They are never joined or treated as the same advertiser experiment.

## Measurement framework

| Capability | Question | Implementation |
|---|---|---|
| Attribution reconciliation | Who gets credit? | Publisher, first/last-click proxies, linear; 1/7/14/30-day windows |
| Incrementality | What changes with assignment? | Full-release conversion/visit contrasts, 95% CIs, balance, exposure diagnostics |
| Uplift / targeting | Who responds more? | T-learner, validation selection, held-out Qini/AUUC and deciles |
| Measurement health | Can we trust the pipeline? | Credit conservation, identity/join checks, daily rolling anomaly flags |

## Data

- [Criteo Attribution](https://huggingface.co/datasets/criteo/criteo-attribution-dataset): **16,468,027 impressions**, 6,142,256 users, 675 campaigns, 438,730 canonical conversions; all six shards.
- [Criteo Uplift](https://huggingface.co/datasets/criteo/criteo-uplift): **13,979,592 records**; all four shards for experiment diagnostics. Model uses a deterministic feature-group subset of **2,797,402** real records, with **559,064** held out for final testing.

Both releases are pinned by revision and SHA-256. **The uplift release was non-uniformly subsampled: public-sample assignment contrasts cannot recover original advertiser population incrementality.** [Provenance and licenses](docs/DATA.md).

## Architecture

Verified parquet → DuckDB event/conversion tables → seven analytical SQL modules → QA → experiment diagnostics + cached uplift evaluation → aggregate tables/figures → GitHub Pages.

Existing `src/measurement/` architecture is retained. `sql/local/` cleans events; `sql/analysis/` reconciles definitions; `sql/bigquery/` adds native cloud diagnostics. `dags/marketing_measurement.py` orchestrates reusable modules. Raw records, fitted models and individual predictions stay out of Git.

## Attribution case study

30-day last-click proxy credits **438,730** conversions versus **237,157** publisher-credited conversions: **+85.0%**, a definition gap, not causal overstatement. A 1-day window credits 228,025. The last clicked-impression lag has median 0.86 and p95 23.61 days.

No source-linked conversion path spans multiple campaigns. Thus first/last/linear campaign credit agrees within a window; publisher/window comparisons provide the actual rank instability. Among 286 campaigns meeting fixed volume thresholds, 30-day proxy versus Criteo rank correlation is **0.9247** for conversion counts (max shift **100** places; 9/10 top-10 overlap) and **0.8462** for transformed CPA (max shift **146**). Compare definitions before optimizing campaign budgets.

## Incrementality case study

Full-release conversion contrast: **+115.2 / 100k assigned participants** (95% CI **108.4–121.9**). Visit contrast: +1,034.2 / 100k. Max absolute feature SMD: 0.0488. Only 3.60% of treatment participants were exposed; exposure-only comparisons are not randomized. The rounded 85% allocation reference is not a confirmatory SRM test.

## Uplift modeling

Separate histogram boosting models for treatment/control; train 1,678,633, validation 559,705, test 559,064. Validation chose 60 iterations. Test Qini **0.00040946** and AUUC **0.00108676** in incremental conversions/person. Top-decile lift is +872.8 / 100k; effects are **not monotonic** across deciles. Use ranking as a hypothesis for a new targeting experiment, not a verified spend policy.

## Measurement health

Prior-seven-day z-scores flag **5 metric/day observations** for review. No detected replay-ID duplication, canonical join loss or attribution-weight failures. Historical lateness and missing-event rates remain null. A reusable prospective power planner needs about **870,047** participants for a +20% relative conversion lift at the observed baseline and 85:15 allocation.

## SQL / BigQuery / Airflow

**BigQuery-compatible pipeline implemented; local DuckDB execution verified.** GoogleSQL render/round-trip tests pass; BigQuery service and Airflow runtime have **not** been executed. Docker/ADC instructions: [deployment guide](docs/DEPLOYMENT.md). Pages displays static evidence and does not host BigQuery or schedule Airflow.

## Reproduce locally

Python 3.11+; ~1.24 GB source downloads and additional space for the local database/model artifacts. Use a machine with sufficient memory/disk (8+ GB RAM, 12+ GB free disk suggested; actual requirements vary).

```bash
python -m venv .venv
# Windows: .venv/Scripts/activate ; macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[cloud,test]"
python -m measurement.cli run
python -m pytest -q
python scripts/save_artifacts.py
python -m http.server 8766 --bind 127.0.0.1 --directory artifacts
```

Open `http://127.0.0.1:8766/report.html`. No GCP account required. `run` verifies cached source hashes and reuses versioned completed stages. `--force` rebuilds local aggregate stages. Uplift model cache keys include model code, source lock and settings; use `settings.json` to change model settings; `ranking.settings.json` controls the independent campaign volume screen. `python -m pytest tests/test_science.py -q` runs small deterministic fixtures with no downloads.

## Limitations / key takeaways

Click time is a labeled impression-time proxy; costs are transformed, not dollars. No actual ROAS/iROAS, same-campaign causal reconciliation, geo effects, MMM or GeoLift can be established from these columns. Public release sampling, missing original experiment IDs and marginal intervals limit causal transport. Anonymous feature groups have no demographic meaning. [Hillstrom](https://kohaningithub.github.io/marketing-incrementality/hillstrom_report.html) remains a separate supplementary example.

**A credible measurement system explains disagreement, quantifies uncertainty and keeps unobserved quantities unavailable.**
