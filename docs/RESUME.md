# Resume / interview positioning

## Current, verified scope

**Marketing Incrementality & Attribution Measurement** — Python, SQL, DuckDB, Experimentation; BigQuery & Airflow deployment configuration

- Built and ran a real-data measurement pipeline across 16.47M advertising impressions and 64K randomized experiment participants; implemented event cleaning, canonical conversion identities, 1/7/30-day attribution windows, and campaign/day/context reporting.
- Identified 2,910 reused source conversion IDs and prevented cross-user/time merges with composite conversion keys; reconciled attribution weights, window eligibility, conversion joins and campaign marts with automated QA.
- Estimated intent-to-treat conversion and revenue lift, 95% confidence intervals, covariate balance, power/MDE and audience heterogeneity; prepared BigQuery load/transformation scripts and an Airflow DAG with retries and reporting gates.

Keep cloud status explicit until BigQuery jobs and the Airflow DAG have actually run. Do not imply the independent event and experiment datasets are linked.

## 中文面试讲法

这个项目的重点是“归因与因果的区别”，以及在真实数据不完整的条件下如何保证工程和统计结果可信。

1. 数据方面：全部输入来自公开真实数据。广告事件数据没有随机 holdout；随机邮件实验没有点击时间线和投放成本。因此我用两条独立分析路径覆盖不同能力，而不是把不存在的关系拼接出来。
2. 清洗方面：全量 QA 发现 2,910 个 conversion ID 在不同用户/时间中重复。直接 group by conversion_id 会误合并；我改用组合键并保存冲突审计。Impression 的来源行键用于防止重复 ingestion，不用于声称恢复真实 user identity。
3. 实验方面：以随机 assignment 为依据做 ITT，不筛掉没有点击或访问的人。男女装邮件分别提高 conversion rate 约 0.681 / 0.311 个百分点；新客、历史渠道和城乡差异通过 interaction tests 和多重检验校正检查。
4. 商业方面：处理组全部收入相对因果增量收入约为 1.85x / 2.54x，但不能将它称作 last-click 高估率。没有真实投放成本就不填 ROAS，也不假装已经实现 budget optimization。
5. 工程方面：本地 SQL/分析已运行；BigQuery 和 Airflow 的代码配置准备完毕。未来真实部署后，再补充 job IDs、运行日志、数据新鲜度和故障恢复证据。

## Do not claim yet

- Production BigQuery deployment, live Airflow operation or continuous monitoring.
- Campaign-level causal ROAS from the Criteo event release.
- Exact last-click timestamp reconstruction, real geographic targeting from anonymized Criteo categories, or actual observed late-arrival rates.
- Budget savings, profitability improvement or experimentally validated targeting policy from this offline analysis.
