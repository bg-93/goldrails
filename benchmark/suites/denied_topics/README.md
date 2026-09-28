# Suite: Denied topics

**Task.** Apply a supplied topic definition, including its stated exceptions.

**Status.** Smoke suite. Cases: 28 authored requests against `topics.json` v1 (in-topic, near-miss, off-topic), `label_basis: llm`, all in tune; BARRED's health-advice task is the planned published source. Question set `v1/f3-topics`: one Noul per topic carrying the definition and examples verbatim, plus any_denied_topic. Bedrock: ApplyGuardrail against the versioned topics guardrail; its answer is binary (detected), so AUROC on it is coarse. First smoke: Jev AUROC 1.00 (fp 0.06), Bedrock 0.85 (recall 0.83, fp 0.12) on 28 authored rows; a smoke of the pipeline, not a result.

Every suite holds five things and the harness reads nothing else: task, cases (versioned, shared schema, provenance
with every transformation), expected outcome in the suite's own form, system configuration (question set plus
decision rule, or guardrail configuration), and scoring written before any run. See docs/18.
