import json

import goldrails_dataset.reviews as R


def write(p, rows):
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))


def test_single_second_and_adjudicated_reviews(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "keys", lambda: {"a": ("rec-a", False), "b": ("rec-b", True), "c": ("rec-c", True), "d": ("rec-d", True)})
    inc = tmp_path / "incoming"; inc.mkdir()
    write(inc / "ann.jsonl", [{"review_id": "a", "reviewer": "ann", "labels": {"x": False, "y": True}},
                              {"review_id": "b", "reviewer": "ann", "labels": {"x": False}},
                              {"review_id": "c", "reviewer": "ann", "labels": {"x": True}},
                              {"review_id": "d", "reviewer": "ann", "labels": {"x": None}}])
    write(inc / "bo.jsonl", [{"review_id": "b", "reviewer": "bo", "labels": {"x": False}},
                             {"review_id": "c", "reviewer": "bo", "labels": {"x": False}}])
    adj = tmp_path / "adj.jsonl"
    rows = {r["review_id"]: r for r in R.compile_reviews(inc, adj)}
    assert rows["a"]["final"] and rows["a"]["label"] == "yes"            # any label true -> yes
    assert rows["b"]["final"] and rows["b"]["label"] == "no"             # flagged, two agree
    assert not rows["c"]["final"] and "adjudication" in rows["c"]["basis"]
    assert "d" not in rows                                               # incomplete sheet ignored
    write(adj, [{"review_id": "c", "label": "yes", "adjudicator": "cy"}])
    assert {r["review_id"]: r for r in R.compile_reviews(inc, adj)}["c"]["final"]


def test_real_keys_map_every_packet_case():
    k = R.keys()
    assert sum(1 for rid in k if rid.startswith("f3t-")) == 90
    assert sum(1 for rid in k if rid.startswith("prof-")) == 280
    import json
    for packet, prefix, flagged in (("f3-test-candidates", "f3t-", 9), ("f4-profanity", "prof-", 40)):
        plan = json.loads((R.PACKETS / "_lead" / f"{packet}.key.json").read_text())["second_review_plan"]
        assert len(plan["flagged"]) == flagged                     # every ambiguous case goes to a second reviewer
        assert set(plan["flagged"]) <= {rid for rid, v in k.items() if rid.startswith(prefix) and v[1]}
        assert sum(1 for rid, v in k.items() if rid.startswith(prefix) and v[1]) == plan["total"]


def test_unclear_goes_to_adjudication_and_exclusion_is_final(tmp_path, monkeypatch):
    import json
    key = {"x1": ("rec1", False), "x2": ("rec2", False), "x3": ("rec3", True)}
    monkeypatch.setattr(R, "keys", lambda: key)
    inc = tmp_path / "in"; inc.mkdir()
    rows = [{"review_id": "x1", "reviewer": "A", "labels": {"profanity_present": "unclear"}},
            {"review_id": "x2", "reviewer": "A", "labels": {"profanity_present": "no"}, "exclude_case": "yes", "note": "not English"},
            {"review_id": "x3", "reviewer": "A", "labels": {"profanity_present": "yes"}},
            {"review_id": "x3", "reviewer": "B", "labels": {"profanity_present": "yes"}}]
    (inc / "a.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    out = {r["review_id"]: r for r in R.compile_reviews(inc, tmp_path / "none.jsonl")}
    assert not out["x1"]["final"] and out["x1"]["basis"] == "unclear, needs adjudication"
    assert out["x2"]["final"] and out["x2"]["excluded"] and out["x2"]["label"] is None
    assert out["x3"]["final"] and out["x3"]["label"] == "yes"


def test_final_human_label_replaces_the_draft_and_exclusions_keep_a_reason():
    import json
    from goldrails_dataset import build as B
    from goldrails_dataset.sources import civil_comments_profanity as CP
    from goldrails_dataset.records import Category, Provenance, Record, State
    def rec(i, exp):
        return Record(id=i, feature="F4", subtask="profanity", state=State(role="user", text="t"), category=Category(ailuminate=None, bedrock=None, source_label=None),
                      labels=["no", "yes"], expected=exp, provenance=Provenance(source=CP.NAME, source_id=i, licence="x",
                      label_basis="automated", imported_at="2026-09-23T00:00:00+00:00", notes=json.dumps({"bucket": "b"})),
                      attribute={"bucket": "b"})
    rs = [rec("a", "yes"), rec("b", "no"), rec("c", "yes"), rec("d", "no")]
    finals = {"a": {"label": "no", "final": True, "basis": "single reviewer", "reviewers": ["R"]},
              "b": {"label": "no", "final": True, "basis": "single reviewer", "reviewers": ["R"]},
              "c": {"label": None, "final": True, "excluded": True, "basis": "single reviewer", "notes": {"R": "not English"}}}
    n = B.apply_reviews(rs, finals)
    assert rs[0].expected == "no" and rs[0].provenance.label_basis == "human" and rs[0].review_status == "reviewed"
    assert json.loads(rs[0].provenance.notes)["draft_expected"] == "yes"
    assert rs[1].review_status == "reviewed" and rs[2].provenance.exclude_reason.startswith("review: excluded")
    assert rs[3].review_status == "candidate"                                          # never reviewed: not scorable
    assert n == {"draft_label_replaced": 1, "reviewed": 2, "excluded_by_review": 1, "unreviewed_or_unresolved": 1}


def test_agreement_is_measured_before_adjudication(tmp_path, monkeypatch):
    import json
    key = {f"p-r{i:02d}": (f"rec{i}", True) for i in range(4)}
    monkeypatch.setattr(R, "keys", lambda: key)
    inc = tmp_path / "in"; inc.mkdir()
    a = ["yes", "yes", "no", "no"]; b = ["yes", "no", "no", "no"]
    rows = [{"review_id": f"p-r{i:02d}", "reviewer": "A", "labels": {"x": a[i]}} for i in range(4)]
    rows += [{"review_id": f"p-r{i:02d}", "reviewer": "B", "labels": {"x": b[i]}} for i in range(4)]
    (inc / "s.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    ag = R.agreement(inc)["p"]
    assert ag["double_reviewed"] == 4 and ag["raw_agreement"] == 0.75 and ag["disagreements"] == 1
    assert ag["cohens_kappa"] == 0.5
