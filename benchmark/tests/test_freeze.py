"""The frozen manifest end to end: its Git identity, the runner's refusal to touch test rows without it, the stamp on
every test record, and the leaderboard's final mode scoring with the frozen thresholds. Local Git only; no network,
model or cloud calls."""
import json
import os
import subprocess
from types import SimpleNamespace

import pytest

import goldrails_bench.runner as R
from goldrails_bench import freeze
from goldrails_bench import leaderboard as lb
from goldrails_bench.freeze import FreezeError
from goldrails_bench.policy import DEFAULT_POLICY, NO_RETRY, TRANSIENT_3

PAST = "2020-01-01T00:00:00+0000"
QS = {"v1-f3-topics": {"questions": {"q": {"type": "noul", "instructions": "is this on the denied topic?"}}, "decision": ["q"]}}


def git(repo, *args, date=None):
    env = dict(os.environ)
    if date:
        env.update(GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
    return subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                           "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args],
                          check=True, capture_output=True, text=True, env=env)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    git(r, "init", "-q")
    (r / "README").write_text("x\n")
    git(r, "add", "README")
    git(r, "commit", "-q", "-m", "init", date=PAST)
    return r


def commit(repo, path, date=PAST):
    git(repo, "add", str(path.relative_to(repo)))
    git(repo, "commit", "-q", "-m", "freeze", date=date)


class Client:
    """Scores violations 0.9 and benign rows 0.1 (by row id parity); counts calls."""
    def __init__(self, system="api"):
        self.system, self.calls = system, 0

    def ask(self, state, questions):
        self.calls += 1
        s = 0.9 if state["pos"] else 0.1
        return SimpleNamespace(ok=True, error=None, model=self.system, latency_s=0.01, usage={"input_tokens": 3},
                               answers={k: {"type": "noul", "noul": s} for k in questions}, raw={})


def row(i, split, sha):
    return SimpleNamespace(id=f"f3-{i}", subtask="topic", expected="yes" if i % 2 else "no", group=f"g{i}",
                           provenance=SimpleNamespace(source="t"),
                           dataset={"source": "none", "feature": "F3", "split": split, "sha256": sha})


@pytest.fixture(autouse=True)
def _state(monkeypatch):
    monkeypatch.setattr(R, "state_of", lambda r: {"pos": int(r.id.split("-")[1]) % 2 == 1})


def quiet(*_):
    pass


def tuned_manifest(tmp_path, repo, client, name="manifest.json", test_sha="dtest", policy=DEFAULT_POLICY):
    tune = R.run_matrix({client.system: client}, QS, [row(i, "tune", "dtune") for i in range(20)],
                        results_path=tmp_path / "tune.jsonl", progress=quiet, policy=policy)
    assert all("freeze" not in r for r in tune)                     # tuning runs are unaffected
    doc = lb.evaluate(lb.load_inputs([tmp_path / "tune.jsonl"])[0], mode="smoke", replicates=20, seed=1)
    path = repo / name
    freeze.write_manifest(doc, path, retry_policy=policy, test_datasets={"denied_topics": test_sha},
                          bootstrap={"replicates": 20, "seed": 1})
    return path


# --- manifest_identity -------------------------------------------------------------------------------------------

def test_identity_is_the_file_hash_and_its_last_commit(tmp_path, repo):
    p = repo / "m.json"
    p.write_text('{"a": 1}\n')
    with pytest.raises(FreezeError, match="not committed"):
        freeze.manifest_identity(p)                                  # untracked
    commit(repo, p, date="2021-02-03T04:05:06+0000")
    ident = freeze.manifest_identity(p)
    head = git(repo, "rev-parse", "HEAD").stdout.strip()
    assert ident["commit"] == head and ident["committed_at"] == "2021-02-03T04:05:06Z"
    assert ident["manifest_sha256"] == __import__("hashlib").sha256(b'{"a": 1}\n').hexdigest()
    p.write_text('{"a": 2}\n')
    with pytest.raises(FreezeError, match="uncommitted changes"):
        freeze.manifest_identity(p)
    git(repo, "add", "m.json")
    with pytest.raises(FreezeError, match="uncommitted changes"):   # staged is still uncommitted
        freeze.manifest_identity(p)


