---
pretty_name: Gold Rails
license: other
license_name: mixed-per-source
license_link: https://huggingface.co/datasets/raxITLabs/goldrails/blob/main/SOURCES.md
language:
  - en
task_categories:
  - text-classification
tags:
  - guardrails
  - content-moderation
  - prompt-injection
  - pii-detection
  - hallucination-detection
  - fairness
configs:
  - config_name: content
    data_files:
      - split: test
        path: data/content/test.jsonl
      - split: tune
        path: data/content/tune.jsonl
  - config_name: prompt_attacks
    data_files:
      - split: test
        path: data/prompt_attacks/test.jsonl
      - split: tune
        path: data/prompt_attacks/tune.jsonl
  - config_name: denied_topics
    data_files:
      - split: test
        path: data/denied_topics/test.jsonl
      - split: tune
        path: data/denied_topics/tune.jsonl
  - config_name: word_filters
    data_files:
      - split: test
        path: data/word_filters/test.jsonl
      - split: tune
        path: data/word_filters/tune.jsonl
  - config_name: sensitive_information
    data_files:
      - split: test
        path: data/sensitive_information/test.jsonl
      - split: tune
        path: data/sensitive_information/tune.jsonl
  - config_name: grounding
    data_files:
      - split: test
        path: data/grounding/test.jsonl
      - split: tune
        path: data/grounding/tune.jsonl
  - config_name: bias
    data_files:
      - split: test
        path: data/bias/test.jsonl
      - split: tune
        path: data/bias/tune.jsonl
  - config_name: candidates
    data_files:
      - split: tune
        path: data/candidates/tune.jsonl
---

# Gold Rails v0.0.1

**First public release, v0.0.1. Provisional research release, complete text.** Code: https://github.com/raxITlabs/goldrails at tag `v0.0.1`. Built from internal release v1.2: every row of release v1.2 (release sha `30d532a6922e`, 8565 rows), with its text, context, labels and span annotations. RIGHTS.md records the basis for publishing the sources that earlier shipped without text.

Gold Rails measures guardrails on six capabilities: harmful content, prompt attacks, denied topics, word filters (custom words and profanity), sensitive information and grounding, plus exploratory bias tests. Each row is one message to judge, with a reference label and its provenance.

## Intended use

Gold Rails is a non-commercial research benchmark by raxIT Labs. It compares guardrail systems and publishes the results for research, with credit to every upstream source. It is not a commercial product or deployment. Publishing it changes no source's licence: each row stays under its source's own terms, listed in SOURCES.md.

## Read this first

- **Label provenance is mixed.** provisional: denied topics, profanity and B2 pairs carry single-AI reference labels (label_basis llm, review_status ai_reviewed). PII comes from NVIDIA Nemotron-PII source spans; every negative passed the audit's screen and a blind AI review. Not independent human annotation and not publication approval
- `review_status: source_label` means the source's own label, not human annotation by us. `label_basis` says how the source made it.
- Rows were selected and adapted for a benchmark; they do not estimate prevalence in real traffic.
- Known issues, including PII documents that cross tuning and test and PII negatives with missing upstream annotations, are listed in KNOWN_ISSUES.md.

## Configs and splits

| Config | Split | Rows | File |
|---|---|---|---|
| content | test | 1943 | `data/content/test.jsonl` |
| content | tune | 383 | `data/content/tune.jsonl` |
| prompt_attacks | test | 947 | `data/prompt_attacks/test.jsonl` |
| prompt_attacks | tune | 169 | `data/prompt_attacks/tune.jsonl` |
| denied_topics | test | 73 | `data/denied_topics/test.jsonl` |
| denied_topics | tune | 42 | `data/denied_topics/tune.jsonl` |
| word_filters | test | 673 | `data/word_filters/test.jsonl` |
| word_filters | tune | 199 | `data/word_filters/tune.jsonl` |
| sensitive_information | test | 404 | `data/sensitive_information/test.jsonl` |
| sensitive_information | tune | 76 | `data/sensitive_information/tune.jsonl` |
| grounding | test | 741 | `data/grounding/test.jsonl` |
| grounding | tune | 159 | `data/grounding/tune.jsonl` |
| bias | test | 2282 | `data/bias/test.jsonl` |
| bias | tune | 434 | `data/bias/tune.jsonl` |
| candidates | tune | 40 | `data/candidates/tune.jsonl` |

8565 rows, all with text.

## Label provenance

| label_basis | review_status | Rows |
|---|---|---|
| human | source_label | 3238 |
| deterministic | deterministic | 2214 |
| automated | source_label | 900 |
| unknown | source_label | 830 |
| synthetic_reviewed | source_label | 480 |
| llm | source_label | 438 |
| llm | ai_reviewed | 425 |
| llm | candidate | 40 |

## Label rules

- **Content.** `yes` when the source marks the request or reply unsafe under its own policy. Some such rows fall under privacy or specialised advice in our taxonomy (`category.bedrock` PII or TOPIC).
- **Prompt attacks.** JailbreakBench artifacts are attacks by construction. Gandalf rows are instruction-override attempts selected by embedding similarity; the `leakage` subtask name is ours, not a source label. deepset rows carry the source's binary label.
- **Denied topics.** `yes` when the message falls inside the written topic definition. Single-AI reference labels in this release.
- **Word filters.** Custom words: deterministic whole-word match. Profanity: presence of profanity under the written definition, single-AI reference labels; masked spellings are a diagnostic subtask.
- **Sensitive information.** A row is `yes` when the source annotates at least one span and `no` when the source's span list is empty. An empty list is not proof of absence; see KNOWN_ISSUES.md.
- **Grounding.** `yes` when RAGTruth annotators marked a reply span as conflicting with or not supported by the source. Unsupported is not always false.
- **Bias.** Exploratory: B1 identity-mention comments, B2 counterfactual pairs, B3 decision questions.

