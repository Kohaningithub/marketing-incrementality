-- Separate experiment release. NEVER join this table to attribution campaign/user IDs.
CREATE OR REPLACE TABLE `__PROJECT__.__DATASET__.uplift_arm_summary` AS
SELECT treatment, COUNT(*) AS n, SUM(conversion) AS conversions,AVG(conversion) AS conversion_rate,
 SUM(visit) AS visits,AVG(visit) AS visit_rate, AVG(exposure) AS exposure_rate
FROM `__PROJECT__.__DATASET__.uplift_raw` GROUP BY treatment;

-- Sufficient statistics for the same Python Newcombe CI / pooled z-test calculations.
CREATE OR REPLACE TABLE `__PROJECT__.__DATASET__.uplift_itt` AS
SELECT t.n AS treatment_n,c.n AS control_n,
 t.conversion_rate-c.conversion_rate AS conversion_lift,
 SAFE_DIVIDE(t.conversion_rate-c.conversion_rate,c.conversion_rate) AS conversion_relative_lift,
 (t.conversion_rate-c.conversion_rate)*100000 AS incremental_conversions_per_100k,
 t.visit_rate-c.visit_rate AS visit_lift,
 t.exposure_rate AS exposure_given_treatment,c.exposure_rate AS exposure_given_control
FROM `__PROJECT__.__DATASET__.uplift_arm_summary` t
CROSS JOIN `__PROJECT__.__DATASET__.uplift_arm_summary` c WHERE t.treatment=1 AND c.treatment=0;

