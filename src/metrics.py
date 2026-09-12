"""
Joins eval/dataset.jsonl (gold labels) against results/run_results.jsonl
(model predictions) and produces:

  results/metrics_report.md - tier-level precision/recall/F1, confusion
                               matrix, and overall accuracy
  results/review_queue.md   - every disagreement, with critical misses
                               (gold tier 3 scored lower) surfaced first,
                               followed by all cases labeled ambiguous
                               in the gold set

Usage:
    python src/metrics.py
"""

from collections import defaultdict
from pathlib import Path

from scoring import classify_disagreement, join, load_jsonl

ROOT = Path(__file__).resolve().parent.parent
DATASET_PATH = ROOT / "eval" / "dataset.jsonl"
RESULTS_PATH = ROOT / "results" / "run_results.jsonl"
METRICS_REPORT_PATH = ROOT / "results" / "metrics_report.md"
REVIEW_QUEUE_PATH = ROOT / "results" / "review_queue.md"

TIERS = [0, 1, 2, 3]


def precision_recall_f1(tp, fp, fn):
    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")
    valid = precision == precision and recall == recall and (precision + recall) > 0
    f1 = 2 * precision * recall / (precision + recall) if valid else float("nan")
    return precision, recall, f1


def main():
    gold = load_jsonl(DATASET_PATH)
    preds = load_jsonl(RESULTS_PATH)

    missing = set(gold) - set(preds)
    if missing:
        print(f"Warning: {len(missing)} cases have no prediction (run src/classify.py first).")

    joined = join(gold, preds)
    n = len(joined)
    correct = sum(1 for g, p in joined if g["gold_tier"] == p["predicted_tier"])
    accuracy = correct / n if n else float("nan")

    confusion = defaultdict(int)  # (gold, pred) -> count
    for g, p in joined:
        confusion[(g["gold_tier"], p["predicted_tier"])] += 1

    tier_stats = {}
    for t in TIERS:
        tp = confusion[(t, t)]
        fp = sum(confusion[(g, t)] for g in TIERS if g != t)
        fn = sum(confusion[(t, p)] for p in TIERS if p != t)
        precision, recall, f1 = precision_recall_f1(tp, fp, fn)
        tier_stats[t] = {
            "tp": tp, "fp": fp, "fn": fn,
            "precision": precision, "recall": recall, "f1": f1,
        }

    disagreements = [(g, p, classify_disagreement(g, p)) for g, p in joined]
    critical_misses = [(g, p) for g, p, reason in disagreements if reason == "critical_miss"]
    other_disagreements = [(g, p) for g, p, reason in disagreements if reason == "disagreement"]

    lines = []
    lines.append("# Metrics Report\n")
    lines.append(f"Cases scored: {n} (of {len(gold)} in dataset)\n")
    lines.append(f"Overall accuracy: {accuracy:.1%}\n")
    lines.append(f"**Tier-3 critical misses: {len(critical_misses)}** "
                 f"(gold=imminent risk, model scored it lower — the metric that matters most)\n")

    lines.append("## Per-tier precision / recall / F1\n")
    lines.append("| Tier | TP | FP | FN | Precision | Recall | F1 |")
    lines.append("|------|----|----|----|-----------|--------|----|")
    for t in TIERS:
        s = tier_stats[t]
        lines.append(
            f"| {t} | {s['tp']} | {s['fp']} | {s['fn']} | "
            f"{s['precision']:.1%} | {s['recall']:.1%} | {s['f1']:.1%} |"
        )
    lines.append("")

    lines.append("## Confusion matrix (rows = gold, cols = predicted)\n")
    header = "| gold \\\\ pred | " + " | ".join(str(t) for t in TIERS) + " |"
    lines.append(header)
    lines.append("|" + "---|" * (len(TIERS) + 1))
    for g in TIERS:
        row = [str(confusion[(g, p)]) for p in TIERS]
        lines.append(f"| {g} | " + " | ".join(row) + " |")
    lines.append("")

    METRICS_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")

    review_lines = ["# Review Queue\n"]
    review_lines.append(
        "Cases routed to human review: critical misses first (highest priority), "
        "then all disagreements, then every case the gold set itself flags as ambiguous.\n"
    )

    if critical_misses:
        review_lines.append("## 🔴 Critical misses (gold tier 3, scored lower)\n")
        for g, p in critical_misses:
            review_lines.append(
                f"- **{g['id']}** — gold=3, predicted={p['predicted_tier']}\n"
                f"  - text: \"{g['text']}\"\n"
                f"  - model rationale: {p.get('rationale')}\n"
            )

    if other_disagreements:
        review_lines.append("## 🟡 Other disagreements\n")
        for g, p in other_disagreements:
            review_lines.append(
                f"- **{g['id']}** — gold={g['gold_tier']}, predicted={p['predicted_tier']}\n"
                f"  - text: \"{g['text']}\"\n"
                f"  - model rationale: {p.get('rationale')}\n"
            )

    ambiguous_cases = [g for g in gold.values() if g.get("ambiguous")]
    if ambiguous_cases:
        review_lines.append(
            "## ⚪ Flagged ambiguous in gold set (always reviewed regardless of model output)\n"
        )
        for g in ambiguous_cases:
            p = preds.get(g["id"], {})
            review_lines.append(
                f"- **{g['id']}** — gold={g['gold_tier']}, predicted={p.get('predicted_tier')}\n"
                f"  - text: \"{g['text']}\"\n"
                f"  - note: {g.get('notes')}\n"
            )

    REVIEW_QUEUE_PATH.write_text("\n".join(review_lines), encoding="utf-8")

    print(f"Accuracy: {accuracy:.1%} ({correct}/{n})")
    print(f"Critical misses: {len(critical_misses)}")
    print(f"Wrote {METRICS_REPORT_PATH}")
    print(f"Wrote {REVIEW_QUEUE_PATH}")


if __name__ == "__main__":
    main()
