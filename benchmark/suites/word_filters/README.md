# Suite: Word filters

**Task.** Match configured terms under the declared matching rules.

**Status.** Smoke suite. Cases: 44 deterministic rows generated from `words.json` v1 (exact, case, punctuation, position; suffixed, split, reversed, run-together, unrelated), `label_basis: deterministic`. Question set `v1/f4-words`. Reference system: `regex-baseline` implementing the stated rule. Bedrock: ApplyGuardrail word policy. First smoke: regex, Jev and Bedrock all perfect on 41 rows. Managed profanity is configured but not enumerated in cases.

Every suite holds five things and the harness reads nothing else: task, cases (versioned, shared schema, provenance
with every transformation), expected outcome in the suite's own form, system configuration (question set plus
decision rule, or guardrail configuration), and scoring written before any run. See docs/18.
