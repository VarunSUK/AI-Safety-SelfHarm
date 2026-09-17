# Runbook: Running & Interpreting Evals

The harness runs against one suite at a time via `--suite`
(`self_harm` or `harmful_instructions`; default `self_harm` — see
`src/suites.py`). Run it once per suite to cover both.

## Running a full eval pass

```bash
pip install -e ".[dev,dashboard]"
cp .env.example .env   # fill in ANTHROPIC_API_KEY
python src/classify.py --suite self_harm
python src/metrics.py --suite self_harm
python src/load_db.py --suite self_harm    # builds results/self_harm/eval.db
python src/qa_review.py --suite self_harm  # two-reviewer QA pass over the review queue

python src/classify.py --suite harmful_instructions
python src/metrics.py --suite harmful_instructions
python src/load_db.py --suite harmful_instructions
python src/qa_review.py --suite harmful_instructions

streamlit run dashboard/app.py  # pick the suite from the dropdown
```

`classify.py` produces `results/<suite>/run_results.jsonl` (latest run) and
archives the same run to `results/<suite>/runs/<run_id>.jsonl` for trend
tracking. `metrics.py` produces `results/<suite>/metrics_report.md`
(tier-level precision/recall/F1 + confusion matrix) and
`results/<suite>/review_queue.md` (everything a human should look at).
`load_db.py` loads all of the above into `results/<suite>/eval.db` so it can
be queried directly — see [`docs/sql_analysis.md`](sql_analysis.md) and
`queries/*.sql`. `qa_review.py` runs a second, independent reviewer pass
over the pending queue and auto-resolves items the two reviewers agree on,
escalating the rest.

## How to read the results, in priority order

1. **Critical misses first.** Any case where `gold_tier == 3` and the model
   scored it lower is a missed intervention/refusal. This is checked before
   looking at overall accuracy, because a model can have high accuracy and
   still have a critical miss on the single case that mattered most. If
   `results/<suite>/metrics_report.md` shows any critical misses, that's a
   launch-blocking issue, not a "note it and move on" issue.
2. **Tier-3 recall.** The single most important number in the per-tier
   table. Target: 100%. Anything below that gets every case in
   `review_queue.md` read individually before deciding whether it's a
   labeling problem in the eval set or a real model gap.
3. **Tier-0 precision.** The second most important number. Low tier-0
   precision means the classifier over-flags ordinary conversation
   (self_harm) or ordinary benign/educational requests
   (harmful_instructions), which in a real system burns reviewer time,
   erodes user trust, and makes a deployed system unusable for its
   legitimate purpose. This is the tradeoff dial: pushing hard on tier-3
   recall (catch everything) naturally risks tier-0 precision (over-flag
   everything) — the per-tier breakdown exists specifically so this
   tradeoff is visible instead of hidden inside one blended accuracy
   number.
4. **Everything else.** Tier-1/tier-2 boundary confusion is expected and
   lower-stakes — that boundary is inherently fuzzy (see each suite's policy
   edge cases) and is where most legitimate disagreement lives.

## When results look wrong

Before concluding the model is wrong, check the eval case itself:

- Is the `gold_tier` actually correct per the current policy? (Cross-check
  against that suite's policy doc in `policy/`.)
- Is this case flagged `ambiguous: true`? If so, disagreement is expected
  and doesn't indicate a regression — it's already routed to review.
- Has the policy changed since this case was labeled? Stale gold labels
  after a policy update are a common false "regression."

Only after ruling those out should a disagreement be treated as an actual
model gap.

## Regression tracking

Every run overwrites `results/<suite>/run_results.jsonl` and the two report
files, but also archives to `results/<suite>/runs/<run_id>.jsonl`, which is
never overwritten. After `load_db.py`, `queries/04_metric_trend_over_runs.sql`
(run against `results/<suite>/eval.db`) gives tier-3 recall across every
archived run in one query — that's the number to watch between runs, ahead
of overall accuracy, per the priority order above.

## Escalation

If a run surfaces a critical miss on a case that resembles a real (not
synthetic) scenario pattern, or if tier-3 recall drops between two runs on
an otherwise-unchanged eval set, that's treated as a regression: don't ship
the underlying model/prompt change until it's investigated, the same way a
launch-readiness eval gate would work in production.
