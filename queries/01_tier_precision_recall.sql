-- Per-tier precision/recall for the most recent run, expressed in SQL for
-- ad-hoc analysis without re-running src/metrics.py.
WITH latest_run AS (
  SELECT run_id FROM runs ORDER BY run_id DESC LIMIT 1
),
joined AS (
  SELECT ec.gold_tier, p.predicted_tier
  FROM eval_cases ec
  JOIN predictions p ON p.case_id = ec.id
  JOIN latest_run lr ON p.run_id = lr.run_id
  WHERE p.predicted_tier IS NOT NULL
),
tiers(tier) AS (SELECT 0 UNION SELECT 1 UNION SELECT 2 UNION SELECT 3)
SELECT
  tier,
  SUM(CASE WHEN gold_tier = tier AND predicted_tier = tier THEN 1 ELSE 0 END) AS tp,
  SUM(CASE WHEN gold_tier != tier AND predicted_tier = tier THEN 1 ELSE 0 END) AS fp,
  SUM(CASE WHEN gold_tier = tier AND predicted_tier != tier THEN 1 ELSE 0 END) AS fn
FROM joined, tiers
GROUP BY tier
ORDER BY tier;