def test_identity_refuses_a_file_outside_git_or_missing(tmp_path):
    p = tmp_path / "loose.json"
    p.write_text("{}")
    with pytest.raises(FreezeError, match="not in a Git repository"):
        freeze.manifest_identity(p)
    with pytest.raises(FreezeError, match="does not exist"):
        freeze.manifest_identity(tmp_path / "nope.json")


# --- the runner --------------------------------------------------------------------------------------------------

def test_test_rows_need_a_manifest_before_any_call(tmp_path):
    c = Client()
    with pytest.raises(FreezeError, match="no freeze_manifest"):
        R.run_matrix({"api": c}, QS, [row(0, "test", "dtest")], results_path=tmp_path / "t.jsonl", progress=quiet)
    assert c.calls == 0 and not (tmp_path / "t.jsonl").exists()


def test_uncommitted_manifest_is_refused_before_any_call(tmp_path, repo):
    path = tuned_manifest(tmp_path, repo, Client())
    c = Client()
    with pytest.raises(FreezeError, match="not committed"):
        R.run_matrix({"api": c}, QS, [row(0, "test", "dtest")], progress=quiet, freeze_manifest=path)
    assert c.calls == 0


def test_arm_not_in_the_manifest_is_refused_before_any_call(tmp_path, repo):
    path = tuned_manifest(tmp_path, repo, Client())
    commit(repo, path)
    c = Client()
    with pytest.raises(FreezeError, match="dataset d2"):             # a dataset version that was not frozen
        R.run_matrix({"api": c}, QS, [row(0, "test", "d2")], progress=quiet, freeze_manifest=path)
    other = Client("other-system")
    with pytest.raises(FreezeError, match="other-system"):
        R.run_matrix({"api": c, "other": other}, QS, [row(0, "test", "dtest")], progress=quiet, freeze_manifest=path)
    edited = {"v1-f3-topics": {"questions": {"q": {"type": "noul", "instructions": "edited after the freeze"}}}}
    with pytest.raises(FreezeError, match="not frozen"):             # changed question wording: a new config hash
        R.run_matrix({"api": c}, edited, [row(0, "test", "dtest")], progress=quiet, freeze_manifest=path)
    assert c.calls == 0 and other.calls == 0


def test_retry_policy_must_be_the_frozen_one(tmp_path, repo):
    path = tuned_manifest(tmp_path, repo, Client())
    commit(repo, path)
    c = Client()
    with pytest.raises(FreezeError, match="retry policy"):
        R.run_matrix({"api": c}, QS, [row(0, "test", "dtest")], progress=quiet, freeze_manifest=path, policy=NO_RETRY)
    assert c.calls == 0


def test_manifest_identity_is_stamped_on_test_records_and_the_sidecar(tmp_path, repo):
    path = tuned_manifest(tmp_path, repo, Client())
    commit(repo, path)
    ident = freeze.manifest_identity(path)
    stamp = {k: ident[k] for k in ("manifest_sha256", "commit", "committed_at")}
    out = R.run_matrix({"api": Client()}, QS, [row(i, "test", "dtest") for i in range(4)],
                       results_path=tmp_path / "test.jsonl", progress=quiet, freeze_manifest=path)
    assert len(out) == 4 and all(r["freeze"] == stamp for r in out)
    on_disk = [json.loads(x) for x in (tmp_path / "test.jsonl").read_text().splitlines()]
    assert all(r["freeze"] == stamp for r in on_disk)
    arms = [json.loads(x) for x in (tmp_path / "test.arms.jsonl").read_text().splitlines()]
    assert arms[0]["freeze"] == stamp


# --- the whole route: tune, freeze, commit, test, score ----------------------------------------------------------

