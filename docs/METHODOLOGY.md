# Measurement definitions

## Attribution estimand

`last_click_proxy` selects the most recent **observed clicked impression** explicitly linked by the source to a canonical conversion. An eligible touch has `0 <= conversion_seconds - impression_seconds <= window_days * 86400`; the lower and upper bounds are inclusive. Windows are 1, 7 and 30 days. Ties resolve by descending source click position and then stable event ID, and are counted in QA.

Credit is one per `(window_days, conversion_key)`. Windows are alternative specifications, not additive conversions. Every winner belongs to the campaign/day/context of the selected impression; costs and impression denominators use that same impression cohort. Publisher conversion attribution is aggregated at canonical conversion level and compared to the presence of a proxy winner. `publisher_only` and `proxy_only` are scope disagreements, not demonstrated pipeline bugs or causal lift.

There is no complete cross-channel click log and no independent click time. This proxy cannot reproduce an advertiser's exact production last-click rule. A 30-day conversion label extending past the last observed impression is not necessarily late data; the source includes future outcome labels. Touch coverage near the source boundaries is incomplete. The original publisher sampling further limits population inference.

CPA = transformed impression cost / attributed conversions, in transformed source units. ROAS requires sales revenue / true ad cost. `cpo` is not revenue. Criteo attributed ROAS and iROAS are NULL.

## Randomized experiment

The experimental unit is the released customer row. Estimate intent-to-treat effects from **assignment**, using all assigned customers including nonvisitors and nonbuyers. The control group is shared by both treatment comparisons. Do not condition on engagement or conversion, which are post-treatment outcomes.

For treatment `t` and control `c`:

```
conversion_rate = converted_participants / assigned_participants
absolute_lift = mean(Y_t) - mean(Y_c)
relative_lift = absolute_lift / mean(Y_c)
incremental_outcome_in_treated_population = n_t * absolute_lift
incremental_revenue = n_t * (mean(revenue_t) - mean(revenue_c))
```

Binary effects use Newcombe score difference intervals and two-sided pooled two-proportion z-tests. Revenue effects use unadjusted differences in means and Welch t intervals, appropriate as a large-sample approximation with independent assignments; skewness and rare purchases make small-group estimates less stable. The 95% intervals are marginal. Holm p-value adjustment is applied separately within each two-campaign outcome family; conversion is primary, revenue and visit are secondary. Comparing the campaigns directly uses Mens-minus-Womens without treating their shared-control contrasts as independent.

Allocation balance uses a chi-square test against equal thirds. Feature balance uses standardized mean differences for continuous variables and one-hot encoded historical categories. Small SMDs and a nonsignificant allocation test are diagnostics, not proof that every identification assumption holds.

MDE is the positive absolute rate difference required for 80% power under a two-sided normal approximation using the arcsine effect size. It uses the observed control rate only as a planning reference. The 20% relative-lift target is an explicit design sensitivity assumption, not an observed outcome or simulated dataset. Alpha 0.05 and 0.025 rows show unadjusted and conservative two-comparison planning. This is not post-hoc "observed power" at the estimated effect.

## Heterogeneous effects

Explore urbanicity, historical purchase channel, prior spend band, new-customer status and prior Mens/Womens purchase. These are observed pre-treatment attributes. Each level compares treatment to control within that level. A level-versus-rest contrast tests whether its treatment effect differs from the disjoint complement using an independent-variance normal approximation. An inverse-variance omnibus test tests equal effects across all levels of a dimension. BH FDR is applied over all level-versus-rest tests, and separately over the omnibus family.

The segment analyses are exploratory, not preregistered policy evaluations. Do not infer heterogeneity from "significant in one segment, not significant in another." Reuse of the same experiment for selection can overstate targeting performance; validate any chosen policy in a new holdout before allocating a budget.

## Economics and allocation

The ratio of all observed treated revenue to estimated incremental revenue is a counterfactual overcounting benchmark. It is not an observed last-click inflation ratio. The observed total includes purchases that would have happened without marketing.

The public experiment lacks campaign expenditure. Incremental revenue per recipient is a break-even ad-cost ceiling before product costs and margin. It is not profit. Without observed costs, iROAS and campaign iROAS rank remain unavailable, not zero.

Optional `--costs` input is a real CSV with exactly one record per treatment arm and these columns:

| Field | Required meaning |
|---|---|
| `arm` | Exact existing treatment arm label |
| `incremental_spend` | Observed treatment ad cost minus control ad cost scaled to treatment population, positive |
| `source_reference` | Traceable campaign ledger/source reference, not a made-up URL |
| `same_experiment_dollar_units` | Boolean `True` attesting same experimental population, period and monetary units as outcomes |

The adapter treats cost as fixed and computes `incremental_total / incremental_spend` and conditional CI bounds. It ranks campaigns by the lower iROAS bound. This is an accounting extension awaiting real inputs, not a verified result for the public data. Do not substitute assumed CPM, email pricing, campaign CPO, or unrelated Criteo spend. Positive average iROAS alone does not establish profitable scale; margin, uncertainty, capacity and marginal response matter.
