-- Every case where gold risk was imminent (tier 3) but the latest run
-- scored it lower -- the single most important failure mode to monitor.
-- (See docs/runbook.md: this is checked before overall accuracy.)
SELECT ec.id, ec.text, ec.gold_tier, p.predicted_tier, p.rationale
FROM eval_cases ec
JOIN predictions p ON p.case_id = ec.id
JOIN (SELECT run_id FROM runs ORDER BY run_id DESC LIMIT 1) lr ON p.run_id = lr.run_id
WHERE ec.gold_tier = 3 AND p.predicted_tier < 3;
