# SOP: Adding a New Eval Case

This describes how to add a case to `eval/dataset.jsonl`, written the way a
team runbook would be so a new reviewer (technical or not) could follow it
without prior context.

## 1. Decide what gap the case fills

Before writing a case, check whether it's actually needed:

- Does an existing case already cover this tier + edge-case combination? If
  yes, a near-duplicate adds noise, not signal — skip it.
- Is this covering a **known failure mode** (something the classifier has
  gotten wrong in a past run — see `results/review_queue.md`), a **new
  edge-case type** not yet represented, or a **tier boundary** (the line
  between tier 1 and tier 2 is where most disagreement happens — that
  boundary deserves more cases than the obvious tier-0 and tier-3 extremes)?

An eval set that only contains easy, obvious cases saturates immediately
(every model gets 100%) and stops being useful. The valuable cases live at
the boundaries and in the edge-case list in `policy/self_harm_policy.md`.

## 2. Write the case

Add one line to `eval/dataset.jsonl` with this schema:

```json
{
  "id": "t<tier>-<sequence>",
  "text": "<the input message>",
  "gold_tier": 0,
  "requires_resources": false,
  "third_party": false,
  "ambiguous": false,
  "edge_case_type": "hyperbole",
  "notes": "<one sentence explaining why this tier, referencing the policy rule if relevant>"
}
```

- `id` — `t{tier}-{two-digit sequence}`, unique within the file.
- `gold_tier` — must be justified by a rule in `policy/self_harm_policy.md`,
  not by gut feel. If you can't point to which policy rule drives the label,
  the case isn't ready yet — go fix the policy first (see step 4) or don't
  add it.
- `ambiguous` — set `true` if a reasonable, policy-literate reviewer could
  land on a different tier. Ambiguous cases are always routed to the review
  queue regardless of what the model predicts (see `src/metrics.py`).
- `notes` — this is what a reviewer reads to understand *why* the label is
  what it is. Write it for someone who has read the policy but not written
  this case.

## 3. Never include real method/dosage information as an *answer*

Method or lethality **requests** are valid and important eval inputs (they
are Tier 3 signals per policy rule 5). The dataset must never contain the
corresponding harmful information as content — only the request itself.

## 4. If the case doesn't fit the current policy, fix the policy first

If a real case doesn't cleanly map to an existing tier, that's a signal the
policy has a gap, not that the case should be forced into the closest tier.
Update `policy/self_harm_policy.md` with a new edge-case rule (with
rationale), then label the case against the updated rule. Policy changes and
the eval cases that motivated them should land in the same PR so the "why"
isn't lost.

## 5. Re-run the harness

```bash
python src/classify.py
python src/metrics.py
```

Check `results/metrics_report.md` for the new tier's precision/recall and
`results/review_queue.md` for whether the new case landed in a critical miss
or other disagreement.
