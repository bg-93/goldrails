# Labels and sampling audit — 24 September 2026

Read-only audit of the v1.1-ai build and first-benchmark-v1.1-ai selection. No labels, code, runs or frozen artifacts changed. This is another AI audit, not independent human annotation. The original single-AI labels remain single-AI reference labels.

## Scope and methods

- Programmatically inspected all 8,965 build rows and all 2,518 selected rows. Selection contains 1,624 core test + 488 core tune + 308 bias test + 98 bias tune; the 1,624 includes 31 obfuscation diagnostic test rows, not an extra headline subtask.
- Recomputed recorded-group and normalized-text split checks; normalization lowercases and collapses whitespace.
- Read all 115 denied-topic texts and labels (42 tune,73 test), all16 B2 rows (8 pairs), a fixed random sample of40 profanity rows (Python Random(24), drawn from the200 selected primary profanity rows), and first20 selected PII negatives. Extended PII inspection to every release negative containing password/username/email/IP markers.
- Compared these findings with the source-fidelity reviewer, who independently checked pinned originals. This report does not include synthetic credential strings or personal identifiers.

## Main finding: the current split audit misses PII parent chunks

`dataset/goldrails_dataset/sources/ai4privacy.py` assigns group to the entire source row ID, including its letter suffix. Related text chunks such as [AI4Privacy id],[AI4Privacy id],[AI4Privacy id] are therefore separate groups. Grouping by numeric parent stem gives:

| Scope | Parent stems across tune/test | Rows involved |
|---|---:|---:|
| Release PII build |34|80|
| Actual selected PII subset |3|7|

Selected parents: 50846 (A/B test,E tune),51890 (A test,B tune),53180 (F test,A tune). The source-fidelity reviewer confirmed actual adjacent-text continuations for [AI4Privacy id]/B and [AI4Privacy id]/B. The numeric-stem count is a conservative inferred parent grouping, not a verified upstream parent-key specification for all34 stems. This is evidence of parent-document overlap, not exact text duplication.

Current gates genuinely find zero recorded-group overlaps, zero whitespace/case-normalized text overlaps, and zero normalized duplicates in the entire build. Those results do not establish parent-document separation. The apparent clean audit reflects the grouping definition.

**Release impact:** block a claim that PII has independently held-out source documents. Preserve the frozen run. Add a disclosed sensitivity calculation dropping the four affected test rows; it cannot undo any tuning effect. For a clean new benchmark, fix parent grouping, freeze a fresh subset and evaluate it. Do not silently rewrite frozen IDs or claims.

## Concrete PII label omissions

The label rule treats an empty source span list as benign. It misses unannotated supported entities:

| Source row | Gold Rails row | Current split | Observed issue |
|---|---|---|---|
|[AI4Privacy id]|f5-ai4privacy-[withheld]|test subset|Explicit temporary password; spans empty, expected no|
|[AI4Privacy id]|f5-ai4privacy-[withheld]|tune subset|Email address fragment is still syntactically a complete email; expected no|
|[AI4Privacy id]|f5-ai4privacy-[withheld]|tune subset|Signature contains a complete email address; expected no|
|[AI4Privacy id]|f5-ai4privacy-[withheld]|release test, not selected|Explicit username; expected no|

The source reviewer confirms [AI4Privacy id] has an empty privacy_mask in the pinned original, so this is upstream annotation omission faithfully imported, not fabricated text or a wrong offset conversion. The other originals are under verification.

**Release impact:** cannot portray every negative as verified entity-free. Review all PII negatives, retaining original source labels and a separate audited/adapted label field. Until then, identify these as concrete suspected/confirmed label errors and publish a separately labeled sensitivity view, preserving primary results. Do not simply strengthen a placeholder regex and assert the remaining negatives are clean. Two suspects are tuning rows; changing their labels can alter fitted thresholds and therefore requires a new analysis identity and explicit correction history.

## Denied topics: coherent narrow task, limited support

All115 reviewed examples appear broadly consistent with the supplied personal-investment, specific diagnosis/dosage, and personal legal-advice definitions. I did not establish an additional definite mislabel among them. That is AI agreement, not independent human validation.

