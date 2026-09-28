# Gold Rails v1.2 counts

Generated from `dataset/release/v1.2/manifest.json`. 8565 rows.

| Suite | Subtask | Split | Class | Review status | Rows |
|---|---|---|---|---|---|
| bias | b1_disparate_fpr | test | no | source_label | 382 |
| bias | b1_disparate_fpr | test | yes | source_label | 380 |
| bias | b1_disparate_fpr | tune | no | source_label | 68 |
| bias | b1_disparate_fpr | tune | yes | source_label | 70 |
| bias | b2_counterfactual | test | no | ai_reviewed | 4 |
| bias | b2_counterfactual | test | yes | ai_reviewed | 4 |
| bias | b2_counterfactual | tune | no | ai_reviewed | 4 |
| bias | b2_counterfactual | tune | yes | ai_reviewed | 4 |
| bias | b3_decision | test | None | source_label | 381 |
| bias | b3_decision | test | ans0 | deterministic | 381 |
| bias | b3_decision | test | ans1 | deterministic | 381 |
| bias | b3_decision | test | ans2 | deterministic | 369 |
| bias | b3_decision | tune | None | source_label | 69 |
| bias | b3_decision | tune | ans0 | deterministic | 69 |
| bias | b3_decision | tune | ans1 | deterministic | 69 |
| bias | b3_decision | tune | ans2 | deterministic | 81 |
| content | harmful_goal | test | no | source_label | 85 |
| content | harmful_goal | test | yes | source_label | 85 |
| content | harmful_goal | tune | no | source_label | 15 |
| content | harmful_goal | tune | yes | source_label | 15 |
| content | input | test | no | source_label | 369 |
| content | input | test | yes | source_label | 372 |
| content | input | tune | no | source_label | 81 |
| content | input | tune | yes | source_label | 78 |
| content | output | test | no | source_label | 338 |
| content | output | test | yes | source_label | 315 |
| content | output | tune | no | source_label | 63 |
| content | output | tune | yes | source_label | 60 |
| content | over_refusal | test | no | source_label | 379 |
| content | over_refusal | tune | no | source_label | 71 |
| denied_topics | topic | test | no | ai_reviewed | 44 |
| denied_topics | topic | test | yes | ai_reviewed | 29 |
| denied_topics | topic | tune | no | ai_reviewed | 23 |
| denied_topics | topic | tune | yes | ai_reviewed | 19 |
| grounding | grounding | test | no | source_label | 359 |
| grounding | grounding | test | yes | source_label | 382 |
| grounding | grounding | tune | no | source_label | 91 |
| grounding | grounding | tune | yes | source_label | 68 |
| prompt_attacks | injection | test | no | source_label | 206 |
| prompt_attacks | injection | test | yes | source_label | 116 |
| prompt_attacks | injection | tune | no | candidate | 10 |
| prompt_attacks | injection | tune | no | source_label | 37 |
| prompt_attacks | injection | tune | yes | source_label | 21 |
| prompt_attacks | jailbreak | test | yes | deterministic | 243 |
| prompt_attacks | jailbreak | tune | no | candidate | 4 |
| prompt_attacks | jailbreak | tune | yes | deterministic | 43 |
| prompt_attacks | leakage | test | yes | source_label | 382 |
| prompt_attacks | leakage | tune | no | candidate | 6 |
| prompt_attacks | leakage | tune | yes | source_label | 68 |
| sensitive_information | pii | test | no | source_label | 192 |
| sensitive_information | pii | test | yes | source_label | 212 |
| sensitive_information | pii | tune | no | candidate | 20 |
| sensitive_information | pii | tune | no | source_label | 38 |
| sensitive_information | pii | tune | yes | source_label | 38 |
| word_filters | profanity | test | no | ai_reviewed | 126 |
| word_filters | profanity | test | yes | ai_reviewed | 80 |
| word_filters | profanity | tune | no | ai_reviewed | 32 |
| word_filters | profanity | tune | yes | ai_reviewed | 20 |
| word_filters | profanity_obfuscated | test | yes | ai_reviewed | 31 |
| word_filters | profanity_obfuscated | tune | yes | ai_reviewed | 5 |
| word_filters | word | test | no | deterministic | 348 |
| word_filters | word | test | yes | deterministic | 88 |
| word_filters | word | tune | no | deterministic | 102 |
| word_filters | word | tune | yes | deterministic | 40 |

## Redistribution

| Source | Mode |
|---|---|
| aegis2 | text |
| ailuminate_demo | text |
| bbq | text |
| bias_pairs_reviewed | ids_only |
| civil_comments_identity | ids_only |
| civil_comments_profanity | text |
| deepset_injections | text |
| discrim_eval | text |
| f2_controls | text |
| f3_controls | text |
| f3_test_candidates | text |
| f4_words | text |
| f5_controls | text |
| gandalf | text |
| jailbreakbench | text |
| jbb_artifacts | text |
| nemotron_pii | ids_only |
| openai_moderation | text |
| orbench | text |
| ragtruth | ids_only |

## Exclusions

- Automated Reasoning: formal verification is not detection.
- Indirect prompt attacks: every LLMail-Inject set tested is separable by trivial baselines (char n-gram AUROC 0.96 to 0.99); diagnostic only.
- Grounding query relevance: no labelled source yet; deferred.
- Masking: scored separately from detection; not part of the detection release's critical path.
- Enumerating a managed service's proprietary profanity vocabulary (profanity detection itself is evaluated), images, non-English text, streaming and deployment controls.
- Bias B2 counterfactual pairs: exploratory diagnostics outside every score.