def test_final_leaderboard_scores_with_the_frozen_thresholds_and_proves_the_freeze(tmp_path, repo):
    path = tuned_manifest(tmp_path, repo, Client())
    commit(repo, path)                                               # committed in 2020, before any test attempt
    R.run_matrix({"api": Client()}, QS, [row(i, "test", "dtest") for i in range(20, 40)],
                 results_path=tmp_path / "test.jsonl", progress=quiet, freeze_manifest=path)
    ledgers = [tmp_path / "test.jsonl", tmp_path / "test.arms.jsonl"]
    doc = lb.build(ledgers, mode="final", freeze_manifest_path=path)
    a = doc["arms"][0]
    assert a["thresholds_source"] == "frozen_manifest" and a["freeze"]["status"] == "frozen"
    assert a["subtasks"]["topic"]["threshold"]["frozen"] is True and a["subtasks"]["topic"]["task_score"] == 100.0
    fm = doc["freeze_manifest"]
    assert fm["manifest_sha256"] == freeze.manifest_identity(path)["manifest_sha256"] and fm["identity_error"] is None
    assert fm["arms_using_frozen_thresholds"] == [a["arm_id"]] and fm["records"]["test_records"] == 20
    freeze_blockers = [b for b in doc["publication_blockers"] if "manifest" in b or "freeze" in b]
    assert freeze_blockers == []
    assert doc["suites"]["denied_topics"]["bootstrap"]["replicates"] == 20     # the frozen bootstrap


def test_final_leaderboard_blocks_a_manifest_edited_after_the_test(tmp_path, repo):
    path = tuned_manifest(tmp_path, repo, Client())
    commit(repo, path)
    R.run_matrix({"api": Client()}, QS, [row(i, "test", "dtest") for i in range(20, 40)],
                 results_path=tmp_path / "test.jsonl", progress=quiet, freeze_manifest=path)
    m = json.loads(path.read_text())
    m["arms"][0]["thresholds"]["topic"]["threshold"] = 0.95        # "retuned" after seeing the test
    path.write_text(json.dumps(m))
    ledgers = [tmp_path / "test.jsonl"]
    doc = lb.build(ledgers, mode="final", freeze_manifest_path=path)
    assert any("uncommitted changes" in b for b in doc["publication_blockers"])
    commit(repo, path, date="2099-01-01T00:00:00+0000")              # committing the edit does not help
    doc = lb.build(ledgers, mode="final", freeze_manifest_path=path)
    assert any("different manifest sha256" in b for b in doc["publication_blockers"])
    assert any("not before the first test attempt" in b for b in doc["publication_blockers"])
    assert not doc["valid_for_publication"]


def test_cli_keeps_the_freeze_manifest_flag(tmp_path, repo):
    path = tuned_manifest(tmp_path, repo, Client())
    commit(repo, path)
    R.run_matrix({"api": Client()}, QS, [row(i, "test", "dtest") for i in range(20, 40)],
                 results_path=tmp_path / "test.jsonl", progress=quiet, freeze_manifest=path)
    out = tmp_path / "lb.json"
    assert lb.main([str(tmp_path / "test.jsonl"), "--mode", "final", "--freeze-manifest", str(path),
                    "--out", str(out)]) == 0
    doc = json.loads(out.read_text())
    assert doc["freeze_manifest"]["commit"] == freeze.manifest_identity(path)["commit"]
    assert doc["arms"][0]["freeze"]["status"] == "frozen"


def _frozen_with_old_scoring(tmp_path, repo):
    """A manifest frozen under earlier scoring code: its recorded leaderboard sha256 differs from the code now."""
    path = tuned_manifest(tmp_path, repo, Client())
    m = json.loads(path.read_text())
    m["scoring"]["sha256"] = "0" * 64
    path.write_text(json.dumps(m))
    commit(repo, path)
    R.run_matrix({"api": Client()}, QS, [row(i, "test", "dtest") for i in range(20, 40)],
                 results_path=tmp_path / "test.jsonl", progress=quiet, freeze_manifest=path)
    return path, [tmp_path / "test.jsonl", tmp_path / "test.arms.jsonl"]


def _approval(repo, path, **over):
    a = {"approval_version": lb.APPROVAL_VERSION, "primary_manifest_sha256": freeze.manifest_identity(path)["manifest_sha256"],
         "frozen_scoring_sha256": "0" * 64, "approved_scoring_sha256": lb._sha256_file(lb.__file__), "schema": lb.SCHEMA,
         "approved_by": "Owner", "approved_at": "2026-09-23", "changes": [{"commit": "abc", "description": "bug fix"}],
         "unchanged": ["questions", "thresholds"], **over}
    p = repo / "approval.json"
    p.write_text(json.dumps(a))
    return p


