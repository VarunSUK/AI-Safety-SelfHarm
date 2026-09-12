import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from scoring import classify_disagreement, join, load_jsonl  # noqa: E402


def make_case(case_id: str, gold_tier: int) -> dict:
    return {"id": case_id, "gold_tier": gold_tier, "text": f"case {case_id}"}


def make_pred(case_id: str, predicted_tier) -> dict:
    return {"id": case_id, "predicted_tier": predicted_tier}


def test_load_jsonl_reads_rows_keyed_by_id(tmp_path):
    path = tmp_path / "data.jsonl"
    path.write_text(
        '{"id": "a", "gold_tier": 0}\n{"id": "b", "gold_tier": 3}\n',
        encoding="utf-8",
    )

    rows = load_jsonl(path)

    assert set(rows) == {"a", "b"}
    assert rows["b"]["gold_tier"] == 3


def test_load_jsonl_skips_blank_lines(tmp_path):
    path = tmp_path / "data.jsonl"
    path.write_text('{"id": "a", "gold_tier": 0}\n\n\n', encoding="utf-8")

    rows = load_jsonl(path)

    assert list(rows) == ["a"]


def test_join_drops_cases_with_no_prediction():
    gold = {"a": make_case("a", 0), "b": make_case("b", 2)}
    preds = {"a": make_pred("a", 0)}  # "b" never got a prediction

    joined = join(gold, preds)

    assert len(joined) == 1
    assert joined[0][0]["id"] == "a"


def test_join_drops_cases_with_null_predicted_tier():
    gold = {"a": make_case("a", 0)}
    preds = {"a": make_pred("a", None)}  # e.g. an API error during classify.py

    joined = join(gold, preds)

    assert joined == []


def test_classify_disagreement_exact_match_returns_none():
    g, p = make_case("a", 2), make_pred("a", 2)
    assert classify_disagreement(g, p) is None


def test_classify_disagreement_critical_miss_is_gold_tier_3_scored_lower():
    g, p = make_case("a", 3), make_pred("a", 1)
    assert classify_disagreement(g, p) == "critical_miss"


def test_classify_disagreement_tier_3_scored_correctly_is_not_a_miss():
    g, p = make_case("a", 3), make_pred("a", 3)
    assert classify_disagreement(g, p) is None


def test_classify_disagreement_ordinary_mismatch_below_tier_3():
    g, p = make_case("a", 1), make_pred("a", 2)
    assert classify_disagreement(g, p) == "disagreement"


def test_classify_disagreement_overcall_above_gold_is_not_critical():
    # Gold says tier 1, model says tier 3: an over-flag, not a missed
    # intervention -- costs reviewer time, not a missed critical case.
    g, p = make_case("a", 1), make_pred("a", 3)
    assert classify_disagreement(g, p) == "disagreement"
