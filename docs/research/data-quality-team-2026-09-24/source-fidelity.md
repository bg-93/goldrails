# Source fidelity audit — 24 September 2026

Read-only audit of release v1.1-ai, the first-benchmark manifest, current loaders, and original publisher data at pinned revisions. No labels, model settings, results or cloud resources changed. Findings distinguish faithful copying from valid task adaptation. This is an AI audit, not independent human annotation.

## Verdict

The import pipeline copies the checked source material faithfully. **That does not establish label completeness, grouping correctness, or equivalence to Bedrock's features.** PII document grouping needs correction before a clean held-out claim. The source's missing PII annotations and Gandalf's unsupported leakage subtype need explicit treatment. None of this requires discarding the other suites.

## Quantified checks

All **5,222 imported release rows** from ten sources below were compared with original data at the loader's pinned revision. No mismatched input text was found. For native binary labels, expected outcomes were checked against those labels; construction-based labels were checked against loader/source split rules. RAGTruth source text was also compared; AI4Privacy span counts, offsets and original types were compared. This verifies transport/transformation, not whether annotators were correct.

| Source | Rows checked | Reference and scope |
|---|---:|---|
| Aegis 2 | 1,248 | Pinned cached original test Arrow; text and prompt/response safety label |
| OpenAI moderation mirror | 244 | Pinned cached original train Arrow; text and any-positive eight-category rule; mirror not independently matched to OpenAI's original repository |
| OR-Bench | 450 | Pinned cached original hard-1k Arrow; exact text; benign label by membership |
| deepset injections | 380 | Pinned cached original train Arrow; exact text and binary label |
| Gandalf | 450 | Pinned cached original train Arrow; exact text; no native subtype label exists |
| AI4Privacy | 880 | Fresh streamed pinned validation data; text, span count, original type and offsets |
| RAGTruth | 900 | Fresh fetched pinned source_info and response JSONL; reply, full source, any-span label |
| JBB artifacts | 286 | Fresh fetched pinned attack artifact files; exact prompt; attack-by-construction label |
| JBB behaviors | 200 | Pinned source through loader; goal text and harmful/benign split |
| AILuminate demo | 184 | Fresh pinned original CSV through loader; prompt text and hazardous-by-construction label |

Evidence code: `dataset/goldrails_dataset/sources/`; release data: `dataset/release/v1.1-ai/build/`. Audit scripts and compact counts are retained under `evidence/`: `source-cache-and-ragtruth-check.py`, `pii-original-check.py`, `remaining-source-check.py`, and `source-fidelity-counts.json`. No raw source texts are included in the evidence artifacts.

## 1. PII document chunks cross tuning and test — high priority

The loader groups by the complete source ID, including its suffix. Direct original-text evidence shows these IDs can denote fragments of one document:

- `[AI4Privacy id]` ends in `conflicts be`; `[AI4Privacy id]` begins `tween team members`. Both are test examples; `[AI4Privacy id]`, the same conflict-resolution protocol's ending, is tuning.
- `[AI4Privacy id]` ends in `Social Security `; `[AI4Privacy id]` begins `Number:`. The former is test and the latter tuning.
- `[AI4Privacy id]` opens an intervention-proposal JSON document; `[AI4Privacy id]` closes its participant list and proposal summary. These are tune and test respectively.

All seven texts match the pinned original. The other reviewer independently counted 34 shared numeric stems/80 release rows and three stems/seven selected rows. Those counts are their analysis; the concrete original-document evidence above is independently confirmed here. The README defines `id` only as an entry identifier, so a universal numeric-stem rule is an inference, not an explicit publisher guarantee.

**Fix:** Conservatively group suffix variants together; audit the rebuild. Existing affected PII findings should carry the exposure limitation. If correcting the held-out claim, use a predeclared new clean confirmation set; do not silently change old splits or pretend a retroactive grouping fix makes the old run untouched.

## 2. Missing PII spans originate upstream — high priority

Original rows `[AI4Privacy id]`, `[AI4Privacy id]`, `[AI4Privacy id]`, and `[AI4Privacy id]` have empty `privacy_mask` arrays. Their release counterparts faithfully preserve this. The text nevertheless contains a temporary-password presentation, email-like values, or an explicit username. `[AI4Privacy id]`, for example, ends with an explicit Username field; `[AI4Privacy id]` includes an email-like contact string. Some placeholder cases still need a precise synthetic-entity rule, but empty spans cannot automatically establish absence.

The first three are in the selected test/tuning material per the labels reviewer; `[AI4Privacy id]` is a release example. This audit confirms original span absence for all four, not exhaustive semantic relabeling of all negatives.

**Fix:** review span-free negatives against the actual supported-entity task, preserve original labels separately, record adjudicated corrections and uncertainty. Do not conflate a source-quality defect with an importer bug. Do not replace all original positives with AI judgment.

## 3. Gandalf is not an authoritative leakage-subtype dataset — medium/high

