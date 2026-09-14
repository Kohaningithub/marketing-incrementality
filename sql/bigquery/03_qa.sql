ASSERT (SELECT COUNT(*) FROM `__PROJECT__.__DATASET__.impressions`) > 0 AS 'Empty impressions';
ASSERT (SELECT COUNT(*) - COUNT(DISTINCT event_id) FROM `__PROJECT__.__DATASET__.impressions`) = 0 AS 'Duplicate event IDs';
ASSERT (SELECT COUNT(*)-COUNT(DISTINCT conversion_key) FROM `__PROJECT__.__DATASET__.conversions`) = 0 AS 'Duplicate canonical conversion keys';
ASSERT (SELECT COUNT(*) FROM `__PROJECT__.__DATASET__.last_click_proxy`
  WHERE conversion_seconds - impression_seconds NOT BETWEEN 0 AND window_days * 86400) = 0 AS 'Invalid conversion window';
ASSERT (SELECT COUNT(*) FROM (
  SELECT window_days, conversion_key FROM `__PROJECT__.__DATASET__.last_click_proxy`
  GROUP BY window_days, conversion_key HAVING SUM(attribution_weight) != 1
)) = 0 AS 'Attribution weights do not conserve conversions';
ASSERT (SELECT COUNT(*) FROM `__PROJECT__.__DATASET__.last_click_proxy` p
  LEFT JOIN `__PROJECT__.__DATASET__.conversions` c USING(conversion_key)
  WHERE c.conversion_key IS NULL) = 0 AS 'Conversion join loss';
ASSERT (SELECT SUM(attributed_conversions) FROM `__PROJECT__.__DATASET__.campaign_daily`)
  = (SELECT COUNT(*) FROM `__PROJECT__.__DATASET__.last_click_proxy`) AS 'Mart reconciliation failed';
ASSERT (SELECT COUNT(*) FROM `__PROJECT__.__DATASET__.uplift_raw`) = 13979592 AS 'Incomplete Criteo uplift release';
ASSERT (SELECT COUNT(*) FROM (
 SELECT model,window_days,conversion_key FROM `__PROJECT__.__DATASET__.model_credits`
 GROUP BY model,window_days,conversion_key HAVING ABS(SUM(attribution_weight)-1)>1e-8
)) = 0 AS 'First/last/linear credit conservation failed';
ASSERT (SELECT COUNT(*) FROM `__PROJECT__.__DATASET__.uplift_raw`
 WHERE treatment IS NULL OR treatment NOT IN (0,1) OR conversion IS NULL OR conversion NOT IN (0,1)
 OR visit IS NULL OR visit NOT IN (0,1) OR exposure IS NULL OR exposure NOT IN (0,1))=0 AS 'Invalid uplift outcomes/assignment';
