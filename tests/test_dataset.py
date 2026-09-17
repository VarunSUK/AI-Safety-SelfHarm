"""Sanity checks on every eval suite's dataset.jsonl.

These exist because a labeled eval set is only as trustworthy as its own
integrity: a duplicate id, a stray tier value, or an id whose prefix
disagrees with its own gold_tier would silently corrupt every metric
computed from it. Run in CI so a bad case gets caught at PR time, not after
someone's already trusted a metrics report built on top of it. Parametrized
over every suite in src/suites.py so adding a new domain gets these checks
for free.
"""

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from suites import SUITES  # noqa: E402

COMMON_REQUIRED_FIELDS = {"id", "text", "gold_tier", "ambiguous", "edge_case_type", "notes"}
SUITE_NAMES = sorted(SUITES)


def load_cases(suite_name):
    path = SUITES[suite_name]["dataset_path"]
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


@pytest.mark.parametrize("suite_name", SUITE_NAMES)
def test_dataset_is_non_empty(suite_name):
    assert len(load_cases(suite_name)) > 0


@pytest.mark.parametrize("suite_name", SUITE_NAMES)
def test_ids_are_unique(suite_name):
    cases = load_cases(suite_name)
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)), f"duplicate case id in {suite_name} dataset"


@pytest.mark.parametrize("suite_name", SUITE_NAMES)
def test_every_case_has_common_required_fields(suite_name):
    for case in load_cases(suite_name):
        missing = COMMON_REQUIRED_FIELDS - set(case)
        assert not missing, f"{suite_name}/{case.get('id')} is missing fields: {missing}"


@pytest.mark.parametrize("suite_name", SUITE_NAMES)
def test_every_case_in_a_suite_shares_the_same_field_set(suite_name):
    cases = load_cases(suite_name)
    expected = set(cases[0])
    for case in cases[1:]:
        assert set(case) == expected, (
            f"{suite_name}/{case['id']} has a different field set than "
            f"{suite_name}/{cases[0]['id']} — every case in one suite must share one schema"
        )


@pytest.mark.parametrize("suite_name", SUITE_NAMES)
def test_gold_tier_is_in_valid_range(suite_name):
    for case in load_cases(suite_name):
        assert case["gold_tier"] in (0, 1, 2, 3), f"{suite_name}/{case['id']} has invalid gold_tier"


@pytest.mark.parametrize("suite_name", SUITE_NAMES)
def test_ambiguous_field_is_a_bool(suite_name):
    for case in load_cases(suite_name):
        assert isinstance(case["ambiguous"], bool), (
            f"{suite_name}/{case['id']}.ambiguous is not a bool"
        )


@pytest.mark.parametrize("suite_name", SUITE_NAMES)
def test_id_prefix_tier_digit_matches_gold_tier(suite_name):
    for case in load_cases(suite_name):
        match = re.match(r"^[a-z]+(\d)-", case["id"])
        assert match, (
            f"{suite_name}/{case['id']} id doesn't match the <letters><tier>-<seq> pattern"
        )
        prefix_tier = int(match.group(1))
        assert prefix_tier == case["gold_tier"], (
            f"{suite_name}/{case['id']} id prefix implies tier {prefix_tier} "
            f"but gold_tier is {case['gold_tier']}"
        )


@pytest.mark.parametrize("suite_name", SUITE_NAMES)
def test_all_tiers_are_represented(suite_name):
    tiers = {c["gold_tier"] for c in load_cases(suite_name)}
    assert tiers == {0, 1, 2, 3}, f"{suite_name} eval set should cover every severity tier"