[Publisher card at pinned revision](https://huggingface.co/datasets/Lakera/gandalf_ignore_instructions/blob/04737b65e90a6794ec227012e4a255a7def6344b/README.md) describes embedding-similarity selection against an instruction-override phrase, followed by filtering and deduplication. It acknowledges that some selected samples may not be actual injections. It does not supply per-row secret-extraction/leakage labels or the original protected instruction context.

`gandalf.py` maps every row to `subtask="leakage"`, expected yes. There are 450 release rows and 80 selected test rows. Faithful text copying does not validate that subtype. Broad attack detection is a defensible proxy with noise disclosure; claiming that the named leakage detector correctly detects leakage is stronger than the source supports.

**Fix:** label this as source-selected injection attempts; retain current results as a proxy or separately audit subtype labels. Do not expand this source as authoritative leakage positives without annotation. Keep subtype specificity out of claims until verified.

## 4. Content source policies extend beyond five content filters — medium

Of 240 selected positive content test rows, **32 map in the project's own taxonomy to other feature types: 21 PII and 11 TOPIC**. Examples include `f1-ailuminate_demo-428b0b9c9d` (PII) and `f1-ailuminate_demo-1430f9a97c` (TOPIC). `score.py`/leaderboard compare source unsafe labels to the configured detector output; these are not automatically equivalent to the five content categories.

This does not prove all 32 labels are wrong: a request involving privacy or advice can also violate misconduct. It does show that simple taxonomy conversion is insufficient evidence of equivalence.

**Fix:** disclose source-policy agreement vs feature-specific accuracy. Add a clearly marked sensitivity breakdown for the 32 rows using existing outputs. For the next release, review boundary mapping independently before tuning. Do not change the frozen primary score to the more favorable variant.

## 5. Grounding fidelity is strong; preserve annotation nuance — lower priority

All 900 replies and sources match pinned RAGTruth originals. No invalid annotation offsets were found. 899 responses have source quality `good`; one is `incorrect_refusal`. Forty-seven rows include at least one source `implicit_true` annotation: content can be factually correct yet unsupported by the supplied source. That is compatible with a grounding task, but not with calling every positive factually false. The loader omits `implicit_true`, `due_to_null` and annotation comments from normalized spans.

**Fix:** keep source grounding semantics, mention unsupported is not necessarily false, preserve original annotation metadata in a permitted reconstruction/sidecar format. Query shortening is an explicit adaptation and source documents remain intact. Source: [RAGTruth publisher repository](https://github.com/ParticleMedia/RAGTruth).

## Attribution and limits

The attribution reviewer owns permissions and package wording. Source revision identifiers are present in loaders; per-row provenance is not equally complete across sources. OR-Bench's loader header still says human labeling although actual records correctly use `automated`; fix that comment. Aegis retains only the first mapped category, so category fields must not be presented as exhaustive original annotations.

This audit does not prove lack of training contamination, label validity of every example, copyright permission, or production representativeness. Rebuilding source rows through existing loader code is a consistency check; the direct cache/stream/raw comparisons above provide stronger independent transport evidence. No recommendation here authorizes changing a frozen result silently.

## Cross-review debate and bounded release verdict

The labels reviewer’s strongest finding is demonstrated continuation across splits, not the numerical suffix alone. Their proposed removal of four affected test rows is useful sensitivity analysis, but cannot reverse tuning exposure or establish a clean corrected test. The three shared families in the selected set are sufficient to qualify PII independence; there is no evidence to invalidate the other five suites. All four listed omitted-span originals are now confirmed, updating the review’s pending verification note. Whether every temporary-password placeholder counts as a supported entity should still follow the declared entity rule.

The attribution reviewer’s notices, stale card, path and reconstruction findings affect publication packaging, not numerical results. The annotation-permission concern remains bounded: IDs-only is not automatic clearance, but the appropriate remedy is withholding the uncertain package component or resolving its basis, not rerunning the benchmark.

Gandalf’s subtype mapping is an unsupported specialization. Its broad injection classification remains a plausible noisy proxy; both source selection and missing context must be disclosed. Do not state that all80 rows are definitely mislabeled or that the whole attack score is invalid. Likewise32 out-of-content-taxonomy positives do not establish32 incorrect reference labels; they identify a feature-equivalence review slice.

Recommendation: finish a provisional research release with source-fidelity checks, limitations and properly packaged attribution. Repair PII parent grouping and review its negatives for a new clean PII confirmation result. Keep this bounded; no broader corpus expansion is required by these findings.

### Password-policy resolution

Rechecked the actual frozen `benchmark/question_sets/v2/f5-pii.json`: PASSWORD asks whether text contains a password or passcode, with no exclusion for synthetic/placeholder-looking values. Original47929C explicitly presents a concrete string as a temporary password and gives login/reset context. Under that actual task wording its empty-span negative is a reference mismatch, even though this audit does not establish a live real-world credential. The synthetic appearance is not a reason to pass it while scoring other synthetic credentials. This resolves the earlier conditional wording for this example.
