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
ASSERT (SELECT COUNT(*) FROM `__PROJECT__.__DATASET__.experiment_participants`) = 64000 AS 'Incomplete experiment';
