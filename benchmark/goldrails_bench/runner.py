"""Run rows x question sets x systems, concurrently across systems, serially or with a few workers within one.

Accuracy passes want throughput: every system runs at the same time, and a hosted API can take several in-flight
requests. Latency measurement wants the opposite, one request at a time, and is a separate small pass (``serial=True``)
so the two are never mixed in one number. Retries follow the run's frozen ``RetryPolicy`` (policy.py; the default is
none): every attempt is kept on the record, and a row whose last attempt failed is recorded with ok=False and
``exhausted: true``.

    from goldrails_bench.runner import run_matrix
    calls = run_matrix(systems, qsets, rows, workers={"jev-1.13.0": 8}, results_path="benchmark/results/run.jsonl")

With ``results_path`` every finished row is appended to that JSONL as it completes, and a rerun with the same path
skips rows already there, keyed by system, question set, config hash, dataset version, row id and row content hash.
An edited question, a new adapter version or a changed row reruns; a recorded row, failed or not, is never rerun.
Records written before ``row_hash`` existed cannot prove their row content, so resuming such a ledger reruns them.
The VM has an 8-hour hard stop, so a long pass is several resumable invocations, never one that must finish in memory.

Test rows need a frozen manifest (freeze.py). When any row is on the test split, ``run_matrix`` requires
``freeze_manifest``: before any call it proves the manifest is committed (``freeze.manifest_identity``) and that every
(system, config_hash, dataset sha256) about to run is an arm in it, and that the run's retry policy is the frozen
one, raising ``FreezeError`` otherwise. The manifest identity ({manifest_sha256, commit, committed_at}) is written
into the arms sidecar and every test record under ``freeze``. Tuning runs are unaffected.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from goldrails_dataset.records import canonical

from . import freeze as freeze_mod
from .freeze import FreezeError
from .policy import DEFAULT_POLICY, RetryPolicy, ask_with_policy, exhausted
from .question_sets import SEP
from .systemone import SystemOneClient, state_of

DEFAULT_GPU_WORKERS = 2   # keeps one request in flight over the tunnel while the GPU works on the other


def adapter_of(client) -> dict:
    """The adapter that turns a row into this system's request: declared name and version, or the class path for a
    client that declares none (test fakes, older clients)."""
    a = getattr(client, "adapter", None)
    if a:
        return {"name": a["name"], "version": a["version"], "declared": True}
    return {"name": f"{type(client).__module__}.{type(client).__qualname__}", "version": None, "declared": False}


def config_hash(client, qs: dict) -> str:
    """Identity of one experiment arm: the system's declared model and identity, the exact question wording, the
    client's endpoint where the client exposes one, and the adapter version where the client declares one. Part of
    every ledger record and of the resume key, so an edited question set, a swapped checkpoint or changed
    preprocessing never reuses old rows. The SDK client inside ``SystemOneClient`` exposes no ``base_url``, so for
    System One systems the endpoint is not in the hash; the checkpoint identity is. Clients without a declared
    adapter hash exactly as before, which keeps ``backfill_arms`` able to verify old ledgers."""
    ident = {"system": client.system, "model": getattr(client, "model", None),
             "identity": getattr(client, "identity", None),   # checkpoint ref+revision, API name+region: what "model" resolves to
             "base_url": getattr(getattr(client, "client", None), "base_url", None) and str(client.client.base_url),
             "questions": qs["questions"],
             "decision": qs.get("decision")}   # the decision rule is part of the arm: changing it is a new configuration
    if getattr(client, "adapter", None):
        ident["adapter"] = {"name": client.adapter["name"], "version": client.adapter["version"]}
    return hashlib.sha256(json.dumps(ident, sort_keys=True, default=str).encode()).hexdigest()[:16]


def row_hash_of(r) -> str | None:
    """Hash of the row's canonical content (text, context, source, query, labels, spans, provenance minus import
    time). Part of the resume key, so a row edited under the same id and dataset tag is run again."""
    return hashlib.sha256(canonical(r).encode()).hexdigest()[:16] if hasattr(r, "to_dict") else None


def split_of_row(r) -> str | None:
    """The split a row belongs to: its dataset tag first, then the row's own field."""
    return (getattr(r, "dataset", None) or {}).get("split") or getattr(r, "split", None)


