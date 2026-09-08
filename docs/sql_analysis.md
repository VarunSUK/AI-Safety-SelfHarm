# SQL Analysis Layer

`results/eval.db` (SQLite, built by `src/load_db.py`) exists so eval results
can be queried directly instead of only being read as generated Markdown —
the same shift a real team makes once an eval harness needs to answer
one-off questions ("how has tier-3 recall moved over the last five runs?",
"what's the review queue backlog by reason?") that weren't anticipated when
the reports were written.

## Building the database

```bash
python src/classify.py      # writes results/runs/<run_id>.jsonl
python src/load_db.py       # builds/refreshes results/eval.db
```

`load_db.py` is safe to re-run: it reloads `eval_cases` from
`eval/dataset.jsonl` fresh each time, loads every archived run in
`results/runs/`, and rebuilds `review_queue` for the latest run only (older
runs' queues are history, not something to keep re-triaging).

## Schema

| Table | Purpose |
|---|---|
| `eval_cases` | Gold labels — one row per case in `eval/dataset.jsonl`. |
| `runs` | One row per `classify.py` run (`run_id`, `model`). |
| `predictions` | One row per `(run_id, case_id)` — every prediction from every archived run, so metrics can be compared across runs. |
| `review_queue` | Auto-built for the latest run: critical misses, other disagreements, and gold-flagged ambiguous cases. `status` starts `pending`. |
| `review_decisions` | Filled in by `src/qa_review.py` — one row per (queue item, reviewer). |

## Example queries (`queries/`)

- `01_tier_precision_recall.sql` — precision/recall/F1 inputs per tier, latest run.
- `02_critical_misses.sql` — the cases that matter most: gold tier 3, scored lower.
- `03_review_queue_backlog.sql` — queue health by reason and status.
- `04_metric_trend_over_runs.sql` — tier-3 recall across every archived run, for regression tracking.
- `05_reviewer_agreement.sql` — QA inter-rater agreement (auto-resolved vs. escalated).

Run one with the `sqlite3` CLI:

```bash
sqlite3 results/eval.db < queries/02_critical_misses.sql
```

or from Python:

```python
import sqlite3
conn = sqlite3.connect("results/eval.db")
conn.execute(open("queries/02_critical_misses.sql").read()).fetchall()
```

## Why this exists as its own layer

The Markdown reports from `src/metrics.py` are the right format for a
single run's launch-readiness check — readable top to bottom, no query
needed. The SQL layer is for the questions that come up *after* that: is
this run's regression new, or has recall been drifting for weeks; which
edge-case types account for most of the review queue; did the two QA
reviewers actually agree at a higher rate on tier-0 cases than tier-2
cases. Those are exploratory, one-off questions — a fixed report can't
anticipate all of them, but a normalized table can answer any of them.
