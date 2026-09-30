# Offline reliability simulation

## Purpose and claim boundary

This lane verifies that Gold Rails measures failures consistently before anyone spends money on live provider calls.
It uses no Jev key, AWS credentials, cloud infrastructure, or Hugging Face dataset.

It supports this claim:

> Gold Rails' retry, backoff, attempt, exhaustion, latency-amplification and estimated duplicate-cost accounting has
> been exercised against deterministic failure scenarios.

It does **not** support this claim:

> Jev is more or less reliable than another guardrail.

That second claim needs a later live run in which Jev and each comparator receive the same workload and load profile.
The offline lane makes that later result trustworthy: an eventual success cannot hide earlier failed attempts, and an
outage cannot accidentally become a correct quality decision.

## Run it

```bash
make reliability-sim
```

Or choose a temporary output directory:

```bash
uv run python benchmark/runs/reliability_simulation.py --out /tmp/goldrails-reliability
```

The command makes no network calls. The default output directory is ignored by Git because it is generated evidence.

## Structure

| Component | Location | Responsibility |
|---|---|---|
| Scenario document | `benchmark/fault_scenarios/v1.json` | Human-readable inputs: logical request count, retry policy and scripted outcomes |
| Scripted provider | `benchmark/goldrails_bench/reliability.py` | Implements the same `ask` shape as a provider adapter but returns deterministic outcomes |
| Policy under test | `benchmark/goldrails_bench/policy.py` | The production retry classification, attempt limit and exponential backoff |
| Simulation runner | `benchmark/runs/reliability_simulation.py` | Loads scenarios, runs them without sleeping or using the network, and writes separate evidence |
| Attempt ledger | `benchmark/results/reliability-simulation/attempts.jsonl` | One row per logical request, containing every attempt and virtual backoff delay |
| Summary | `benchmark/results/reliability-simulation/summary.json` | Retry amplification, recovery, exhaustion, latency and estimated duplicate cost by scenario |
| Tests | `benchmark/tests/test_reliability.py` | Proves the simulator, scenario coverage, metric formulas and quality isolation |

The word *virtual* is important. A scripted attempt can declare five seconds of latency without making the test suite
sleep for five seconds. Backoff is recorded by an injected function instead of real sleeping. The report therefore
models the application-visible duration while remaining fast and deterministic.

## Scenario anatomy

One scenario applies the same outcome script to a stated number of independent logical requests:

```json
{
  "name": "throttle-then-recover",
  "requests": 10,
  "retry_policy": {
    "name": "transient-3",
    "max_retries": 3,
    "backoff_s": 2.0
  },
  "outcomes": [
    {"kind": "http_429", "latency_s": 0.05},
    {"kind": "success", "latency_s": 0.2}
  ]
}
```

For each request, the first attempt is rate-limited. Gold Rails classifies that error as transient, waits a virtual two
seconds, and succeeds on the second attempt. Ten logical requests therefore produce twenty provider attempts and a
retry amplification of `20 / 10 = 2.0x`.

The versioned scenario file covers:

- First-attempt success.
- HTTP 429 throttling followed by recovery.
- HTTP 500 and 503 server failures followed by recovery.
- Persistent timeout through the complete retry budget.
- Connection reset followed by recovery.
- A valid but slow response.
- A malformed response which is not retried.

These are fixtures, not provider observations. Their purpose is to expose accounting mistakes with outcomes that are
known in advance.

## Why the error categories differ

`429`, `500`, `503`, timeouts and connection resets are transient: another attempt may succeed. The simulator maps
them to the same error classes recognised by `RetryPolicy`.

A malformed response is different. The provider returned something which the adapter could not turn into a guardrail
decision. Repeating an identical request will often repeat the same schema or validation problem, so it is final by
default. This prevents three unnecessary retries from turning one unusable answer into four potentially billable
unusable answers.

A slow response is successful. Keeping `ok=true` while retaining its five-second duration lets a later report ask two
separate questions:

1. Did the guardrail return a usable decision?
2. Did it return within the application's latency objective?

## Retry and attempt substructures

