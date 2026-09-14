# Resume bullets and interview explanation

Use 3–5 bullets appropriate to space. Describe implementation separately from unverified deployment.

- Built a reproducible Python/SQL advertising-measurement pipeline over 16.47M real Criteo impressions, with canonical conversion deduplication, four attribution windows, campaign reconciliation and automated QA.
- Reconciled publisher, first-click, last-click and linear credit definitions across 675 campaigns; quantified an 85% 30-day proxy-versus-publisher gap while distinguishing attribution credit from causal impact.
- Analyzed 13.98M Criteo experiment records using assignment-based contrasts, Newcombe confidence intervals, feature balance and exposure diagnostics; reported +115 conversion contrasts per 100k with explicit public-sampling limitations.
- Developed a T-learner on 2.80M real records with feature-group train/validation/test splits; evaluated held-out Qini/AUUC and treatment-effect deciles on 559k records, exposing non-monotonic targeting performance.
- Implemented prospective power/MDE planning, daily measurement-health checks, BigQuery-compatible SQL and a modular Airflow DAG; verified local execution and published an auditable GitHub Pages report.

## 60-second interview explanation

I built this project around three measurement questions: who gets attribution credit, what changes with randomized treatment assignment, and why those answers differ. I used two independent public Criteo releases, never joined them. On 16.5 million impressions, I reconstructed source-linked conversion paths and compared publisher, first-click, last-click and linear definitions across four windows. The 30-day proxy credited 85% more conversions than the publisher benchmark, but that is a definition gap—not causal overstatement. On 14 million experiment records, I estimated assignment-based conversion and visit effects with confidence intervals, checked feature balance and separated assignment from exposure. I then evaluated a T-learner on a held-out test set and built power and monitoring tools. The important judgment was recognizing public-sampling limitations, preserving null results, and refusing to invent ROI. The local pipeline ran; BigQuery and Airflow are implemented but not runtime-verified.

## 中文面试口述

我把项目围绕三个问题来做：广告拿到多少归因 credit，随机分配处理后结果改变多少，以及为什么不同测量定义会给出不同答案。我用了两份独立的真实 Criteo 数据，没有把它们拼成同一个实验。对约 1,647 万条 impression，我构建了 canonical conversion path，比较四种归因定义和四个窗口。30 天 proxy 比 publisher 多 85% credit，但我明确区分了定义差异和因果高估。另一份约 1,398 万条实验记录用于 assignment-based lift、置信区间、balance 和 exposure 检查；再用独立测试集评估 uplift 模型，同时做 power/MDE 和日级监控。最重要的是公开抽样限制、模型的非单调结果和不虚构 ROI。Python/DuckDB 全流程已运行，BigQuery 和 Airflow 只描述为已实现配置。
