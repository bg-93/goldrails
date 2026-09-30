"""Deterministic, offline reliability simulations for the Gold Rails harness.

This module deliberately does not import datasets, scoring, or leaderboard code.  It tests the
measurement machinery around a guardrail: retry classification, backoff, attempt accounting,
exhaustion, latency amplification, and estimated duplicate cost.  It does *not* measure the
reliability of Jev, Bedrock, or any other real provider.

The simulator reuses :func:`goldrails_bench.policy.ask_with_policy`, so a scenario exercises the
same retry implementation used by real benchmark adapters without making network calls.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .policy import RetryPolicy, ask_with_policy, exhausted
from .systemone import SystemOneCall


FAULTS = {
    "success": None,
    "http_429": "RateLimitError: simulated HTTP 429",
    "http_500": "InternalServerError: simulated HTTP 500",
    "http_503": "ServiceUnavailableError: simulated HTTP 503",
    "timeout": "APITimeoutError: simulated request timeout",
    "connection_reset": "APIConnectionError: simulated connection reset",
    # A response which cannot be interpreted is an adapter failure, not a transient transport
    # failure. Retrying the same payload would normally add cost without changing the response.
    "malformed_response": "MalformedResponseError: simulated response has no usable decision",
}
VALID_OUTCOMES = {*FAULTS, "slow_success"}


@dataclass(frozen=True)
class ScriptedOutcome:
    """One deterministic result returned by :class:`ScriptedProvider`."""

    kind: str
    latency_s: float = 0.01
    input_tokens: int = 10

    @classmethod
    def from_dict(cls, value: dict) -> "ScriptedOutcome":
        kind = value.get("kind")
        if kind not in VALID_OUTCOMES:
            raise ValueError(f"unknown scripted outcome {kind!r}; expected one of {sorted(VALID_OUTCOMES)}")
        latency = float(value.get("latency_s", 2.0 if kind == "slow_success" else 0.01))
        tokens = int(value.get("input_tokens", 10))
        if latency < 0 or tokens < 0:
            raise ValueError("latency_s and input_tokens must be non-negative")
        return cls(kind=kind, latency_s=latency, input_tokens=tokens)


class ScriptedProvider:
    """A network-free provider adapter which returns a fixed sequence of outcomes.

    It has the same ``ask(state, questions)`` shape as the real adapters.  The provider does not
    sleep: ``latency_s`` is simulated data, keeping the test suite fast and deterministic.
    """

    adapter = {"name": "offline-scripted-provider", "version": "1"}

    def __init__(self, outcomes: list[ScriptedOutcome], system: str = "offline-simulator"):
        if not outcomes:
            raise ValueError("a scripted provider needs at least one outcome")
        self.system = system
        self.model = "deterministic-script-v1"
        self.identity = {"offline": True, "script": [o.kind for o in outcomes]}
        self._outcomes = list(outcomes)
        self.calls = 0

    def ask(self, state: Any, questions: dict) -> SystemOneCall:
        index = min(self.calls, len(self._outcomes) - 1)
        outcome = self._outcomes[index]
        self.calls += 1
        success = outcome.kind in {"success", "slow_success"}
        answers = {key: {"type": "noul", "noul": 0.8} for key in questions} if success else None
        raw = {"simulated": True, "outcome": outcome.kind}
        return SystemOneCall(
            system=self.system,
            ok=success,
            model=self.model,
            answers=answers,
            usage={"input_tokens": outcome.input_tokens},
            latency_s=outcome.latency_s,
            error=None if success else FAULTS[outcome.kind],
            raw=raw,
        )


def _policy(value: dict) -> RetryPolicy:
    return RetryPolicy(
        max_retries=int(value.get("max_retries", 3)),
        backoff_s=float(value.get("backoff_s", 2.0)),
        name=value.get("name", "offline-transient-3"),
    )


def load_scenarios(path: str | Path) -> dict:
    """Load and validate the small, dataset-independent scenario document."""
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema_version") != 1:
        raise ValueError("reliability scenario schema_version must be 1")
    if not isinstance(doc.get("scenarios"), list) or not doc["scenarios"]:
        raise ValueError("reliability scenario document needs a non-empty scenarios list")
    names = set()
    for scenario in doc["scenarios"]:
        name = scenario.get("name")
        if not name or name in names:
            raise ValueError(f"scenario names must be non-empty and unique; got {name!r}")
        names.add(name)
        if int(scenario.get("requests", 0)) <= 0:
            raise ValueError(f"scenario {name!r} needs requests > 0")
        if not scenario.get("outcomes"):
            raise ValueError(f"scenario {name!r} needs at least one outcome")
        for outcome in scenario["outcomes"]:
            ScriptedOutcome.from_dict(outcome)
        _policy(scenario.get("retry_policy", {}))
    return doc


def simulate_scenario(scenario: dict, attempt_cost_usd: float = 0.0) -> list[dict]:
    """Run one scenario and return one reliability record per logical request.

    Backoff uses a recording function instead of real sleep.  The resulting end-to-end latency is
    therefore the virtual sum of attempt latency plus policy backoff, while the simulation itself
    completes immediately.
    """
    if attempt_cost_usd < 0:
        raise ValueError("attempt_cost_usd must be non-negative")
    outcomes = [ScriptedOutcome.from_dict(v) for v in scenario["outcomes"]]
    policy = _policy(scenario.get("retry_policy", {}))
    records = []
    questions = {"decision": {"type": "noul", "instructions": "offline reliability fixture"}}
    for number in range(1, int(scenario["requests"]) + 1):
        provider = ScriptedProvider(outcomes, system=f"offline:{scenario['name']}")
        waits: list[float] = []
        final, attempts = ask_with_policy(
            provider,
            {"role": "user", "text": "fixed offline reliability payload"},
            questions,
            policy=policy,
            sleep=waits.append,
        )
        attempt_latency = sum(float(a.get("latency_s") or 0.0) for a in attempts)
        total_backoff = sum(waits)
        records.append({
            "record_type": "reliability_simulation",
            "schema_version": 1,
            "scenario": scenario["name"],
            "description": scenario.get("description"),
            "request_id": f"{scenario['name']}:{number:06d}",
            "ok": bool(final.ok),
            "recovered": bool(final.ok and len(attempts) > 1),
            "exhausted": exhausted(attempts),
            "attempt_count": len(attempts),
            "retry_count": len(attempts) - 1,
            "attempts": attempts,
            "backoff_delays_s": waits,
            "backoff_s": round(total_backoff, 6),
            "attempt_latency_s": round(attempt_latency, 6),
            "end_to_end_latency_s": round(attempt_latency + total_backoff, 6),
            "estimated_attempt_cost_usd": round(len(attempts) * attempt_cost_usd, 12),
            "estimated_duplicate_cost_usd": round(max(0, len(attempts) - 1) * attempt_cost_usd, 12),
            "cost_assumption": "every simulated attempt is billable; replace with invoice evidence for live providers",
            "retry_policy": policy.identity(),
            "quality_scored": False,
        })
    return records


def _percentile(values: list[float], q: float) -> float | None:
    """Nearest-rank percentile, suitable for the small transparent simulation report."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(q * len(ordered)) - 1)]


