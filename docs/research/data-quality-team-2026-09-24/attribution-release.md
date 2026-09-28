# Attribution and Hugging Face release audit

Read-only review, 24 September 2026. No upload, model calls, corpus download, or dataset edits. This is an AI audit of documented provenance and packaging, not independent human annotation or a legal opinion.

## Decision

The local dataset is substantially traceable, but the current HF folder is **not upload-ready as a self-contained, attributed dataset**. Fix metadata, notices, and the AI4Privacy distribution decision before uploading. These findings do not call for new model runs.

## Verified local evidence

- `dataset/release/v1.1-ai/hf/` contains 15 JSONL files and **8,965 records** across 20 source keys. It contains no README, source attribution file, license notices, or reconstruction instructions file.
- **2,696 IDs-only records**: AI4Privacy 880, RAGTruth 900, Civil Comments identity 900, and reviewed bias pairs 16. All have text, context, source, query and tool-call state fields null. Examined spans/metadata contain offsets and labels, not copied passages. Bias metadata does retain individual demographic descriptors and transformations; IDs-only does not mean metadata-free.
- 6,269 records retain text under the current policy. Every source has a redistribution policy entry. The policy distinguishes AI labels from human review and defaults unknown sources to IDs-only.
- Sampled loader revisions for AI4Privacy, RAGTruth, JBB artifacts, BBQ and the profanity corpus are full immutable commit hashes. The profanity lexicon is separately pinned.
- Package rows retain stable IDs, source IDs, canonical hashes, original/mapped label information and revision metadata, although publisher URLs generally live in loader code rather than a self-contained source registry.

## Findings requiring correction before upload

### 1. Stale dataset card and invalid paths (high)

`dataset/DATASET_CARD.md` describes v1.0, 8,658 records and old review/scope rules. The actual extension is v1.1-ai, 8,965 records with AI-reviewed denied topics, profanity and B2. It still describes no completed review, B2 absent, indirect attacks as a scored subtask, and authored cases as never test. Several licence table statements say text will ship while current policy says IDs-only.

The card's YAML points at `data/content/tune.jsonl`, `ids/sensitive_information/...` etc. The actual package uses `content/tune.jsonl`, `sensitive_information/...`, and other suite folders. There is no separate `sensitive_information_ids` config, and the card does not declare the actual candidates config. No generated replacement card or upload script using an alternative was found in the dataset/benchmark code searched.

**Fix:** generate README from the release manifest and actual file layout; validate every declared path resolves. Identify mixed text/IDs-only records explicitly. Add the omitted profanity source and lexicon, current label policy, actual exclusions and exact counts. Do not copy this stale card to HF.

### 2. Source names alone are incomplete attribution (high)

The policy repeatedly says attribution is “named in the dataset card”; the Citation section says users should cite upstream sources themselves. The package includes no copyright or permission notices. The pinned JBB artifacts licence explicitly requires retaining its copyright and permission notice; OpenAI's upstream MIT licence does too. CC-BY sources also need a usable source/licence attribution trail and indication of adaptations.

**Fix:** add a source registry with publisher, original URL, mirror URL if used, pinned revision, licence link/file, requested citation, and our transformations. Bundle required notices for redistributed sources (including MIT lexicon where applicable). Distinguish original OpenAI dataset attribution from the `mmathys` mirror attribution. Include citations requested by original creators, rather than placing all responsibility on downstream users.

### 3. AI4Privacy: IDs-only does not establish rights to copied annotations (high, bounded)

The pinned upstream licence restricts use to academic/non-commercial research and requires explicit permission for redistribution and derivative dissemination. The package strips the source text but republishes 880 rows containing entity span annotations and derived labels. The licence does not explicitly grant an exception for those annotations. Local documentation already recognizes that use permission is unresolved.

**Fix:** do not describe these annotations as cleared merely because text is absent. Hold this portion of the HF annotation package until permission or a documented applicable basis is established. A selection-ID/source-pointer manifest is a narrower alternative, subject to its own review. This finding does not automatically invalidate measured results; it limits what we can confidently publish as reusable data. Do not require an entire benchmark rerun simply to repair distribution packaging.

