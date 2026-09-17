# SOP: Adding a New Eval Case (or a New Eval Suite)

This describes how to add a case to an existing suite's `dataset.jsonl`, and
how to add an entirely new suite, written the way a team runbook would be so
a new reviewer (technical or not) could follow it without prior context.

The harness currently covers two suites — see `src/suites.py`:

| Suite | Policy | Dataset |
|---|---|---|
| `self_harm` | `policy/self_harm_policy.md` | `eval/self_harm/dataset.jsonl` |
| `harmful_instructions` | `policy/harmful_instructions_policy.md` | `eval/harmful_instructions/dataset.jsonl` |

## Adding a case to an existing suite

### 1. Decide what gap the case fills

Before writing a case, check whether it's actually needed:

- Does an existing case already cover this tier + edge-case combination? If
  yes, a near-duplicate adds noise, not signal — skip it.
- Is this covering a **known failure mode** (something the classifier has
  gotten wrong in a past run — see `results/<suite>/review_queue.md`), a
  **new edge-case type** not yet represented, or a **tier boundary** (the
  line between tier 1 and tier 2 is where most disagreement happens — that
  boundary deserves more cases than the obvious tier-0 and tier-3 extremes)?

An eval set that only contains easy, obvious cases saturates immediately
(every model gets 100%) and stops being useful. The valuable cases live at
the boundaries and in the edge-case list in that suite's policy doc.

### 2. Write the case

Add one line to `eval/<suite>/dataset.jsonl`. Every suite's cases must share
`id`, `text`, `gold_tier`, `ambiguous`, `edge_case_type`, and `notes`
(enforced by `tests/test_dataset.py`); suite-specific boolean flags (e.g.
self-harm's `requires_resources`/`third_party`, or harmful_instructions'
`requires_refusal`/`dual_use_borderline`) are additive and must be present
on every case within that one suite (also enforced by the tests — a suite's
own rows must share one field set even though different suites don't have
to share it with each other):

```json
{
  "id": "t<tier>-<sequence>",
  "text": "<the input message>",
  "gold_tier": 0,
  "ambiguous": false,
  "edge_case_type": "hyperbole",
  "notes": "<one sentence explaining why this tier, referencing the policy rule if relevant>"
}
```

- `id` — `{letter}{tier}-{two-digit sequence}` (e.g. `t2-05`, `h3-01`),
  unique within the file. The leading letter is free-form per suite (`t` for
  self_harm, `h` for harmful_instructions) but the digit right after it must
  equal `gold_tier` — a test enforces this.
- `gold_tier` — must be justified by a rule in that suite's policy doc, not
  by gut feel. If you can't point to which policy rule drives the label, the
  case isn't ready yet — go fix the policy first (see step 4) or don't add
  it.
- `ambiguous` — set `true` if a reasonable, policy-literate reviewer could
  land on a different tier. Ambiguous cases are always routed to the review
  queue regardless of what the model predicts (see `src/metrics.py`).
- `notes` — this is what a reviewer reads to understand *why* the label is
  what it is. Write it for someone who has read the policy but not written
  this case.

### 3. Never include real harmful content as an *answer*

Method, dosage, or attack-capability **requests** are valid and important
eval inputs — that's the whole point of a tier-3 case. The dataset must
never contain the corresponding harmful information as content, only the
request itself (self-harm policy rule 3; harmful_instructions policy's
Content note).

### 4. If the case doesn't fit the current policy, fix the policy first

If a real case doesn't cleanly map to an existing tier, that's a signal the
policy has a gap, not that the case should be forced into the closest tier.
Update that suite's policy doc with a new edge-case rule (with rationale),
then label the case against the updated rule. Policy changes and the eval
cases that motivated them should land in the same PR so the "why" isn't
lost.

### 5. Re-run the harness

```bash
python src/classify.py --suite <suite>
python src/metrics.py --suite <suite>
```

Check `results/<suite>/metrics_report.md` for the new tier's
precision/recall and `results/<suite>/review_queue.md` for whether the new
case landed in a critical miss or other disagreement.

## Adding an entirely new suite

1. Write a policy doc under `policy/` following the structure of the
   existing two: severity tiers, expected behavior per tier, edge-case
   guidance, and a "metrics that matter" note.
2. Write `eval/<suite>/dataset.jsonl` covering every tier, weighted toward
   boundaries and edge cases (not easy obvious ones — see step 1 above).
3. Add a classify prompt and two reviewer prompts (strict + err-cautious) to
   `src/suites.py`, and register the suite in the `SUITES` dict with its
   `dataset_path`, `results_dir`, and `policy_path`.
4. That's it — `classify.py`, `metrics.py`, `load_db.py`, `qa_review.py`,
   every `queries/*.sql` file, the dashboard, and the CI-run test suite all
   work against the new suite unmodified, because none of them depend on
   suite-specific prompt text or gold-label field names.
