CREATE OR REPLACE TABLE `__PROJECT__.__DATASET__.experiment_arm_summary` AS
SELECT arm, COUNT(*) AS participants, SUM(conversion) AS conversions,
       AVG(conversion) AS conversion_rate, SUM(revenue) AS observed_revenue,
       AVG(revenue) AS revenue_per_participant, VAR_SAMP(revenue) AS revenue_variance
FROM `__PROJECT__.__DATASET__.experiment_participants`
GROUP BY arm;

CREATE OR REPLACE TABLE `__PROJECT__.__DATASET__.experiment_incrementality` AS
SELECT t.arm, t.participants, t.conversion_rate, c.conversion_rate AS control_conversion_rate,
       t.conversion_rate - c.conversion_rate AS conversion_lift_absolute,
       SAFE_DIVIDE(t.conversion_rate - c.conversion_rate,c.conversion_rate) AS conversion_lift_relative,
       t.revenue_per_participant - c.revenue_per_participant AS incremental_revenue_per_participant,
       (t.revenue_per_participant - c.revenue_per_participant)*t.participants AS incremental_revenue,
       CAST(NULL AS FLOAT64) AS incremental_roas,
       'Unavailable: no observed campaign cost in source' AS incremental_roas_status
FROM `__PROJECT__.__DATASET__.experiment_arm_summary` t
CROSS JOIN `__PROJECT__.__DATASET__.experiment_arm_summary` c
WHERE t.arm != 'No E-Mail' AND c.arm = 'No E-Mail';
