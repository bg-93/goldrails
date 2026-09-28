"""Masked-spelling diagnostic for the profanity subtask. Never part of any score.

    uv run python benchmark/runs/profanity_diagnostic.py

Reads the ``profanity_obfuscated`` rows from ``ext-test.jsonl`` (spellings such as f*ck or sh!t, labelled by the same
review as the profanity subtask: single-AI reference labels in the provisional v1.1-ai subset) and reports, per system, how often each is flagged at that system's frozen
profanity threshold: detection on rows reviewers marked present, false flags on rows marked absent. The main profanity
result is an exact-word capability test; this file keeps evasion-style spellings visible without folding them in.
Writes ``benchmark/results/first-benchmark/profanity-obfuscation.json``.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from goldrails_bench.score import score_of

REPO = Path(__file__).resolve().parents[2]
RES = REPO / "benchmark" / "results" / "first-benchmark"
EXTS = sorted((REPO / "benchmark" / "subsets" / "first-benchmark").glob("freeze-extension-*.json"))


def main() -> int:
    ledger = RES / "ext-test.jsonl"
    if not ledger.exists() or not EXTS:
        print("no extension test ledger yet")
        return 0
    arms = {(a["system"], a["question_set"], a["config_hash"]): a for p in EXTS for a in json.loads(p.read_text())["arms"]
            if a["suite"] == "word_filters"}
    tally = defaultdict(lambda: {"present": 0, "detected": 0, "absent": 0, "false_flags": 0, "failed": 0})
    for line in ledger.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r.get("subtask") != "profanity_obfuscated":
            continue
        arm = arms.get((r["system"], r["question_set"], r["config_hash"]))
        if arm is None:
            continue
        th = float(arm["thresholds"]["profanity"]["threshold"])   # stored at full precision, possibly as a string
        t = tally[r["system"]]
        if not r.get("ok") or not r.get("answers"):
            t["failed"] += 1
            continue
        flagged = score_of(r) >= th
        if r["expected"] == "yes":
            t["present"] += 1; t["detected"] += flagged
        elif r["expected"] == "no":
            t["absent"] += 1; t["false_flags"] += flagged
    subset = json.loads(EXTS[0].read_text())["extends"].get("subset") or "first-benchmark"
    man = json.loads((REPO / "benchmark" / "subsets" / subset / "manifest.json").read_text())
    basis = ("single-AI reference labels (provisional)" if man.get("provisional_ai_reference") else "human-reviewed labels")
    out = {"kind": "diagnostic, not scored", "rows": f"profanity_obfuscated (masked spellings), {basis}, subset {subset}",
           "threshold": "each system's frozen profanity threshold (" + ", ".join(p.name for p in EXTS) + ")",
           "systems": {s: {**t, "detection_rate": t["detected"] / t["present"] if t["present"] else None,
                           "false_flag_rate": t["false_flags"] / t["absent"] if t["absent"] else None}
                       for s, t in sorted(tally.items())}}
    (RES / "profanity-obfuscation.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out["systems"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