def test_changed_scoring_code_blocks_without_an_approval(tmp_path, repo):
    path, ledgers = _frozen_with_old_scoring(tmp_path, repo)
    doc = lb.build(ledgers, mode="final", freeze_manifest_path=path)
    assert any("scoring code changed since the freeze" in b for b in doc["publication_blockers"])
    assert "analysis_versions" not in doc


def test_a_committed_approval_turns_the_scoring_change_into_a_labelled_corrected_analysis(tmp_path, repo):
    path, ledgers = _frozen_with_old_scoring(tmp_path, repo)
    ap = _approval(repo, path)
    doc = lb.build(ledgers, mode="final", freeze_manifest_path=path, approval_paths=[ap])
    assert any("scoring code changed" in b for b in doc["publication_blockers"])   # uncommitted approval does not count
    commit(repo, ap)
    doc = lb.build(ledgers, mode="final", freeze_manifest_path=path, approval_paths=[ap])
    assert not any("scoring code changed" in b for b in doc["publication_blockers"])
    v = doc["analysis_versions"][0]
    assert v["kind"] == "corrected analysis" and v["approved_by"] == "Owner" and v["approval_commit"]
    assert doc["arms"][0]["thresholds_source"] == "frozen_manifest"                 # thresholds still the frozen ones


def test_an_approval_for_other_code_or_another_manifest_does_not_apply(tmp_path, repo):
    path, ledgers = _frozen_with_old_scoring(tmp_path, repo)
    for over in ({"approved_scoring_sha256": "1" * 64}, {"primary_manifest_sha256": "2" * 64}, {"approved_by": ""}):
        ap = _approval(repo, path, **over)
        commit(repo, ap)
        doc = lb.build(ledgers, mode="final", freeze_manifest_path=path, approval_paths=[ap])
        assert any("scoring code changed" in b for b in doc["publication_blockers"]), over


def _extension(tmp_path, repo, primary_path, system="api2", name="ext.json", extends_sha=None, test_sha="dtest2"):
    """Freeze a new arm on its own tuning rows, extending the primary manifest."""
    c = Client(system)
    R.run_matrix({system: c}, QS, [row(i, "tune", "dtune2") for i in range(20)],
                 results_path=tmp_path / f"tune-{system}.jsonl", progress=quiet, policy=DEFAULT_POLICY)
    doc = lb.evaluate(lb.load_inputs([tmp_path / f"tune-{system}.jsonl"])[0], mode="smoke", replicates=20, seed=1)
    path = repo / name
    sha = extends_sha or freeze.manifest_identity(primary_path)["manifest_sha256"]
    freeze.write_manifest(doc, path, retry_policy=DEFAULT_POLICY, test_datasets={"denied_topics": test_sha},
                          bootstrap={"replicates": 20, "seed": 1}, extends={"manifest_sha256": sha, "reason": "reviewed later"})
    return path


def test_extension_manifest_freezes_new_arms_beside_the_primary(tmp_path, repo):
    primary = tuned_manifest(tmp_path, repo, Client())
    commit(repo, primary)
    R.run_matrix({"api": Client()}, QS, [row(i, "test", "dtest") for i in range(20, 40)],
                 results_path=tmp_path / "test.jsonl", progress=quiet, freeze_manifest=primary)
    ext = _extension(tmp_path, repo, primary)
    commit(repo, ext)
    R.run_matrix({"api2": Client("api2")}, QS, [row(i, "test", "dtest2") for i in range(20, 40)],
                 results_path=tmp_path / "test-ext.jsonl", progress=quiet, freeze_manifest=ext)
    ledgers = [tmp_path / "test.jsonl", tmp_path / "test.arms.jsonl", tmp_path / "test-ext.jsonl", tmp_path / "test-ext.arms.jsonl"]
    doc = lb.build(ledgers, mode="final", freeze_manifest_path=primary, extension_manifest_paths=[ext])
    assert [b for b in doc["publication_blockers"] if "manifest" in b or "freeze" in b] == []
    st = {a["system"]: a["freeze"] for a in doc["arms"]}
    assert st["api"]["status"] == "frozen" and st["api2"]["status"] == "frozen" and st["api2"]["via"] == "extension"
    assert doc["freeze_manifest"]["extensions"][0]["records"]["test_records"] == 20
    # without the extension, the new arm is not frozen
    doc2 = lb.build(ledgers, mode="final", freeze_manifest_path=primary)
    assert any("not in the frozen manifest" in b for b in doc2["publication_blockers"])


