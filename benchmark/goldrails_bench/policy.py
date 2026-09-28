"""The frozen failure, retry and provenance policy for a benchmark run. Pure functions, no model calls.

Retries. A row is sent through an adapter up to ``1 + max_retries`` times per call. The default is ``max_retries=0``:
one attempt, nothing retried, the failure is the measurement. A run may declare a positive retry count before it
starts (it is written into the arms sidecar and every record); only transient transport errors (connection resets,
timeouts, throttling, 5xx) are retried, never an answer the system returned and never an adapter refusal. Every
attempt, successful or not, is kept on the record under ``attempts`` with its error, latency and usage, so retries
are visible in cost and latency.

Exhausted. A row is *exhausted* when its last attempt failed: either the retry budget is used up, or the error is not
retryable (an adapter that cannot represent the row, a validation error, nothing mappable). An exhausted row is
final under the frozen policy: a resume never retries it, because a failure is a measurement.

Scoring. Every labelled row in an evaluated arm counts in the primary score. A decided row earns credit 1 when its
prediction matches the expected label, else 0. An exhausted row, and a row that returned but carries no decision
(nothing the decision rule can score), earns 0: no correctness credit in either class. The primary task score is

    100 x 1/2 x (violation recall credit + benign pass credit)

with both rates over *all* labelled rows of their class. Conditional quality (decided rows only) and the failure
rate are shown beside it, never instead of it. The older diagnostics in ``score.summarise`` (``failure_policy``
exclude, flag, pass) are unchanged.

Provenance. A record's dataset origin is *verified* only when its dataset version can be found in the Git history
of the sample file it names (or the rehash tool proved its content identical to a committed version). Records with
no dataset identity, a version that is in no commit, or a row hash that disagrees with the named version are
``origin unverifiable``: reports list them as such and the primary summary keeps them in their own group, never
pooled with verified rows.
"""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass

# --- retries and attempts --------------------------------------------------------------------------------------

# Error class names (the prefix of a recorded ``error`` string, "Type: message") that indicate a transport failure
# worth retrying under a positive retry budget. Anything else is final on first failure.
TRANSIENT = ("APIConnectionError", "APITimeoutError", "ConnectError", "ConnectTimeout", "ReadTimeout", "ReadError",
             "RemoteProtocolError", "TimeoutException", "ConnectionError", "EndpointConnectionError",
             "ReadTimeoutError", "ConnectTimeoutError", "ThrottlingException", "TooManyRequestsException",
             "ServiceUnavailableException", "InternalServerException", "InternalServerError", "RateLimitError",
             "ServiceUnavailableError")


@dataclass(frozen=True)
class RetryPolicy:
    """How many times one call may be attempted, and which failures qualify. Frozen per run."""
    max_retries: int = 0
    retry_on: tuple = TRANSIENT
    backoff_s: float = 0.0          # sleep before retry n is backoff_s * 2**(n-1)
    name: str = "no-retry"

    def __post_init__(self):
        if self.max_retries < 0:
            raise ValueError("max_retries must be >= 0")

    def identity(self) -> dict:
        """What the ledger and arms sidecar record about the policy."""
        return {"name": self.name, "max_retries": self.max_retries, "backoff_s": self.backoff_s,
                "retry_on": list(self.retry_on) if self.max_retries else []}

    def retryable(self, error: str | None) -> bool:
        """The error's class name is on the transient list, allowing a library prefix: the TypeSafe SDK raises
        ``TypeSafeAPIConnectionError`` for an ``APIConnectionError``. Before 23 September 2026 only exact names matched,
        so the SDK's connection errors were never retried (documented in the first benchmark's correction)."""
        head = (error or "").split(":", 1)[0].strip()
        return bool(head) and any(head == t or head.endswith(t) for t in self.retry_on)

    def should_retry(self, error: str | None, attempts_made: int) -> bool:
        """True when another attempt is allowed after ``attempts_made`` failed attempts."""
        return attempts_made <= self.max_retries and self.retryable(error)

    def wait(self, attempts_made: int, sleep=time.sleep) -> None:
        if self.backoff_s > 0:
            sleep(self.backoff_s * 2 ** (attempts_made - 1))


NO_RETRY = RetryPolicy()
# Contract v1 (docs/19): up to three retries with backoff, for transient infrastructure errors only (the TRANSIENT
# list above). An answer is never retried because it is unwelcome: a returned answer is final. Every attempt, and its
# usage, is written to the record, so retries are counted in cost.
TRANSIENT_3 = RetryPolicy(max_retries=3, backoff_s=2.0, name="transient-3")
DEFAULT_POLICY = TRANSIENT_3


