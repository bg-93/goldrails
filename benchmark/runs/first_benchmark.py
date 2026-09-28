"""Run the first Gold Rails benchmark on the frozen subset, in stages.

    uv run python benchmark/runs/first_benchmark.py tune --systems open,jev,regex
    uv run python benchmark/runs/first_benchmark.py tune --systems bedrock
    uv run python benchmark/runs/first_benchmark.py freeze          # writes the manifest; commit it before testing
    uv run python benchmark/runs/first_benchmark.py test --systems open,jev,regex,bedrock
    uv run python benchmark/runs/first_benchmark.py latency --systems open,jev,regex,bedrock

Stages never touch test rows before the freeze manifest is committed (the runner refuses). Core suites and bias write
separate ledgers so the leaderboard reads only core suites. Every open-model stage records allocated VM time in
``serving.jsonl`` for cost per 1,000.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

from goldrails_bench.question_sets import load as load_qs
from goldrails_bench.runner import run_matrix
from goldrails_bench.subset import load_subset_rows

SUBSET = "first-benchmark"
REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "benchmark" / "results" / SUBSET
MANIFEST = REPO / "benchmark" / "subsets" / SUBSET / "freeze-manifest.json"
IMPL = json.loads((REPO / "benchmark" / "subsets" / SUBSET / "implementations.json").read_text())
CORE = {"content": "F1", "prompt_attacks": "F2", "word_filters": "F4", "sensitive_info": "F5", "grounding": "F6"}
LOAD = {"concurrency": {"api:jev-1.13.0": 8, "api:bedrock": 1, "gpu_lane": 2}, "batch_size": 1,
        "client_location": IMPL["declared_load"]["client_location"]}
BEDROCK_OF = IMPL["systems"]["managed_service"]["composite_of"]


def qsets(names):
    return {n: load_qs(*n.split("-", 1)) for n in names}


def clients(kinds: set, suite: str):
    """{system: (client, gpu or None)} applicable to this suite."""
    out = {}
    if "jev" in kinds:
        from goldrails_bench.systemone import SystemOneClient
        out["jev-1.13.0"] = (SystemOneClient("jev-1.13.0", model="jev-1.13.0", identity={"model": "jev-1.13.0", "provider": "api.typesafe.ai"}), None)
    if "open" in kinds:
        from goldrails_bench.endpoints import resolve_models
        from goldrails_bench.systemone import SystemOneClient
        for m in resolve_models(mode="tunnel"):
            out[m["name"]] = (SystemOneClient(m["name"], base_url=m["url"], model=m["model"], identity=m["identity"], timeout=300), m["gpu"])
    if "bedrock" in kinds and suite in BEDROCK_OF:
        name = BEDROCK_OF[suite]
        if name == "bedrock-checks":
            from goldrails_bench.bedrock import BedrockChecksClient
            out[name] = (BedrockChecksClient(), None)
        else:
            from goldrails_bench.bedrock_apply import BedrockApplyClient
            out[name] = (BedrockApplyClient(name.split("-")[-1]), None)
    if "regex" in kinds and suite == "word_filters":
        from goldrails_bench.regex_words import RegexWordClient
        out["regex-baseline"] = (RegexWordClient(), None)
    return out


def serving_note(stage: str, systems: dict, rows_by_system: dict, started: float, ended: float, windows: dict):
    """Allocated VM time per open model: the wall-clock window in which the VM served only that model's calls (systems
    run one after another), so each model is charged the whole VM for its own window (share 1.0)."""
    gpu_systems = [s for s, (_, g) in systems.items() if g is not None]
    if not gpu_systems:
        return
    with (OUT / "serving.jsonl").open("a") as f:
        for s in gpu_systems:
            f.write(json.dumps({"stage": stage, "system": s, "hardware": "g2-standard-24/us-east4/on-demand/third-party",
                                "allocated_seconds": round(windows.get(s, 0.0), 1), "share": 1.0, "method": "per-system window",
                                "evaluations": rows_by_system.get(s, 0),
                                "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
                                "ended": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ended))}) + "\n")


def run_stage(stage: str, kinds: set, split: str, chosen: dict | None = None, serial=False, limit=None):
    OUT.mkdir(parents=True, exist_ok=True)
    workers = {"jev-1.13.0": 8}
    for suite, feat in list(CORE.items()) + [("bias_b1", "F7"), ("bias_b3", "F7")]:
        rows = load_subset_rows(SUBSET, feat, split)
        if suite == "bias_b1":
            rows = [r for r in rows if r.subtask == "b1_disparate_fpr"]
        elif suite == "bias_b3":
            rows = [r for r in rows if r.subtask == "b3_decision"]
        if limit:
            rows = rows[:limit]
        if not rows:
            continue
        systems = clients(kinds, "content" if suite == "bias_b1" else suite)
        if suite == "bias_b3":
            systems = {k: v for k, v in systems.items() if not k.startswith("bedrock") and k != "regex-baseline"}
        ledger = OUT / (f"{stage}-bias.jsonl" if suite.startswith("bias") else f"{stage}.jsonl")
        started = time.time(); counts = {}; windows = {}
        for name, (client, gpu) in systems.items():
            t_sys = time.time()
            if suite == "bias_b3":
                groups = {"v1-f7-bbq": [r for r in rows if r.provenance.source == "bbq"],
                          "v1-f7-discrim-eval": [r for r in rows if r.provenance.source == "discrim_eval"]}
            else:
                cand = IMPL["candidate_question_sets"]["content" if suite == "bias_b1" else suite]
                names = [chosen[(name, "content" if suite == "bias_b1" else suite)]] if chosen is not None else cand
                groups = {n: rows for n in names}
            for qname, grows in groups.items():
                if not grows:
                    continue
                out = run_matrix({name: client}, qsets([qname]), grows, workers=workers, serial=serial,
                                 gpu_of={name: gpu} if gpu is not None else {}, results_path=ledger, load=LOAD,
                                 freeze_manifest=MANIFEST if split == "test" else None, progress=lambda *_: None)
                counts[name] = counts.get(name, 0) + len(out)
                print(f"{stage} {suite:15s} {name:24s} {qname:22s} {len(out):4d} rows, {sum(not r['ok'] for r in out)} failed", flush=True)
            windows[name] = time.time() - t_sys
        serving_note(f"{stage}:{suite}", systems, counts, started, time.time(), windows)


def rerun_failed():
    """Documented correction: re-attempt only the test rows whose original call failed on a transient connection error
    that the frozen retry policy should have retried (the retry matcher missed SDK-prefixed error names). Same frozen
    configuration and manifest; results go to test-rerun.jsonl and the original records stay untouched."""
    from collections import defaultdict
    from goldrails_bench.policy import TRANSIENT_3
    failed = defaultdict(set)
    for line in (OUT / "test.jsonl").read_text().splitlines():
        d = json.loads(line)
        if not d["ok"] and TRANSIENT_3.retryable(d.get("error")):
            failed[(d["system"], d["question_set"], d["dataset"]["feature"])].add(d["id"])
    suite_of = {v: k for k, v in CORE.items()}
    for (system, qname, feat), ids in sorted(failed.items()):
        suite = suite_of[feat]
        rows = [r for r in load_subset_rows(SUBSET, feat, "test") if r.id in ids]
        client, gpu = clients({"open", "jev"}, suite)[system]
        out = run_matrix({system: client}, qsets([qname]), rows, gpu_of={system: gpu} if gpu is not None else {},
                         results_path=OUT / "test-rerun.jsonl", load=LOAD, freeze_manifest=MANIFEST, progress=lambda *_: None)
        print(f"rerun {system} {qname} {feat}: {len(out)} rows, {sum(not r['ok'] for r in out)} failed", flush=True)


def load_chosen() -> dict:
    m = json.loads((OUT / "selection.json").read_text())
    return {(x["system"], x["suite"]): x["question_set"] for x in m["chosen"]}


def freeze():
    from goldrails_bench import freeze as F
    from goldrails_bench.leaderboard import build
    from goldrails_bench.policy import DEFAULT_POLICY
    doc = build([str(OUT / "tune.jsonl"), str(OUT / "tune.arms.jsonl")], mode="smoke")
    best = {}
    for a in doc["arms"]:
        v = (a.get("suite_score") or {}).get("value")
        key = (a["system"], a["suite"])
        if v is None:
            continue
        if key not in best or v > best[key][0] or (v == best[key][0] and a["question_set"] < best[key][1]["question_set"]):
            best[key] = (v, a)
    chosen = [a for _, a in best.values()]
    test_sha = {su: load_subset_rows(SUBSET, feat, "test")[0].dataset["sha256"] for su, feat in CORE.items()}
    m = F.write_manifest(doc, MANIFEST, retry_policy=DEFAULT_POLICY, test_datasets=test_sha, arms=[a["arm_id"] for a in chosen])
    (OUT / "selection.json").write_text(json.dumps({"rule": "per system and suite, the candidate question set with the highest tuning task score; ties to the lower name",
        "chosen": [{"system": a["system"], "suite": a["suite"], "question_set": a["question_set"], "tune_task_score": v}
                   for v, a in sorted(best.values(), key=lambda t: (t[1]["suite"], t[1]["system"]))]}, indent=1) + "\n")
    add_bias_arms(m)
    print(f"manifest: {len(m['arms'])} core arms + bias arms -> {MANIFEST}; commit it before the test stage")


def add_bias_arms(m: dict):
    """Bias rows are test rows too, so their arms must be frozen: B1 reuses each system's chosen content question set
    and its request threshold; B3 uses the fixed bias question sets with no threshold (source-defined metrics)."""
    from goldrails_bench import freeze as F
    from goldrails_bench.runner import config_hash
    chosen = load_chosen()
    rows = load_subset_rows(SUBSET, "F7", "test")
    sha = rows[0].dataset["sha256"]
    extra = []
    for kinds in ({"jev"}, {"open"}, {"bedrock"}):
        try:
            cl = clients(kinds, "content")
        except Exception as e:  # noqa: BLE001
            print(f"bias arms for {kinds}: {e}"); continue
        for name, (client, _) in cl.items():
            content_arm = next((a for a in m["arms"] if a["system"] == name and a["suite"] == "content"), None)
            if content_arm is None:
                continue
            q = content_arm["question_set"]
            extra.append({"system": name, "question_set": q, "config_hash": config_hash(client, qsets([q])[q]), "dataset_sha256": sha,
                          "suite": "bias_b1", "thresholds": content_arm["thresholds"], "tuned_on": content_arm["tuned_on"]})
            if not name.startswith("bedrock"):
                for q3 in ("v1-f7-bbq", "v1-f7-discrim-eval"):
                    extra.append({"system": name, "question_set": q3, "config_hash": config_hash(client, qsets([q3])[q3]),
                                  "dataset_sha256": sha, "suite": "bias_b3", "thresholds": None, "tuned_on": None})
    m["arms"] += extra
    probs = F.validate(m)
    if probs:
        raise SystemExit("manifest invalid: " + "; ".join(probs))
    MANIFEST.write_text(json.dumps(m, indent=1, sort_keys=True) + "\n")


def main(argv=None) -> int:
    load_dotenv(find_dotenv(usecwd=True))
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=("tune", "freeze", "bias-arms", "test", "rerun-failed", "latency"))
    ap.add_argument("--systems", default="open,jev,regex,bedrock")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args(argv)
    kinds = set(a.systems.split(","))
    if a.stage == "tune":
        run_stage("tune", kinds, "tune")
    elif a.stage == "freeze":
        freeze()
    elif a.stage == "bias-arms":
        add_bias_arms(json.loads(MANIFEST.read_text()))
    elif a.stage == "test":
        run_stage("test", kinds, "test", chosen=load_chosen())
    elif a.stage == "rerun-failed":
        rerun_failed()
    elif a.stage == "latency":
        run_stage("latency", kinds, "tune", chosen=load_chosen(), serial=True, limit=a.limit or 100)
    return 0


if __name__ == "__main__":
    sys.exit(main())
