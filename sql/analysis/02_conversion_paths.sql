-- Use source-linked user/conversion paths, not a user-only join across advertisers.
CREATE OR REPLACE TABLE conversion_paths AS
SELECT c.conversion_key, c.user_id, c.conversion_seconds, c.publisher_attribution,
 MIN(i.campaign_id) AS campaign_id, COUNT(DISTINCT i.campaign_id) AS campaign_count,
 COUNT(*) AS linked_impressions, SUM(i.click) AS linked_clicks,
 MIN(i.impression_seconds) AS first_impression_seconds,
 MAX(i.impression_seconds) AS last_impression_seconds,
 MIN(CASE WHEN i.click=1 THEN i.impression_seconds END) AS first_clicked_impression_seconds,
 MAX(CASE WHEN i.click=1 THEN i.impression_seconds END) AS last_clicked_impression_seconds
FROM conversions c JOIN impressions i ON c.conversion_key=i.conversion_key AND c.user_id=i.user_id
GROUP BY c.conversion_key,c.user_id,c.conversion_seconds,c.publisher_attribution;

CREATE OR REPLACE TABLE conversion_lag_quantiles AS
SELECT 'last_clicked_impression_to_conversion' AS lag_definition,
 COUNT(*) AS conversions, MEDIAN((conversion_seconds-last_clicked_impression_seconds)/86400.0) AS median_days,
 QUANTILE_CONT((conversion_seconds-last_clicked_impression_seconds)/86400.0,.75) AS p75_days,
 QUANTILE_CONT((conversion_seconds-last_clicked_impression_seconds)/86400.0,.90) AS p90_days,
 QUANTILE_CONT((conversion_seconds-last_clicked_impression_seconds)/86400.0,.95) AS p95_days
FROM conversion_paths WHERE last_clicked_impression_seconds IS NOT NULL
UNION ALL
SELECT 'first_linked_impression_to_conversion',COUNT(*),
 MEDIAN((conversion_seconds-first_impression_seconds)/86400.0),
 QUANTILE_CONT((conversion_seconds-first_impression_seconds)/86400.0,.75),
 QUANTILE_CONT((conversion_seconds-first_impression_seconds)/86400.0,.90),
 QUANTILE_CONT((conversion_seconds-first_impression_seconds)/86400.0,.95)
FROM conversion_paths;

CREATE OR REPLACE TABLE conversion_lag_histogram AS
SELECT CAST(FLOOR((conversion_seconds-last_clicked_impression_seconds)/86400.0) AS BIGINT) AS lag_day,
 COUNT(*) AS conversions FROM conversion_paths
WHERE last_clicked_impression_seconds IS NOT NULL GROUP BY lag_day;