def _iso_ms(t: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + f".{int((t % 1) * 1000):03d}Z"


def attempt_record(call, chunk: int, attempt: int, started: float | None = None, ended: float | None = None) -> dict:
    """One attempt as stored on the ledger record: enough to count retries, cost and latency later.

    ``at`` is the completion time to the second (kept for older readers). ``started_at`` and ``ended_at`` are the
    wall-clock start and end of the call to the millisecond, so serving windows come from measured times rather than
    from completion time minus latency. Ledgers written before 23 September 2026 have only ``at``."""
    ended = time.time() if ended is None else ended
    rec = {"chunk": chunk, "attempt": attempt, "ok": bool(call.ok), "error": call.error,
           "latency_s": round(call.latency_s, 3) if call.latency_s is not None else None, "usage": call.usage,
           "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ended)), "ended_at": _iso_ms(ended)}
    if started is not None:
        rec["started_at"] = _iso_ms(started)
    return rec


def ask_with_policy(client, state, questions: dict, policy: RetryPolicy = DEFAULT_POLICY, chunk: int = 0,
                    sleep=time.sleep):
    """(final call, [attempt records]). The final call is the last attempt; it failed only if the row is exhausted."""
    attempts = []
    while True:
        started = time.time()
        call = client.ask(state, questions)
        attempts.append(attempt_record(call, chunk, len(attempts) + 1, started=started, ended=time.time()))
        if call.ok or not policy.should_retry(call.error, len(attempts)):
            return call, attempts
        policy.wait(len(attempts), sleep)


def exhausted(attempts: list[dict]) -> bool:
    """A row is exhausted when the final attempt of any of its chunks failed."""
    last = {}
    for a in attempts:
        last[a["chunk"]] = a
    return any(not a["ok"] for a in last.values())


# --- outcomes and credit ---------------------------------------------------------------------------------------

FAILED, NO_DECISION, DECIDED = "failed", "no_decision", "decided"
LABELS = ("yes", "no")


def outcome(record: dict, score: float | None) -> str:
    """failed (exhausted: the call did not return), no_decision (returned, nothing the rule can score), decided."""
    if not record.get("ok"):
        return FAILED
    return NO_DECISION if score is None else DECIDED


def credit(record: dict, score: float | None, threshold: float = 0.5) -> int:
    """Primary-score credit: 1 only for a decided row whose prediction (score >= threshold) matches ``expected``.
    Failed and no-decision rows earn 0 whatever their label. Unlabelled rows are not scored (0, and excluded by
    ``primary_summary``)."""
    if outcome(record, score) != DECIDED or record.get("expected") not in LABELS:
        return 0
    return int((score >= threshold) == (record["expected"] == "yes"))


# --- provenance ------------------------------------------------------------------------------------------------

VERIFIED, UNVERIFIABLE, UNCHECKED = "origin verified", "origin unverifiable", "origin unchecked"


def origin_of(record: dict, versions_of=None) -> tuple[str, str]:
    """(status, reason) for the dataset version a record says it was run on.

    ``versions_of(rel_path)`` returns that sample file's versions as ``rehash_ledger.git_versions`` does
    ([{ref, sha_old, sha_new, rows}], working copy first). Without it, records the rehash tool did not annotate are
    ``origin unchecked``; reports pass it so every record is checked against Git."""
    d = record.get("dataset") or {}
    if not d.get("sha256"):
        return UNVERIFIABLE, "no dataset identity on the record"
    note = d.get("rehash_note") or ""
    if "not in git" in note:
        return UNVERIFIABLE, note
    if "row_hash disagrees" in note:
        return UNVERIFIABLE, note
    if not (d.get("source") and d.get("feature") and d.get("split")):
        return UNVERIFIABLE, "dataset identity names no source file"
    if versions_of is None:
        if note.startswith(("verified", "moved")):
            return VERIFIED, note
        return UNCHECKED, note or "not checked against git"
    rel = f"{d['source']}/{d['feature']}.{d['split']}.jsonl"
    try:
        versions = versions_of(rel)
    except Exception as e:  # noqa: BLE001  a missing git or file is a reason, not a crash
        return UNVERIFIABLE, f"cannot read git history of {rel}: {type(e).__name__}"
    shas = {d["sha256"], d.get("rehashed_from")} - {None}
    committed = [v for v in versions if v["ref"] != "working" and shas & {v["sha_old"], v["sha_new"]}]
    if not committed:
        working = any(v["ref"] == "working" and shas & {v["sha_old"], v["sha_new"]} for v in versions)
        return UNVERIFIABLE, ("matches the uncommitted working copy only" if working else f"dataset version not in the git history of {rel}")
    rh = record.get("row_hash")
    if rh and not any(v["rows"].get(record.get("id")) == rh for v in committed):
        return UNVERIFIABLE, "row_hash disagrees with every committed copy of that dataset version"
    return VERIFIED, f"dataset version found in commit {committed[0]['ref']}"


def cached_versions(versions_of=None):
    """A memoised ``versions_of``; defaults to reading Git through ``rehash_ledger.git_versions``."""
    if versions_of is None:
        from .rehash_ledger import git_versions as versions_of
    cache: dict = {}

    def get(rel):
        if rel not in cache:
            cache[rel] = versions_of(rel)
        return cache[rel]
    return get


def origin_report(records: list[dict], versions_of=None) -> str:
    """Markdown listing each dataset version in the records with its origin status. Unverifiable versions are named
    with their record counts and reasons, so a reader can see they were scored apart and why."""
    get = cached_versions(versions_of)
    by = defaultdict(lambda: {"n": 0, "arms": set(), "status": None, "reasons": set()})
    for r in records:
        d = r.get("dataset") or {}
        status, reason = origin_of(r, get)
        key = ((d.get("sha256") or "none")[:12], status)
        b = by[key]; b["n"] += 1; b["arms"].add((r.get("system"), r.get("question_set"))); b["status"] = status; b["reasons"].add(reason)
    unv = sum(b["n"] for b in by.values() if b["status"] == UNVERIFIABLE)
    lines = ["## Dataset origin", "",
             (f"{unv} of {len(records)} records have **origin unverifiable**: the dataset version they name cannot be "
              "found in Git, or they name none. They are scored in their own groups, never pooled with verified rows."
              if unv else f"All {len(records)} records name a dataset version found in Git history."), "",
             "| dataset sha | origin | records | arms | reason |", "|---|---|---|---|---|"]
    for (sha, status), b in sorted(by.items(), key=lambda kv: (kv[1]["status"] != UNVERIFIABLE, kv[0])):
        lines.append(f"| {sha} | {status} | {b['n']} | {len(b['arms'])} | {'; '.join(sorted(b['reasons']))} |")
    return "\n".join(lines)


# --- the primary metric path -----------------------------------------------------------------------------------

def primary_summary(records: list[dict], threshold: float = 0.5, versions_of=None) -> list[dict]:
    """One line per (arm, origin status) with the primary task score under this policy: exhausted and no-decision
    rows get zero credit. Records should be exploded (one per question set) and deduplicated as ``score`` does.
    Unlabelled rows are counted and left out of the score."""
    from .score import arm_of, primary_credit, score_of
    get = cached_versions(versions_of) if versions_of is not None else None
    groups = defaultdict(list)
    for r in records:
        groups[arm_of(r) + (origin_of(r, get)[0],)].append(r)
    lines = []
    for (system, qs, cfg, dsha, origin), rs in sorted(groups.items(), key=lambda kv: tuple(str(x) for x in kv[0])):
        labelled = [r for r in rs if r.get("expected") in LABELS]
        s = {id(r): (score_of(r) if r.get("ok") else None) for r in labelled}
        out = {id(r): outcome(r, s[id(r)]) for r in labelled}
        pos = [r for r in labelled if r["expected"] == "yes"]; neg = [r for r in labelled if r["expected"] == "no"]
        c = {id(r): primary_credit(r, threshold) for r in labelled}
        recall = sum(c[id(r)] for r in pos) / len(pos) if pos else None
        passed = sum(c[id(r)] for r in neg) / len(neg) if neg else None
        dpos = [r for r in pos if out[id(r)] == DECIDED]; dneg = [r for r in neg if out[id(r)] == DECIDED]
        crec = sum(c[id(r)] for r in dpos) / len(dpos) if dpos else None
        cpass = sum(c[id(r)] for r in dneg) / len(dneg) if dneg else None
        n_fail = sum(1 for r in labelled if out[id(r)] == FAILED); n_nd = sum(1 for r in labelled if out[id(r)] == NO_DECISION)
        lines.append({"system": system, "question_set": qs, "config_hash": cfg, "dataset_sha": (dsha or "")[:12] or None,
                      "origin": origin, "n": len(rs), "unlabelled": len(rs) - len(labelled), "positives": len(pos),
                      "negatives": len(neg), "failed": n_fail, "no_decision": n_nd,
                      "decided": len(labelled) - n_fail - n_nd, "threshold": threshold,
                      "violation_recall": recall, "benign_pass_rate": passed,
                      "primary_score": 100 * 0.5 * (recall + passed) if recall is not None and passed is not None else None,
                      "conditional_score": 100 * 0.5 * (crec + cpass) if crec is not None and cpass is not None else None,
                      "failure_rate": (n_fail + n_nd) / len(labelled) if labelled else None})
    return lines


def policy_of(records: list[dict]) -> list[dict]:
    """The distinct retry policies recorded on a set of records (legacy records predate the field)."""
    seen = {}
    for r in records:
        p = r.get("retry_policy")
        seen[repr(sorted((p or {"name": "unrecorded (legacy: no retries)"}).items()))] = p or {"name": "unrecorded (legacy: no retries)"}
    return list(seen.values())


__all__ = ["RetryPolicy", "DEFAULT_POLICY", "TRANSIENT_3", "TRANSIENT", "ask_with_policy", "attempt_record", "exhausted", "outcome",
           "credit", "origin_of", "origin_report", "primary_summary", "policy_of", "FAILED", "NO_DECISION", "DECIDED",
           "VERIFIED", "UNVERIFIABLE", "UNCHECKED", "asdict"]
