CREATE OR REPLACE TABLE campaign_reconciliation AS
WITH campaign AS (
 SELECT campaign_id,COUNT(*) AS impressions,COUNT(DISTINCT user_id) AS unique_users,SUM(click) AS clicks,
 SUM(transformed_cost) AS transformed_media_cost FROM impressions GROUP BY campaign_id
), credit AS (
 SELECT model,window_days,campaign_id,SUM(attribution_weight) AS credited_conversions
 FROM model_credits GROUP BY model,window_days,campaign_id
), definitions AS (SELECT DISTINCT model,window_days FROM model_credits), totals AS (
 SELECT c.*,d.model,d.window_days,COALESCE(a.credited_conversions,0) AS credited_conversions,
 COALESCE(b.credited_conversions,0) AS publisher_conversions
 FROM campaign c CROSS JOIN definitions d
 LEFT JOIN credit a ON c.campaign_id=a.campaign_id AND d.model=a.model AND d.window_days=a.window_days
 LEFT JOIN credit b ON c.campaign_id=b.campaign_id AND b.model='publisher' AND b.window_days=30
), ranked AS (
 SELECT *,RANK() OVER(PARTITION BY model,window_days ORDER BY ROUND(credited_conversions,8) DESC) AS campaign_rank
 FROM totals
)
SELECT r.*,r.credited_conversions-r.publisher_conversions AS absolute_difference,
 100.0*(r.credited_conversions-r.publisher_conversions)/NULLIF(r.publisher_conversions,0) AS percentage_difference,
 r.clicks*1.0/NULLIF(r.impressions,0) AS ctr,
 r.credited_conversions/NULLIF(r.impressions,0) AS conversions_per_impression,
 r.transformed_media_cost/NULLIF(r.credited_conversions,0) AS transformed_cost_per_attributed_conversion,
 r.campaign_rank-b.campaign_rank AS rank_change_vs_publisher
FROM ranked r LEFT JOIN ranked b ON r.campaign_id=b.campaign_id AND b.model='publisher' AND b.window_days=30;
