CREATE OR REPLACE TABLE first_click_attribution AS
SELECT window_days,conversion_key,event_id,campaign_id,relative_day,1.0 AS attribution_weight
FROM attribution_candidates
QUALIFY ROW_NUMBER() OVER (PARTITION BY window_days,conversion_key
 ORDER BY impression_seconds,click_pos,event_id)=1;

CREATE OR REPLACE VIEW linear_attribution AS
SELECT window_days,conversion_key,event_id,campaign_id,relative_day,
 1.0/COUNT(*) OVER (PARTITION BY window_days,conversion_key) AS attribution_weight
FROM attribution_candidates;

-- Publisher flag is a supplied definition, not a reconstructed vendor.
-- Latest linked impression is only a reporting-day placement convention.
CREATE OR REPLACE TABLE publisher_attribution AS
SELECT c.conversion_key,i.event_id,i.campaign_id,i.relative_day,1.0 AS attribution_weight
FROM conversions c JOIN impressions i ON c.conversion_key=i.conversion_key
WHERE c.publisher_attribution=1
QUALIFY ROW_NUMBER() OVER(PARTITION BY c.conversion_key ORDER BY i.impression_seconds DESC,i.event_id)=1;