def check_freeze(systems: dict, qsets: dict, rows: list, freeze_manifest, policy: RetryPolicy) -> dict | None:
    """Before any call: None for a run with no test rows; otherwise the manifest identity to stamp on test records.
    Raises FreezeError when test rows come without a committed manifest, when the run's retry policy is not the
    frozen one, or when a (system, config_hash, dataset sha256) about to run on test rows is not a manifest arm."""
    test_rows = [r for r in rows if split_of_row(r) == "test"]
    if not test_rows:
        return None
    if not freeze_manifest:
        raise FreezeError(f"{len(test_rows)} test rows and no freeze_manifest: the test split runs only under a "
                          "committed frozen manifest")
    manifest, ident = freeze_mod.load_committed(freeze_manifest)
    if json.loads(json.dumps(policy.identity())) != manifest.get("retry_policy"):
        raise FreezeError(f"retry policy {policy.identity()} is not the frozen one {manifest.get('retry_policy')}")
    frozen = {(a["system"], a["config_hash"], a["dataset_sha256"]) for a in manifest["arms"]}
    dshas = sorted({(getattr(r, "dataset", None) or {}).get("sha256") for r in test_rows}, key=str)
    missing = [(client.system, qname, config_hash(client, qs), d) for client in systems.values()
               for qname, qs in qsets.items() for d in dshas
               if (client.system, config_hash(client, qs), d) not in frozen]
    if missing:
        raise FreezeError("not frozen in " + str(freeze_manifest) + ": " + "; ".join(
            f"{s} {q} config {c} dataset {(d or 'none')[:12]}" for s, q, c, d in missing))
    return freeze_mod.record_stamp(ident)


def done_key(system: str, qname: str, cfg: str | None, dataset: dict | None, rid: str, row_hash: str | None) -> tuple:
    return (system, qname, cfg, (dataset or {}).get("sha256"), rid, row_hash)


DEFAULT_GPU_MAX_QUESTIONS = 16   # a local server's peak activation memory grows with questions per call; hosted APIs are uncapped


def _one(client: SystemOneClient, qname: str, qs: dict, r, max_questions: int | None = None, cfg: str | None = None,
         policy: RetryPolicy = DEFAULT_POLICY, freeze: dict | None = None) -> dict:
    """One row through one question set. With ``max_questions`` the questions go in chunks of that size to the same
    system, answers are joined, latency is the sum over each chunk's final attempt, and the row is ok only if every
    chunk was. Each chunk is attempted under ``policy``; every attempt is kept in ``attempts``."""
    state = state_of(r)
    items = list(qs["questions"].items())
    n = max_questions or len(items) or 1
    chunks = [dict(items[i:i + n]) for i in range(0, len(items), n)] or [{}]
    calls, attempts = [], []
    for i, ch in enumerate(chunks):
        c, a = ask_with_policy(client, state, ch, policy, chunk=i)
        calls.append(c); attempts += a
    ok = all(c.ok for c in calls)
    answers = {k: v for c in calls if c.ok for k, v in (c.answers or {}).items()} if ok else None
    rec = {"question_set": qname, "system": client.system, "id": r.id, "subtask": r.subtask, "expected": r.expected,
            "source": r.provenance.source, "ok": ok, "error": next((c.error for c in calls if not c.ok), None),
            "model": calls[0].model, "latency_s": round(sum(c.latency_s or 0 for c in calls), 3),
            "tokens": sum((c.usage or {}).get("input_tokens") or 0 for c in calls) or None, "answers": answers,
            "calls": len(calls), "config_hash": cfg or config_hash(client, qs),
            "question_sets": sorted({k.split(SEP, 1)[0] for k in qs["questions"] if SEP in k}) or [qname],
            "dataset": getattr(r, "dataset", None),
            "row_hash": row_hash_of(r),
            "decision_keys": qs.get("decision"),
            "adapter": adapter_of(client), "retry_policy": policy.identity(),
            "attempts": attempts, "retries": len(attempts) - len(chunks), "exhausted": exhausted(attempts),
            "group": getattr(r, "group", None),
            "expected_types": sorted({s["label"] for s in (getattr(r, "spans", None) or [])}) if getattr(r, "spans", None) is not None else None,
            "raw": [c.raw for c in calls]}
    if freeze and split_of_row(r) == "test":
        rec["freeze"] = freeze
    return rec


class Ledger:
    """Append-only JSONL of finished rows, plus a sidecar ``<ledger>.arms.jsonl`` holding one line per experiment arm
    (config hash -> system, model identity, question set name and the exact questions as sent, dataset identity).
    Reports render from the sidecar, so editing a question-set file later cannot change what an old run says."""

    def __init__(self, path):
        self.path = Path(path); self.lock = threading.Lock()
        self.arms_path = self.path.with_name(self.path.stem + ".arms.jsonl")
        self.done = set(); self.arms = {}
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    d = json.loads(line); self.done.add(done_key(d["system"], d["question_set"], d.get("config_hash"), d.get("dataset"), d["id"], d.get("row_hash")))
        if self.arms_path.exists():
            for line in self.arms_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    a = json.loads(line); self.arms[(a["config_hash"], (a.get("dataset") or {}).get("sha256"))] = a
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record_arm(self, client, qname: str, qs: dict, cfg: str, dataset: dict | None, policy: RetryPolicy = DEFAULT_POLICY,
                   load: dict | None = None, freeze: dict | None = None):
        key = (cfg, (dataset or {}).get("sha256"))
        if key in self.arms:
            return
        arm = {"config_hash": cfg, "system": client.system, "model": getattr(client, "model", None),
               "identity": getattr(client, "identity", None), "question_set": qname, "questions": qs["questions"],
               "decision": qs.get("decision"), "decision_rule": qs.get("decision_rule"),
               "adapter": adapter_of(client), "retry_policy": policy.identity(),
               "load": load,   # declared {concurrency, batch_size, client_location}: what latency and cost are measured under
               "dataset": dataset, "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        if freeze:
            arm["freeze"] = freeze
        with self.lock:
            with self.arms_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(arm, ensure_ascii=False) + "\n")
            self.arms[key] = arm

    def add(self, rec: dict):
        with self.lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            self.done.add(done_key(rec["system"], rec["question_set"], rec.get("config_hash"), rec.get("dataset"), rec["id"], rec.get("row_hash")))


