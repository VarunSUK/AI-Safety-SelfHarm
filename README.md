# AI Safety Evaluation Harness

![CI](https://github.com/VarunSUK/AI-Safety-SelfHarm/actions/workflows/ci.yml/badge.svg)

A small, complete evaluation harness for AI safety classifiers, covering
**two eval suites** on one shared harness: self-harm/crisis risk, and
harmful-instructions/dangerous-capability refusal. Each suite has a policy
with severity tiers, a hand-labeled eval dataset built around edge cases
(not just the obvious ones), an LLM-based classifier (Claude), a metrics +
review-queue pipeline that treats missed high-severity cases as the metric
that matters most, a two-reviewer QA workflow, a SQL analysis layer, and an
interactive dashboard.

Built as a portfolio project for an AI safety / Trust & Safety evaluations
interview — deliberately scoped to demonstrate the full lifecycle of an eval
(policy → rubric → dataset → run → metrics → review queue → SOP), and to
show that lifecycle is a *methodology*, not a one-off script tied to a
single harm area. See [`src/suites.py`](src/suites.py) for the suite
registry; adding a third domain is policy doc + dataset + two prompts +
one registry entry (see [`docs/eval_creation_sop.md`](docs/eval_creation_sop.md)) —
everything else (scoring, SQL layer, dashboard, CI) works unmodified.

## Why this project

It mirrors the core workflow of an AI safety evaluations role:

- **Policy → rubric → measurable criteria, across two harm domains.**
  [`policy/self_harm_policy.md`](policy/self_harm_policy.md) and
  [`policy/harmful_instructions_policy.md`](policy/harmful_instructions_policy.md)
  each define severity tiers and, critically, *edge-case rules* — the
  actual hard part of writing a policy that a classifier can be scored
  against. The two share a tier structure (0 = no risk, 3 = severe/imminent)
  but different edge cases: self-harm's third-party reports and media
  quotation vs. harmful-instructions' roleplay jailbreaks and
  prompt-injection wrappers.
- **Labeled eval datasets that target tier boundaries and edge cases**, not
  just easy examples — [`eval/self_harm/dataset.jsonl`](eval/self_harm/dataset.jsonl)
  (28 cases: hyperbole, third-party reports, media quotation, method/lethality
  requests without stated intent, recovery narratives) and
  [`eval/harmful_instructions/dataset.jsonl`](eval/harmful_instructions/dataset.jsonl)
  (24 cases: dual-use professional framing, roleplay/fiction jailbreaks,
  prompt-injection obfuscation, false-authorization claims).
- **Running an eval and interpreting results** —
  [`src/classify.py`](src/classify.py) runs every case in a suite through
  Claude acting as the classifier under test (`--suite self_harm` or
  `--suite harmful_instructions`).
- **Tier-level precision/recall, not one blended accuracy number** —
  [`src/metrics.py`](src/metrics.py) computes per-tier precision/recall/F1
  and a confusion matrix, and separately surfaces **critical misses**
  (a truly high-severity case scored as lower severity) as the single most
  important signal, ahead of overall accuracy — for both suites.
- **A review queue with a two-reviewer QA pass** — every disagreement and
  every case the gold set itself flags as ambiguous gets routed to
  `results/<suite>/review_queue.md` / the `review_queue` table, critical
  misses first. [`src/qa_review.py`](src/qa_review.py) then runs a second,
  independently-framed reviewer pass over the queue: items the two
  reviewers agree on are auto-resolved, items they disagree on are
  escalated rather than trusted on one pass — a quality-assurance pattern,
  not just a bigger prompt.
- **A SQL analysis layer** — [`src/load_db.py`](src/load_db.py) loads every
  eval case, every archived run, and the review queue into SQLite
  (`results/<suite>/eval.db`, one per suite, same schema), with example
  queries in [`queries/`](queries/) for per-tier precision/recall, critical
  misses, review-queue backlog by status, tier-3 recall trend across runs,
  and reviewer agreement — see [`docs/sql_analysis.md`](docs/sql_analysis.md).
- **SOPs and a runbook** written for how a team would actually operate this
  — [`docs/eval_creation_sop.md`](docs/eval_creation_sop.md) (including how
  to add a whole new suite) and [`docs/runbook.md`](docs/runbook.md).
- **An interactive dashboard** — [`dashboard/app.py`](dashboard/app.py)
  (Streamlit) with a suite picker, reading `results/<suite>/eval.db`
  directly: KPI tiles (accuracy, tier-3 recall, critical misses), per-tier
  precision/recall, a confusion-matrix heatmap, a review-queue table, and a
  tier-3-recall trend line across runs.
- **A test suite and CI** — [`tests/`](tests/) covers the scoring logic
  (critical-miss classification, join semantics) and both eval datasets'
  own integrity (unique ids, valid tiers, every tier represented,
  consistent schema per suite), parametrized over every registered suite
  and run on every push via [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

## Mapping to the role

Built against Anthropic's Safeguards Enforcement Analyst postings
(both the Safety Evaluations and User Well-being variants — the two-suite
structure exists specifically so the project speaks to the general "safety
evaluations across domains" framing as well as the self-harm-specific one):

| Posting | Where |
|---|---|
| "Curating evaluation datasets" / "designing or running experiments... to determine whether an intervention worked" | `eval/*/dataset.jsonl`, `src/metrics.py` |
| "Translating policy definitions into measurable form — rubrics, review guidelines, classification criteria" | `policy/self_harm_policy.md`, `policy/harmful_instructions_policy.md` |
| "Ensuring evaluations are comprehensive and current" across "evolving policies, threat vectors" | Two independent suites on one harness (`src/suites.py`) — adding a third domain is a policy doc + dataset + registry entry |
| "Threshold-setting and precision/recall tradeoffs" | `src/metrics.py` per-tier precision/recall, `queries/01_tier_precision_recall.sql` |
| "Managing or coordinating content review operations, including quality assurance and workflow management" | `src/qa_review.py`, `review_queue`/`review_decisions` tables |
| "Proficiency in SQL... to measure intervention efficacy, monitor workflow health, and surface policy gaps" | `results/<suite>/eval.db`, `queries/*.sql`, `docs/sql_analysis.md` |
| "Review flagged content to drive enforcement and policy improvements" | `results/<suite>/review_queue.md`, `docs/eval_creation_sop.md`'s "fix the policy first" rule |
| "Monitor how interventions and detection systems perform over time" | `results/<suite>/runs/`, `queries/04_metric_trend_over_runs.sql` |
| "Sound judgment in ambiguous, high-consequence cases" | `ambiguous` field, edge-case rules in each policy |
| "Proficiency with data tools (SQL, dashboards, spreadsheets)" | `dashboard/app.py` (Streamlit) on top of `results/<suite>/eval.db` |
| Preferred: "Experience using agentic tools (e.g. Claude Code) to scale analysis" | this project was built with Claude Code |

Honest gaps: there's no in-product feature here connecting users to crisis
resources (the Product/Legal/external-partner referral-pathway work); the
classifier outputs a discrete tier rather than a continuous score, so this
project demonstrates tier-based classification tradeoffs rather than
continuous threshold tuning; and neither suite has been run against a live
model yet (no API key used in building this — see the "Running it" section
for how to actually generate results). This project is the
detection/eval/review side only.

## Project structure

```
src/suites.py                 Suite registry: dataset/results paths + classify & reviewer prompts per domain
policy/self_harm_policy.md    Severity tiers, expected behavior per tier, edge-case rules (self-harm)
policy/harmful_instructions_policy.md  Same, for dangerous-capability / harmful-instruction requests
eval/self_harm/dataset.jsonl              28 hand-labeled cases across all 4 tiers + edge cases
eval/harmful_instructions/dataset.jsonl   24 hand-labeled cases across all 4 tiers + edge cases
src/classify.py                Runs a suite's dataset through Claude, writes results/<suite>/run_results.jsonl + runs/<run_id>.jsonl
src/scoring.py                 Shared join/disagreement logic used by metrics.py and load_db.py (suite-agnostic)
src/metrics.py                 Scores predictions against gold labels, writes the two reports below
src/load_db.py                 Loads cases + runs + review queue into results/<suite>/eval.db (SQLite)
src/qa_review.py               Two-reviewer QA pass over the review queue: auto-resolve or escalate
queries/*.sql                  Example analysis queries (precision/recall, critical misses, trends, QA agreement)
dashboard/app.py               Streamlit dashboard over results/<suite>/eval.db, with a suite picker
tests/                         pytest suite: scoring logic + eval dataset integrity checks, parametrized over every suite
results/<suite>/metrics_report.md   Per-tier precision/recall/F1 + confusion matrix (generated)
results/<suite>/review_queue.md     Critical misses, disagreements, ambiguous cases (generated)
results/<suite>/qa_review_report.md Reviewer decisions + auto-resolved/escalated counts (generated)
docs/eval_creation_sop.md      How to add a new eval case, or a whole new suite
docs/runbook.md                How to run evals and interpret/escalate results
docs/sql_analysis.md           Schema + how to use the SQL analysis layer
.github/workflows/ci.yml       Lint (ruff) + test (pytest) on every push
```

## Running it

```bash
pip install -e ".[dev,dashboard]"
cp .env.example .env      # add your ANTHROPIC_API_KEY

python src/classify.py --suite self_harm
python src/metrics.py --suite self_harm
python src/load_db.py --suite self_harm
python src/qa_review.py --suite self_harm

python src/classify.py --suite harmful_instructions
python src/metrics.py --suite harmful_instructions
python src/load_db.py --suite harmful_instructions
python src/qa_review.py --suite harmful_instructions

streamlit run dashboard/app.py   # pick a suite from the dropdown
```

See [`docs/runbook.md`](docs/runbook.md) for how to read the output and
[`docs/sql_analysis.md`](docs/sql_analysis.md) for the SQL layer.

## Development

```bash
pip install -e ".[dev]"
ruff check .     # lint
pytest -v        # unit tests + eval dataset integrity checks (both suites)
```

## Content note

Both eval datasets contain synthetic examples — self-harm ideation, and
dangerous-capability requests — written for classifier evaluation, at
varying severity. Per each policy's content rule, neither dataset ever
includes the actual harmful content as an *answer* — only classifies
*requests* for it (a lethality question, an exploit request, a synthesis
request), using generic, non-operational placeholders throughout, since
generating that content is exactly the failure mode each suite exists to
catch.