def test_extension_must_name_the_primary_and_add_only_new_arms(tmp_path, repo):
    primary = tuned_manifest(tmp_path, repo, Client())
    commit(repo, primary)
    wrong = _extension(tmp_path, repo, primary, name="wrong.json", extends_sha="f" * 64)
    commit(repo, wrong)
    dup = _extension(tmp_path, repo, primary, system="api", name="dup.json", test_sha="dtest")
    commit(repo, dup)
    R.run_matrix({"api": Client()}, QS, [row(i, "test", "dtest") for i in range(20, 40)],
                 results_path=tmp_path / "test.jsonl", progress=quiet, freeze_manifest=primary)
    doc = lb.build([tmp_path / "test.jsonl"], mode="final", freeze_manifest_path=primary, extension_manifest_paths=[wrong, dup])
    assert any("extends manifest ffffffffffff" in b for b in doc["publication_blockers"])
    assert any("already frozen by another manifest" in b for b in doc["publication_blockers"])


def test_extension_committed_after_its_test_calls_blocks(tmp_path, repo):
    primary = tuned_manifest(tmp_path, repo, Client())
    commit(repo, primary)
    ext = _extension(tmp_path, repo, primary)
    commit(repo, ext, date="2099-01-01T00:00:00+0000")
    R.run_matrix({"api2": Client("api2")}, QS, [row(i, "test", "dtest2") for i in range(20, 40)],
                 results_path=tmp_path / "test-ext.jsonl", progress=quiet, freeze_manifest=ext)
    doc = lb.build([tmp_path / "test-ext.jsonl"], mode="final", freeze_manifest_path=primary, extension_manifest_paths=[ext])
    assert any("extension manifest 1" in b and "not before the first test attempt" in b for b in doc["publication_blockers"])


def test_a_declared_contract_change_needs_a_committed_approval(tmp_path, repo):
    path = tuned_manifest(tmp_path, repo, Client())
    commit(repo, path)
    R.run_matrix({"api": Client()}, QS, [row(i, "test", "dtest") for i in range(20, 40)],
                 results_path=tmp_path / "test.jsonl", progress=quiet, freeze_manifest=path)
    contract = json.loads(json.dumps(lb.DEFAULT_CONTRACT))
    contract["version"] = "v1.1-draft"
    contract["suites"]["word_filters"]["subtasks"]["profanity"] = {"tags": ["profanity"]}
    cpath = tmp_path / "contract.json"
    cpath.write_text(json.dumps(contract))
    doc = lb.build([tmp_path / "test.jsonl"], contract_path=cpath, mode="final", freeze_manifest_path=path)
    assert any("evaluation contract differs" in b for b in doc["publication_blockers"])
    m = json.loads(path.read_text())
    ap = _approval(repo, path, frozen_scoring_sha256=m["scoring"]["sha256"],
                   frozen_contract_hash=m["contract"]["hash"], approved_contract_hash=doc["contract"]["hash"],
                   contract_change="profanity joins word_filters, equal weight")
    commit(repo, ap)
    doc = lb.build([tmp_path / "test.jsonl"], contract_path=cpath, mode="final", freeze_manifest_path=path, approval_paths=[ap])
    assert not any("evaluation contract differs" in b for b in doc["publication_blockers"])
    assert any(v["kind"] == "declared contract change" for v in doc["analysis_versions"])


def test_an_approval_scores_changed_code_but_publication_needs_the_approvers_confirmation(tmp_path, repo):
    path, ledgers = _frozen_with_old_scoring(tmp_path, repo)
    ap = _approval(repo, path)
    commit(repo, ap)
    doc = lb.build(ledgers, mode="final", freeze_manifest_path=path, approval_paths=[ap])
    assert any("not yet confirmed by the approver" in b for b in doc["publication_blockers"])
    ap2 = _approval(repo, path, confirmation={"by": "Owner", "at": "2026-09-24", "statement": "I approve these hashes."})
    commit(repo, ap2)
    doc = lb.build(ledgers, mode="final", freeze_manifest_path=path, approval_paths=[ap2])
    assert not any("confirmed" in b for b in doc["publication_blockers"])
