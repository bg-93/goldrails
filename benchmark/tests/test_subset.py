from goldrails_dataset.records import Category, Provenance, Record, State
from goldrails_bench.subset import ELIGIBLE, select


def rec(i, feature="F4", subtask="word", expected="yes", split="test", status="deterministic"):
    r = Record(id=f"{feature.lower()}-s-{i:04d}", feature=feature, subtask=subtask, state=State(role="user", text=f"t{i}"),
               category=Category("benign", "NONE", None), labels=["no", "yes"], expected=expected,
               provenance=Provenance(source="s", source_id=str(i), licence="mit", label_basis="deterministic", imported_at="x"),
               split=split, group=f"g{i}", review_status=status)
    r.validate(); return r


def test_candidates_never_selected_and_splits_are_kept():
    rows = [rec(i) for i in range(10)] + [rec(100 + i, status="candidate") for i in range(10)] + [rec(200 + i, split="tune") for i in range(10)]
    got = select(rows, quotas={"core": {"tune": 3, "test": 4}, "F7": {"tune": 1, "test": 1}})
    assert all(r.review_status in ELIGIBLE for r in got)
    assert sum(r.split == "test" for r in got) == 4 and sum(r.split == "tune" for r in got) == 3
    assert {r.id for r in got if r.split == "tune"} <= {rec(200 + i, split="tune").id for i in range(10)}


def test_selection_is_reproducible_and_takes_small_cells_whole():
    rows = [rec(i) for i in range(10)] + [rec(50 + i, expected="no") for i in range(2)]
    q = {"core": {"tune": 0, "test": 5}, "F7": {"tune": 0, "test": 0}}
    a, b = select(rows, 7, q), select(rows, 7, q)
    assert [r.id for r in a] == [r.id for r in b]
    assert sum(r.expected == "no" for r in a) == 2 and sum(r.expected == "yes" for r in a) == 5


def test_carry_over_refuses_a_selection_that_moves_frozen_test_rows(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace
    from goldrails_bench import subset as S
    monkeypatch.setattr(S, "SUBSETS", tmp_path)
    (tmp_path / "old").mkdir()
    (tmp_path / "old" / "manifest.json").write_text(json.dumps({"rows": [
        {"id": "a", "feature": "F1", "subtask": "input", "split": "test"}, {"id": "b", "feature": "F1", "subtask": "input", "split": "test"}]}))
    r = lambda i, f="F1", sp="test", st="input": SimpleNamespace(id=i, feature=f, split=sp, subtask=st)
    assert S.carry_over_problems([r("a"), r("b"), r("t1", "F3")], "old", ["F1"]) == []     # a new F3 row is fine
    assert S.carry_over_problems([r("a"), r("b"), r("p1", st="new")], "old", ["F1"]) == []  # so is a new subtask
    assert S.carry_over_problems([r("a"), r("c")], "old", ["F1"]) == ["F1: 1 added, 1 removed"]