The simulator calls `ask_with_policy`, the same policy function used by real benchmark execution. Each logical request
contains:

| Field | Meaning |
|---|---|
| `attempts` | Every provider interaction, including its error, usage and latency |
| `attempt_count` | Original attempt plus retries |
| `retry_count` | Attempts after the original |
| `backoff_delays_s` | Individual exponential waits, such as `[2, 4, 8]` |
| `backoff_s` | Sum of all waits |
| `attempt_latency_s` | Sum of provider-attempt durations |
| `end_to_end_latency_s` | Attempt durations plus backoff |
| `recovered` | At least one failure occurred before final success |
| `exhausted` | The frozen policy ended without a usable result |

With three retries, a persistent failure produces four attempts. At a two-second base backoff, the waits are two,
four and eight seconds. Four simulated one-second timeouts therefore become eighteen seconds end to end:

```text
4 seconds attempting + 14 seconds backing off = 18 seconds
```

## Summary metrics

### Initial requests

Logical application requests, before retries. This is the correct business denominator.

### Total attempts

All simulated provider calls. The difference from initial requests is retry traffic.

### Retry amplification

```text
total attempts / initial requests
```

This translates reliability into capacity and rate-limit pressure. A value of `1.08x` means eight percent more calls
than the application requested.

### Recovered requests

Requests that failed at least once and ultimately succeeded. This is the benefit obtained from retrying.

### Exhausted requests

Requests that never returned a usable guardrail decision. A production design must choose what happens next: fail
closed, fail open, fall back to another guardrail, or enter a restricted mode.

### End-to-end latency

Provider attempts plus backoff. This is closer to what a user waits for than the final successful attempt alone.

### Estimated duplicate cost

```text
(total attempts - initial requests) * illustrative cost per attempt
```

The default `$0.001` is intentionally illustrative. The ledger states the assumption that every attempt is billable.
A live provider report must replace it with metered usage and invoice evidence.

## Separation from quality scoring

Reliability records contain:

```json
{
  "record_type": "reliability_simulation",
  "quality_scored": false
}
```

They contain no dataset label or `expected` outcome. They are written outside the normal quality ledgers, and the
summary module rejects any other record type. This prevents fake infrastructure failures from changing Jev's or a
comparator's quality score.

The existing quality policy still handles real failed evaluations conservatively: an exhausted live request earns no
quality credit. Existing policy tests also prove that completed failures remain final when a ledger is resumed, so a
later rerun cannot selectively erase an inconvenient failure.

## How this advances the Jev replacement question

Replacing a managed guardrail requires evidence across several independent dimensions:

| Decision dimension | What answers it | Does this lane answer it now? |
|---|---|---|
| Safety quality | Frozen labelled benchmark | No |
| Normal latency | Matched live provider calls | No |
| Direct and total cost | Metering, invoices and operational inputs | No |
| Failure-accounting correctness | Deterministic offline reliability simulation | **Yes** |
| Actual provider reliability | Matched live soak, throttle and incident testing | No |
| Failure-mode suitability | Live results plus a fail-open/fail-closed/fallback policy | Partly; it supplies the metrics |

The contribution is therefore measurement infrastructure, not evidence that Jev is reliable. When keys are available,
the fake provider can be replaced by Jev and Bedrock adapters while retaining the same concepts: attempts, recovery,
exhaustion, backoff, end-to-end latency and cost per successful protected request.

That later comparison can answer questions such as:

- Does Jev throttle more often at the intended production rate?
- Do its transient failures recover within the latency objective?
- Does retry amplification erase its direct API-cost advantage?
- How often does the application receive no usable guardrail decision?
- Is a fallback provider necessary, and what does that do to total cost?

## Extending the lane safely

Add new deterministic infrastructure cases to `benchmark/fault_scenarios/v1.json`, or create a version 2 file if a
scenario's meaning changes. Do not add these cases to the Hugging Face quality dataset: HTTP failures and retry
behaviour are properties of execution, not labelled safety examples.

Do not feed generated simulation ledgers into `leaderboard.py`. A future live reliability command should also write a
separate ledger and report so reliability remains visible beside quality rather than being silently mixed into it.
