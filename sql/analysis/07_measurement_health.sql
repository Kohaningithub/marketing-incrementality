CREATE OR REPLACE TABLE daily_measurement AS
WITH traffic AS (
 SELECT relative_day,COUNT(*) AS impressions,COUNT(DISTINCT user_id) AS unique_users,
 SUM(click) AS clicks,SUM(click)*1.0/COUNT(*) AS ctr,SUM(transformed_cost) AS transformed_cost,
 (COUNT(*)-COUNT(DISTINCT event_id))*1.0/COUNT(*) AS replay_duplicate_rate,
 SUM(CASE WHEN conversion=1 AND conversion_key IS NULL THEN 1 ELSE 0 END)*1.0/COUNT(*) AS malformed_conversion_key_rate
 FROM impressions GROUP BY relative_day
), credits AS (
 SELECT relative_day,COUNT(*) AS attributed_conversions FROM last_click_proxy WHERE window_days=30 GROUP BY relative_day
), published AS (
 SELECT relative_day,COUNT(*) AS publisher_conversions FROM publisher_attribution GROUP BY relative_day
)
SELECT t.*,COALESCE(c.attributed_conversions,0) AS conversions,
 COALESCE(p.publisher_conversions,0) AS attributed_conversions,
 COALESCE(p.publisher_conversions,0)*1.0/NULLIF(c.attributed_conversions,0) AS attribution_rate,
 CAST(NULL AS DOUBLE) AS original_missing_event_rate,
 CAST(NULL AS DOUBLE) AS original_duplicate_event_rate,
 CASE WHEN t.relative_day IN (SELECT MIN(relative_day) FROM traffic UNION ALL SELECT MAX(relative_day) FROM traffic)
 THEN 1 ELSE 0 END AS boundary_day
FROM traffic t LEFT JOIN credits c ON t.relative_day=c.relative_day LEFT JOIN published p ON t.relative_day=p.relative_day;
