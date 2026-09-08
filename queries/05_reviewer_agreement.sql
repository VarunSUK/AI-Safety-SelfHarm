-- Inter-rater agreement between the two QA reviewer passes (src/qa_review.py):
-- how many queue items each pass auto-resolved (reviewers agreed with each
-- other) vs. escalated to a human tie-breaker (reviewers disagreed).
SELECT
  status,
  COUNT(*) AS n_items,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
FROM review_queue
WHERE run_id = (SELECT run_id FROM runs ORDER BY run_id DESC LIMIT 1)
  AND status IN ('auto_resolved', 'escalated')
GROUP BY status;
