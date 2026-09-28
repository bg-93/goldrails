# Gold Rails data-quality team review

24 September 2026 · v1.1-ai · pre-publication review

## Decision

**Keep the completed benchmark as a provisional historical result, but repair the publication package and qualify the PII evaluation before uploading. Do not expand the dataset yet.** The team found real issues beyond the previously passing page-consistency checks. None establishes that the entire benchmark must be discarded.

Three specialist AI reviewers independently investigated source fidelity, labels/sampling, and attribution/release packaging. The lead audited release/subset/ledger integrity. Reviewers exchanged findings and challenged the distinction between copying correctly, labelling correctly, separating documents, and having permission to redistribute. This is an AI audit, not independent human adjudication or a legal determination.

No model calls, cloud operations, uploads, dataset edits, threshold changes or scoring changes were made. Only review reports and audit evidence were produced.

## What was verified

- **8,965 release records:** all 14 canonical files and 15 HF JSONL files match their manifest byte hashes and counts. Build and HF ID sets agree.
- **2,518 selected records:** every ID, feature, subtask, split, expected label and recorded group matches the release. All original, rerun and extension test-ledger expected labels match their release rows.
- **5,222 imported records from ten sources:** input text matches pinned cached or freshly fetched source material; original label/span mappings were checked as applicable. One source is a pinned OpenAI moderation mirror, not independently proved identical to OpenAI's original repository. Some later checks use the existing loader and are weaker than independent raw comparisons; the source report identifies their scope.
- **Semantic inspection:** all 115 denied-topic rows, all 16 retained B2 rows, a fixed 40-row profanity sample, and targeted PII negatives. Denied-topic/profanity inspection did not establish a new definite label error; this does not certify all labels.
- Zero recorded-group crossing and zero whitespace/case-normalized text duplicates. The PII finding below shows why those are incomplete independence checks.

## Findings and consequences

| Priority | Finding | What it changes | Minimum action |
|---|---|---|---|
| High | PII fragments from the same original document cross tune/test. Three selected document families involve seven rows: four test and three tune. Two have literal adjacent-text continuations; the third shares the same document structure. | The current claim of independently held-out PII documents is not supported. | Preserve old run; document affected IDs. Correct parent grouping for a new version. A clean PII claim needs a fresh confirmation set. |
| High | Four upstream PII rows have empty span annotations despite apparent supported entities. Three are selected: one test and two tune. | Some apparent model false flags may be reference-label errors; tuning may also be affected. | Audit all PII negatives blind to outputs, preserving original and reviewed labels separately. The temporary-password case was checked against the frozen question and fits its stated definition. |
| High, publication | HF folder lacks its own current README and required source notices; the existing card describes v1.0 and paths that do not match the package. | Downloaders cannot reliably understand, load or attribute the release. | Generate current card/configs, source registry, notices and exact reconstruction instructions. Validate locally before upload. |
| High, publication | AI4Privacy text is stripped, but its copied span annotations and derived labels remain; upstream redistribution restrictions do not explicitly clear that export. | IDs-only cannot be described as automatically cleared. | Hold those annotation files until a documented distribution basis is established. Evaluate a minimal source-selection pointer manifest separately. |
| Medium | Gandalf was similarity-selected for instruction-override attempts; our loader labels every example as leakage without original subtype labels. | Eighty attack test rows do not independently establish leakage-specific accuracy. | Describe as a noisy source-selected attack proxy; qualify existing subtype claims. Audit subtypes before expanding them. |
| Medium | Thirty-two of 240 positive content test rows map in our own taxonomy to PII or TOPIC rather than the five content categories. | Source-policy agreement and feature-specific accuracy can differ. | Publish a source/task-mapping breakdown and a disclosed sensitivity view; do not assume all 32 are wrong or silently remove them. |
| Medium | Release generation writes files before checking whether an immutable version changed. Static inspection, not reproduced. | A rejected rebuild can damage a previously frozen directory. | Build into a temporary directory; verify before promoting a new version. |
| Limit | Four B2 test pairs represent three groups; custom words use 20 templates; attack subtype controls are uneven. | Narrow evidence, not broad fairness or production coverage. | Keep counts, group structure, selection and uncertainty visible. No immediate extra run required. |

