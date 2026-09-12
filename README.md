# AI Safety — Self-Harm Risk Evaluation Harness

![CI](https://github.com/VarunSUK/AI-Safety-SelfHarm/actions/workflows/ci.yml/badge.svg)

A small, complete evaluation harness for a self-harm/crisis risk
classifier: a policy with severity tiers, a hand-labeled eval dataset built
around edge cases (not just the obvious ones), an LLM-based classifier
(Claude), and a metrics + review-queue pipeline that treats missed
high-severity cases as the metric that matters most.

Built as a portfolio project for a Trust & Safety / safety-evaluations
interview — it's deliberately scoped to demonstrate the full lifecycle of an
eval (policy → rubric → dataset → run → metrics → review queue → SOP) rather
than to be a production system.

## Why this project

It mirrors the core workflow of a safeguards/safety-evaluations role:

- **Policy → rubric → measurable criteria.** [`policy/self_harm_policy.md`](policy/self_harm_policy.md)
  defines severity tiers and, critically, *edge-case rules* — the actual
  hard part of writing a policy that a classifier can be scored against.
- **A labeled eval dataset that targets tier boundaries and edge cases**,
  not just easy examples — see [`eval/dataset.jsonl`](eval/dataset.jsonl)
  (hyperbole, third-party reports, media quotation, method/lethality
  requests without stated intent, recovery narratives).
- **Running an eval and interpreting results** — [`src/classify.py`](src/classify.py)
  runs every case through Claude acting as the classifier under test.
- **Tier-level precision/recall, not one blended accuracy number** —
  [`src/metrics.py`](src/metrics.py) computes per-tier precision/recall/F1
  and a confusion matrix, and separately surfaces **critical misses**
  (a truly imminent-risk case scored as lower severity) as the single most
  important signal, ahead of overall accuracy.
- **A review queue with a two-reviewer QA pass** — every disagreement and
  every case the gold set itself flags as ambiguous gets routed to
  `results/review_queue.md` / the `review_queue` table, critical misses
  first. [`src/qa_review.py`](src/qa_review.py) then runs a second,
  independently-framed reviewer pass over the queue: items the two
  reviewers agree on are auto-resolved, items they disagree on are
  escalated rather than trusted on one pass — a quality-assurance pattern,
  not just a bigger prompt.
- **A SQL analysis layer** — [`src/load_db.py`](src/load_db.py) loads every
  eval case, every archived run, and the review queue into SQLite
  (`results/eval.db`), with example queries in [`queries/`](queries/) for
  per-tier precision/recall, critical misses, review-queue backlog by
  status, tier-3 recall trend across runs, and reviewer agreement — see
  [`docs/sql_analysis.md`](docs/sql_analysis.md).
- **SOPs and a runbook** written for how a team would actually operate this
  — [`docs/eval_creation_sop.md`](docs/eval_creation_sop.md) and
  [`docs/runbook.md`](docs/runbook.md).
- **An interactive dashboard** — [`dashboard/app.py`](dashboard/app.py) (Streamlit)
  reads `results/eval.db` directly: KPI tiles (accuracy, tier-3 recall,
  critical misses), per-tier precision/recall, a confusion-matrix heatmap,
  a review-queue table, and a tier-3-recall trend line across runs.
- **A test suite and CI** — [`tests/`](tests/) covers the scoring logic
  (critical-miss classification, join semantics) and the eval dataset's own
  integrity (unique ids, valid tiers, every tier represented), run on every
  push via [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

## Mapping to the role

Built against the Safeguards Enforcement Analyst (User Well-being) posting
specifically:

| Posting | Where |
|---|---|
| "Curating evaluation datasets" / "designing or running experiments... to determine whether an intervention worked" | `eval/dataset.jsonl`, `src/metrics.py` |
| "Translating policy definitions into measurable form — rubrics, review guidelines, classification criteria" | `policy/self_harm_policy.md` |
| "Threshold-setting and precision/recall tradeoffs" | `src/metrics.py` per-tier precision/recall, `queries/01_tier_precision_recall.sql` |
| "Managing or coordinating content review operations, including quality assurance and workflow management" | `src/qa_review.py`, `review_queue`/`review_decisions` tables |
| "Proficiency in SQL... to measure intervention efficacy, monitor workflow health, and surface policy gaps" | `results/eval.db`, `queries/*.sql`, `docs/sql_analysis.md` |
| "Review flagged content to drive enforcement and policy improvements" | `results/review_queue.md`, `docs/eval_creation_sop.md`'s "fix the policy first" rule |
| "Monitor how interventions and detection systems perform over time" | `results/runs/`, `queries/04_metric_trend_over_runs.sql` |
| "Sound judgment in ambiguous, high-consequence cases" | `ambiguous` field, edge-case rules in the policy |
| "Proficiency with data tools (SQL, dashboards, spreadsheets)" | `dashboard/app.py` (Streamlit) on top of `results/eval.db` |
| Preferred: "Experience using agentic tools (e.g. Claude Code) to scale analysis" | this project was built with Claude Code |

Honest gap: there's no in-product feature here connecting users to crisis
resources (the Product/Legal/external-partner referral-pathway work) — this
project is the detection/eval/review side only.

## Project structure

```
policy/self_harm_policy.md   Severity tiers, expected behavior per tier, edge-case rules
eval/dataset.jsonl           28 hand-labeled cases across all 4 tiers + edge cases
src/classify.py              Runs the dataset through Claude, writes results/run_results.jsonl + results/runs/<run_id>.jsonl
src/scoring.py                Shared join/disagreement logic used by metrics.py and load_db.py
src/metrics.py                Scores predictions against gold labels, writes the two reports below
src/load_db.py                Loads cases + runs + review queue into results/eval.db (SQLite)
src/qa_review.py              Two-reviewer QA pass over the review queue: auto-resolve or escalate
queries/*.sql                 Example analysis queries (precision/recall, critical misses, trends, QA agreement)
dashboard/app.py              Streamlit dashboard over results/eval.db
tests/                         pytest suite: scoring logic + eval dataset integrity checks
results/metrics_report.md    Per-tier precision/recall/F1 + confusion matrix (generated)
results/review_queue.md      Critical misses, disagreements, ambiguous cases (generated)
results/qa_review_report.md  Reviewer decisions + auto-resolved/escalated counts (generated)
docs/eval_creation_sop.md    How to add a new eval case
docs/runbook.md               How to run evals and interpret/escalate results
docs/sql_analysis.md          Schema + how to use the SQL analysis layer
.github/workflows/ci.yml      Lint (ruff) + test (pytest) on every push
```

## Running it

```bash
pip install -e ".[dev,dashboard]"
cp .env.example .env      # add your ANTHROPIC_API_KEY
python src/classify.py
python src/metrics.py
python src/load_db.py
python src/qa_review.py
streamlit run dashboard/app.py
```

See [`docs/runbook.md`](docs/runbook.md) for how to read the output and
[`docs/sql_analysis.md`](docs/sql_analysis.md) for the SQL layer.

## Development

```bash
pip install -e ".[dev]"
ruff check .     # lint
pytest -v        # unit tests + eval dataset integrity checks
```

## Content note

The eval dataset contains synthetic examples of self-harm ideation at
varying severity, written for classifier evaluation. Per policy rule 3 in
`policy/self_harm_policy.md`, it deliberately never includes actual
method/dosage information as content — only classifies *requests* for it,
since generating that content is exactly the failure mode a real system
must not have.
