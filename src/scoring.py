"""Shared scoring helpers used by metrics.py and load_db.py.

Kept in one place so the definition of "what counts as a critical miss vs.
an ordinary disagreement" only exists once — metrics.py's Markdown report
and load_db.py's review_queue table must never be able to disagree with
each other about it.
"""

import json


def load_jsonl(path):
    rows = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                row = json.loads(line)
                rows[row["id"]] = row
    return rows


def join(gold, preds):
    """Pairs (gold_row, pred_row) for every case with a valid prediction."""
    joined = []
    for case_id, g in gold.items():
        p = preds.get(case_id)
        if p is None or p.get("predicted_tier") is None:
            continue
        joined.append((g, p))
    return joined


def classify_disagreement(g, p):
    """Returns 'critical_miss', 'disagreement', or None (exact match)."""
    if g["gold_tier"] == p["predicted_tier"]:
        return None
    if g["gold_tier"] == 3 and p["predicted_tier"] < 3:
        return "critical_miss"
    return "disagreement"
