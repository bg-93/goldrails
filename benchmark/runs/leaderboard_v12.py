"""Leaderboard v1.2: the six-category result with PII on NVIDIA Nemotron-PII. The earlier results are untouched.

    uv run python benchmark/runs/leaderboard_v12.py

Runs the unchanged evaluator under contract v1.1, the primary freeze manifest, extension manifests 1 to 3, approval
4 and the declared implementations. The core ledgers are read without their PII rows (the old AI4Privacy test rows,
kept as they were in leaderboard-provisional.json); PII comes from ``pii-v12-test.jsonl`` under extension manifest 3.
Every other category's rows, thresholds and scores are the same as in leaderboard-provisional.json. Writes
``benchmark/results/first-benchmark/leaderboard-v1.2.json``. No model calls.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RES = REPO / "benchmark" / "results" / "first-benchmark"
SUB = REPO / "benchmark" / "subsets" / "first-benchmark"
OUT = RES / "leaderboard-v1.2.json"


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        args, dropped = [], 0
        for name in ("test", "test-rerun"):
            dst = tmp / f"{name}.jsonl"
            with (RES / f"{name}.jsonl").open(encoding="utf-8") as fin, dst.open("w", encoding="utf-8") as fout:
                for line in fin:
                    if json.loads(line).get("id", "").startswith("f5-"):
                        dropped += 1
                        continue
                    fout.write(line)
            args += [str(dst), str(RES / f"{name}.arms.jsonl")]
        for name in ("ext-test", "pii-v12-test"):
            args += [str(RES / f"{name}.jsonl"), str(RES / f"{name}.arms.jsonl")]
        cmd = [sys.executable, "-m", "goldrails_bench.leaderboard", *args, "--mode", "final",
               "--contract", "benchmark/contracts/v1.1.json", "--freeze-manifest", str(SUB / "freeze-manifest.json"),
               *[x for n in (1, 2, 3) for x in ("--extension-manifest", str(SUB / f"freeze-extension-{n}.json"))],
               "--analysis-approval", str(SUB / "analysis-approval-4.json"),
               "--implementations", str(SUB / "implementations-v1.1.json"),
               "--serving", str(RES / "serving-v12.json"), "--out", str(OUT)]
        r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
        if r.returncode:
            print(r.stdout[-2000:], r.stderr[-2000:])
            return r.returncode
    doc = json.loads(OUT.read_text())
    doc.setdefault("provenance", {})["v1_2"] = {
        "pii_rows_dropped_from_core_ledgers": dropped,
        "pii_ledger": "pii-v12-test.jsonl", "pii_manifest": "freeze-extension-3.json", "dataset": "v1.2 (first-benchmark-v1.2)"}
    OUT.write_text(json.dumps(doc, indent=1) + "\n")
    print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "done", f"({dropped} old PII ledger rows left out)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
