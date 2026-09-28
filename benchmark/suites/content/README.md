# Suite: Content

**Task.** Detect the specified violation while passing permitted content, including benign text that sounds dangerous.

**Status.** Working pilot. Question sets live in `benchmark/question_sets/v1` and `v2` (to move here); results in `benchmark/results/pilot-cloud-pass.jsonl`.

Every suite holds five things and the harness reads nothing else: task, cases (versioned, shared schema, provenance
with every transformation), expected outcome in the suite's own form, system configuration (question set plus
decision rule, or guardrail configuration), and scoring written before any run. See docs/18.
