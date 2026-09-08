# Runbook: Running & Interpreting Evals

## Running a full eval pass

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in ANTHROPIC_API_KEY
python src/classify.py
python src/metrics.py
```

This produces `results/run_results.jsonl` (raw predictions),
`results/metrics_report.md` (tier-level precision/recall/F1 + confusion
matrix), and `results/review_queue.md` (everything a human should look at).

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

Every run overwrites `results/run_results.jsonl` and the two report files.
To track a metric over time (e.g. across model versions or after adding new
eval cases), commit the reports at the timestamp they were generated —
`results/metrics_report.md`'s accuracy and tier-3 recall numbers are the two
to diff between runs. A drop in tier-3 recall between two committed reports
is the signal that should trigger the escalation in the section above,
regardless of what overall accuracy did.

## Escalation

If a run surfaces a critical miss on a case that resembles a real (not
synthetic) scenario pattern, or if tier-3 recall drops between two runs on
an otherwise-unchanged eval set, that's treated as a regression: don't ship
the underlying model/prompt change until it's investigated, the same way a
launch-readiness eval gate would work in production.
