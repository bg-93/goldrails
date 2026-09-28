"""Frozen manifests: what was fixed on tuning rows before any test call, and the Git identity that proves when.

A manifest holds the scoring code identity (leaderboard module sha256 and result schema), the retry policy, the
contract (subtasks, weights, FPR budget, bootstrap seed and replicates) and a list of arms. Each arm is one exact
(system, question_set, config_hash, dataset_sha256) combination, where ``dataset_sha256`` is the test dataset version
the arm will be run on, with the thresholds fit on its tuning rows (and, for binary or step services, the declared
operating point). Write one from a tuning-mode leaderboard result, then commit it:

    doc = leaderboard.evaluate(tune_records, mode="smoke")
    freeze.write_manifest(doc, "benchmark/manifests/v1.json", retry_policy=policy.DEFAULT_POLICY,
                          test_datasets={"denied_topics": "<sha256 of F3.test.jsonl>", ...})

The runner refuses test rows unless a committed manifest lists the exact arm, and stamps the manifest identity on
every test record. The leaderboard's final mode scores with these thresholds and never refits.

A correction after the test is a separate manifest with a ``corrects`` block naming the primary manifest's sha256 and
one entry per corrected arm; it is committed before the corrected run, and the original run stays in the results.

An extension adds arms the primary manifest never listed (a suite whose test rows became eligible later, such as a
reviewed category). It is a separate manifest with an ``extends`` block naming the primary manifest's sha256, frozen
on its own tuning rows and committed before its own test calls. Its arms may not overlap the primary's; the primary's
arms and results are untouched.

Pure functions plus local ``git`` reads. No network, model or cloud calls.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

MANIFEST_VERSION = "goldrails-freeze/1"
REQUIRED_KEYS = ("manifest_version", "frozen_at", "scoring", "retry_policy", "contract", "arms")
ARM_KEYS = ("system", "question_set", "config_hash", "dataset_sha256")
TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class FreezeError(RuntimeError):
    """The freeze cannot be proved: no manifest, an uncommitted manifest, or an arm the manifest does not list."""


# --- building a manifest -----------------------------------------------------------------------------------------

def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def scoring_identity() -> dict:
    """The scoring code a manifest freezes: the leaderboard module's sha256 and its result schema."""
    from . import leaderboard as lb
    return {"module": "goldrails_bench.leaderboard", "sha256": _sha256_bytes(Path(lb.__file__).read_bytes()),
            "schema": lb.SCHEMA}


def _policy_identity(retry_policy) -> dict:
    ident = retry_policy.identity() if hasattr(retry_policy, "identity") else dict(retry_policy)
    return json.loads(json.dumps(ident))


def _exact(th: dict | None) -> float | None:
    """The full-precision threshold (the result document rounds floats to 6 places)."""
    if not th:
        return None
    e = th.get("threshold_exact")
    if e is not None:
        return float(e)
    t = th.get("threshold")
    return None if t is None else float(t)


def _contract_block(doc: dict, bootstrap: dict | None) -> dict:
    c = doc.get("contract") or {}
    required = list(c.get("required_suites") or [])
    suites = c.get("suites") or {}
    boot = {**{k: v for k, v in (c.get("bootstrap") or {}).items() if k in ("replicates", "seed", "ci")},
            **(bootstrap or {})}
    return {
        "version": c.get("version"), "status": c.get("status"), "hash": c.get("hash"),
        "required_suites": required,
        "subtasks": {su: {"subtasks": list((spec.get("subtasks") or {})),
                          "optional_subtasks": list((spec.get("optional_subtasks") or {}))}
                     for su, spec in suites.items()},
        "weights": {"suites": {su: 1 / len(required) for su in required} if required else {},
                    "subtasks": {su: {st: 1 / len(spec["subtasks"]) for st in (spec.get("subtasks") or {})}
                                 for su, spec in suites.items()}},
        "fpr_budget": c.get("fpr_budget"),
        "operating_point": c.get("operating_point"),
        "bootstrap": boot,
    }


def _thresholds_of(arm: dict, operating_point) -> dict:
    """Frozen thresholds per subtask from one arm of a tuning-mode result. Subtasks with no fitted threshold are left
    out, so final mode reports them as not evaluated."""
    scale = arm.get("score_scale")
    out = {}
    for st, s in (arm.get("subtasks") or {}).items():
        th = s.get("threshold")
        if not th or th.get("basis") == "not_fit":
            continue
        t = _exact(th)
        sec = s.get("secondary") or {}
        entry = {"threshold": t, "basis": th.get("basis"),
                 "tuning_task_score": th.get("tuning_task_score"),
                 "tuning_false_positive_rate": th.get("tuning_false_positive_rate"),
                 "secondary": {"threshold": _exact(sec), "basis": sec.get("basis"), "status": sec.get("status"),
                               "budget": sec.get("budget"), "tuning_recall": sec.get("tuning_recall"),
                               "tuning_false_positive_rate": sec.get("tuning_false_positive_rate")}}
        if scale == "binary":
            entry["operating_point"] = operating_point
        elif scale == "ordered_steps":
            entry["operating_point"] = t     # a cut between the service's steps, chosen on tuning
        out[st] = entry
    return out