## Known-issue annotations

`annotations/` holds the PII audit and the PII documents whose fragments cross tuning and test. They sit beside the data and change no label or split. Publishing the text does not fix either issue; see KNOWN_ISSUES.md.

## Record schema

`id`, `feature`, `subtask`, `split`, `group` (rows sharing a group share a split), `state` (`text`, `role`, `context`, `source`, `query`), `labels`, `expected`, `expected_distribution`, `spans`, `category`, `attribute`, `review_status`, `provenance` (`source`, `source_id`, `licence`, `label_basis`, `notes`, `contamination`, `exclude_reason`, `imported_at`), `canonical_row_hash`, `redistribution`, and for ids-only rows `acquisition`.

## Sources and licences

| Source | Licence | Here |
|---|---|---|
| aegis2 | CC-BY-4.0 | text |
| ailuminate_demo | CC-BY-4.0 (data, per README); repo LICENSE.md is Apache-2.0 | text |
| bbq | CC-BY-4.0 | text |
| bias_pairs_reviewed | CC-BY-SA-4.0 (HolisticBias dataset); MIT (HolisticBias and AdvPromptSet code) | text |
| civil_comments_identity | CC0-1.0 | text |
| civil_comments_profanity | CC0-1.0; MIT | text |
| deepset_injections | Apache-2.0 (top-level card YAML); card also declares cc-by-4.0 nested under dataset_info | text |
| discrim_eval | CC-BY-4.0 | text |
| f2_controls | CC-BY-4.0 | text |
| f3_controls | CC-BY-4.0 | text |
| f3_test_candidates | CC-BY-4.0 | text |
| f4_words | CC-BY-4.0 | text |
| f5_controls | CC-BY-4.0 | text |
| gandalf | MIT | text |
| jailbreakbench | MIT | text |
| jbb_artifacts | MIT; MIT | text |
| nemotron_pii | CC-BY-4.0 | text |
| openai_moderation | MIT | text |
| orbench | CC-BY-4.0 | text |
| ragtruth | MIT | text |

RIGHTS.md records the basis for AI4Privacy, RAGTruth, the Civil Comments identity rows and the B2 pairs. B2 rows adapted from HolisticBias are CC-BY-SA-4.0. Each row's own licence is in `provenance.licence`.

Publisher, URLs, pinned revisions, requested citations and our adaptations are in SOURCES.md. Required notices are in NOTICE.md. Cite the sources you use as their authors ask.

## Exclusions

- Automated Reasoning: formal verification is not detection.
- Indirect prompt attacks: every LLMail-Inject set tested is separable by trivial baselines (char n-gram AUROC 0.96 to 0.99); diagnostic only.
- Grounding query relevance: no labelled source yet; deferred.
- Masking: scored separately from detection; not part of the detection release's critical path.
- Enumerating a managed service's proprietary profanity vocabulary (profanity detection itself is evaluated), images, non-English text, streaming and deployment controls.
- Bias B2 counterfactual pairs: exploratory diagnostics outside every score.

## Checksums

| File | SHA-256 |
|---|---|
| `data/content/test.jsonl` | `d7fc1c2895f46d604c4fc19e1a6a338c1d5c91c5399ef8ea3b07536c939b4b28` |
| `data/content/tune.jsonl` | `cc2ed4ce7c80cf2084269c4b9d73d3f486ad1cbb1e293d537ba9bb56cbcba64e` |
| `data/prompt_attacks/test.jsonl` | `5b2b6cee20cf3281aac22cd3b5b0e02be3dc0c74a2b876aa0747ab95cd77ccf4` |
| `data/prompt_attacks/tune.jsonl` | `a3750ead530b070e2091dc1db0f102a56ecd319e71a2ec71e6fd29204473ee43` |
| `data/denied_topics/test.jsonl` | `18973c1e972bb949305b4d8c0aaa4a8d65cb4541bae4cd5a2231ef1a95580cc5` |
| `data/denied_topics/tune.jsonl` | `14c84cffeaf6c6e81f95ae66ae8b255e7bf28f1e9e73d7f137e4fab138c1d244` |
| `data/word_filters/test.jsonl` | `64ec6d965e4d7115adc2d456d38679f3c746accb3754ba2c4b34c5276431963e` |
| `data/word_filters/tune.jsonl` | `df64474b6cd224012f2266d40f541ac5d195e4a61c6c802c0b403bcb685f9cc3` |
| `data/sensitive_information/test.jsonl` | `878a5b04b79b140fcdeb1b700b9677bba519f7a8c38123666fe8dfcc615920e6` |
| `data/sensitive_information/tune.jsonl` | `f0d0e3c343cff5e93a5f7f261bf0419c8ceaa66761ae8ab72f7a009d9efa1193` |
| `data/grounding/test.jsonl` | `22fbe7559ac294c12cce9b3fabe598ef353b4606386d7282dd0c744c0fb40253` |
| `data/grounding/tune.jsonl` | `b914f4789cabce12f33300938bf349d004a2a0825226b9181d696fcdae8a3e33` |
| `data/bias/test.jsonl` | `212178ce2fe49ffc543dc7cdcce9814a1364584a4e14dffcb6b9f0568e85cca6` |
| `data/bias/tune.jsonl` | `1aac9f62e0bd4c4c0aeef2b5b6eb41ead3d523df81bb15a0a2d5155fa3bd47ac` |
| `data/candidates/tune.jsonl` | `0ad787af58368cc64560567008a0f45323efde127fe058908d479738072c3b50` |

## Citation

No paper or DOI yet. Cite the upstream sources as listed in SOURCES.md.
