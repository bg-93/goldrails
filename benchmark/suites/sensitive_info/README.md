# Suite: Sensitive information

**Task.** Detect the right entity types and, where required, mask the right spans.

**Status.** Smoke suite for detection. Cases: AI4Privacy pii-masking-300k English rows (pinned revision, custom licence, not redistributed) with spans mapped to AWS entity types, the source's own PII-free chunks and twenty authored controls as negatives. Question set `benchmark/question_sets/v1/f5-pii.json`: one Noul per entity type plus contains_pii. Bedrock: InvokeGuardrailChecks sensitiveInformation with the same entity list; offsets kept in the ledger for the masking study. Masking not yet built. Detail: Two results kept apart: detection (InvokeGuardrailChecks returns entity detections with character offsets and does not redact; our Bedrock adapter does not send this check yet) and masking (ApplyGuardrail on the service side; for decision models a complete implementation including span extraction and redaction, costed as a whole). Span-labelled sources: AI4Privacy PII Masking 300k (English subset, custom licence), PII Arena, PIIBench, synthetic identifiers. Benign controls (text with numbers, names of public figures, non-PII identifiers) are part of the first smoke.

Every suite holds five things and the harness reads nothing else: task, cases (versioned, shared schema, provenance
with every transformation), expected outcome in the suite's own form, system configuration (question set plus
decision rule, or guardrail configuration), and scoring written before any run. See docs/18.

**Smoke v2, 48 tuning rows (22 September 2026).** Shared supported-entity task: Jev AUROC 0.96, recall 0.87, false flags
0.12; Bedrock 0.95, 0.93, 0.06. This small tuning sample does not establish a reliable difference between them; at the
0.5 threshold Bedrock has higher recall and fewer false flags, and matched operating points with held-out uncertainty
estimates are still needed before any comparison is stated.

**Negative-example construction.** AI4Privacy chunks with no labelled span are used as PII-free negatives except when
they contain a masking placeholder (pattern `[A-Z]{3,}_[A-Z0-9]{1,3}`, e.g. "USERNAME_B:"). That exclusion is an
artifact of how we construct negatives from a masking dataset, applied by rule to every row regardless of which
system flags it; it is not a claim that the source annotated those chunks wrongly.

**Heuristic mapping.** `SOCIALNUMBER` spans whose value has the 123-45-6789 form map to `US_SOCIAL_SECURITY_NUMBER`.
The pattern is evidence of SSN-like formatting, not of US jurisdiction. Rows relying on it are marked in the span
(`source_label: SOCIALNUMBER`) and are kept out of strict entity-level correctness claims until source metadata or
context supports the jurisdiction.
