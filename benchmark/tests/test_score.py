from goldrails_bench.score import auroc, indicator_max, summarise


def rec(id, expected, ok=True, answers=None, subtask="input"):
    return {"system": "s", "question_set": "q", "id": id, "expected": expected, "subtask": subtask, "ok": ok, "answers": answers}


def test_auroc_and_indicator_max():
    assert auroc([0.9, 0.8], [0.1, 0.2]) == 1.0 and auroc([0.5], [0.5]) == 0.5 and auroc([], [0.1]) is None
    assert indicator_max({"hate": {"type": "noul", "noul": 0.2}, "severity": {"type": "score", "score": 3}, "intent_real_world": {"type": "noul", "noul": 0.9}}) == 0.2
    assert indicator_max({"severity": {"type": "score", "score": 3}}) is None


def test_failed_and_no_decision_rows_are_counted_not_scored_as_benign():
    rows = [rec("a", "yes", answers={"hate": {"type": "noul", "noul": 0.9}}),
            rec("b", "no", answers={"hate": {"type": "noul", "noul": 0.1}}),
            rec("c", "yes", answers={"severity": {"type": "score", "score": 2.0}}),   # returned, nothing to decide on
            rec("d", "yes", ok=False)]                                                # call failed
    line = summarise(rows)[0]
    assert (line["failed"], line["no_decision"], line["decided"]) == (1, 1, 2)
    assert line["accuracy"] == 1.0 and line["harmful_recall"] == 1.0          # exclude: metrics over decided rows only
    flag = summarise(rows, failure_policy="flag")[0]
    assert flag["harmful_recall"] == 1.0 and flag["accuracy"] == 1.0          # fail closed: c and d count as flagged (both harmful)
    p = summarise(rows, failure_policy="pass")[0]
    assert p["harmful_recall"] == 1 / 3 and p["accuracy"] == 0.5             # fail open: c and d count as passed


def test_empty_answers_count_as_no_decision_under_every_policy():
    rows = [rec("a", "yes", answers={}), rec("b", "no", answers={"hate": {"type": "noul", "noul": 0.1}})]
    for policy, recall in (("exclude", None), ("flag", 1.0), ("pass", 0.0)):
        line = summarise(rows, failure_policy=policy)[0]
        assert line["no_decision"] == 1 and line["decided"] == 1 and line["harmful_recall"] == recall


def test_arms_with_different_config_hashes_are_scored_separately():
    a = {**rec("x", "yes", answers={"hate": {"type": "noul", "noul": 0.9}}), "config_hash": "old"}
    b = {**rec("x", "yes", answers={"hate": {"type": "noul", "noul": 0.1}}), "config_hash": "new"}
    lines = summarise([a, b])
    assert [(l["config_hash"], l["harmful_recall"]) for l in lines] == [("new", 0.0), ("old", 1.0)]


def test_failed_merged_call_fails_every_constituent_set():
    from goldrails_bench.score import explode
    r = {"system": "s", "question_set": "all", "id": "x", "expected": "yes", "subtask": "input", "ok": False, "answers": None,
         "question_sets": ["v1-a", "v1-b"]}
    out = explode([r])
    assert [o["question_set"] for o in out] == ["v1-a", "v1-b"] and all(not o["ok"] for o in out)
    assert all(l["failed"] == 1 for l in summarise(out))


def test_breakdown_reports_matching_detector_separately_from_any_detector():
    from goldrails_bench.score import breakdown
    a = {**rec("a", "yes", answers={"prompt_injection": {"type": "noul", "noul": 0.9}, "prompt_leakage": {"type": "noul", "noul": 0.1}}, subtask="leakage"), "source": "gandalf"}
    line = breakdown([a])[0]
    assert line["any_detector_flagged"] == 1 and line["matching_detector"] == "prompt_leakage" and line["matching_detector_flagged"] == 0


def test_breakdown_keeps_configurations_apart():
    from goldrails_bench.score import breakdown
    a = {**rec("a", "yes", answers={"q": {"type": "noul", "noul": 0.9}}), "config_hash": "one", "source": "s"}
    b = {**rec("a", "yes", answers={"q": {"type": "noul", "noul": 0.1}}), "config_hash": "two", "source": "s"}
    assert [(l["config_hash"], l["any_detector_flagged"]) for l in breakdown([a, b])] == [("one", 1), ("two", 0)]


