-- Impression-cohort metrics. Users and labeled conversions are not additive over days.
CREATE OR REPLACE TABLE daily_campaign_metrics AS
SELECT campaign_id, relative_day, COUNT(*) AS impressions,
 COUNT(DISTINCT user_id) AS unique_users, SUM(click) AS clicks,
 SUM(click)*1.0/COUNT(*) AS ctr, COUNT(DISTINCT conversion_key) AS linked_conversions,
 COUNT(DISTINCT CASE WHEN conversion_key IS NOT NULL THEN user_id END)*1.0/
 COUNT(DISTINCT user_id) AS linked_user_conversion_rate,
 SUM(transformed_cost) AS transformed_media_cost
FROM impressions GROUP BY campaign_id,relative_day;
