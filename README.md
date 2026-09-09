# Marketing Incrementality & Attribution Measurement

使用完整真实数据构建的营销衡量项目：Python 清洗、SQL 事件归因、随机实验增量分析、BigQuery 部署脚本和 Airflow DAG。所有分析输入均为真实公开记录，没有模拟 impressions、clicks、conversions、spend 或 revenue。

**先看结果：** 随项目保存的 [交互分析报告](artifacts/report.html)、[中文结果摘要](artifacts/findings.md)、[实际执行记录](docs/VALIDATION.md)。完整复现命令在下方。报告可离线打开，包含 campaign 筛选、窗口切换、实验置信区间和 QA。重新运行的结果写入 `outputs/`；使用 `python scripts/save_artifacts.py` 更新可分享快照。

**执行边界：** 本地 pipeline 已实际运行。BigQuery 和 Airflow 提供可审阅的代码、配置与验证命令；本机没有 GCP 配置或 Docker，尚未完成这两项运行验证。不要在简历中写成已上线生产系统。

## 真实数据与可回答的问题

| 数据 | 实际可用字段 | 本项目用途 | 缺失内容 |
|---|---|---|---|
| [Criteo Attribution Dataset](https://huggingface.co/datasets/criteo/criteo-attribution-dataset) | 全部六个官方 Parquet 分片；impression、点击标记、conversion ID/time、campaign、匿名上下文、变换后成本 | 事件清洗、1/7/30 天归因窗口、campaign/day/context metrics、QA | 独立 click timestamp、真实日期、geo、销售收入、随机 holdout、真实成本 |
| [Hillstrom / MineThatData](https://blog.minethatdata.com/2008/03/minethatdata-e-mail-analytics-and-data.html) | 全部 64,000 人，Mens/Womens/No-email 随机分组，14 天访问、转化、实际消费；城乡和历史购买属性 | ITT conversion/revenue lift、balance、MDE、分组异质性 | 事件时间线、邮件点击、投放成本 |

两套数据**没有关联键**。本项目不会跨数据集拼接 campaign、将 Criteo `cpo` 当销售收入，或用用户访问替代邮件点击。Criteo 是发布方抽样后的历史流量，指标只描述该发布样本，不代表完整流量的校准 KPI。

原始文件位于 `data/raw/`，不纳入 Git。`sources.lock.json` 固定 Criteo revision、每个分片的 SHA-256 和 Hillstrom 文件 SHA-256；`data/raw/manifest.json` 记录本次来源、文件大小和验证时间。Criteo 按 CC BY-NC-SA 4.0 发布。详见 [数据说明](docs/DATA.md)。

## 本地运行

需要 Python 3.11+、约 800 MB 原始下载空间，以及额外约 8–12 GB 工作空间。DuckDB 默认单线程、4 GB 内存上限，并按来源分片清洗以限制内存峰值。实际验证环境为 Windows / Python 3.14。

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[cloud,test]"
.venv/Scripts/python.exe -m measurement.cli run
.venv/Scripts/python.exe -m pytest -q
Start-Process outputs/report.html
```

macOS / Linux 将 `.venv/Scripts/python.exe` 换成 `.venv/bin/python`。请从本项目根目录运行，或使用 `--root` 指定项目根目录。完整 pipeline 会校验下载缓存，再重建结果；不会重复累加同一批数据。

单独重跑某一步：

```powershell
.venv/Scripts/python.exe -m measurement.cli ingest
.venv/Scripts/python.exe -m measurement.cli clean
.venv/Scripts/python.exe -m measurement.cli transform
.venv/Scripts/python.exe -m measurement.cli qa
.venv/Scripts/python.exe -m measurement.cli experiment
.venv/Scripts/python.exe -m measurement.cli report
```

## 输出与指标

| 输出 | 内容 |
|---|---|
| `data/measurement.duckdb` | raw views、impressions、click indicators、deduplicated conversions、统一 events view、归因表和 mart |
| `data/processed/campaign_daily.parquet` | campaign × relative day × anonymous context × window；geo 显式为空 |
| `outputs/campaign_summary.csv` | campaign 归因计数、点击数、变换成本和 transformed CPA |
| `outputs/experiment_effects.csv` | conversion/revenue/visit 的 ITT、95% CI、Holm p-values |
| `outputs/balance.csv` | 所有处理前连续特征与类别 dummy 的 standardized mean differences |
| `outputs/power_mde.csv` | 80% power MDE、20% relative-lift planning sensitivity、所需样本量 |
| `outputs/heterogeneous_effects.csv` | 城乡、历史渠道、消费分组、新客与历史品类的 effect、CI、interaction 与 FDR |
| `outputs/heterogeneity_omnibus.csv` | 各维度内 treatment effect 是否相同的 omnibus 检验 |
| `outputs/budget_decisions.csv` | 增量收入、成本盈亏平衡上限、缺失 iROAS 状态与决策限制 |
| `outputs/qa.json` | ID 冲突、join loss、窗口违规、归因守恒和数据可观测性 |

转化率分母明确区分：`conversions_per_impression` 是归因转化 / impression；`user_conversion_rate` 是单一维度单元中归因转化用户 / reached users；实验 conversion rate 是转化人数 / 随机分配人数。用户分母不能跨 day/context 直接相加。CPA 使用变换后成本，字段名显式带 `transformed_units`。

`attributed_roas`、`incremental_roas` 在公开事件 mart 中均为 NULL。Hillstrom 提供因果增量收入，但成本缺失，因此默认不生成 iROAS 排名。拥有同一实验、同一货币口径的真实成本后，可调用：

```powershell
.venv/Scripts/python.exe -m measurement.cli experiment --costs path/to/observed_campaign_costs.csv
.venv/Scripts/python.exe -m measurement.cli report
```

输入契约见 [方法与成本口径](docs/METHODOLOGY.md)。该扩展根据 iROAS 的置信下界排序；没有成本时不生成虚构排名。平均增量回报也不能直接代替边际预算响应曲线。

## 工程结构

```text
Verified publisher snapshots
  -> Python / DuckDB ingestion and cleaning
  -> canonical event and conversion identities
  -> SQL window attribution + campaign marts
  -> QA gates
  -> Python randomized experiment analysis
  -> offline report

Optional cloud path:
  verified shards -> BigQuery snapshot loads -> GoogleSQL tables/views
                  -> ASSERT quality gates -> query job audit logs

Airflow: ingestion -> cleaning -> transformation -> QA -> experimentation
         -> optional BigQuery load/transform/QA -> reporting
```

源数据是固定历史快照，DAG 默认手动触发、`catchup=False`、最多一个活动 run；自动重跑历史快照不代表实时数据。任务重试两次，失败阻断下游报告。未来接入真实事件时间和 arrival time 后，`measurement.monitoring.event_health` 可检查 late events；缺失事件需要权威完成批次清单。

## BigQuery / Airflow

完整命令和限制见 [部署说明](docs/DEPLOYMENT.md)。无需 GCP 也可先生成 GoogleSQL：

```powershell
.venv/Scripts/python.exe -m measurement.cli render-cloud --project YOUR_PROJECT_ID
```

输出到 `outputs/bigquery/`，包含 SQL 清洗、按 relative day 分区的 impressions/marts、归因和实验汇总、ASSERT QA。渲染和语法检查不等于 BigQuery 服务端执行。

## 面试表达

可以如实说明：使用真实公开广告事件和独立随机实验构建测量 pipeline；发现并修复 source conversion ID 重用导致的误合并风险；完成全量本地归因与实验分析；实现 BigQuery 加载/转换脚本与 Airflow 编排配置。

不要声称发现某个 Criteo campaign 的 last-click ROAS 高估因果 ROAS，或已经凭本项目实施预算优化。公开数据缺少支持这两个结论所需的关联实验和成本信息。详见 [可用于简历的表述](docs/RESUME.md)。