CREATE OR REPLACE TABLE `__PROJECT__.__DATASET__.uplift_feature_balance` AS
SELECT 'f0' AS feature, AVG(IF(treatment=1,f0,NULL)) AS treatment_mean, AVG(IF(treatment=0,f0,NULL)) AS control_mean, SAFE_DIVIDE(AVG(IF(treatment=1,f0,NULL))-AVG(IF(treatment=0,f0,NULL)),SQRT((VAR_SAMP(IF(treatment=1,f0,NULL))+VAR_SAMP(IF(treatment=0,f0,NULL)))/2)) AS smd, COUNTIF(f0 IS NULL OR IS_NAN(f0) OR IS_INF(f0)) AS missing_or_nonfinite FROM `__PROJECT__.__DATASET__.uplift_raw`
UNION ALL
SELECT 'f1' AS feature, AVG(IF(treatment=1,f1,NULL)) AS treatment_mean, AVG(IF(treatment=0,f1,NULL)) AS control_mean, SAFE_DIVIDE(AVG(IF(treatment=1,f1,NULL))-AVG(IF(treatment=0,f1,NULL)),SQRT((VAR_SAMP(IF(treatment=1,f1,NULL))+VAR_SAMP(IF(treatment=0,f1,NULL)))/2)) AS smd, COUNTIF(f1 IS NULL OR IS_NAN(f1) OR IS_INF(f1)) AS missing_or_nonfinite FROM `__PROJECT__.__DATASET__.uplift_raw`
UNION ALL
SELECT 'f2' AS feature, AVG(IF(treatment=1,f2,NULL)) AS treatment_mean, AVG(IF(treatment=0,f2,NULL)) AS control_mean, SAFE_DIVIDE(AVG(IF(treatment=1,f2,NULL))-AVG(IF(treatment=0,f2,NULL)),SQRT((VAR_SAMP(IF(treatment=1,f2,NULL))+VAR_SAMP(IF(treatment=0,f2,NULL)))/2)) AS smd, COUNTIF(f2 IS NULL OR IS_NAN(f2) OR IS_INF(f2)) AS missing_or_nonfinite FROM `__PROJECT__.__DATASET__.uplift_raw`
UNION ALL
SELECT 'f3' AS feature, AVG(IF(treatment=1,f3,NULL)) AS treatment_mean, AVG(IF(treatment=0,f3,NULL)) AS control_mean, SAFE_DIVIDE(AVG(IF(treatment=1,f3,NULL))-AVG(IF(treatment=0,f3,NULL)),SQRT((VAR_SAMP(IF(treatment=1,f3,NULL))+VAR_SAMP(IF(treatment=0,f3,NULL)))/2)) AS smd, COUNTIF(f3 IS NULL OR IS_NAN(f3) OR IS_INF(f3)) AS missing_or_nonfinite FROM `__PROJECT__.__DATASET__.uplift_raw`
UNION ALL
SELECT 'f4' AS feature, AVG(IF(treatment=1,f4,NULL)) AS treatment_mean, AVG(IF(treatment=0,f4,NULL)) AS control_mean, SAFE_DIVIDE(AVG(IF(treatment=1,f4,NULL))-AVG(IF(treatment=0,f4,NULL)),SQRT((VAR_SAMP(IF(treatment=1,f4,NULL))+VAR_SAMP(IF(treatment=0,f4,NULL)))/2)) AS smd, COUNTIF(f4 IS NULL OR IS_NAN(f4) OR IS_INF(f4)) AS missing_or_nonfinite FROM `__PROJECT__.__DATASET__.uplift_raw`
UNION ALL
SELECT 'f5' AS feature, AVG(IF(treatment=1,f5,NULL)) AS treatment_mean, AVG(IF(treatment=0,f5,NULL)) AS control_mean, SAFE_DIVIDE(AVG(IF(treatment=1,f5,NULL))-AVG(IF(treatment=0,f5,NULL)),SQRT((VAR_SAMP(IF(treatment=1,f5,NULL))+VAR_SAMP(IF(treatment=0,f5,NULL)))/2)) AS smd, COUNTIF(f5 IS NULL OR IS_NAN(f5) OR IS_INF(f5)) AS missing_or_nonfinite FROM `__PROJECT__.__DATASET__.uplift_raw`
UNION ALL
SELECT 'f6' AS feature, AVG(IF(treatment=1,f6,NULL)) AS treatment_mean, AVG(IF(treatment=0,f6,NULL)) AS control_mean, SAFE_DIVIDE(AVG(IF(treatment=1,f6,NULL))-AVG(IF(treatment=0,f6,NULL)),SQRT((VAR_SAMP(IF(treatment=1,f6,NULL))+VAR_SAMP(IF(treatment=0,f6,NULL)))/2)) AS smd, COUNTIF(f6 IS NULL OR IS_NAN(f6) OR IS_INF(f6)) AS missing_or_nonfinite FROM `__PROJECT__.__DATASET__.uplift_raw`
UNION ALL
SELECT 'f7' AS feature, AVG(IF(treatment=1,f7,NULL)) AS treatment_mean, AVG(IF(treatment=0,f7,NULL)) AS control_mean, SAFE_DIVIDE(AVG(IF(treatment=1,f7,NULL))-AVG(IF(treatment=0,f7,NULL)),SQRT((VAR_SAMP(IF(treatment=1,f7,NULL))+VAR_SAMP(IF(treatment=0,f7,NULL)))/2)) AS smd, COUNTIF(f7 IS NULL OR IS_NAN(f7) OR IS_INF(f7)) AS missing_or_nonfinite FROM `__PROJECT__.__DATASET__.uplift_raw`
UNION ALL
SELECT 'f8' AS feature, AVG(IF(treatment=1,f8,NULL)) AS treatment_mean, AVG(IF(treatment=0,f8,NULL)) AS control_mean, SAFE_DIVIDE(AVG(IF(treatment=1,f8,NULL))-AVG(IF(treatment=0,f8,NULL)),SQRT((VAR_SAMP(IF(treatment=1,f8,NULL))+VAR_SAMP(IF(treatment=0,f8,NULL)))/2)) AS smd, COUNTIF(f8 IS NULL OR IS_NAN(f8) OR IS_INF(f8)) AS missing_or_nonfinite FROM `__PROJECT__.__DATASET__.uplift_raw`
UNION ALL
SELECT 'f9' AS feature, AVG(IF(treatment=1,f9,NULL)) AS treatment_mean, AVG(IF(treatment=0,f9,NULL)) AS control_mean, SAFE_DIVIDE(AVG(IF(treatment=1,f9,NULL))-AVG(IF(treatment=0,f9,NULL)),SQRT((VAR_SAMP(IF(treatment=1,f9,NULL))+VAR_SAMP(IF(treatment=0,f9,NULL)))/2)) AS smd, COUNTIF(f9 IS NULL OR IS_NAN(f9) OR IS_INF(f9)) AS missing_or_nonfinite FROM `__PROJECT__.__DATASET__.uplift_raw`
UNION ALL
SELECT 'f10' AS feature, AVG(IF(treatment=1,f10,NULL)) AS treatment_mean, AVG(IF(treatment=0,f10,NULL)) AS control_mean, SAFE_DIVIDE(AVG(IF(treatment=1,f10,NULL))-AVG(IF(treatment=0,f10,NULL)),SQRT((VAR_SAMP(IF(treatment=1,f10,NULL))+VAR_SAMP(IF(treatment=0,f10,NULL)))/2)) AS smd, COUNTIF(f10 IS NULL OR IS_NAN(f10) OR IS_INF(f10)) AS missing_or_nonfinite FROM `__PROJECT__.__DATASET__.uplift_raw`
UNION ALL
SELECT 'f11' AS feature, AVG(IF(treatment=1,f11,NULL)) AS treatment_mean, AVG(IF(treatment=0,f11,NULL)) AS control_mean, SAFE_DIVIDE(AVG(IF(treatment=1,f11,NULL))-AVG(IF(treatment=0,f11,NULL)),SQRT((VAR_SAMP(IF(treatment=1,f11,NULL))+VAR_SAMP(IF(treatment=0,f11,NULL)))/2)) AS smd, COUNTIF(f11 IS NULL OR IS_NAN(f11) OR IS_INF(f11)) AS missing_or_nonfinite FROM `__PROJECT__.__DATASET__.uplift_raw`;
