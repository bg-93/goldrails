"""Run the arms that became eligible after review (denied topics, profanity, B2 pairs) beside the frozen first
benchmark, reusing its clients, question sets and declared load. The review may be human (dataset v1.1) or, for the
provisional extension, a single AI reviewer (dataset v1.1-ai, subset first-benchmark-v1.1-ai); the subset manifest says
which, and every report carries it.

A set of systems can be frozen and run as its own numbered extension (``--extension 2 --systems bedrock``), for example
when one provider's credentials arrive later; each extension manifest is committed before its own test calls.

    uv run python benchmark/runs/extension_run.py tune --systems open,jev,bedrock
    uv run python benchmark/runs/extension_run.py freeze          # writes the extension manifest; commit it
    uv run python benchmark/runs/extension_run.py test --systems open,jev,bedrock
    uv run python benchmark/runs/extension_run.py latency --systems open,jev,bedrock

Rows come from the v1.1 subset (``--subset``, default ``first-benchmark-v1.1``), which must keep the first benchmark's
core test rows unchanged (``subset --carry-over first-benchmark``). Nothing here touches a core arm.

- Denied topics tunes its candidate question set on the reviewed tuning rows; the best set per system is frozen. Every
  system gets the same topic definitions, examples and order (topics.json; Bedrock's guardrail is built from it).
- Profanity (word filters, contract v1.1) asks decision models ``v1-f4-profanity``; Bedrock answers the same key from
  the frozen word-filter guardrail's managed PROFANITY list only. The masked-spelling rows (``profanity_obfuscated``)
  run with the same frozen arm as a diagnostic: the leaderboard never scores them.
- B2 reuses each system's frozen content question set and ``request`` threshold from the primary manifest; not tuned.

The extension manifest (``freeze-extension-1.json``) names the primary manifest's sha256. The runner refuses test rows
until it is committed. Ledgers: ``ext-tune.jsonl``, ``ext-test.jsonl``, ``ext-test-bias.jsonl``, ``ext-latency.jsonl``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
import first_benchmark as FB  # noqa: E402  (the frozen run's clients, question sets, load and paths)

from goldrails_bench.runner import run_matrix  # noqa: E402
from goldrails_bench.subset import load_subset_rows  # noqa: E402

PRIMARY = FB.MANIFEST
EXT_DIR = FB.REPO / "benchmark" / "subsets" / FB.SUBSET
ext_path = lambda n: EXT_DIR / f"freeze-extension-{n}.json"
selection_path = lambda n: FB.OUT / ("ext-selection.json" if n == 1 else f"ext-selection-{n}.json")
CONTRACT = FB.REPO / "benchmark" / "contracts" / "v1.1.json"
OUT = FB.OUT
# stage -> (feature, subtasks on tune, subtasks on test, leaderboard suite, client suite, candidate question sets)
STAGES = {
    "denied_topics": ("F3", {"topic"}, {"topic"}, "denied_topics", "denied_topics", ["v1-f3-topics"]),
    "profanity": ("F4", {"profanity"}, {"profanity", "profanity_obfuscated"}, "word_filters", "word_filters", ["v1-f4-profanity"]),
    "bias_b2": ("F7", set(), {"b2_counterfactual"}, "bias_b2", "content", None),
}


def rows_for(subset: str, stage: str, split: str) -> list:
    feat, tune_subs, test_subs, *_ = STAGES[stage]
    subs = tune_subs if split == "tune" else test_subs
    return [r for r in load_subset_rows(subset, feat, split) if r.subtask in subs]


def systems_for(stage: str, kinds: set) -> dict:
    systems = FB.clients(kinds, STAGES[stage][4])
    return {k: v for k, v in systems.items() if k != "regex-baseline"}       # the regex baseline covers custom words only


def run(stage_name: str, subset: str, kinds: set, split: str, chosen=None, serial=False, limit=None, ext=1):
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = ext_path(ext) if split == "test" else None
    for stage, (feat, _, _, suite, _, cands) in STAGES.items():
        rows = rows_for(subset, stage, split)[: limit or None]
        if not rows:
            print(f"{stage_name} {stage}: no eligible {split} rows in {subset}", flush=True)
            continue
        ledger = OUT / (f"ext-{stage_name}-bias.jsonl" if stage == "bias_b2" else f"ext-{stage_name}.jsonl")
        for name, (client, gpu) in systems_for(stage, kinds).items():
            if chosen is not None:
                names = [chosen[(name, suite)]] if (name, suite) in chosen else []
            else:
                names = cands or []
            for q in names:
                out = run_matrix({name: client}, FB.qsets([q]), rows, workers={"jev-1.13.0": 8}, serial=serial,
                                 gpu_of={name: gpu} if gpu is not None else {}, results_path=ledger, load=FB.LOAD,
                                 freeze_manifest=manifest, progress=lambda *_: None)
                print(f"{stage_name} {stage:14s} {name:24s} {q:20s} {len(out):4d} rows, {sum(not r['ok'] for r in out)} failed", flush=True)


def chosen_map(ext: int = 1) -> dict:
    sel = json.loads(selection_path(ext).read_text())
    return {(x["system"], x["suite"]): x["question_set"] for x in sel["chosen"]}


def freeze(subset: str, kinds: set, ext: int = 1):
    from goldrails_bench import freeze as F
    from goldrails_bench.leaderboard import build
    from goldrails_bench.policy import DEFAULT_POLICY
    from goldrails_bench.runner import config_hash
    primary = json.loads(PRIMARY.read_text())
    primary_sha = hashlib.sha256(PRIMARY.read_bytes()).hexdigest()
    splits = {json.loads(l)["dataset"]["split"] for l in (OUT / "ext-tune.jsonl").read_text().splitlines() if l.strip()}
    if splits != {"tune"}:   # question-set choice and thresholds come from tuning rows only
        raise SystemExit(f"ext-tune.jsonl holds splits {sorted(splits)}; only tuning rows may select or fit anything")
    doc = build([str(OUT / "ext-tune.jsonl"), str(OUT / "ext-tune.arms.jsonl")], contract_path=CONTRACT, mode="smoke")
    names = set(systems_for("denied_topics", kinds)) | set(systems_for("profanity", kinds))
    earlier = set()
    for n in range(1, ext):   # arms frozen by an earlier extension stay there
        if ext_path(n).exists():
            earlier |= {a["system"] for a in json.loads(ext_path(n).read_text())["arms"]}
    best = {}
    for a in doc["arms"]:
        if a["system"] not in names or a["system"] in earlier:
            continue
        # a profanity arm covers one of word_filters' two subtasks, so rank by the subtasks it scored
        subs = [x["task_score"] for x in a["subtasks"].values() if x.get("status") == "evaluated" and x.get("task_score") is not None]
        v = (a.get("suite_score") or {}).get("value") or (sum(subs) / len(subs) if subs else None)
        k = (a["system"], a["suite"])
        if v is not None and (k not in best or v > best[k][0] or (v == best[k][0] and a["question_set"] < best[k][1]["question_set"])):
            best[k] = (v, a)
    test_sha = {}
    for stage in ("denied_topics", "profanity"):
        feat, suite = STAGES[stage][0], STAGES[stage][3]
        test_sha[suite] = load_subset_rows(subset, feat, "test")[0].dataset["sha256"]
    subset_man = json.loads((FB.REPO / "benchmark" / "subsets" / subset / "manifest.json").read_text())
    basis = ("single-AI reference labels (provisional)" if subset_man.get("provisional_ai_reference") else "human review")
    m = F.write_manifest(doc, ext_path(ext), retry_policy=DEFAULT_POLICY, test_datasets=test_sha,
                         arms=[a["arm_id"] for _, a in best.values()],
                         extends={"manifest_sha256": primary_sha,
                                  "reason": f"denied topics, profanity and B2 pairs became eligible after review: {basis} "
                                            f"(subset {subset}, contract v1.1)", "subset": subset,
                                  "systems": sorted(names - earlier)})
    chosen = [{"system": a["system"], "suite": a["suite"], "question_set": a["question_set"], "tune_task_score": v}
              for v, a in sorted(best.values(), key=lambda t: (t[1]["suite"], t[1]["system"]))]
    b2 = rows_for(subset, "bias_b2", "test")
    if b2:   # B2 reuses the frozen content arm of each system: same question set, same request threshold
        sha = load_subset_rows(subset, "F7", "test")[0].dataset["sha256"]
        for name, (client, _) in systems_for("bias_b2", kinds).items():
            if name in earlier:
                continue
            content = next((a for a in primary["arms"] if a["system"] == name and a["suite"] == "content"), None)
            if content is None:
                continue
            q = content["question_set"]
            m["arms"].append({"system": name, "question_set": q, "config_hash": config_hash(client, FB.qsets([q])[q]),
                              "dataset_sha256": sha, "suite": "bias_b2", "thresholds": content["thresholds"],
                              "tuned_on": content["tuned_on"]})
            chosen.append({"system": name, "suite": "bias_b2", "question_set": q, "tune_task_score": None})
    probs = F.validate(m)
    if probs:
        raise SystemExit("extension manifest invalid: " + "; ".join(probs))
    ext_path(ext).write_text(json.dumps(m, indent=1, sort_keys=True) + "\n")
    selection_path(ext).write_text(json.dumps({
        "rule": ("denied topics and profanity: the candidate question set with the highest tuning task score per "
                 "system, ties to the lower name; B2: the system's frozen content question set and request threshold"),
        "contract": str(CONTRACT.relative_to(FB.REPO)), "chosen": chosen}, indent=1) + "\n")
    print(f"extension manifest: {len(m['arms'])} arms -> {ext_path(ext).relative_to(FB.REPO)}; commit it before the test stage")


def main(argv=None) -> int:
    load_dotenv(find_dotenv(usecwd=True))
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=("tune", "freeze", "test", "latency"))
    ap.add_argument("--systems", default="open,jev,bedrock")
    ap.add_argument("--subset", default="first-benchmark-v1.1")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--extension", type=int, default=1, help="which extension manifest to freeze or run under")
    a = ap.parse_args(argv)
    kinds = set(a.systems.split(","))
    if a.stage == "tune":
        run("tune", a.subset, kinds, "tune")
    elif a.stage == "freeze":
        freeze(a.subset, kinds, a.extension)
    elif a.stage == "test":
        run("test", a.subset, kinds, "test", chosen=chosen_map(a.extension), ext=a.extension)
    else:
        run("latency", a.subset, kinds, "tune", chosen=chosen_map(a.extension), serial=True, limit=a.limit or 50,
            ext=a.extension)
    return 0


if __name__ == "__main__":
    sys.exit(main())
