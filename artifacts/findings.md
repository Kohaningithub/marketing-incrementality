# 实际运行结果 / Marketing Incrementality

完整 Criteo 发布数据：16,468,027 impressions、5,947,563 click indicators、438,730 distinct conversions、675 campaigns。

完整 Hillstrom 随机实验：64,000 customers，14 天结果窗口。

| Campaign | Conversion lift (百分点) | 95% CI (百分点) | Incremental revenue / recipient | 95% CI |
|---|---:|---|---:|---|
| Mens E-Mail | 0.681 | [0.501, 0.864] | 0.770 | [0.485, 1.055] |
| Womens E-Mail | 0.311 | [0.150, 0.475] | 0.424 | [0.169, 0.680] |

SRM p=0.9037; 最大 |SMD|=0.0164。

处理组全部收入 / 因果增量收入：Mens 1.85x，Womens 2.54x。这不是 last-click 高估率。

ROAS / iROAS 不可识别：Criteo 无 sales revenue / holdout，Hillstrom 无 campaign cost，二者不可关联。

Local execution verified. BigQuery and Airflow runtime deployment pending.

详细交互报告：outputs/report.html。统计表、QA、图表均在 outputs/。