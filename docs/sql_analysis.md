# SQL Analysis Layer

`results/<suite>/eval.db` (SQLite, built by `src/load_db.py --suite
<suite>`; one database per suite — see `src/suites.py`) exists so eval
results can be queried directly instead of only being read as generated
Markdown — the same shift a real team makes once an eval harness needs to
answer one-off questions ("how has tier-3 recall moved over the last five
runs?", "what's the review queue backlog by reason?") that weren't
anticipated when the reports were written.

## Building the database

```bash
python src/classify.py --suite self_harm   # writes results/self_harm/runs/<run_id>.jsonl
python src/load_db.py --suite self_harm    # builds/refreshes results/self_harm/eval.db
```

Swap `--suite self_harm` for `--suite harmful_instructions` to build the
other suite's database.

`load_db.py` is safe to re-run: it reloads `eval_cases` from that suite's
`dataset.jsonl` fresh each time, loads every archived run in
`results/<suite>/runs/`, and rebuilds `review_queue` for the latest run only
(older runs' queues are history, not something to keep re-triaging).

## Schema

The schema is identical across every suite's database — only the gold
labels and prompts differ per suite, not the table shapes — so every query
below runs unmodified against `results/self_harm/eval.db` or
`results/harmful_instructions/eval.db`.

| Table | Purpose |
|---|---|
| `eval_cases` | Gold labels — one row per case in that suite's `dataset.jsonl`. Common fields (`id`, `text`, `gold_tier`, `ambiguous`, `edge_case_type`, `notes`) are columns; suite-specific fields (e.g. self-harm's `requires_resources`/`third_party`, or harmful_instructions' `requires_refusal`/`dual_use_borderline`) live in `extra_json`. |
| `runs` | One row per `classify.py` run (`run_id`, `model`). |
| `predictions` | One row per `(run_id, case_id)` — every prediction from every archived run, so metrics can be compared across runs. `extra_json` holds any suite-specific fields the classifier returned. |
| `review_queue` | Auto-built for the latest run: critical misses, other disagreements, and gold-flagged ambiguous cases. `status` starts `pending`. |
| `review_decisions` | Filled in by `src/qa_review.py` — one row per (queue item, reviewer). |

## Example queries (`queries/`)

- `01_tier_precision_recall.sql` — precision/recall/F1 inputs per tier, latest run.
- `02_critical_misses.sql` — the cases that matter most: gold tier 3, scored lower.
- `03_review_queue_backlog.sql` — queue health by reason and status.
- `04_metric_trend_over_runs.sql` — tier-3 recall across every archived run, for regression tracking.
- `05_reviewer_agreement.sql` — QA inter-rater agreement (auto-resolved vs. escalated).

Run one with the `sqlite3` CLI, pointed at whichever suite's database:

```bash
sqlite3 results/self_harm/eval.db < queries/02_critical_misses.sql
sqlite3 results/harmful_instructions/eval.db < queries/02_critical_misses.sql
```

or from Python:

```python
import sqlite3
conn = sqlite3.connect("results/harmful_instructions/eval.db")
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
