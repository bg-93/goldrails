from types import SimpleNamespace

from goldrails_bench.runner import run_matrix


class FakeClient:
    """Answers every question with 0.5; fails ids listed in ``bad``."""
    def __init__(self, system, bad=()):
        self.system, self.bad, self.calls = system, set(bad), 0

    def ask(self, state, questions):
        self.calls += 1
        ok = state["text"] not in self.bad
        return SimpleNamespace(ok=ok, error=None if ok else "boom", model=self.system, latency_s=0.01, usage={"input_tokens": 3},
                               answers={k: {"type": "noul", "noul": 0.5} for k in questions} if ok else None, raw={"echo": len(questions)})


def row(i):
    return SimpleNamespace(id=f"r{i}", subtask="input", expected="no", provenance=SimpleNamespace(source="t"))


def state_of(r):
    return {"text": r.id}


def test_chunking_joins_answers_and_counts_calls(monkeypatch):
    import goldrails_bench.runner as R
    monkeypatch.setattr(R, "state_of", state_of)
    c = FakeClient("local")
    qs = {"all": {"questions": {f"q{i}": {"type": "noul", "instructions": "?"} for i in range(42)}}}
    out = run_matrix({"local": c}, qs, [row(0)], gpu_of={"local": 0}, progress=lambda *_: None)
    assert out[0]["ok"] and len(out[0]["answers"]) == 42 and out[0]["calls"] == 3 and c.calls == 3


def test_ledger_resumes_and_skips_done_rows(tmp_path, monkeypatch):
    import goldrails_bench.runner as R
    monkeypatch.setattr(R, "state_of", state_of)
    path = tmp_path / "run.jsonl"
    qs = {"s": {"questions": {"q": {"type": "noul", "instructions": "?"}}}}
    c1 = FakeClient("api", bad={"r1"})
    out1 = run_matrix({"api": c1}, qs, [row(0), row(1), row(2)], results_path=path, progress=lambda *_: None)
    assert sum(r["ok"] for r in out1) == 2 and path.read_text().count("\n") == 3
    c2 = FakeClient("api")
    out2 = run_matrix({"api": c2}, qs, [row(0), row(1), row(2), row(3)], results_path=path, progress=lambda *_: None)
    assert c2.calls == 1 and [r["id"] for r in out2] == ["r3"]   # failed rows are recorded, not retried; only new rows run


def test_changed_question_wording_is_a_new_arm_not_a_resume(tmp_path, monkeypatch):
    import goldrails_bench.runner as R
    monkeypatch.setattr(R, "state_of", state_of)
    path = tmp_path / "run.jsonl"
    c1 = FakeClient("api")
    run_matrix({"api": c1}, {"s": {"questions": {"q": {"type": "noul", "instructions": "old wording"}}}}, [row(0)], results_path=path, progress=lambda *_: None)
    c2 = FakeClient("api")
    out = run_matrix({"api": c2}, {"s": {"questions": {"q": {"type": "noul", "instructions": "new wording"}}}}, [row(0)], results_path=path, progress=lambda *_: None)
    assert c2.calls == 1 and len(out) == 1                     # same system, set name and row id, different config hash -> re-run
    recs = [__import__("json").loads(l) for l in path.read_text().splitlines()]
    assert len({r["config_hash"] for r in recs}) == 2 and all(r["raw"] for r in recs)


def test_identity_changes_the_config_hash_and_records_constituent_sets(monkeypatch):
    import goldrails_bench.runner as R
    monkeypatch.setattr(R, "state_of", state_of)
    qs = {"questions": {"v1-a__q": {"type": "noul", "instructions": "?"}, "v1-b__q": {"type": "noul", "instructions": "?"}}}
    c1, c2 = FakeClient("api"), FakeClient("api"); c1.identity = {"revision": "aaa"}; c2.identity = {"revision": "bbb"}
    assert R.config_hash(c1, qs) != R.config_hash(c2, qs)
    out = run_matrix({"api": c1}, {"all": qs}, [row(0)], progress=lambda *_: None)
    assert out[0]["question_sets"] == ["v1-a", "v1-b"]


def test_arm_sidecar_snapshots_the_questions_as_sent(tmp_path, monkeypatch):
    import goldrails_bench.runner as R
    monkeypatch.setattr(R, "state_of", state_of)
    path = tmp_path / "run.jsonl"
    qs = {"s": {"questions": {"q": {"type": "noul", "instructions": "as sent"}}}}
    run_matrix({"api": FakeClient("api")}, qs, [row(0)], results_path=path, progress=lambda *_: None)
    arms = [__import__("json").loads(l) for l in (tmp_path / "run.arms.jsonl").read_text().splitlines()]
    assert len(arms) == 1 and arms[0]["questions"]["q"]["instructions"] == "as sent" and arms[0]["system"] == "api"
