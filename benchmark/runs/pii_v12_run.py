"""PII rerun on NVIDIA Nemotron-PII (dataset v1.2, subset first-benchmark-v1.2) for every system.

    uv run python benchmark/runs/pii_v12_run.py tune      # the 50 PII tuning rows, every system
    uv run python benchmark/runs/pii_v12_run.py freeze    # writes freeze-extension-3.json; commit it
    uv run python benchmark/runs/pii_v12_run.py test      # the 160 PII test rows, once, under the committed manifest
    uv run python benchmark/runs/pii_v12_run.py latency   # serial latency pass, 50 rows per system

Each system keeps the question set frozen for PII in the first benchmark (v2-f5-pii for all seven); only the threshold
is fitted again, on the new tuning rows, by the same rule (maximise tuning task score). The manifest names the primary
manifest's sha256 and is committed before any test call; the runner refuses test rows until then. Ledgers:
``pii-v12-tune.jsonl``, ``pii-v12-test.jsonl``, ``pii-v12-latency.jsonl``. The first benchmark's PII results stay as
they were.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
import first_benchmark as FB  # noqa: E402

from goldrails_bench.runner import run_matrix  # noqa: E402
from goldrails_bench.subset import load_subset_rows  # noqa: E402

SUBSET = "first-benchmark-v1.2"
SUITE = "sensitive_info"
EXT = FB.REPO / "benchmark" / "subsets" / FB.SUBSET / "freeze-extension-3.json"
SELECTION = FB.OUT / "pii-v12-selection.json"
CONTRACT = FB.REPO / "benchmark" / "contracts" / "v1.1.json"


def frozen_question_sets() -> dict:
    sel = json.loads((FB.OUT / "selection.json").read_text())
    return {c["system"]: c["question_set"] for c in sel["chosen"] if c["suite"] == SUITE}


def rows(split: str) -> list:
    return [r for r in load_subset_rows(SUBSET, "F5", split) if r.subtask == "pii"]


def systems(kinds: set) -> dict:
    return {k: v for k, v in FB.clients(kinds, SUITE).items() if k != "regex-baseline"}


def run(stage: str, kinds: set, split: str, serial=False, limit=None, manifest=None, rerun=False):
    FB.OUT.mkdir(parents=True, exist_ok=True)
    rs = rows(split)[: limit or None]
    qs = frozen_question_sets()
    ledger = FB.OUT / f"pii-v12-{stage}{'-rerun' if rerun else ''}.jsonl"   # a recorded row is never rerun in place
    for name, (client, gpu) in systems(kinds).items():
        q = qs[name]
        out = run_matrix({name: client}, FB.qsets([q]), rs, workers={"jev-1.13.0": 8}, serial=serial,
                         gpu_of={name: gpu} if gpu is not None else {}, results_path=ledger, load=FB.LOAD,
                         freeze_manifest=manifest, progress=lambda *_: None)
        print(f"pii-v12 {stage:8s} {name:24s} {q:12s} {len(out):4d} rows, {sum(not r['ok'] for r in out)} failed", flush=True)


def freeze(kinds: set):
    from goldrails_bench import freeze as F
    from goldrails_bench.leaderboard import build
    from goldrails_bench.policy import DEFAULT_POLICY
    ledgers = [p for p in (FB.OUT / "pii-v12-tune.jsonl", FB.OUT / "pii-v12-tune-rerun.jsonl") if p.exists()]
    for tune in ledgers:
        splits = {json.loads(x)["dataset"]["split"] for x in tune.read_text().splitlines() if x.strip()}
        if splits != {"tune"}:
            raise SystemExit(f"{tune.name} holds splits {sorted(splits)}; only tuning rows may fit anything")
    args = [str(x) for p in ledgers for x in (p, p.with_suffix(".arms.jsonl")) if x.exists()]
    doc = build(args, contract_path=CONTRACT, mode="smoke")   # a successful re-attempt supersedes its failed original
    names = set(systems(kinds))
    arms = [a for a in doc["arms"] if a["system"] in names and a["suite"] == SUITE]
    primary_sha = hashlib.sha256(FB.MANIFEST.read_bytes()).hexdigest()
    test_sha = rows("test")[0].dataset["sha256"]
    m = F.write_manifest(doc, EXT, retry_policy=DEFAULT_POLICY, test_datasets={SUITE: test_sha},
                         arms=[a["arm_id"] for a in arms],
                         extends={"manifest_sha256": primary_sha, "subset": SUBSET, "systems": sorted(names),
                                  "reason": ("PII source replaced by NVIDIA Nemotron-PII (dataset v1.2) after its audit; "
                                             "each system keeps its frozen PII question set and refits its threshold "
                                             "on the new tuning rows (contract v1.1)")})
    probs = F.validate(m)
    if probs:
        raise SystemExit("extension manifest invalid: " + "; ".join(probs))
    EXT.write_text(json.dumps(m, indent=1, sort_keys=True) + "\n")
    SELECTION.write_text(json.dumps({
        "rule": "each system's PII question set frozen in the first benchmark (selection.json); threshold refitted on v1.2 tuning rows",
        "chosen": [{"system": a["system"], "suite": SUITE, "question_set": a["question_set"],
                    "tune_task_score": (a.get("suite_score") or {}).get("value")} for a in sorted(arms, key=lambda a: a["system"])]},
        indent=1) + "\n")
    print(f"extension manifest: {len(m['arms'])} arms -> {EXT.relative_to(FB.REPO)}; commit it before the test stage")


def main(argv=None) -> int:
    load_dotenv(find_dotenv(usecwd=True))
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=("tune", "freeze", "test", "latency"))
    ap.add_argument("--systems", default="open,jev,bedrock")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--rerun", action="store_true", help="write to the -rerun ledger (re-attempts of failed rows)")
    a = ap.parse_args(argv)
    kinds = set(a.systems.split(","))
    if a.stage == "tune":
        run("tune", kinds, "tune", limit=a.limit, rerun=a.rerun)
    elif a.stage == "freeze":
        freeze(kinds)
    elif a.stage == "test":
        run("test", kinds, "test", manifest=EXT, rerun=a.rerun)
    else:
        run("latency", kinds, "tune", serial=True, limit=a.limit or 50, manifest=EXT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
