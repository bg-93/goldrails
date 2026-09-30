"""Run the deterministic offline reliability lane.

No API key, cloud account, or Hugging Face dataset is read.  The generated attempts ledger and
summary are deliberately separate from quality ledgers and cannot enter the leaderboard.

    uv run python benchmark/runs/reliability_simulation.py
    uv run python benchmark/runs/reliability_simulation.py --out /tmp/goldrails-reliability
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from goldrails_bench.reliability import run_scenarios

REPO = Path(__file__).resolve().parents[2]
DEFAULT_SCENARIOS = REPO / "benchmark" / "fault_scenarios" / "v1.json"
DEFAULT_OUT = REPO / "benchmark" / "results" / "reliability-simulation"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run Gold Rails' network-free reliability simulation")
    parser.add_argument("--scenarios", type=Path, default=DEFAULT_SCENARIOS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--attempt-cost-usd",
        type=float,
        default=None,
        help="illustrative cost for every simulated attempt; defaults to the scenario file value",
    )
    args = parser.parse_args(argv)
    summary = run_scenarios(args.scenarios, args.out, args.attempt_cost_usd)
    print(json.dumps(summary["totals"], indent=2))
    print(f"wrote {args.out / 'attempts.jsonl'}")
    print(f"wrote {args.out / 'summary.json'}")
    print("offline simulation only: these figures do not describe Jev or another provider")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
