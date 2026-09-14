# Measurement contracts and interpretation

## A. Attribution: full release

`warehouse.clean` scans six parquet shards with a 4 GB DuckDB memory limit and one thread. Stable event identity is shard + row ordinal, scoped to the pinned revision. Duplicate replay IDs are removed; repeated users and equal-valued records are retained. Source ID equality is not proof of duplicate people or events. Binary flags, nonfinite/negative cost and impossible timelines are validated; source sentinels become null.

There are 2,910 raw conversion IDs reused across user/time pairs. Canonical conversion identity is `(conversion_id, uid, conversion_timestamp)`. The query reconstructs only the source's explicitly linked conversion paths, rather than inventing cross-advertiser relationships through a user-only join. No canonical path spans campaigns in this release.

Publisher timestamps are relative seconds, not Unix time. `floor(seconds/86400)` yields relative days 0–30. Independent click timestamp, calendar origin and timezone are unavailable. Typed UTC/geo fields stay null. The measured click is a clicked-impression indicator, so every reconstructed model is labeled **proxy**.

Eligible touches: `click=1` and `0 <= conversion_seconds - impression_seconds <= window_days*86400`, windows 1/7/14/30. First touch chooses ascending timestamp/click-position/event-ID; last chooses descending timestamp/click-position, then ascending stable event-ID. Linear assigns `1 / eligible touches`. Per-conversion weights must sum to one within tolerance 1e-8. Float accumulation can produce sub-micro-conversion differences; displayed counts round, ranking rounds credit to eight decimals to avoid meaningless float tie breaks.

Publisher attribution is the canonical maximum source flag. Latest linked impression only supplies a reporting day. The publisher benchmark is fixed, not re-windowed or represented as another vendor. First, last and linear can pick different event credits but have identical campaign totals in this single-campaign-path release.

### Denominators and reporting time

- CTR = clicked-impression indicators / impressions.
- Campaign/day `linked_user_conversion_rate` = distinct reached users with a linked conversion label / distinct reached users. Cohort labels can occur after the displayed impression day.
- Model CVR = credited conversions / impressions. A count-per-impression rate is not a unique-person conversion probability.
- Context/day `user_conversion_rate` uses distinct credited users / reached users on the selected touch day.
- Transformed CPA = sum of source transformed cost / attributed conversions; neither cost nor cpo is literal advertiser currency or sales revenue.
- Click-through conversion share = canonical conversions with at least one linked clicked impression / all canonical conversions. It equals 100% **in this selected release**, not in the advertiser's complete funnel.
- Lag quantiles: last clicked impression → conversion, and first linked impression → conversion; full canonical paths. No exact click time is reconstructed.
- Campaign ranking is descending credited conversion count with shared ranks for ties. Rank delta = proxy rank − publisher rank; a negative value means improved rank under the proxy. Small-volume campaign shifts do not establish economic value.

Conversions/users are not additive across impression cohorts; canonical conversions are counted once only at the canonical or selected-touch grain. Labels after the impression collection period are observed outcomes, not proof of ingestion lateness.

## B. Uplift: full release diagnostics

Official Criteo describes a collection of randomized incrementality tests. Full pinned release: 13,979,592 rows; treatment 11,882,655 and control 2,096,937. **The publisher's non-uniform privacy subsampling prevents recovering original population incrementality.** We preserve assignment-based ITT contrasts in the released sample; do not sell them as original business effects.

Compute treatment/control rates, absolute difference, relative difference, Newcombe score 95% CI, pooled two-proportion z-test and increments per 100k. A zero control rate makes relative lift undefined; all-zero outcomes yield p=1. A numerically underflowed tiny p is displayed `<1e-300`. Intervals assume independent observations; trial/user IDs for clustering or transport weighting are unavailable.

For f0–f11, SMD = (treatment mean − control mean) / sqrt((treatment variance + control variance)/2). Missing/nonfinite and invalid assignment/outcomes are counted explicitly. Balance is a diagnostic, not a guarantee of transportability.