def summarise(records: list[dict]) -> dict:
    """Aggregate reliability records without importing or invoking quality scoring."""
    if not records:
        raise ValueError("cannot summarise an empty reliability ledger")
    by_scenario: dict[str, list[dict]] = {}
    for record in records:
        if record.get("record_type") != "reliability_simulation":
            raise ValueError("reliability summary accepts reliability_simulation records only")
        by_scenario.setdefault(record["scenario"], []).append(record)

    def one(name: str, rows: list[dict]) -> dict:
        attempts = sum(r["attempt_count"] for r in rows)
        latencies = [r["end_to_end_latency_s"] for r in rows]
        initial = len(rows)
        return {
            "scenario": name,
            "initial_requests": initial,
            "total_attempts": attempts,
            "retry_amplification": round(attempts / initial, 6),
            "recovered_requests": sum(bool(r["recovered"]) for r in rows),
            "exhausted_requests": sum(bool(r["exhausted"]) for r in rows),
            "success_rate": round(sum(bool(r["ok"]) for r in rows) / initial, 6),
            "total_backoff_s": round(sum(r["backoff_s"] for r in rows), 6),
            "mean_end_to_end_latency_s": round(sum(latencies) / initial, 6),
            "p95_end_to_end_latency_s": round(_percentile(latencies, 0.95), 6),
            "estimated_duplicate_cost_usd": round(sum(r["estimated_duplicate_cost_usd"] for r in rows), 12),
        }

    scenarios = [one(name, rows) for name, rows in sorted(by_scenario.items())]
    total_initial = sum(x["initial_requests"] for x in scenarios)
    total_attempts = sum(x["total_attempts"] for x in scenarios)
    return {
        "report_type": "offline_reliability_simulation",
        "schema_version": 1,
        "quality_scored": False,
        "interpretation": (
            "Validates Gold Rails failure accounting; it does not measure the reliability of Jev or another provider."
        ),
        "totals": {
            "initial_requests": total_initial,
            "total_attempts": total_attempts,
            "retry_amplification": round(total_attempts / total_initial, 6),
            "recovered_requests": sum(x["recovered_requests"] for x in scenarios),
            "exhausted_requests": sum(x["exhausted_requests"] for x in scenarios),
            "total_backoff_s": round(sum(x["total_backoff_s"] for x in scenarios), 6),
            "estimated_duplicate_cost_usd": round(sum(x["estimated_duplicate_cost_usd"] for x in scenarios), 12),
        },
        "scenarios": scenarios,
    }


def run_scenarios(path: str | Path, out_dir: str | Path, attempt_cost_usd: float | None = None) -> dict:
    """Execute a scenario file and write a separate ledger plus summary report."""
    doc = load_scenarios(path)
    cost = float(doc.get("estimated_cost_per_attempt_usd", 0.0) if attempt_cost_usd is None else attempt_cost_usd)
    records = [record for scenario in doc["scenarios"] for record in simulate_scenario(scenario, cost)]
    summary = summarise(records)
    summary["scenario_source"] = str(path)
    summary["estimated_cost_per_attempt_usd"] = cost
    destination = Path(out_dir)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "attempts.jsonl").write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records), encoding="utf-8"
    )
    (destination / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary
