"""
Runs a two-reviewer QA pass over the pending items in an eval suite's
review queue.

Each pending item is classified independently by two differently-framed
reviewer prompts (same underlying rubric, different emphasis — one applies
it literally, one is instructed to err toward the higher-risk tier when
genuinely torn). If the two reviewers agree with each other, the item is
auto-resolved to their shared tier. If they disagree, it's escalated rather
than silently trusting one reviewer — the same pattern a real review
operation uses a second reviewer + escalation path for, instead of trusting
a single pass.

Note: this simulates a two-person QA pass using two prompt framings, since
this is a portfolio project without a live review team. The schema
(review_queue / review_decisions) and the auto-resolve/escalate workflow are
what a real operation would run with actual human reviewers.

Usage:
    python src/qa_review.py [--suite self_harm|harmful_instructions]

Requires: results/<suite>/eval.db already built (run src/load_db.py first).
"""

import argparse
import json
import os
import sqlite3
import sys
import time

from anthropic import Anthropic
from dotenv import load_dotenv

from suites import ROOT, SUITES, get_suite


def classify_with_prompt(client, model, system_prompt, text):
    response = client.messages.create(
        model=model,
        max_tokens=200,
        system=system_prompt,
        messages=[{"role": "user", "content": text}],
    )
    parsed = json.loads(response.content[0].text.strip())
    return parsed["tier"], parsed.get("notes")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", default="self_harm", choices=sorted(SUITES))
    args = parser.parse_args()
    suite = get_suite(args.suite)
    reviewer_prompts = suite["reviewer_prompts"]

    db_path = suite["results_dir"] / "eval.db"
    report_path = suite["results_dir"] / "qa_review_report.md"

    load_dotenv(ROOT / ".env")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(
            "ANTHROPIC_API_KEY not set. Copy .env.example to .env and fill it in.",
            file=sys.stderr,
        )
        sys.exit(1)
    model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
    client = Anthropic(api_key=api_key)

    if not db_path.exists():
        print(f"{db_path} not found. Run src/load_db.py first.", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    latest = conn.execute("SELECT run_id FROM runs ORDER BY run_id DESC LIMIT 1").fetchone()
    if latest is None:
        print("No runs in the database.", file=sys.stderr)
        sys.exit(1)
    latest_run_id = latest["run_id"]

    pending = conn.execute(
        """SELECT rq.review_id, rq.case_id, rq.reason, ec.text, ec.gold_tier
           FROM review_queue rq
           JOIN eval_cases ec ON ec.id = rq.case_id
           WHERE rq.run_id = ? AND rq.status = 'pending'""",
        (latest_run_id,),
    ).fetchall()

    if not pending:
        print(f"No pending review queue items for run {latest_run_id}.")
        return

    report_lines = [
        f"# QA Review Report - {suite['label']}\n",
        f"Run: {latest_run_id}\n",
        f"Items reviewed: {len(pending)}\n",
        "PLACEHOLDER_SUMMARY\n",
    ]
    resolved, escalated = 0, 0

    for i, row in enumerate(pending, 1):
        print(f"[{i}/{len(pending)}] reviewing {row['case_id']}...", end=" ", flush=True)
        decisions = {}
        for reviewer, prompt in reviewer_prompts.items():
            tier, notes = classify_with_prompt(client, model, prompt, row["text"])
            decisions[reviewer] = (tier, notes)
            conn.execute(
                "INSERT INTO review_decisions (review_id, reviewer, decided_tier, notes) "
                "VALUES (?,?,?,?)",
                (row["review_id"], reviewer, tier, notes),
            )
            time.sleep(0.2)

        tiers = [t for t, _ in decisions.values()]
        agree = len(set(tiers)) == 1
        status = "auto_resolved" if agree else "escalated"
        conn.execute(
            "UPDATE review_queue SET status = ? WHERE review_id = ?",
            (status, row["review_id"]),
        )
        resolved += int(agree)
        escalated += int(not agree)
        print(status)

        report_lines.append(f"## {row['case_id']} ({row['reason']}) — {status}")
        report_lines.append(f"- gold tier: {row['gold_tier']}")
        for reviewer, (tier, notes) in decisions.items():
            report_lines.append(f"- {reviewer}: tier={tier} — {notes}")
        report_lines.append("")

    conn.commit()
    conn.close()

    n = len(pending)
    summary = (
        f"Auto-resolved (reviewers agreed): {resolved}/{n}  \n"
        f"Escalated (reviewers disagreed, needs a human tie-breaker): {escalated}/{n}\n"
    )
    report_lines[report_lines.index("PLACEHOLDER_SUMMARY\n")] = summary
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    print(f"\nAuto-resolved: {resolved}/{n}, Escalated: {escalated}/{n}")
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    main()
