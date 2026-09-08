-- Review queue health for the latest run: how many items are pending vs.
-- auto-resolved vs. escalated, broken out by why they were routed to
-- review in the first place. Run src/qa_review.py to populate resolved
-- statuses; freshly loaded queues will show entirely 'pending'.
SELECT reason, status, COUNT(*) AS n
FROM review_queue
WHERE run_id = (SELECT run_id FROM runs ORDER BY run_id DESC LIMIT 1)
GROUP BY reason, status
ORDER BY reason, status;