85% is a **rounded release statistic**, not a verified experimental allocation contract. Its binomial check is labeled a reference comparison, not confirmatory SRM. Without original trial identifiers/assignment probabilities, retrospective sampling cannot be separated from initial randomization.

Exposure is actual effective ad exposure; assignment is auction opportunity. Exposure given treatment is 3.6037%, control 0%. Stratified outcomes by exposure are descriptive only. We skip causal IV/LATE because sampling, exclusion and monotonicity cannot be established from the anonymized file.

## C. Uplift model: deterministic subset

Memory-bounded DuckDB hash filtering scans all rows; pandas sees only the retained 2,797,402 rows. MD5 of seed + the twelve-feature vector creates groups. The first 32 bits select ~20%; the next 32 choose train/validation/test at 60/20/20. Exact feature vectors never cross splits. Original user IDs are unavailable; feature grouping is conservative and is not a recovered person identity. Covariates only determine splitting; assignment, exposure and outcomes never enter split logic.

T-learner: two HistGradientBoostingClassifier models, one per arm; 15 leaves, min leaf 200, learning rate .08, L2=1, fixed seed, no internal early stopping. Compare 60/120 iterations using validation Qini; select 60, then evaluate the test once. Single-thread source scans and two model threads limit resource use. Models and individual test predictions stay local.

For sorted top fraction q, `G(q)=sum[Y*T/p - Y*(1-T)/(1-p)]/N`, p = observed evaluation-split treatment proportion. AUUC is the exact trapezoid integral over score-block endpoints. Qini integrates `G(q)-q*G(1)`. Equal scores are averaged as blocks. Random baseline is expected random ranking, not simulated users. Treat-all endpoint is the arm-rate difference for that evaluation split. Metrics are incremental outcomes/person; charts scale by 100k. The unknown release selection mechanism limits propensity/policy interpretation.

Deciles use held-out scores, not outcome-driven segmentation; boundary ties use source IDs. Each decile includes N, actual arm outcomes/rates, observed lift and marginal Newcombe CI. No multiplicity-adjusted or population-level curve CI is claimed. Lowest predicted decile has positive observed lift: positive global Qini does not imply perfect calibration, monotonic ranking or a tested advertiser policy.

## D. Prospective readiness

`measurement.experiment_design.readiness` accepts baseline, exactly one relative/absolute positive target, allocation, alpha, desired power and total available N. It uses the two-proportion arcsine effect size and NormalIndPower, rounds required N upward per arm, and solves MDE numerically. Outputs required N, available N, achieved power and readiness. At baseline .001937588, 85:15, alpha .05, target +20%, desired .80: required total 870,047. The target is an explicit design assumption, independent of retrospective significance. No geographic clustering, repeated-look correction or business dollar return is assumed.

## E. Health and reconciliation

Daily metrics use source-relative day. The daily conversion denominator is 30-day proxy conversions placed on winning clicked-impression day; publisher-attributed numerator uses latest linked-impression day. Daily ratio changes can arise from placement definitions, not solely tracking quality. Original missing/duplicate/late events are not identifiable and remain null. Replay-key duplication, malformed canonical keys, join loss and weight conservation are observable checks.

Rolling baseline: previous seven complete non-boundary days, excluding current value; sample standard deviation; |z|≥3 means review. First/last days excluded; warmup requires seven prior observations. Constant baseline plus a deviation gets a zero-variance review, not an invented z-score. Five metric/day flags occurred; these exploratory correlated checks are not multiple-testing-adjusted or proof of an incident. Investigate traffic/campaign mix and placement definitions before escalation.

## F. Complementarity without linkage

A and B share a publisher, not known users, advertisers, campaigns or dates. Never join them. No numerical campaign attribution-versus-causal overstatement, true monetary ROAS, incremental ROAS, budget amounts, geo effects, MMM or GeoLift is reported. The original Hillstrom analysis remains supplementary only.