The remaining scope discrepancy in the manifest lists managed profanity as excluded even though its behavior is now evaluated. Clarify that proprietary vocabulary enumeration is unavailable, while profanity detection is included. Preserve the old manifest and record a versioned metadata correction.

## What the reviewers debated

**Does exact agreement with the source make labels trustworthy?** No. The source reviewer found faithful imports; the label reviewer found omissions in the original PII spans. Both can be true. Publisher authority does not replace task-specific validation.

**Do shared number stems prove leakage?** Not by themselves. The upstream card does not define suffix semantics. Thirty-four release parent stems involving 80 rows are candidates identified by an audit heuristic. The stronger evidence is the actual document continuity in the three selected families. The report keeps those evidence levels separate.

**Does a synthetic password count?** The reviewers initially disagreed about the placeholder boundary. The source reviewer checked the actual frozen PASSWORD question: it asks for a password/passcode without excluding synthetic examples. The original row presents a concrete value as a temporary password with login/reset context. The reviewers therefore agree that the negative conflicts with the task as written. All four examples retain empty upstream spans. No labels were changed, and no literal credential-like strings are reproduced here.

**Does this require rerunning all six categories?** No. The clean-independence problem is localized to PII. A post-hoc sensitivity view can show dependence on suspect rows, but cannot erase exposure or undo tuning effects. A fresh PII confirmation run is the route to a clean claim; the other categories keep their historical scores and disclosed scope limits.

**Is blanking text sufficient for publication?** No general conclusion follows. All 2,696 IDs-only rows have their state content stripped, but attribution and rights for copied annotations still need a source-specific basis. This is a packaging/permission question, separate from measured model quality.

## Short execution plan

1. **Preserve evidence.** Keep every existing release, split, threshold, ledger and primary score intact. Add this audit to the known-issues/corrections trail.
2. **Fix publication packaging offline.** Current README with actual paths/counts, candidates config, AI review status, citations, publisher/mirror URLs, full pinned revisions, licence notices and transformations. Resolve or withhold restricted annotation exports. Make rebuilds atomic and provide concrete reconstruction instructions.
3. **Bound the PII repair.** Review negative-label completeness and candidate document families, without showing reviewers model predictions. Preserve source labels alongside adapted labels. Produce an explicit correction manifest.
4. **Use existing outputs for diagnostics.** Report a PII sensitivity view for affected rows and a content mapping breakdown. Freeze the rules for these views first and label them post-hoc; do not pick whichever variant improves a system's rank.
5. **Choose the release claim.** The current run can be reported as provisional with these limitations. If the release is to claim a clean held-out PII evaluation, repair grouping, tune on permitted groups, freeze a fresh unseen test selection and run only the necessary PII confirmation. Previously examined inputs must not become a fresh tuning-driven holdout.
6. **Publish only after package validation and owner authorization.** Do not add more examples simply to increase size. Agent consensus is never represented as independent human labelling.

## Attribution fields required per source

Publisher; original URL; mirror URL if used; exact revision; source citation; licence identifier and notice/link; text vs IDs-only mode; original task and labels; our adaptation and label mapping; reviewer provenance; exclusions; reconstruction code revision. Per-row source IDs connect the registry to the actual records.

## Detailed reviews

- [Source fidelity](source-fidelity.md)
- [Labels and sampling](labels-sampling.md)
- [Attribution and release packaging](attribution-release.md)
- [Release/subset/ledger integrity](integrity.md)

These reports state checked counts and limitations. They do not certify training-data noncontamination, every semantic label, legal permission for every possible use, or production representativeness.
