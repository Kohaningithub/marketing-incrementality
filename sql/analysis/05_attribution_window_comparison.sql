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


-- Publisher attribution is a fixed supplied flag, with unknown native eligibility/window.
-- NULL is deliberate: do not retrofit an observed-click eligibility contract to the publisher.
CREATE OR REPLACE TABLE attribution_reconciliation AS
WITH eligible AS (
 SELECT window_days, COUNT(DISTINCT conversion_key) AS eligible_conversions
 FROM attribution_candidates GROUP BY window_days
), observed AS (SELECT COUNT(*) AS observed_conversions FROM conversions)
SELECT w.model AS method,w.window_days,
 CASE WHEN w.model='publisher' THEN CAST(NULL AS BIGINT) ELSE COALESCE(e.eligible_conversions,0) END AS eligible_conversions,
 w.credited_conversions AS attributed_conversions,o.observed_conversions,
 w.credited_conversions/NULLIF(o.observed_conversions,0) AS share_of_observed_conversions,
 w.absolute_difference AS difference_vs_criteo,w.percentage_difference AS pct_difference_vs_criteo,
 CASE WHEN w.model='publisher' THEN 'Fixed source flag; native window and eligibility unavailable'
 ELSE 'Observed clicked-impression proxy eligibility' END AS eligibility_definition
FROM window_comparison w LEFT JOIN eligible e ON w.window_days=e.window_days CROSS JOIN observed o;
