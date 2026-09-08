"""
Builds/refreshes results/eval.db (SQLite) from eval/dataset.jsonl and every
archived run in results/runs/*.jsonl.

Tables:
  eval_cases      gold labels, one row per case
  runs            one row per classify.py run (run_id, model)
  predictions     one row per (run_id, case_id)
  review_queue    auto-rebuilt for the LATEST run only: critical misses,
                  other disagreements, and gold-flagged ambiguous cases,
                  each starting status='pending'
  review_decisions  filled in by src/qa_review.py

Usage:
    python src/load_db.py
"""

import sqlite3
from pathlib import Path

from scoring import load_jsonl, join, classify_disagreement

ROOT = Path(__file__).resolve().parent.parent
DATASET_PATH = ROOT / "eval" / "dataset.jsonl"
RUNS_DIR = ROOT / "results" / "runs"
DB_PATH = ROOT / "results" / "eval.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS eval_cases (
    id TEXT PRIMARY KEY,
    text TEXT,
    gold_tier INTEGER,
    requires_resources INTEGER,
    third_party INTEGER,
    ambiguous INTEGER,
    edge_case_type TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    model TEXT
);

CREATE TABLE IF NOT EXISTS predictions (
    run_id TEXT,
    case_id TEXT,
    predicted_tier INTEGER,
    predicted_requires_resources INTEGER,
    predicted_third_party INTEGER,
    rationale TEXT,
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


def to_int_or_none(v):
    return None if v is None else int(v)


def main():
    gold = load_jsonl(DATASET_PATH)
    run_files = sorted(RUNS_DIR.glob("*.jsonl"))
    if not run_files:
        raise SystemExit("No runs found in results/runs/. Run src/classify.py first.")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)

    conn.execute("DELETE FROM eval_cases")
    for g in gold.values():
        conn.execute(
            "INSERT INTO eval_cases VALUES (?,?,?,?,?,?,?,?)",
            (
                g["id"], g["text"], g["gold_tier"],
                int(g["requires_resources"]), int(g["third_party"]), int(g["ambiguous"]),
                g["edge_case_type"], g["notes"],
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
                "INSERT INTO predictions VALUES (?,?,?,?,?,?,?)",
                (
                    run_id, case_id, p.get("predicted_tier"),
                    to_int_or_none(p.get("predicted_requires_resources")),
                    to_int_or_none(p.get("predicted_third_party")),
                    p.get("rationale"), p.get("error"),
                ),
            )

    # Review queue only ever reflects the latest run — older runs' queues
    # are history, not something to keep re-triaging.
    conn.execute("DELETE FROM review_queue WHERE run_id = ?", (latest_run_id,))
    latest_preds = load_jsonl(RUNS_DIR / f"{latest_run_id}.jsonl")
    joined = join(gold, latest_preds)
    for g, p in joined:
        reason = classify_disagreement(g, p)
        if reason:
            conn.execute(
                "INSERT INTO review_queue (run_id, case_id, reason, status) VALUES (?,?,?,'pending')",
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
                    "INSERT INTO review_queue (run_id, case_id, reason, status) VALUES (?,?,?,'pending')",
                    (latest_run_id, g["id"], "ambiguous_gold_label"),
                )

    conn.commit()
    n_cases = conn.execute("SELECT COUNT(*) FROM eval_cases").fetchone()[0]
    n_runs = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    n_queue = conn.execute(
        "SELECT COUNT(*) FROM review_queue WHERE run_id=?", (latest_run_id,)
    ).fetchone()[0]
    conn.close()

    print(f"Loaded {n_cases} eval cases and {n_runs} run(s) into {DB_PATH}")
    print(f"Latest run: {latest_run_id} — {n_queue} item(s) in review queue")


if __name__ == "__main__":
    main()
