CREATE OR REPLACE TABLE model_credits AS
SELECT 'last_click_proxy' AS model,* FROM last_click_attribution
UNION ALL SELECT 'first_click_proxy',* FROM first_click_attribution
UNION ALL SELECT 'linear_proxy',* FROM linear_attribution
UNION ALL SELECT 'publisher',w.window_days,p.* FROM publisher_attribution p
CROSS JOIN (VALUES (1),(7),(14),(30)) AS w(window_days);

CREATE OR REPLACE TABLE window_comparison AS
WITH totals AS (
 SELECT model,window_days,SUM(attribution_weight) AS credited_conversions FROM model_credits GROUP BY model,window_days
), benchmark AS (SELECT COUNT(*) AS benchmark_conversions FROM publisher_attribution)
SELECT t.*,b.benchmark_conversions,
 t.credited_conversions-b.benchmark_conversions AS absolute_difference,
 100.0*(t.credited_conversions-b.benchmark_conversions)/NULLIF(b.benchmark_conversions,0) AS percentage_difference,
 t.credited_conversions-LAG(t.credited_conversions) OVER(PARTITION BY model ORDER BY window_days) AS additional_vs_previous_window
FROM totals t CROSS JOIN benchmark b;
