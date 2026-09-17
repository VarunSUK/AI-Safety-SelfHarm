"""
Runs every case in an eval suite's dataset through Claude acting as the
classifier under test, and writes predictions to
results/<suite>/run_results.jsonl (plus an archived copy per run under
results/<suite>/runs/).

Usage:
    python src/classify.py [--suite self_harm|harmful_instructions] [--limit N]

Requires ANTHROPIC_API_KEY (see .env.example).
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

from suites import SUITES, get_suite

ROOT = Path(__file__).resolve().parent.parent


def load_dataset(dataset_path):
    cases = []
    with open(dataset_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def classify_one(client, model, system_prompt, text):
    response = client.messages.create(
        model=model,
        max_tokens=300,
        system=system_prompt,
        messages=[{"role": "user", "content": text}],
    )
    raw = response.content[0].text.strip()
    return raw, json.loads(raw)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", default="self_harm", choices=sorted(SUITES))
    parser.add_argument("--limit", type=int, default=None, help="Only run the first N cases")
    args = parser.parse_args()
    suite = get_suite(args.suite)

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
    cases = load_dataset(suite["dataset_path"])
    if args.limit:
        cases = cases[: args.limit]

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results_dir = suite["results_dir"]
    results_path = results_dir / "run_results.jsonl"
    runs_dir = results_dir / "runs"
    results_dir.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for i, case in enumerate(cases, 1):
        print(f"[{i}/{len(cases)}] {case['id']}...", end=" ", flush=True)
        try:
            raw, parsed = classify_one(client, model, suite["classify_prompt"], case["text"])
            result = {
                "id": case["id"],
                "run_id": run_id,
                "model": model,
                "predicted_tier": parsed.get("tier"),
                "rationale": parsed.get("rationale"),
                "extra": {k: v for k, v in parsed.items() if k not in ("tier", "rationale")},
                "error": None,
            }
            print(f"tier={result['predicted_tier']}")
        except Exception as exc:  # API errors, malformed JSON, etc.
            result = {
                "id": case["id"],
                "run_id": run_id,
                "model": model,
                "predicted_tier": None,
                "rationale": None,
                "extra": {},
                "error": str(exc),
            }
            print(f"ERROR: {exc}")
        results.append(result)
        time.sleep(0.2)  # stay well under rate limits

    # results/<suite>/run_results.jsonl always reflects the latest run (what
    # metrics.py scores by default); results/<suite>/runs/<run_id>.jsonl
    # archives every run so trends can be tracked over time (queries/04_*.sql).
    with open(results_path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")
    with open(runs_dir / f"{run_id}.jsonl", "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    print(f"\nWrote {len(results)} predictions to {results_path} and {runs_dir / run_id}.jsonl")


if __name__ == "__main__":
    main()
