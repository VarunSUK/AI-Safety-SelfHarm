"""
Builds/refreshes results/<suite>/eval.db (SQLite) from an eval suite's
dataset.jsonl and every archived run in results/<suite>/runs/*.jsonl.

Tables:
  eval_cases      gold labels, one row per case. Fields common across every
                  suite (id, text, gold_tier, ambiguous, edge_case_type,
                  notes) are columns; anything suite-specific (e.g.
                  self-harm's requires_resources/third_party, or
                  harmful_instructions' requires_refusal/dual_use_borderline)
                  lives in extra_json so the schema doesn't have to change
                  per domain.
  runs            one row per classify.py run (run_id, model)
  predictions     one row per (run_id, case_id); suite-specific prediction
                  fields live in extra_json the same way
  review_queue    auto-rebuilt for the LATEST run only: critical misses,
                  other disagreements, and gold-flagged ambiguous cases,
                  each starting status='pending'
  review_decisions  filled in by src/qa_review.py

Usage:
    python src/load_db.py [--suite self_harm|harmful_instructions]
"""

import argparse
import json
import sqlite3

from scoring import classify_disagreement, join, load_jsonl
from suites import SUITES, get_suite

SCHEMA = """
CREATE TABLE IF NOT EXISTS eval_cases (
    id TEXT PRIMARY KEY,
    text TEXT,
    gold_tier INTEGER,
    ambiguous INTEGER,
    edge_case_type TEXT,
    notes TEXT,
    extra_json TEXT
);

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    model TEXT
);

CREATE TABLE IF NOT EXISTS predictions (
    run_id TEXT,
    case_id TEXT,
    predicted_tier INTEGER,
    rationale TEXT,
    extra_json TEXT,
    error TEXT,
    PRIMARY KEY (run_id, case_id)
);

CREATE TABLE IF NOT EXISTS review_queue (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    case_id TEXT,
    reason TEXT,
    status TEXT DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS review_decisions (
    review_id INTEGER,
    reviewer TEXT,
    decided_tier INTEGER,
    notes TEXT,
    FOREIGN KEY (review_id) REFERENCES review_queue(review_id)
);
"""

COMMON_CASE_FIELDS = {"id", "text", "gold_tier", "ambiguous", "edge_case_type", "notes"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", default="self_harm", choices=sorted(SUITES))
    args = parser.parse_args()
    suite = get_suite(args.suite)

    dataset_path = suite["dataset_path"]
    runs_dir = suite["results_dir"] / "runs"
    db_path = suite["results_dir"] / "eval.db"

    gold = load_jsonl(dataset_path)
    run_files = sorted(runs_dir.glob("*.jsonl"))
    if not run_files:
        raise SystemExit(f"No runs found in {runs_dir}. Run src/classify.py first.")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)

    conn.execute("DELETE FROM eval_cases")
    for g in gold.values():
        extra = {k: v for k, v in g.items() if k not in COMMON_CASE_FIELDS}
        conn.execute(
            "INSERT INTO eval_cases VALUES (?,?,?,?,?,?,?)",
            (
                g["id"], g["text"], g["gold_tier"],
                int(bool(g["ambiguous"])), g["edge_case_type"], g["notes"],
                json.dumps(extra),
            ),
        )

    latest_run_id = None
    for run_file in run_files:
        run_id = run_file.stem
        latest_run_id = run_id  # run_ids are UTC timestamps, so filenames sort chronologically
        preds = load_jsonl(run_file)
        model = next((p.get("model") for p in preds.values() if p.get("model")), "unknown")
        conn.execute("INSERT OR REPLACE INTO runs VALUES (?,?)", (run_id, model))
        conn.execute("DELETE FROM predictions WHERE run_id = ?", (run_id,))
        for case_id, p in preds.items():
            conn.execute(
                "INSERT INTO predictions VALUES (?,?,?,?,?,?)",
                (
                    run_id, case_id, p.get("predicted_tier"), p.get("rationale"),
                    json.dumps(p.get("extra") or {}), p.get("error"),
                ),
            )

    # Review queue only ever reflects the latest run — older runs' queues
    # are history, not something to keep re-triaging.
    conn.execute("DELETE FROM review_queue WHERE run_id = ?", (latest_run_id,))
    latest_preds = load_jsonl(runs_dir / f"{latest_run_id}.jsonl")
    joined = join(gold, latest_preds)
    for g, p in joined:
        reason = classify_disagreement(g, p)
        if reason:
            conn.execute(
                "INSERT INTO review_queue (run_id, case_id, reason, status) "
                "VALUES (?,?,?,'pending')",
                (latest_run_id, g["id"], reason),
            )
    for g in gold.values():
        if g.get("ambiguous"):
            already_queued = conn.execute(
                "SELECT 1 FROM review_queue WHERE run_id=? AND case_id=?",
                (latest_run_id, g["id"]),
            ).fetchone()
            if not already_queued:
                conn.execute(
                    "INSERT INTO review_queue (run_id, case_id, reason, status) "
                    "VALUES (?,?,?,'pending')",
                    (latest_run_id, g["id"], "ambiguous_gold_label"),
                )

    conn.commit()
    n_cases = conn.execute("SELECT COUNT(*) FROM eval_cases").fetchone()[0]
    n_runs = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    n_queue = conn.execute(
        "SELECT COUNT(*) FROM review_queue WHERE run_id=?", (latest_run_id,)
    ).fetchone()[0]
    conn.close()

    print(f"[{suite['label']}] Loaded {n_cases} eval cases and {n_runs} run(s) into {db_path}")
    print(f"Latest run: {latest_run_id} — {n_queue} item(s) in review queue")


if __name__ == "__main__":
    main()