def write_manifest(doc: dict, path, *, retry_policy, test_datasets: dict, arms=None, bootstrap: dict | None = None,
                   corrects: dict | None = None, extends: dict | None = None, frozen_at: str | None = None) -> dict:
    """Build a manifest from a tuning-mode leaderboard result and write it to ``path``. Returns the manifest.

    ``doc`` must be a tuning-mode (``smoke``) result whose thresholds were fit on rows recorded as ``tune``; a row
    with no recorded split, or a final-mode result, raises. ``test_datasets`` maps each suite to the sha256 of the
    test dataset version its arms will run on (it may equal the tuning sha when one file holds both splits).
    ``arms`` restricts the manifest to those arm ids. ``bootstrap`` overrides the contract's seed and replicates.
    ``corrects`` makes this a correction manifest: {"manifest_sha256": <primary>, "corrections": [{system,
    question_set, original_config_hash, corrected_config_hash, dataset_sha256, reason, informed_by_test}]}.
    ``extends`` makes this an extension manifest: {"manifest_sha256": <primary>, "reason": ...}."""
    if doc.get("mode") != "smoke":
        raise FreezeError(f"a manifest is written from a tuning-mode result; this one is mode {doc.get('mode')!r}")
    wanted = set(arms) if arms is not None else None
    chosen = [a for a in doc.get("arms", []) if wanted is None or a["arm_id"] in wanted]
    if wanted is not None and len(chosen) != len(wanted):
        missing = sorted(wanted - {a["arm_id"] for a in chosen})
        raise FreezeError(f"arms not in the tuning result: {missing}")
    op = (doc.get("contract") or {}).get("operating_point")
    out_arms = []
    for a in chosen:
        unknown = (a.get("sample_sizes") or {}).get("rows_split_unknown") or 0
        if unknown:
            raise FreezeError(f"{a['arm_id']}: {unknown} rows have no recorded split, so its thresholds were not fit "
                              "on tune rows only")
        if a["suite"] not in test_datasets:
            raise FreezeError(f"{a['arm_id']}: no test dataset version given for suite {a['suite']}")
        out_arms.append({
            "system": a["system"], "question_set": a["question_set"], "config_hash": a["config_hash"],
            "dataset_sha256": test_datasets[a["suite"]], "suite": a["suite"], "score_scale": a.get("score_scale"),
            "tuned_on": {"arm_id": a["arm_id"], "dataset_sha256": (a.get("dataset") or {}).get("sha256"),
                         "fit_rows": (a.get("sample_sizes") or {}).get("fit_rows")},
            "thresholds": _thresholds_of(a, op),
        })
    m = {
        "manifest_version": MANIFEST_VERSION,
        "frozen_at": frozen_at or time.strftime(TIME_FORMAT, time.gmtime()),
        "scoring": scoring_identity(),
        "retry_policy": _policy_identity(retry_policy),
        "contract": _contract_block(doc, bootstrap),
        "arms": out_arms,
    }
    if corrects is not None and extends is not None:
        raise FreezeError("a manifest either corrects or extends the primary, not both")
    if corrects is not None:
        m["corrects"] = corrects
    if extends is not None:
        m["extends"] = extends
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(m, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return m


# --- reading a manifest ------------------------------------------------------------------------------------------

def arm_key(a: dict) -> tuple:
    return tuple(a.get(k) for k in ARM_KEYS)


def validate(m: dict) -> list[str]:
    """Problems with a manifest's shape; empty when it is usable."""
    if not isinstance(m, dict):
        return ["manifest is not a JSON object"]
    probs = [f"missing {k}" for k in REQUIRED_KEYS if k not in m]
    if m.get("manifest_version") not in (None, MANIFEST_VERSION):
        probs.append(f"manifest_version {m.get('manifest_version')!r} is not {MANIFEST_VERSION}")
    for i, a in enumerate(m.get("arms") or []):
        miss = [k for k in ARM_KEYS if not a.get(k)]
        if miss:
            probs.append(f"arm {i} lacks {', '.join(miss)}")
    x = m.get("extends")
    if x is not None:
        if not x.get("manifest_sha256"):
            probs.append("extends names no primary manifest_sha256")
        if not x.get("reason"):
            probs.append("extends gives no reason")
        if m.get("corrects") is not None:
            probs.append("a manifest cannot both correct and extend")
    c = m.get("corrects")
    if c is not None:
        if not c.get("manifest_sha256"):
            probs.append("corrects names no primary manifest_sha256")
        for i, e in enumerate(c.get("corrections") or []):
            miss = [k for k in ("system", "question_set", "original_config_hash", "corrected_config_hash",
                                "dataset_sha256", "reason") if not e.get(k)]
            if miss:
                probs.append(f"correction {i} lacks {', '.join(miss)}")
    return probs


def _git(cwd, *args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, timeout=20)


def manifest_identity(path) -> dict:
    """{path, manifest_sha256, commit, committed_at} for a committed manifest file. ``commit`` is the last commit
    that touched it and ``committed_at`` that commit's committer time in UTC. Raises FreezeError when the file is
    missing, outside a Git repository, untracked, never committed, or has uncommitted (staged or unstaged) changes."""
    p = Path(path).resolve()
    if not p.is_file():
        raise FreezeError(f"manifest {path} does not exist")
    top = _git(p.parent, "rev-parse", "--show-toplevel")
    if top.returncode != 0 or not top.stdout.strip():
        raise FreezeError(f"manifest {path} is not in a Git repository")
    root = Path(top.stdout.strip()).resolve()
    rel = p.relative_to(root).as_posix()
    if _git(root, "ls-files", "--error-unmatch", "--", rel).returncode != 0:
        raise FreezeError(f"manifest {rel} is not committed (untracked)")
    st = _git(root, "status", "--porcelain", "--untracked-files=all", "--", rel)
    if st.returncode != 0:
        raise FreezeError(f"cannot read Git status of {rel}: {st.stderr.strip()}")
    if st.stdout.strip():
        raise FreezeError(f"manifest {rel} has uncommitted changes")
    log = _git(root, "log", "-1", "--format=%H %ct", "--", rel)
    if log.returncode != 0 or not log.stdout.strip():
        raise FreezeError(f"manifest {rel} is not committed")
    commit, ts = log.stdout.split()
    return {"path": rel, "manifest_sha256": _sha256_bytes(p.read_bytes()), "commit": commit,
            "committed_at": datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime(TIME_FORMAT)}


def record_stamp(identity: dict) -> dict:
    """What the runner writes on every test record and in the arms sidecar."""
    return {k: identity[k] for k in ("manifest_sha256", "commit", "committed_at")}


@dataclass
class FrozenManifest:
    """A loaded manifest with its Git identity, or the reason the identity could not be proved."""
    manifest: dict
    identity: dict | None = None
    error: str | None = None
    path: str | None = None

    @property
    def sha256(self) -> str | None:
        return (self.identity or {}).get("manifest_sha256")


def load(path) -> FrozenManifest:
    """Read a manifest and prove its identity. An identity failure is kept in ``error`` (the leaderboard turns it
    into a publication blocker); a missing or unparseable file raises."""
    m = json.loads(Path(path).read_text(encoding="utf-8"))
    try:
        ident, err = manifest_identity(path), None
    except FreezeError as e:
        ident, err = None, str(e)
    return FrozenManifest(m, ident, err, str(path))


def load_committed(path) -> tuple[dict, dict]:
    """(manifest, identity) or FreezeError: the runner's strict read."""
    ident = manifest_identity(path)
    m = json.loads(Path(path).read_text(encoding="utf-8"))
    probs = validate(m)
    if probs:
        raise FreezeError(f"manifest {path}: " + "; ".join(probs))
    return m, ident


def threshold_map(primary: FrozenManifest | dict | None, corrections=(), extensions=()) -> dict:
    """Arm key -> {role, manifest_sha256, thresholds, score_scale} from the primary manifest and any extension
    manifests (role ``frozen``) and any correction manifests (role ``corrected``)."""
    out = {}
    for role, fm in ([("frozen", primary)] + [("frozen", x) for x in extensions or ()]
                     + [("corrected", c) for c in corrections or ()]):
        if fm is None:
            continue
        m = fm.manifest if isinstance(fm, FrozenManifest) else fm
        sha = fm.sha256 if isinstance(fm, FrozenManifest) else None
        for a in m.get("arms") or []:
            out[arm_key(a)] = {"role": role, "manifest_sha256": sha, "thresholds": a.get("thresholds") or {},
                               "score_scale": a.get("score_scale")}
    return out


def parse_time(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, TIME_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            return None


__all__ = ["MANIFEST_VERSION", "FreezeError", "FrozenManifest", "write_manifest", "manifest_identity", "load",
           "load_committed", "validate", "arm_key", "threshold_map", "record_stamp", "scoring_identity", "parse_time"]
