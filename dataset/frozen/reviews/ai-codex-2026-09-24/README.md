# Completed AI review and execution handoff — 24 September 2026

The owner asked Codex to judge the pending data and move the benchmark forward quickly. This packet completes a **single AI review**, not independent human annotation or two-reviewer adjudication. Use it for an explicitly AI-reviewed provisional extension. Preserve that distinction in the dataset card, contract amendment, plots and overall result.

## What is complete

All 420 original items were read in full against the supplied definitions before mapping keys were opened. No model-under-test calls or outputs were used to choose labels. Prior conversation included benchmark design and aggregate results; this reviewer is not independent of benchmark design. Mapping keys were opened only after raw review files were written, to attach canonical IDs; draft labels were not used to revise judgments.

| Packet | Reviewed | Outcome |
|---|---:|---|
| Denied-topic controls | 28 | 12 inside a denied topic, 16 outside |
| Denied-topic candidates | 90 | 36 inside, 51 outside, 3 unresolved |
| Profanity candidates | 280 | 125 present, 149 absent, 6 unresolved, including diagnostics |
| B2 counterfactual pairs | 22 | 8 retained; 14 rejected from scoring with explanations |

The retained B2 pool contains four flag pairs and four pass pairs. It is a small diagnostic, not a fairness ranking. Rejected pairs include a fish-sex substitution, incompatible religious references, and altered factual or rhetorical premises. Do not replace them with unreviewed generated pairs simply to meet a count.

## Execution decisions

1. Use clear AI labels for the provisional run. Exclude unresolved items before any test calls and disclose their IDs/reasons. Do not infer another person's vote, create a second reviewer identity, calculate inter-rater agreement from this review, or rename these labels as human.
2. Preserve the raw sheets. `mapped-ai-reference.jsonl` contains canonical record IDs and eligibility for the original packets. `f4-profanity-reserve.jsonl` supplies source IDs for reserve rows. A named AI-reviewed status must be carried through the builder, subset selection and report. The current `build.apply_reviews()` and B2 loader hard-code `human`, so do not feed these files through the human importer unchanged.
3. Keep `label_basis: llm`. Explicitly record that the human-review requirement is replaced for this provisional extension by the owner's instruction to use an AI judge. Keep the original human-reviewed release policy and historical results intact. This instruction is not publication approval or an owner signature on exact scorer hashes.
4. Follow `diagnostic-placement.json`: six primary candidates contain only masked profanity or abbreviations, so move them to the obfuscation diagnostic before freezing. This decision uses the text alone, not system outputs. Exact word matching should not be penalized for missing these cases.
5. Restore the planned positive pool from the existing frozen reserve queue. The first **25** round-robin reserve entries were sufficient; they add 11 clear positives, 9 clear negatives and 5 unresolved cases. Entries 26–28 were also read and recorded but are not admitted because the target was reached at 25. After diagnostic reassignment, the recommended primary pool is **100 positive and 158 negative**, plus 11 unresolved excluded cases. Select the planned balanced 200 messages deterministically, then the grouped 40/160 tuning/test split. This is a planning count, not proof that a rebuilt subset already passes its audit.
6. For denied topics, use the existing group/examined rules. Retain the three uncertain investment-boundary cases outside scoring; no question rewrites are necessary for this provisional pass.
7. Freeze AI label files, source revisions, exclusions, spelling assignments, subset, tuning allowance and scoring weights before new test calls. Preserve the original core test rows and thresholds. Run denied topics, profanity and the retained B2 pairs through the extension machinery; use unchanged old results only where the comparison contract permits carry-over.
8. Plot the expanded six-category result as **provisional: denied topics/profanity use single-AI reference labels**. Preserve the original five-category view. Report B2 separately with its actual post-split pair count, and disclose that hard/unresolved items were omitted.

## Files and validation

- Raw labels: `f3-denied-topics.jsonl`, `f3-test-candidates.jsonl`, `f4-profanity.jsonl`, `b2-v0.jsonl`.
- Additional reserve texts and judgments: `reserve-packet.jsonl`, `f4-profanity-reserve.jsonl`.
- Canonical IDs: `mapped-ai-reference.jsonl`.
- Source and artifact checksums: `manifest.json`.
- Spelling routing: `diagnostic-placement.json`.

Validated exact template ID/order coverage, non-null answers, 442 unique mapped original record IDs, explicit AI provenance, and source-file hashes. This validates the review artifacts, not the benchmark runner. The untracked `dataset/frozen/reviews.jsonl` was neither read nor overwritten. No cloud resource was started, no paid model calls were made, and no dataset was uploaded.

## Small quality notes for the developer

- `f3t-r048`, `f3t-r052`, `f3t-r081` expose the broad investment definition's boundary around currency exchange, public-policy investment discussion and household budgets. IDs use the packet's actual formatting (`f3t-r48`, etc.) in the JSONL.
- Profanity uncertainty includes the detective sense of “dicks”, a quoted donkey metaphor, “bloody murder”, and some colloquial or multilingual insults. Keep their reasons in the release exclusions.
- The documented profanity reserve replacement corrects a shortage discovered by actual review, without using any evaluated model's behavior.
- Existing approval/sign-off records must remain truthful about who authorized what; a delegated AI judgment is not a new human annotation or retrospective signature.
