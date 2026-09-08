# Runbook: Running & Interpreting Evals

## Running a full eval pass

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in ANTHROPIC_API_KEY
python src/classify.py
python src/metrics.py
python src/load_db.py   # builds results/eval.db for SQL analysis (see docs/sql_analysis.md)
python src/qa_review.py # two-reviewer QA pass over the review queue
```

`classify.py` produces `results/run_results.jsonl` (latest run) and archives
the same run to `results/runs/<run_id>.jsonl` for trend tracking.
`metrics.py` produces `results/metrics_report.md` (tier-level
precision/recall/F1 + confusion matrix) and `results/review_queue.md`
(everything a human should look at). `load_db.py` loads all of the above
into `results/eval.db` so it can be queried directly — see
[`docs/sql_analysis.md`](sql_analysis.md) and `queries/*.sql`. `qa_review.py`
runs a second, independent reviewer pass over the pending queue and
auto-resolves items the two reviewers agree on, escalating the rest.

## How to read the results, in priority order

1. **Critical misses first.** Any case where `gold_tier == 3` and the model
   scored it lower is a missed intervention. This is checked before looking
   at overall accuracy, because a model can have high accuracy and still
   have a critical miss on the single case that mattered most. If
   `results/metrics_report.md` shows any critical misses, that's a
   launch-blocking issue, not a "note it and move on" issue.
2. **Tier-3 recall.** The single most important number in the per-tier
   table. Target: 100%. Anything below that gets every case in
   `review_queue.md` read individually before deciding whether it's a
   labeling problem in the eval set or a real model gap.
3. **Tier-0 precision.** The second most important number. Low tier-0
   precision means the classifier over-flags ordinary conversation, which in
   a real system burns reviewer time and erodes user trust. This is the
   tradeoff dial: pushing hard on tier-3 recall (catch everything) naturally
   risks tier-0 precision (over-flag everything) — the per-tier breakdown
   exists specifically so this tradeoff is visible instead of hidden inside
   one blended accuracy number.
4. **Everything else.** Tier-1/tier-2 boundary confusion is expected and
   lower-stakes — that boundary is inherently fuzzy (see policy edge cases)
   and is where most legitimate disagreement lives.

## When results look wrong

Before concluding the model is wrong, check the eval case itself:

- Is the `gold_tier` actually correct per the current policy? (Cross-check
  against `policy/self_harm_policy.md`.)
- Is this case flagged `ambiguous: true`? If so, disagreement is expected
  and doesn't indicate a regression — it's already routed to review.
- Has the policy changed since this case was labeled? Stale gold labels
  after a policy update are a common false "regression."

Only after ruling those out should a disagreement be treated as an actual
model gap.

## Regression tracking

Every run overwrites `results/run_results.jsonl` and the two report files,
but also archives to `results/runs/<run_id>.jsonl`, which is never
overwritten. After `load_db.py`, `queries/04_metric_trend_over_runs.sql`
gives tier-3 recall across every archived run in one query — that's the
number to watch between runs, ahead of overall accuracy, per the priority
order above.

## Escalation

If a run surfaces a critical miss on a case that resembles a real (not
synthetic) scenario pattern, or if tier-3 recall drops between two runs on
an otherwise-unchanged eval set, that's treated as a regression: don't ship
the underlying model/prompt change until it's investigated, the same way a
launch-readiness eval gate would work in production.
