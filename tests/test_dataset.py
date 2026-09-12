"""Sanity checks on eval/dataset.jsonl itself.

These exist because a labeled eval set is only as trustworthy as its own
integrity: a duplicate id, a stray tier value, or an id whose prefix
disagrees with its own gold_tier would silently corrupt every metric
computed from it. Run in CI so a bad case gets caught at PR time, not after
someone's already trusted a metrics report built on top of it.
"""

import json
from pathlib import Path

DATASET_PATH = Path(__file__).resolve().parent.parent / "eval" / "dataset.jsonl"
REQUIRED_FIELDS = {
    "id",
    "text",
    "gold_tier",
    "requires_resources",
    "third_party",
    "ambiguous",
    "edge_case_type",
    "notes",
}


def load_cases():
    with open(DATASET_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def test_dataset_is_non_empty():
    assert len(load_cases()) > 0


def test_ids_are_unique():
    cases = load_cases()
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)), "duplicate case id in eval/dataset.jsonl"


def test_every_case_has_required_fields():
    for case in load_cases():
        missing = REQUIRED_FIELDS - set(case)
        assert not missing, f"{case.get('id')} is missing fields: {missing}"


def test_gold_tier_is_in_valid_range():
    for case in load_cases():
        assert case["gold_tier"] in (0, 1, 2, 3), f"{case['id']} has invalid gold_tier"


def test_boolean_fields_are_actual_booleans():
    for case in load_cases():
        for field in ("requires_resources", "third_party", "ambiguous"):
            assert isinstance(case[field], bool), f"{case['id']}.{field} is not a bool"


def test_id_prefix_matches_gold_tier():
    for case in load_cases():
        prefix_tier = int(case["id"].split("-")[0].lstrip("t"))
        assert prefix_tier == case["gold_tier"], (
            f"{case['id']} id prefix implies tier {prefix_tier} "
            f"but gold_tier is {case['gold_tier']}"
        )


def test_all_tiers_are_represented():
    tiers = {c["gold_tier"] for c in load_cases()}
    assert tiers == {0, 1, 2, 3}, "eval set should cover every severity tier"
