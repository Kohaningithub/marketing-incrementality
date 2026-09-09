-- Source identity, not user identity, is the replay deduplication key.
-- Identical covariates do not imply duplicate customers or impressions.
CREATE OR REPLACE TABLE impressions AS
SELECT event_id, uid AS user_id, campaign AS campaign_id,
       timestamp AS impression_seconds,
       CAST(FLOOR(timestamp / 86400.0) AS BIGINT) AS relative_day,
       CAST(NULL AS TIMESTAMP) AS event_timestamp_utc,
       CAST(NULL AS VARCHAR) AS geo,
       CAST(cat1 AS VARCHAR) AS context_segment,
       click, conversion,
       NULLIF(conversion_id, -1) AS conversion_id,
       NULLIF(conversion_timestamp, -1) AS conversion_seconds,
       CASE WHEN conversion_id >= 0 THEN CAST(conversion_id AS VARCHAR) || ':' || CAST(uid AS VARCHAR) || ':' || CAST(conversion_timestamp AS VARCHAR) END AS conversion_key,
       attribution AS publisher_attribution, click_pos, click_nb,
       cost AS transformed_cost, cpo AS transformed_cpo
FROM raw_criteo
WHERE uid IS NOT NULL AND campaign IS NOT NULL AND timestamp >= 0
  AND click IN (0, 1) AND conversion IN (0, 1) AND attribution IN (0, 1)
  AND cost >= 0 AND isfinite(cost)
  AND ((conversion = 0 AND conversion_id = -1 AND conversion_timestamp = -1)
       OR (conversion = 1 AND conversion_id >= 0 AND conversion_timestamp >= timestamp))
QUALIFY ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY event_id) = 1;

CREATE OR REPLACE TABLE conversion_conflicts AS
SELECT conversion_id
FROM impressions WHERE conversion_id IS NOT NULL
GROUP BY conversion_id
HAVING COUNT(DISTINCT user_id) > 1 OR COUNT(DISTINCT conversion_seconds) > 1;

CREATE OR REPLACE TABLE conversions AS
SELECT conversion_key, conversion_id, user_id, conversion_seconds,
       MAX(publisher_attribution) AS publisher_attribution
FROM impressions
WHERE conversion_id IS NOT NULL
GROUP BY conversion_key, conversion_id, user_id, conversion_seconds;

CREATE OR REPLACE VIEW clicks AS
SELECT event_id || ':click' AS event_id, event_id AS impression_event_id,
       user_id, campaign_id, impression_seconds AS associated_impression_seconds,
       CAST(NULL AS TIMESTAMP) AS click_timestamp_utc
FROM impressions WHERE click = 1;

CREATE OR REPLACE VIEW events AS
SELECT event_id, user_id, campaign_id, 'impression' AS event_type,
       impression_seconds AS observed_relative_seconds, event_timestamp_utc
FROM impressions
UNION ALL
SELECT event_id, user_id, campaign_id, 'click_indicator',
       CAST(NULL AS BIGINT), click_timestamp_utc FROM clicks
UNION ALL
SELECT 'conversion:' || conversion_key, user_id, CAST(NULL AS BIGINT),
       'conversion', conversion_seconds, CAST(NULL AS TIMESTAMP) FROM conversions;
