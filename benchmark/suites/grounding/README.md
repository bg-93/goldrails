# Suite: Grounding and relevance

**Task.** Flag claims the source does not support, and replies that do not answer the query.

**Status.** Smoke suite for grounding. Cases: RAGTruth test split, Summary and QA, pinned commit, human hallucination spans; the query is the short task (the question, or a fixed instruction), because Bedrock's query limit is one text unit. Question set `v1/f6-grounding`: unsupported (labelled), irrelevant (no label in RAGTruth; reported without a score). Bedrock: ApplyGuardrail contextual grounding; score inverted (1 - grounded). First smoke on 30 rows: Jev AUROC 0.87, Bedrock 0.74; Bedrock's default 0.5 threshold gives recall 0.40 at fp 0.13.

Every suite holds five things and the harness reads nothing else: task, cases (versioned, shared schema, provenance
with every transformation), expected outcome in the suite's own form, system configuration (question set plus
decision rule, or guardrail configuration), and scoring written before any run. See docs/18.
