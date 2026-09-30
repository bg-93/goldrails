"""The offline reliability lane: scripted faults, accounting, output, and quality isolation."""
import json
from pathlib import Path

import pytest

from goldrails_bench.reliability import (
    ScriptedOutcome,
    ScriptedProvider,
    load_scenarios,
    run_scenarios,
    simulate_scenario,
    summarise,
)

REPO = Path(__file__).resolve().parents[2]
SCENARIOS = REPO / "benchmark" / "fault_scenarios" / "v1.json"


def scenario(name, outcomes, requests=1, retries=3, backoff=2.0):
    return {
        "name": name,
        "description": "test fixture",
        "requests": requests,
        "retry_policy": {"name": "test", "max_retries": retries, "backoff_s": backoff},
        "outcomes": [{"kind": kind, "latency_s": latency} for kind, latency in outcomes],
    }


@pytest.mark.parametrize("kind", ["http_429", "http_500", "http_503", "timeout", "connection_reset"])
def test_transient_faults_retry_and_recover(kind):
    record, = simulate_scenario(scenario(kind, [(kind, 0.1), ("success", 0.2)]))
    assert record["ok"] and record["recovered"] and not record["exhausted"]
    assert record["attempt_count"] == 2 and record["retry_count"] == 1
    assert [a["ok"] for a in record["attempts"]] == [False, True]


def test_malformed_response_is_not_retried():
    record, = simulate_scenario(scenario("bad-shape", [("malformed_response", 0.1), ("success", 0.2)]))
    assert not record["ok"] and record["exhausted"] and record["attempt_count"] == 1
    assert record["attempts"][0]["error"].startswith("MalformedResponseError")


def test_backoff_attempts_latency_and_duplicate_cost_are_all_visible():
    record, = simulate_scenario(
        scenario("two-failures", [("http_429", 0.05), ("http_503", 0.05), ("success", 0.2)]),
        attempt_cost_usd=0.01,
    )
    assert record["backoff_delays_s"] == [2.0, 4.0]
    assert record["attempt_count"] == 3 and len(record["attempts"]) == 3
    assert record["attempt_latency_s"] == pytest.approx(0.3)
    assert record["end_to_end_latency_s"] == pytest.approx(6.3)
    assert record["estimated_attempt_cost_usd"] == pytest.approx(0.03)
    assert record["estimated_duplicate_cost_usd"] == pytest.approx(0.02)


def test_retry_budget_is_bounded_and_exhaustion_is_reported():
    record, = simulate_scenario(scenario("persistent", [("timeout", 1.0)], retries=3))
    assert not record["ok"] and record["exhausted"]
    assert record["attempt_count"] == 4 and record["retry_count"] == 3
    assert record["backoff_delays_s"] == [2.0, 4.0, 8.0]
    assert record["end_to_end_latency_s"] == 18.0


def test_slow_success_is_successful_but_remains_slow():
    record, = simulate_scenario(scenario("slow", [("slow_success", 5.0)]))
    assert record["ok"] and not record["recovered"] and not record["exhausted"]
    assert record["end_to_end_latency_s"] == 5.0


def test_summary_uses_logical_requests_as_the_denominator_and_is_not_quality_scored():
    records = simulate_scenario(
        scenario("recover", [("http_429", 0.1), ("success", 0.2)], requests=4),
        attempt_cost_usd=0.01,
    )
    summary = summarise(records)
    line, = summary["scenarios"]
    assert line["initial_requests"] == 4 and line["total_attempts"] == 8
    assert line["retry_amplification"] == 2.0 and line["recovered_requests"] == 4
    assert line["estimated_duplicate_cost_usd"] == pytest.approx(0.04)
    assert summary["quality_scored"] is False
    assert all(r["quality_scored"] is False and "expected" not in r for r in records)


def test_versioned_scenarios_cover_every_documented_outcome():
    doc = load_scenarios(SCENARIOS)
    kinds = {outcome["kind"] for item in doc["scenarios"] for outcome in item["outcomes"]}
    assert kinds == {
        "success", "http_429", "http_500", "http_503", "timeout", "connection_reset",
        "slow_success", "malformed_response",
    }


def test_runner_writes_a_separate_attempt_ledger_and_summary(tmp_path):
    summary = run_scenarios(SCENARIOS, tmp_path)
    attempts_path, summary_path = tmp_path / "attempts.jsonl", tmp_path / "summary.json"
    records = [json.loads(line) for line in attempts_path.read_text().splitlines()]
    saved = json.loads(summary_path.read_text())
    assert len(records) == 70 and saved == summary
    assert saved["report_type"] == "offline_reliability_simulation"
    assert saved["totals"]["initial_requests"] == 70


def test_scenario_validation_rejects_unknown_faults_and_empty_scripts(tmp_path):
    with pytest.raises(ValueError, match="unknown scripted outcome"):
        ScriptedOutcome.from_dict({"kind": "mystery"})
    with pytest.raises(ValueError, match="at least one outcome"):
        ScriptedProvider([])
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema_version": 2, "scenarios": []}))
    with pytest.raises(ValueError, match="schema_version"):
        load_scenarios(bad)
