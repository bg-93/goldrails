"""Leaderboard v1.3: profanity is "Profanity or obscenity — Civil Comments"; everything else as in v1.2.

    uv run python benchmark/runs/leaderboard_v13.py
    uv run python benchmark/runs/leaderboard_v13.py --ledgers <ledger> <arms> ... --out <file> --note "<what changed>"
    uv run python benchmark/runs/leaderboard_v13.py --final     # signed contract v1.1 and approval 5: leaderboard-final.json

Runs the unchanged evaluator under contract v1.1, the primary freeze manifest, extension manifests 1 to 4, approval 4
and implementations-v1.3 (the profanity subtask answers v1-f4-obscenity). By default it reads the core ledgers
without their PII rows (AI4Privacy; v1.2 replaced them), the extension ledger without the lexicon-selected profanity
rows (kept as their own challenge set in the v1.2 analysis), the Nemotron PII ledger and the Civil Comments profanity
ledger. Category weights are unchanged. Writes ``leaderboard-v1.3.json``. No model calls.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RES = REPO / "benchmark" / "results" / "first-benchmark"
SUB = REPO / "benchmark" / "subsets" / "first-benchmark"


def default_ledgers(tmp: Path) -> tuple[list, dict]:
    args, dropped = [], {"old PII rows": 0, "lexicon-selected profanity rows": 0}
    drops = {"test": lambda r: r.get("id", "").startswith("f5-"), "test-rerun": lambda r: r.get("id", "").startswith("f5-"),
             "ext-test": lambda r: r.get("id", "").startswith("f4-civil_comments_profanity-")}
    for name, drop in drops.items():
        dst = tmp / f"{name}.jsonl"
        with (RES / f"{name}.jsonl").open(encoding="utf-8") as fin, dst.open("w", encoding="utf-8") as fout:
            for line in fin:
                if drop(json.loads(line)):
                    dropped["old PII rows" if name != "ext-test" else "lexicon-selected profanity rows"] += 1
                    continue
                fout.write(line)
        args += [str(dst), str(RES / f"{name}.arms.jsonl")]
    for name in ("pii-v12-test", "prof-v13-test"):
        args += [str(RES / f"{name}.jsonl"), str(RES / f"{name}.arms.jsonl")]
    return args, dropped


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledgers", nargs="*")
    ap.add_argument("--out", default=str(RES / "leaderboard-v1.3.json"))
    ap.add_argument("--note")
    ap.add_argument("--final", action="store_true",
                    help="signed contract v1.1 and the approval-5 records (one per freeze manifest); default out "
                         "leaderboard-final.json. Without it, the draft contract and approval 4, as first built")
    a = ap.parse_args()
    if a.final and a.out == str(RES / "leaderboard-v1.3.json"):
        a.out = str(RES / "leaderboard-final.json")
    contract = "benchmark/contracts/v1.1-signed.json" if a.final else "benchmark/contracts/v1.1.json"
    approvals = (sorted(SUB.glob("analysis-approval-5*.json")) if a.final else [SUB / "analysis-approval-4.json"])
    with tempfile.TemporaryDirectory() as td:
        args, dropped = (a.ledgers, {}) if a.ledgers else default_ledgers(Path(td))
        cmd = [sys.executable, "-m", "goldrails_bench.leaderboard", *args, "--mode", "final",
               "--contract", contract, "--freeze-manifest", str(SUB / "freeze-manifest.json"),
               *[x for n in (1, 2, 3, 4) for x in ("--extension-manifest", str(SUB / f"freeze-extension-{n}.json"))],
               *[x for p in approvals for x in ("--analysis-approval", str(p))],
               "--implementations", str(SUB / "implementations-v1.3.json"),
               "--serving", str(RES / "serving-v13.json"), "--out", a.out]
        r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
        if r.returncode:
            print(r.stdout[-2000:], r.stderr[-2000:])
            return r.returncode
    doc = json.loads(Path(a.out).read_text())
    doc.setdefault("provenance", {})["v1_3"] = {
        "analysis": "v1.3: profanity subtask is 'Profanity or obscenity — Civil Comments' (original obscene rater "
                    "fractions, >= 0.5 yes, 0 no); PII on Nemotron-PII (v1.2); category weights unchanged",
        "rows_left_out": dropped, "note": a.note}
    Path(a.out).write_text(json.dumps(doc, indent=1) + "\n")
    print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "done", dropped)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
