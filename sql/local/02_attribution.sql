-- This is last OBSERVED CLICKED IMPRESSION, not a recovered exact click time.
-- Explicit conversion links avoid inventing advertiser/user cross-campaign joins.
CREATE OR REPLACE TABLE attribution_candidates AS
SELECT w.window_days, c.conversion_key, c.conversion_id, c.user_id, c.conversion_seconds,
       c.publisher_attribution, i.event_id, i.campaign_id, i.relative_day,
       i.context_segment, i.impression_seconds, i.click_pos,
       ROW_NUMBER() OVER (
         PARTITION BY w.window_days, c.conversion_key
         ORDER BY i.impression_seconds DESC, i.click_pos DESC, i.event_id
       ) AS touch_rank,
       COUNT(*) OVER (PARTITION BY w.window_days, c.conversion_key, i.impression_seconds) AS timestamp_ties
FROM conversions c JOIN impressions i
  ON c.conversion_key = i.conversion_key
CROSS JOIN (VALUES (1), (7), (14), (30)) AS w(window_days)
WHERE i.click = 1 AND c.conversion_seconds - i.impression_seconds
      BETWEEN 0 AND w.window_days * 86400;

CREATE OR REPLACE TABLE last_click_proxy AS
SELECT *, 1.0 AS attribution_weight FROM attribution_candidates WHERE touch_rank = 1;

CREATE OR REPLACE TABLE campaign_daily AS
WITH traffic AS (
  SELECT campaign_id, relative_day, context_segment,
         COUNT(*) AS impressions, SUM(click) AS clicks,
         COUNT(DISTINCT user_id) AS reached_users,
         SUM(transformed_cost) AS transformed_spend
  FROM impressions GROUP BY campaign_id, relative_day, context_segment
), attributed AS (
  SELECT window_days, campaign_id, relative_day, context_segment,
         COUNT(*) AS attributed_conversions, COUNT(DISTINCT user_id) AS converted_users
  FROM last_click_proxy GROUP BY window_days, campaign_id, relative_day, context_segment
)
SELECT t.*, w.window_days, CAST(NULL AS VARCHAR) AS geo,
       COALESCE(a.attributed_conversions, 0) AS attributed_conversions,
       COALESCE(a.converted_users, 0) AS converted_users,
       COALESCE(a.attributed_conversions, 0) * 1.0 / NULLIF(t.impressions, 0) AS conversions_per_impression,
       COALESCE(a.converted_users, 0) * 1.0 / NULLIF(t.reached_users, 0) AS user_conversion_rate,
       t.transformed_spend / NULLIF(a.attributed_conversions, 0) AS cpa_transformed_units,
       CAST(NULL AS DOUBLE) AS attributed_roas,
       CAST(NULL AS DOUBLE) AS incremental_roas,
       'Unavailable: no sales revenue or linked randomized holdout; cost is transformed' AS roas_status
FROM traffic t CROSS JOIN (VALUES (1), (7), (14), (30)) AS w(window_days)
LEFT JOIN attributed a ON t.campaign_id = a.campaign_id AND t.relative_day = a.relative_day
  AND t.context_segment = a.context_segment AND w.window_days = a.window_days;

CREATE OR REPLACE TABLE attribution_qa AS
SELECT w.window_days, COUNT(*) AS observed_conversions,
       SUM(CASE WHEN p.conversion_id IS NULL THEN 1 ELSE 0 END) AS no_eligible_observed_touch,
       SUM(CASE WHEN c.publisher_attribution = 1 AND p.conversion_id IS NULL THEN 1 ELSE 0 END) AS publisher_only,
       SUM(CASE WHEN c.publisher_attribution = 0 AND p.conversion_id IS NOT NULL THEN 1 ELSE 0 END) AS proxy_only,
       SUM(CASE WHEN p.timestamp_ties > 1 THEN 1 ELSE 0 END) AS winner_timestamp_ties
FROM conversions c CROSS JOIN (VALUES (1), (7), (14), (30)) AS w(window_days)
LEFT JOIN last_click_proxy p ON c.conversion_key = p.conversion_key AND w.window_days = p.window_days
GROUP BY w.window_days;