### 4. Reconstruction and immutable release guarantee need a clean-room check (medium)

Each IDs-only row gives a generic command with `<version>` placeholder. It does not itself name the repository checkout/commit and setup requirements; the stale card has a `<repo>` placeholder. Pinned loaders are a strong foundation, but a user downloading only HF files lacks the executable reconstruction context.

`release.py` writes build files and packages HF files **before** checking whether the existing release hash differs. Static code inspection shows that a failed rebuild can therefore mutate the directory that it calls immutable while leaving its old manifest behind. This failure mode was not executed or reproduced in this audit, to avoid modifying the release. Separately, package bytes include import timestamps, so canonical reproducibility and byte reproducibility must not be conflated.

**Fix:** reconstruct into a temporary destination, verify canonical hashes, and only then create/promote a new release. Supply a concrete repository URL and code commit after publication. Test one licensed IDs-only reconstruction plus an offline package/schema load from a clean directory; no model calls needed.

## Original-source checks performed

- [JBB artifacts pinned MIT licence](https://github.com/JailbreakBench/artifacts/blob/909e68c/LICENSE): copyright holder and notice-retention condition verified.
- [OpenAI upstream MIT licence](https://github.com/openai/moderation-api-release/blob/main/LICENSE): original attribution and notice condition verified; this is current upstream evidence, not a complete mirror equivalence check.
- [AI4Privacy pinned licence](https://huggingface.co/datasets/ai4privacy/pii-masking-300k/blob/c8c77895a005822682b66ab547fc0422579bc1d3/LICENSE.md): read through raw endpoint; restrictions above verified.
- [deepset pinned card](https://huggingface.co/datasets/deepset/prompt-injections/blob/4f61ecb038e9c3fb77e21034b22511b523772cdd/README.md): raw card has nested CC-BY-4.0 and top-level Apache-2.0. Local policy acknowledges this inconsistency. Retain both declarations and their evidence; do not imply publisher clarification occurred.
- [Google Civil Comments](https://huggingface.co/datasets/google/civil_comments): first-party card declares CC0-1.0 and includes obscenity/identity-attack labels. This verifies source identity and declared licence, not an equation of obscenity with our profanity task.
- [BBQ pinned licence](https://github.com/nyu-mll/BBQ/blob/bea11bd/LICENSE): CC-BY-4.0 verified from raw file.
- [Anthropic discrim-eval pinned card](https://huggingface.co/datasets/Anthropic/discrim-eval/blob/6986d6e/README.md): CC-BY-4.0 and requested citation verified from raw endpoint.

## What is not established by this review

No claim of having revalidated every upstream licence, every corpus row, full clean-room rebuild, or training-data noncontamination. RAGTruth, mirror-based Civil Comments and HolisticBias remain appropriately conservative in the current redistribution policy. The cross-source/task mapping review is owned by the other team members. Agent consensus would not convert source or AI-generated labels into human ground truth.

## Short developer handoff

Keep the model results fixed. Generate the current HF README/source registry, include upstream notices, resolve or withhold AI4Privacy annotation redistribution, and validate the final package paths plus reconstruction procedure. These are a bounded publication-preparation pass, not a new benchmark design phase.

## Debate with source and sampling reviewers

The source reviewer reports exact correspondence of 880 AI4Privacy texts/spans with the pinned source, alongside negative rows that visibly contain supported entity types. These facts are compatible: faithful copying is not proof of complete annotation. If confirmed as omitted supported entities under the task definition, the result limits detector-error and calibration claims; it does not imply corrupt import. A qualified research selection can preserve original labels and disclose incompleteness, subject to distribution rights. It should not advertise a fully annotated gold reference.

The sampling reviewer reports numerically related IDs crossing splits, and the source reviewer identifies actual continuation examples. Numeric stems alone are an audit heuristic, not established upstream semantics. Verified continuations justify narrowing independence claims and a disclosed sensitivity analysis. Preserve original scores; do not silently relabel or resplit the already evaluated set. New stricter grouping belongs in a new dataset version.

These quality limitations and the HF packaging blockers are separate. Fixing notices/cards does not validate labels; fixing labels does not establish redistribution permission. Neither finding warrants adding thousands more examples before understanding the current ones.
