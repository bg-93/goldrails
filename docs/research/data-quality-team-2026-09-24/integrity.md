# Release integrity and evaluated-subset audit

Read-only audit on 24 September 2026. No model calls, cloud operations, uploads, or dataset/scoring edits. Review artifacts are separate from frozen releases. Existing uncommitted page-check.json and research/reviews paths were present before this review.

## Independently checked

- Every manifest file in v1.1-ai: 14 canonical build files and 15 HF JSONL files. Actual byte SHA256 and row counts match all manifest entries.
- 8,965 canonical and 8,965 HF rows: same ID set, no repeated IDs, 8,965 unique canonical_row_hash values.
- All 2,518 entries in first-benchmark-v1.1-ai subset: ID exists in release and feature, subtask, split, expected and group agree.
- Original core test ledger: 9,680 records / 1,360 unique IDs; every ID exists in release, zero expected-label differences.
- Core rerun: 51 records / 51 IDs; zero missing IDs or expected-label differences.
- Extension core ledger: 1,848 records / 264 IDs; zero missing IDs or expected-label differences.
- Original bias test ledger: 1,900 records / 300 IDs; zero missing IDs or expected-label differences.
- Extension bias test ledger: 56 records / 8 IDs; zero missing IDs or expected-label differences.

These validate identity and consistency, not semantic correctness. They do not mean the underlying labels are true or that upstream restrictions permit redistribution.

## Provenance counts in the HF package

| Label basis | Review status | Rows |
|---|---|---:|
| human | source_label | 3,238 |
| deterministic | deterministic | 2,214 |
| automated | source_label | 900 |
| synthetic_reviewed | source_label | 880 |
| unknown | source_label | 830 |
| llm | source_label | 438 |
| llm | ai_reviewed | 425 |
| llm | candidate | 40 |

`source_label` does not mean human annotation. Source reputation and label provenance must stay separate in the dataset card and results.

## Scope metadata discrepancy

The immutable v1.1-ai manifest still lists managed profanity among exclusions despite this release including profanity rows and the completed benchmark scoring them. `dataset/goldrails_dataset/release.py` contains the stale exclusion. This requires a traceable packaging/metadata correction, not silently rewriting the old release or rescoring models.

## Evidence

- dataset/release/v1.1-ai/manifest.json
- dataset/release/v1.1-ai/build/*.jsonl
- dataset/release/v1.1-ai/hf/*/*.jsonl
- benchmark/subsets/first-benchmark-v1.1-ai/manifest.json
- benchmark/results/first-benchmark/{test,test-rerun,ext-test,test-bias,ext-test-bias}.jsonl
