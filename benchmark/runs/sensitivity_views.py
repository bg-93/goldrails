"""Post-hoc sensitivity views after the data-quality review of 24 September 2026. Never replaces a primary score.

    uv run python benchmark/runs/sensitivity_views.py

Follows ``benchmark/subsets/first-benchmark/sensitivity-rules-2026-09-24.json``, committed before any view was
computed. Each view runs the unchanged evaluator, with the frozen thresholds, manifests, approval, contract and
bootstrap of ``leaderboard-provisional.json``, on copies of the test ledgers with the listed rows removed for every
system. Nothing is re-run and no threshold is refitted, so no view undoes tuning exposure. Also writes two breakdowns
from the same ledgers: content recall per mapped category and prompt-attack recall per source. Writes
``benchmark/results/first-benchmark/sensitivity-2026-09-24.json``. No model calls.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RES = REPO / "benchmark" / "results" / "first-benchmark"
SUB = REPO / "benchmark" / "subsets" / "first-benchmark"
RULES = SUB / "sensitivity-rules-2026-09-24.json"
AUDIT = REPO / "dataset" / "frozen" / "reviews" / "ai-pii-negatives-2026-09-24" / "disputed.json"
LEDGERS = ("test", "test-rerun", "ext-test")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from site_results import IMPL, OVERALL_ID  # noqa: E402

from goldrails_bench.score import score_of  # noqa: E402


def release_rows() -> dict:
    sub = json.loads((REPO / "benchmark/subsets/first-benchmark-v1.1-ai/manifest.json").read_text())
    want = {r["id"]: r["split"] for r in sub["rows"]}
    rows = {}
    for p in (REPO / "dataset/release" / sub["release"] / "build").glob("*.jsonl"):
        for line in p.open(encoding="utf-8"):
            r = json.loads(line)
            if r["id"] in want:
                rows[r["id"]] = {**r, "selected_split": want[r["id"]]}
    if not rows:
        raise SystemExit("release build missing; run uv run python -m goldrails_dataset.release --version v1.1-ai")
    return rows


def stem(source_id: str) -> str:
    m = re.match(r"(\d+)[A-Z]*$", str(source_id))
    return m.group(1) if m else str(source_id)


def drops(rows: dict) -> dict:
    pii = [r for r in rows.values() if r["feature"] == "F5" and r["provenance"]["source"] == "ai4privacy"]
    tune_stems = {stem(r["provenance"]["source_id"]) for r in pii if r["selected_split"] == "tune"}
    docs = sorted(r["id"] for r in pii if r["selected_split"] == "test" and stem(r["provenance"]["source_id"]) in tune_stems)
    disputed = json.loads(AUDIT.read_text())["confirmed_present"] if AUDIT.exists() else None
    neg = sorted(i for i in (disputed or []) if i in rows and rows[i]["selected_split"] == "test" and rows[i]["expected"] == "no")
    content = sorted(r["id"] for r in rows.values() if r["feature"] == "F1" and r["selected_split"] == "test"
                     and r["expected"] == "yes" and (r.get("category") or {}).get("bedrock") in ("PII", "TOPIC"))
    gandalf = sorted(r["id"] for r in rows.values() if r["selected_split"] == "test" and r["provenance"]["source"] == "gandalf")
    out = {"pii-independent-documents": docs, "content-five-categories": content, "attacks-without-gandalf": gandalf}
    if disputed is not None:
        out["pii-disputed-negatives"] = neg
        out["pii-both"] = sorted(set(docs) | set(neg))
    return out


def evaluate(drop: set, tmp: Path) -> dict:
    args = []
    for name in LEDGERS:
        src = RES / f"{name}.jsonl"
        dst = tmp / f"{name}.jsonl"
        with src.open(encoding="utf-8") as fin, dst.open("w", encoding="utf-8") as fout:
            for line in fin:
                if json.loads(line).get("id") not in drop:
                    fout.write(line)
        (tmp / f"{name}.arms.jsonl").write_bytes((RES / f"{name}.arms.jsonl").read_bytes())
        args += [str(dst), str(tmp / f"{name}.arms.jsonl")]
    out = tmp / "lb.json"
    cmd = [sys.executable, "-m", "goldrails_bench.leaderboard", *args, "--mode", "final",
           "--contract", "benchmark/contracts/v1.1.json", "--freeze-manifest", str(SUB / "freeze-manifest.json"),
           "--extension-manifest", str(SUB / "freeze-extension-1.json"), "--extension-manifest", str(SUB / "freeze-extension-2.json"),
           "--analysis-approval", str(SUB / "analysis-approval-4.json"), "--implementations", str(SUB / "implementations-v1.1.json"),
           "--serving", str(RES / "serving-final.json"), "--out", str(out)]
    subprocess.run(cmd, cwd=REPO, check=True, capture_output=True)
    return json.loads(out.read_text())


def page_id(system: str) -> str:
    return OVERALL_ID.get(system) or IMPL[system][0]


def summarise(lb: dict, suite: str) -> dict:
    per = {}
    for a in lb["arms"]:
        if a["suite"] == suite:
            ci = a["suite_score"].get("ci") or {}
            per[page_id(a["system"])] = {"score": round(a["suite_score"]["value"], 2), "ci": [ci.get("low"), ci.get("high")],
                                         "rows": a["sample_sizes"]["report_rows"]}
    overall = {page_id(i["implementation"]): {"score": round(i["overall_score"], 2),
                                               "ci": [i["ci"]["low"], i["ci"]["high"]] if i.get("ci") else None}
               for i in lb["overall"]["implementations"] if i.get("ranked")}
    return {"suite": per, "overall": overall}


def breakdowns(rows: dict, lb: dict) -> dict:
    arms = {(a["system"], a["question_set"], a["config_hash"]): a for a in lb["arms"]}
    contract = json.loads((REPO / "benchmark/contracts/v1.1.json").read_text())
    tag_to_subtask = {(suite, tag): name for suite, d in contract["suites"].items()
                      for name, st in d.get("subtasks", {}).items() for tag in st.get("tags", [])}   # ledger tag -> arm subtask
    frozen = {arm["config_hash"]: {k: {"threshold": float(v["threshold"])} for k, v in (arm["thresholds"] or {}).items()
                                   if (v or {}).get("threshold") is not None}
              for m in ("freeze-manifest.json", "freeze-extension-1.json", "freeze-extension-2.json")
              for arm in json.loads((SUB / m).read_text())["arms"]}
    latest = {}
    for name in ("test", "test-rerun"):
        for line in (RES / f"{name}.jsonl").open(encoding="utf-8"):
            r = json.loads(line)
            key = (r["system"], r["question_set"], r["config_hash"], r["id"], r.get("subtask"))
            if key not in latest or r.get("ok"):
                latest[key] = r
    out = {"content_recall_by_category": defaultdict(lambda: defaultdict(lambda: [0, 0])),
           "attack_recall_by_source": defaultdict(lambda: defaultdict(lambda: [0, 0]))}
    for (system, qs, ch, rid, sub), r in latest.items():
        a = arms.get((system, qs, ch))
        row = rows.get(rid)
        if a is None or row is None or row["selected_split"] != "test" or row["expected"] != "yes":
            continue
        # full-precision frozen threshold (the leaderboard rounds for display; the evaluator applies the frozen value)
        th = (frozen.get(ch, {}).get(tag_to_subtask.get((a["suite"], sub), sub)) or {}).get("threshold")
        if th is None:
            continue
        hit = bool(r.get("ok") and r.get("answers") and score_of(r) >= th)
        if a["suite"] == "content":
            cell = out["content_recall_by_category"][(row.get("category") or {}).get("bedrock", "unknown")][page_id(system)]
        elif a["suite"] == "prompt_attacks":
            cell = out["attack_recall_by_source"][row["provenance"]["source"]][page_id(system)]
        else:
            continue
        cell[0] += hit
        cell[1] += 1
    return {k: {c: {s: {"caught": v[0], "of": v[1]} for s, v in sorted(d.items())} for c, d in sorted(t.items())}
            for k, t in out.items()}


def main() -> int:
    rules = json.loads(RULES.read_text())
    rows = release_rows()
    base = json.loads((RES / "leaderboard-provisional.json").read_text())
    views = {}
    with tempfile.TemporaryDirectory() as td:
        for name, ids in drops(rows).items():
            suite = rules["views"][name]["suite"]
            lb = evaluate(set(ids), Path(td))
            views[name] = {"rule": rules["views"][name], "dropped": ids, "n_dropped": len(ids), **summarise(lb, suite),
                           "primary": summarise(base, suite)}
    doc = {"status": rules["status"], "rules": str(RULES.relative_to(REPO)),
           "pii_audit": str(AUDIT.relative_to(REPO)) if AUDIT.exists() else "not yet available",
           "views": views, "breakdowns": breakdowns(rows, base)}
    (RES / "sensitivity-2026-09-24.json").write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    for name, v in views.items():
        j, b = v["suite"].get("jev"), v["suite"].get("bedrock")
        pj, pb = v["primary"]["suite"].get("jev"), v["primary"]["suite"].get("bedrock")
        print(f"{name}: dropped {v['n_dropped']}; Jev {pj['score']} -> {j['score']}, Bedrock {pb['score']} -> {b['score']}; "
              f"overall Jev {v['primary']['overall']['jev']['score']} -> {v['overall']['jev']['score']}, "
              f"Bedrock {v['primary']['overall']['bedrock']['score']} -> {v['overall']['bedrock']['score']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
