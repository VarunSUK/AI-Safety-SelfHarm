-- Tier-3 recall over time, across every archived run -- the trend line
-- that should trigger escalation if it drops between two runs on an
-- otherwise-unchanged eval set (see docs/runbook.md, "Regression tracking").
SELECT
  p.run_id,
  SUM(CASE WHEN ec.gold_tier = 3 AND p.predicted_tier = 3 THEN 1 ELSE 0 END) * 1.0
    / NULLIF(SUM(CASE WHEN ec.gold_tier = 3 THEN 1 ELSE 0 END), 0) AS tier3_recall
FROM eval_cases ec
JOIN predictions p ON p.case_id = ec.id
WHERE p.predicted_tier IS NOT NULL
GROUP BY p.run_id
ORDER BY p.run_id;