def test_entity_breakdown_scores_each_type_against_its_own_spans():
    from goldrails_bench.score import entity_breakdown
    a = {**rec("a", "yes", answers={"NAME": {"type": "noul", "noul": 0.9}, "PASSWORD": {"type": "noul", "noul": 0.1}, "any_supported_entity": {"type": "noul", "noul": 0.9}}), "expected_types": ["NAME", "PASSWORD"]}
    lines = {l["entity"]: l for l in entity_breakdown([a])}
    assert lines["NAME"]["recall"] == 1.0 and lines["PASSWORD"]["recall"] == 0.0 and "any_supported_entity" not in lines


def test_decision_keys_restrict_the_score_to_declared_questions():
    from goldrails_bench.score import score_of
    r = {**rec("a", "no", answers={"unsupported": {"type": "noul", "noul": 0.1}, "irrelevant": {"type": "noul", "noul": 0.9}}), "decision_keys": ["unsupported"]}
    assert score_of(r) == 0.1
    ns = {**rec("a", "no", answers={"v1-f6-grounding__unsupported": {"type": "noul", "noul": 0.2}, "v1-f6-grounding__irrelevant": {"type": "noul", "noul": 0.9}}), "decision_keys": ["unsupported"]}
    assert score_of(ns) == 0.2
    legacy = rec("a", "no", answers={"unsupported": {"type": "noul", "noul": 0.1}, "irrelevant": {"type": "noul", "noul": 0.9}})
    legacy["question_set"] = "v1-f6-grounding"            # older ledger: keys come from the question-set file
    assert score_of(legacy) == 0.1


def test_load_ledger_keeps_only_the_last_record_per_arm_and_row(tmp_path):
    import json
    from goldrails_bench.score import load_ledger
    p = tmp_path / "l.jsonl"
    a = {**rec("x", "yes", answers={"q": {"type": "noul", "noul": 0.1}}), "config_hash": "c", "dataset": {"sha256": "d"}}
    b = {**a, "answers": {"q": {"type": "noul", "noul": 0.9}}}
    p.write_text(json.dumps(a) + "\n" + json.dumps(b) + "\n")
    out = load_ledger(p)
    assert len(out) == 1 and out[0]["answers"]["q"]["noul"] == 0.9 and out.dropped_duplicates == 1


def test_rehash_moves_only_content_identical_rows(tmp_path, monkeypatch):
    import json
    import goldrails_bench.rehash_ledger as RL
    same, changed, cur = "aaaa", "bbbb", "cccc"
    versions = [{"ref": "working", "sha_old": "W_OLD", "sha_new": "CUR", "rows": {"same": same, "changed": cur}},
                {"ref": "abc123", "sha_old": "ORIG_OLD", "sha_new": "ORIG_NEW", "rows": {"same": same, "changed": changed}}]
    monkeypatch.setattr(RL, "git_versions", lambda rel: versions)
    p = tmp_path / "l.jsonl"
    base = {"system": "s", "question_set": "q", "config_hash": "c", "ok": True, "answers": {}, "expected": "no", "subtask": "x"}
    recs = [{**base, "id": "same", "dataset": {"source": "d", "feature": "F1", "split": "tune", "sha256": "ORIG_OLD"}},
            {**base, "id": "changed", "dataset": {"source": "d", "feature": "F1", "split": "tune", "sha256": "ORIG_OLD"}},
            {**base, "id": "changed", "dataset": {"source": "d", "feature": "F1", "split": "tune", "sha256": "CUR", "rehashed_from": "ORIG_NEW"}},
            {**base, "id": "same", "dataset": {"source": "d", "feature": "F1", "split": "tune", "sha256": "LOST"}}]
    p.write_text("".join(json.dumps(r) + "\n" for r in recs))
    RL.main([str(p)])
    out = [json.loads(l) for l in p.read_text().splitlines()]
    assert out[0]["dataset"]["sha256"] == "CUR" and out[0]["dataset"]["rehashed_from"] == "ORIG_OLD"     # identical content: moved
    assert out[1]["dataset"]["sha256"] == "ORIG_OLD" and out[1]["dataset"]["rehash_note"].startswith("kept")  # content changed: kept
    assert out[2]["dataset"]["sha256"] == "ORIG_NEW" and "reverted" in out[2]["dataset"]["rehash_note"]      # weak earlier move undone
    assert out[3]["dataset"]["sha256"] == "LOST" and "not in git" in out[3]["dataset"]["rehash_note"]         # origin unknown: untouched