Test composition:73 rows,29 positives/44 negatives. Assigned topic fields:21 legal,21 medical,17investment,14confusers without a topic. Each row is its own group. The corpus is authored for only three supplied definitions; a perfect score cannot support arbitrary denied topics or broad commercial robustness. Many negatives are definitions/history/logistics while positives explicitly request advice. This is legitimate task coverage but a limited challenge distribution. Repeated intent patterns are not independent semantic coverage merely because they have separate IDs.

Practical improvement: independent blind review first; then a small fresh extension with boundary cases and additional topic definitions. Never change labels to imitate Bedrock.

## Profanity: usable adaptation with selection bias

The40-row fixed sample showed generally consistent application of the stated presence definition, including negative labels for hostile text without vulgar terms and positive labels for quoted/friendly profanity. No definite new error was established. Literal versus vulgar uses remain judgment-dependent (for example the ordinary illegitimacy sense of a word often used as an insult); this deserves human adjudication, not retroactive vendor matching.

Actual primary test160rows80positive/80negative, plus31obfuscation diagnostic positives. These are Civil Comments texts with newly assigned AI profanity labels, not Civil Comments ground-truth profanity labels. Selection depends on source obscenity fractions plus a lexicon. Thus this is a purpose-built, lexicon-selected test slice and may miss terms absent from that lexicon. It does not estimate prevalence in ordinary traffic or coverage of a proprietary managed vocabulary.

The release records14 unresolved labels excluded (3 denied topics,11 profanity),6 moved to diagnostics,39 replaced draft labels. Preserve these counts beside headline results; exclusion of unclear cases narrows the estimand toward unambiguous cases.

## Sampling limits that should remain explicit

| Test slice | Rows | Independent recorded groups | Implication |
|---|---:|---:|---|
|Content|560|473|Several sources and labels mapped to common task; source-specific reporting matters|
|Prompt attacks|320|297|160 deepset,80Gandalf,80JBB; only injection supplies benign controls|
|Custom words|160|20|Template correctness test;160rows is not160independent linguistic patterns|
|Grounding|160|134|Source-level groups rather than answers are resampling units|
|B2|8|3|Four pairs, including two pairs using the same sentence template; individual diagnostics only|

Jailbreak and leakage test subsets each have80positive and zero subtype-matched negatives. Overall false-positive measurement comes from deepset controls. This cannot establish jailbreak-specific or leakage-specific benign rejection rates.

B1 identity mentions are sparse: male18,female14,white7,black6,Christian5,gay/lesbian4,Muslim3,Asian2,transgender1. Discrim-eval has50rows spanning31scenarios;19scenarios occur once,6twice,5three times,1four times. Group gaps cannot isolate demographic effects when scenarios differ. B2 retained16totalrows correctly stay grouped; reviewed source swaps are not equivalent to broad fairness coverage.

## Metadata requiring correction before upload

`dataset/release/v1.1-ai/manifest.json` exclusions still includes “Managed profanity lists, images, non-English text, streaming and deployment controls” and says B2 enters scored results only after review. Clarify that profanity behavior is now evaluated while the proprietary list itself is not enumerated, and B2 is included only as AI-reviewed exploratory diagnostics. Update via a versioned metadata release; do not silently change an immutable package.

## Recommendation

The dataset can be shared as a clearly labeled research artifact after the PII overlap/label issues and metadata inconsistencies are documented; it should not be promoted as uniformly audited authoritative ground truth. For the fastest credible benchmark finish, keep existing results, add a PII sensitivity analysis and known-issues table, and qualify independence claims. If the desired claim is a clean held-out PII result, that slice needs repaired grouping and a fresh confirmation run. No evidence here requires rerunning the other five categories.

## Cross-review debate

The attribution reviewer correctly separates faithful import from complete labels, and IDs-only packaging from annotation redistribution rights. I agree: hold the restricted annotation portion until its publishing basis is resolved, but this alone does not require model reruns. Numeric stems are an audit heuristic; confirmed continuous text is the stronger evidence. Preserve primary scores and present any removals/corrections as explicit sensitivity analyses. Because some omitted-entity labels are tuning rows, correcting test labels alone cannot establish an optimally tuned or clean held-out PII comparison. Packaging corrections and methodological caveats should be handled separately.
