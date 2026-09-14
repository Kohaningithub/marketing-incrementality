# Data provenance and cleaning decisions

The main project uses two independent Criteo releases. All attribution rows and all uplift rows are processed for aggregate statistics. Uplift modeling uses a clearly labeled deterministic ~20% feature-group sample. No synthetic analytical observations, fabricated event times, assumed costs or invented revenue are used. Hand-authored fixtures exist only in unit tests. Hillstrom is supplementary.

## Criteo Attribution

Publisher: [Criteo dataset card](https://huggingface.co/datasets/criteo/criteo-attribution-dataset). Research: [Diemert et al., Attribution Modeling Increases Efficiency of Bidding in Display Advertising](https://arxiv.org/abs/1707.06409). Source and derived data extracts retain [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/); transformations here consist of deduplication, normalization, joins, and aggregation. No endorsement is implied.

Each released row describes an impression and associated outcome labels. Time is relative to the release origin, not a Unix epoch. Click is an indicator; an independent click event timestamp is absent. `cost` and `cpo` are transformed monetary fields; neither is sales revenue. Category semantics are undisclosed. The publisher subsampled the traffic.

Actual profiling, rather than rounded dataset-card counts, determines the reported cardinalities. The release contains repeated numeric conversion IDs with distinct user/time combinations. The pipeline retains a diagnostic `conversion_conflicts` table and defines the canonical conversion key as `(conversion_id, uid, conversion_timestamp)`. This is a conservative observed-identity policy, not proof of underlying real-world order identity. Repeated source IDs must not silently merge different observed customers.

An impression has no publisher event ID. Its stable ingestion key is `publisher_shard_filename:zero_based_row_number`, tied to the locked source revision. This removes ingestion replays without collapsing distinct impressions or repeated users. It cannot identify duplicates already embedded in the publisher source. Exact-value duplicate rows are not assumed to be invalid events.

Conversion `-1` sentinels become NULL. Invalid binary flags, negative/non-finite costs, missing user/campaign IDs, negative impression times and impossible conversion timelines are rejected by SQL. Original records remain available in the raw files. Derived IDs and typed NULL columns are schema metadata, not generated behavioral data.

All temporal metrics use observed relative seconds and `floor(seconds/86400)` day indices. `event_timestamp_utc` remains typed NULL. A real UTC mapping requires a verified source origin; assigning 1970 or a guessed calendar date would fabricate observations. The click view preserves the click indicator and its parent impression; click time stays NULL.

## Criteo Uplift

Publisher: [Criteo HF release](https://huggingface.co/datasets/criteo/criteo-uplift); [research description](https://ailab.criteo.com/criteo-uplift-prediction-dataset/). CC BY-NC-SA 4.0 applies to source/derived data; retain attribution and the noncommercial/share-alike terms. No endorsement implied.

Exact release: 13,979,592 rows, 12 features f0–f11, treatment, exposure, visit, conversion. The older research page's rounded row/feature count differs; the actual pinned HF schema and row count determine this project's coverage. **The release was non-uniformly subsampled for privacy; original advertiser population incrementality cannot be recovered.** No campaign/date/geo/spend/revenue or trial ID linkage is available.

Full diagnostics use all rows. Modeling retains 2,797,402 real records by deterministic feature-vector hash (not random fake data); train 1,678,633, validation 559,705, test 559,064. Native participant IDs are absent; source shard/ordinal is provenance only. Equal-feature groups remain in one split but are not assumed to identify a real person.

## Pinned source revisions

- Attribution: `a8bfbf89a613394ee996f511f029be3adce84906`; six converted parquet files, SHA-256 in `sources.lock.json`.
- Uplift: `a2858f3f05e3f8602c1d57db0217df40139e1c4b`; four converted parquet files, SHA-256 in `uplift.lock.json`.

Downloads are cached and checksum-verified, with retry/backoff on HTTPS. Raw files and individual model predictions are excluded from Git; published tables/figures contain aggregates only. The website and report are derived noncommercial portfolio analyses subject to the data license.

## Hillstrom (supplementary)

Publisher: [Kevin Hillstrom's MineThatData challenge](https://blog.minethatdata.com/2008/03/minethatdata-e-mail-analytics-and-data.html). The source describes randomized Mens email, Womens email and no-email arms, tracked for 14 days, with actual purchase amounts and prior customer attributes.

The original download endpoint is HTTP; its HTTPS endpoint failed certificate validation during this run. The project downloads the original publisher CSV over HTTP, records the SHA-256, and pins that checksum for subsequent runs. It does not disable TLS verification. No separate explicit data redistribution license was identified on the source page; raw data are downloaded on demand and excluded from Git.

The original spelling `Surburban` is normalized to `Suburban`, retaining `zip_code` alongside the normalized `geo_class`. This field is urbanicity, not ZIP geography or randomized geo treatment. `segment` becomes `arm`; `spend` becomes `revenue` because it is the customer's observed outcome purchase amount, not advertising expenditure.

There is no native customer ID. A stable `hillstrom:row_ordinal` key prevents processing replays. Identical customers' released attributes must not be deduplicated as though they identify a person. The pipeline retains all 64,000 participants and validates binary outcomes, nonnegative revenue and conversion/revenue/visit consistency.

## No cross-source linkage

The two sources demonstrate complementary measurement components. They are never joined. Neither common column labels nor shared marketing vocabulary establishes shared customers, advertisers, campaigns, time periods, or experimental units.