def run_system(client: SystemOneClient, qsets: dict, rows: list, workers: int = 1, max_questions: int | None = None,
               ledger: Ledger | None = None, policy: RetryPolicy = DEFAULT_POLICY, load: dict | None = None,
               freeze: dict | None = None) -> list[dict]:
    cfgs = {qname: config_hash(client, qs) for qname, qs in qsets.items()}
    if ledger:
        for qname, qs in qsets.items():
            ledger.record_arm(client, qname, qs, cfgs[qname], getattr(rows[0], "dataset", None) if rows else None, policy, load,
                              freeze)
    jobs = [(qname, qs, r, max_questions, cfgs[qname], policy, freeze) for qname, qs in qsets.items() for r in rows
            if not (ledger and done_key(client.system, qname, cfgs[qname], getattr(r, "dataset", None), r.id, row_hash_of(r)) in ledger.done)]

    def job(*j):
        rec = _one(client, *j)
        if ledger: ledger.add(rec)
        return rec

    if workers <= 1:
        return [job(*j) for j in jobs]
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix=client.system) as ex:
        return [f.result() for f in [ex.submit(job, *j) for j in jobs]]


def run_matrix(systems: dict, qsets: dict, rows: list, workers: dict | None = None, serial: bool = False,
               gpu_of: dict | None = None, max_questions: dict | None = None, results_path=None, progress=print,
               policy: RetryPolicy = DEFAULT_POLICY, load: dict | None = None, freeze_manifest=None) -> list[dict]:
    """All systems at once, except that systems sharing a GPU run one after another on that GPU.

    ``gpu_of`` maps a system name to its GPU index (None or absent = hosted API, gets its own lane). Two local
    servers on one card taking large calls at the same time is how a 22 GB L4 runs out of memory; sequencing them
    per card keeps every card busy without the spike. ``serial=True`` forces one request at a time everywhere.

    ``freeze_manifest`` is required when any row is on the test split (see ``check_freeze``); it is checked before
    the ledger is opened or any call is made."""
    freeze = check_freeze(systems, qsets, rows, freeze_manifest, policy)
    workers, gpu_of, max_questions = workers or {}, gpu_of or {}, max_questions or {}
    ledger = Ledger(results_path) if results_path else None
    if ledger and ledger.done:
        progress(f"resuming: {len(ledger.done)} rows already in {results_path}")
    t0 = time.perf_counter()
    if serial:
        out = []
        for name, client in systems.items():
            out += run_system(client, qsets, rows, 1, max_questions=max_questions.get(name, DEFAULT_GPU_MAX_QUESTIONS if gpu_of.get(name) is not None else None), ledger=ledger, policy=policy, load=load, freeze=freeze)
            progress(f"{name}: done, {time.perf_counter()-t0:.0f}s elapsed")
        return out
    lanes: dict = {}   # lane key -> [system names]; one thread per lane
    for name in systems:
        key = ("gpu", gpu_of[name]) if gpu_of.get(name) is not None else ("api", name)
        lanes.setdefault(key, []).append(name)

    def run_lane(names):
        res = []
        for name in names:
            local = gpu_of.get(name) is not None
            r = run_system(systems[name], qsets, rows, workers.get(name, DEFAULT_GPU_WORKERS if local else 1),
                           max_questions=max_questions.get(name, DEFAULT_GPU_MAX_QUESTIONS if local else None), ledger=ledger, policy=policy, load=load, freeze=freeze)
            progress(f"{name}: {len(r)} calls, {sum(1 for x in r if not x['ok'])} failed, {time.perf_counter()-t0:.0f}s elapsed")
            res += r
        return res

    out = []
    with ThreadPoolExecutor(max_workers=len(lanes), thread_name_prefix="lane") as ex:
        for f in as_completed([ex.submit(run_lane, names) for names in lanes.values()]):
            out += f.result()
    return out
