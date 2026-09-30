# 26. Frozen wording, ordering and representation robustness diagnostics

These diagnostics test whether an otherwise fixed implementation changes its decision when semantically equivalent
wording, ordering or representation changes. They are deliberately separate from the six-suite headline score.
They do not edit the canonical Hugging Face dataset and they never select a preferred wording from test results.

## Separation contract

- Canonical dataset rows and hashes are unchanged. A normal `Record` omits the optional `robustness` field when
  serialised, so historical dataset hashes remain stable.
- Input variants are a derived diagnostic dataset with their own SHA-256 manifest, IDs and provenance.
- Question and adapter variants carry an exact specification hash in the question set and therefore in the runner's
  `config_hash`. An order-only change cannot resume from or pool with a canonical arm.
- Ledger records and arm sidecars carry `diagnostic_only: true`, the base row/question set, variant ID, transformation
  version, specification hash and semantic-equivalence status.
- The robustness report is written under its own output directory. Nothing in `leaderboard.py` imports it, and its
  result explicitly states `headline_scores_affected: false`.

## Frozen specification

`benchmark/robustness/v1/variants.json` defines two layers:

1. **Question/adapter variants:** reversed true/false criteria, reversed question order, a separate PII entity-order
   view, a data-boundary paraphrase, JSON field renaming and context flattening.
2. **Input variants:** Unicode NFD/NFKC forms, punctuation wrapping, plausible irrelevant context and common
   US/Commonwealth spelling substitutions.

Every entry is one of:

- `mechanical`: exact values are retained or the transformation has canonical equivalence; eligible for aggregate
  robustness reporting.
- `reviewed`: a person has confirmed label and policy equivalence; eligible for the aggregate.
- `requires_review`: shown as a provisional per-variant diagnostic and excluded from mean/worst aggregate claims.

Changing a review status changes the specification hash. Commit that change before a test run and list its exact
arms and derived dataset SHA in a robustness extension freeze manifest. Do not promote a variant because its result
looks favourable.

## Generate derived inputs

The source may be any canonical Gold Rails JSONL. The output belongs in a separate working directory or a separate
Hugging Face configuration such as `robustness-v1`; never mix it into `data/{feature}/test.jsonl`.

```bash
uv run python -m goldrails_bench.robustness materialize-inputs \
  --input dataset/path/to/canonical.jsonl \
  --spec benchmark/robustness/v1/variants.json \
  --out benchmark/robustness/generated/inputs.jsonl \
  --manifest benchmark/robustness/generated/inputs.manifest.json
```

Rows on which a transformation is a no-op are omitted and counted as `skipped_no_change`; this prevents identical
copies from inflating stability. Span offsets are remapped for Unicode canonicalization and punctuation wrapping.
Free-form spelling replacement skips span-labelled records because those need task-specific review.

Load the generated rows with `goldrails_bench.robustness.load_materialized_inputs(jsonl, manifest)`. This validates
the derived SHA and attaches the separate dataset identity used by the normal freeze and runner path.

If the derived data is published to Hugging Face, publish it as a diagnostic configuration with its generated
manifest. The canonical Gold Rails configuration remains immutable.

## Generate exact question sets

```bash
uv run python -m goldrails_bench.robustness write-question-sets \
  --base-version v1 \
  --spec benchmark/robustness/v1/variants.json \
  --out benchmark/robustness/generated/question-sets
```

Use `--question-set f2-attacks` repeatedly to restrict generation. The generated `manifest.json` lists every base,
variant and review status. The runner also accepts the in-memory result of
`goldrails_bench.robustness.question_variants`; generated files are review artifacts, not a second source of truth.

## Run and freeze

Use the normal `run_matrix` path. For test rows, create and commit a separate extension freeze manifest containing
the diagnostic configuration hashes and derived dataset SHA. Keep its ledger under
`benchmark/results/robustness/<run-id>/`, not beside the primary ledger.

Canonical thresholds remain the reference. Robustness variants must not fit new test-informed thresholds: the point
is whether the frozen decision changes under the perturbation.

## Report

```bash
uv run python -m goldrails_bench.robustness report \
  --canonical-ledger benchmark/results/<run>/canonical.jsonl \
  --variant-ledger benchmark/results/robustness/<run>/variants.jsonl \
  --freeze-manifest benchmark/subsets/<run>/freeze-manifest.json \
  --out benchmark/results/robustness/<run>/report
```

Outputs are:

- `robustness.json`: full machine-readable summary and matched rows;
- `robustness-pairs.csv`: one canonical/variant comparison per row;
- `README.md`: a clear aggregate-eligible table followed by every variant, including provisional ones.

Per variant the report shows matched and scored pairs, mean and maximum absolute probability change, decision-flip
rate, canonical and variant accuracy, correct-to-wrong rate and wrong-to-correct rate. Per implementation/question
set it shows mean variant accuracy, the worst eligible variant and mean flip rate. If no freeze manifest is supplied,
threshold-dependent fields are omitted instead of silently using `0.5`.

## Interpretation rules

- Report the canonical score, mean eligible-variant performance and worst eligible variant together.
- Keep `requires_review` variants visible but outside aggregate claims.
- Treat a decision flip as sensitivity, not automatically as an error; correctness columns say whether it helped or
  hurt.
- Do not pool variants as extra independent benchmark rows. They are matched observations sharing a base row.
- Do not change the primary leaderboard, thresholds or dataset based on diagnostic test output.
