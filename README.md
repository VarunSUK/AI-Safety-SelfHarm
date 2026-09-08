# AI Safety — Self-Harm Risk Evaluation Harness

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
- **A review queue** — every disagreement and every case the gold set
  itself flags as ambiguous gets routed to `results/review_queue.md`,
  critical misses first.
- **SOPs and a runbook** written for how a team would actually operate this
  — [`docs/eval_creation_sop.md`](docs/eval_creation_sop.md) and
  [`docs/runbook.md`](docs/runbook.md).

## Project structure

```
policy/self_harm_policy.md   Severity tiers, expected behavior per tier, edge-case rules
eval/dataset.jsonl           28 hand-labeled cases across all 4 tiers + edge cases
src/classify.py              Runs the dataset through Claude, writes results/run_results.jsonl
src/metrics.py                Scores predictions against gold labels, writes the two reports below
results/metrics_report.md    Per-tier precision/recall/F1 + confusion matrix (generated)
results/review_queue.md      Critical misses, disagreements, ambiguous cases (generated)
docs/eval_creation_sop.md    How to add a new eval case
docs/runbook.md               How to run evals and interpret/escalate results
```

## Running it

```bash
pip install -r requirements.txt
cp .env.example .env      # add your ANTHROPIC_API_KEY
python src/classify.py
python src/metrics.py
```

See [`docs/runbook.md`](docs/runbook.md) for how to read the output.

## Content note

The eval dataset contains synthetic examples of self-harm ideation at
varying severity, written for classifier evaluation. Per policy rule 3 in
`policy/self_harm_policy.md`, it deliberately never includes actual
method/dosage information as content — only classifies *requests* for it,
since generating that content is exactly the failure mode a real system
must not have.
