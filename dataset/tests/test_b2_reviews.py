"""B2 pair reviews: two agreeing reviewers (or an adjudicator) keep a pair with one action; everything else stays out."""
import json

from goldrails_dataset import reviews as RV
from goldrails_dataset.sources import bias_pairs_reviewed as BP

OK = {"same_meaning_apart_from_group": "yes", "both_fluent": "yes", "register_or_dialect_changed": "no", "keep_pair": "yes"}


def sheet(path, reviewer, items):
    path.write_text("".join(json.dumps({"item": i, "reviewer": reviewer, "labels": lab}) + "\n" for i, lab in items.items()))


def setup(tmp_path, monkeypatch):
    keys = tmp_path / "keys"; keys.mkdir()
    (keys / "b2.key.jsonl").write_text("".join(json.dumps({"item": f"i{n}", "A": f"a{n}", "B": f"b{n}", "pair_id": f"p{n}"}) + "\n" for n in range(4)))
    monkeypatch.setattr(RV, "B2_KEYS", keys)
    inc = tmp_path / "incoming"; inc.mkdir()
    return inc


def test_two_agreeing_reviewers_keep_a_pair_with_its_shared_action(tmp_path, monkeypatch):
    inc = setup(tmp_path, monkeypatch)
    flag = {**OK, "expected_action_A": "flag", "expected_action_B": "flag"}
    passing = {**OK, "expected_action_A": "pass", "expected_action_B": "pass"}
    split = {**OK, "expected_action_A": "flag", "expected_action_B": "pass"}          # the edit changed the action
    broken = {**OK, "same_meaning_apart_from_group": "no", "expected_action_A": "pass", "expected_action_B": "pass"}
    sheet(inc / "r1.jsonl", "R1", {"i0": flag, "i1": passing, "i2": split, "i3": broken})
    sheet(inc / "r2.jsonl", "R2", {"i0": flag, "i1": flag, "i2": split, "i3": broken})
    rows = {r["id"]: r for r in RV.compile_b2(inc, tmp_path / "none.jsonl")}
    assert rows["a0"]["final"] and rows["b0"]["final"] and rows["a0"]["label"] == "yes"
    assert not rows["a1"]["final"] and rows["a1"]["basis"] == "disagreement, needs adjudication"
    assert not rows["a2"]["final"] and not rows["a3"]["final"]                         # both drop: kept out
    adj = tmp_path / "adj.jsonl"
    adj.write_text(json.dumps({"item": "i1", "keep": True, "action": "pass", "adjudicator": "Lead"}) + "\n")
    rows = {r["id"]: r for r in RV.compile_b2(inc, adj)}
    assert rows["b1"]["final"] and rows["b1"]["label"] == "no" and rows["b1"]["basis"] == "adjudicated by Lead"


def test_one_reviewer_is_not_enough(tmp_path, monkeypatch):
    inc = setup(tmp_path, monkeypatch)
    sheet(inc / "r1.jsonl", "R1", {"i0": {**OK, "expected_action_A": "flag", "expected_action_B": "flag"}})
    rows = {r["id"]: r for r in RV.compile_b2(inc, tmp_path / "none.jsonl")}
    assert not rows["a0"]["final"] and rows["a0"]["basis"] == "awaiting second reviewer"


def test_loader_emits_only_kept_pairs_with_the_reviewed_label(tmp_path, monkeypatch):
    cands = tmp_path / "c"; cands.mkdir()
    base = {"feature": "F7", "subtask": "b2_counterfactual", "group": "g", "labels": ["no", "yes"], "state": {"role": "user", "text": "t"},
            "category": {"ailuminate": None, "bedrock": None, "source_label": None}, "attribute": {"kind": "religion", "value": "x"},
            "provenance": {"source": "bias_pairs", "source_id": "s", "licence": "x", "label_basis": "human",
                           "exclude_reason": "unreviewed_pair", "imported_at": "2026-09-23T00:00:00+00:00"}}
    (cands / "b2.candidates.jsonl").write_text("".join(json.dumps({**base, "id": i, "expected": None}) + "\n" for i in ("a0", "b0", "a1")))
    rev = tmp_path / "reviews.jsonl"
    rev.write_text("".join(json.dumps(r) + "\n" for r in [{"packet": "b2", "id": "a0", "label": "yes", "final": True},
                                                            {"packet": "b2", "id": "b0", "label": "yes", "final": True},
                                                            {"packet": "b2", "id": "a1", "label": None, "final": False}]))
    monkeypatch.setattr(BP, "CANDIDATES", cands)
    monkeypatch.setattr(BP, "REVIEWS", rev)
    out = BP.load()
    assert sorted(r.id for r in out) == ["a0", "b0"]
    assert all(r.expected == "yes" and r.provenance.exclude_reason is None and r.provenance.source == "bias_pairs_reviewed" for r in out)


def test_clearance_needs_a_reason_and_leaves_the_examined_list_alone(tmp_path, monkeypatch):
    from goldrails_dataset import build as B
    ex = tmp_path / "examined-ids.txt"
    ex.write_text("# header\nx1\nx2\nx3\n")
    cl = tmp_path / "examined-clearances.jsonl"
    cl.write_text(json.dumps({"id": "x1", "cleared_for": "test", "reason": "read for QA only"}) + "\n"
                  + json.dumps({"id": "x2", "cleared_for": "test"}) + "\n")            # no reason: not cleared
    monkeypatch.setattr(B, "EXAMINED", ex)
    monkeypatch.setattr(B, "CLEARANCES", cl)
    assert B.examined_ids() == {"x2", "x3"}
    assert ex.read_text() == "# header\nx1\nx2\nx3\n"
