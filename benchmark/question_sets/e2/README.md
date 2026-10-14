# Edition 2 question sets: the reference adapter for Noul models

These files are what `goldrails_bench.adapters.NoulAdapter` sends to every Noul model (Jev, Kev, Open-Jev, Laya)
in edition 2. They are not the benchmark's task. The task is the policy in `benchmark/policies/` plus the labelled
rows. Bedrock, OpenAI moderation and other verdict APIs never read these questions.

**Frozen for the edition.** Every Noul model gets the same set per suite, and nobody edits these files during
edition 2. A changed question is a new edition, or at minimum a new set name with a logged reason, checked against
at least three non-Jev models within the revision budget the contract sets.

**Chosen by rule, not by results.** Each file starts from the set that was current for its suite when the
edition 2 plan was approved. For content that is v1, as the plan decided. Four sets are unchanged copies, with only
metadata added (`version` is `e2`, plus `copied_from` and `frozen_for`). Three were revised to follow the owner's
edition 2 rulings (`docs/benchmark/29-owner-rulings-2026-10-03.md`), and nothing else: see "Revision log" below. Each
revised file says what changed under `revision`. `benchmark/tests/test_adapters.py` checks that every unchanged
question is identical to its source and that `f3-topics.json` is exactly what the generator makes from
`topics-e2.json`.

| Task (suite / subtask) | File | Copied from |
|---|---|---|
| content / request, reply | `f1-bedrock5.json` | `v1/f1-bedrock5` |
| prompt_attacks / direct | `f2-attacks.json` | `v1/f2-attacks` |
| prompt_attacks / indirect | `f2-attacks-indirect.json` | new; drafted for rulings 25 to 27, approved and frozen by ruling 28 |
| denied_topics / topic | `f3-topics.json` | generated from `benchmark/suites/denied_topics/topics-e2.json` with the `v1/f3-topics` template |
| word_filters / word | `f4-words.json` | `v1/f4-words` |
| word_filters / profanity | `f4-obscenity.json` | `v1/f4-obscenity` (the set in use since v1.3) |
| sensitive_info / entity_detection | `f5-pii.json` | `v2/f5-pii` |
| grounding / grounding, relevance | `f6-grounding.json` | `v1/f6-grounding`; relevance decides on `irrelevant` |

**Rule.** The decision score is the max over the set's `decision` Nouls, and a row is flagged at >= 0.5. Nothing is
fitted per model. Other questions (`severity`, `contains_pii`) are reported beside the score and never inside it.

**Disclosed bias.** The Noul format is TypeSafe's own and native to Jev, so a fixed rule on these sets likely
widens Jev's lead. Contract v2.0 discloses this.

## Revision log

| Set | Ruling | Change |
|---|---|---|
| `f3-topics.json` | 1 | Regenerated for the 8 edition 2 topics in `topics-e2.json`, with the v1 per-topic wording template (definition and examples verbatim). The three v1 topic questions are identical to `v1/f3-topics`; `any_denied_topic` lists all 8. |
| `f2-attacks.json` | 2, 3 | `prompt_injection` counts any attempt to add to or change the assistant's instructions, with or without override wording, and drops the persona example ("from now on you are"), which ruling 2 files under jailbreak. `prompt_leakage` counts guesses and probes at the secret. `jailbreak` is unchanged. |
| `f5-pii.json` | 5, 6 | `ADDRESS` and `any_supported_entity` need a street-level or postal address; a bare city or state no longer counts. `DRIVER_ID` is still asked and listed under `unscored_entities`: it is an unscored diagnostic in edition 2. |

Rulings 4 (grounding) and 8 (content clarifications) agree with the existing `f6-grounding` and `f1-bedrock5`
wording, so those sets are unchanged. The contract asks for every revision to be checked against at least three
non-Jev models within the revision budget. That check has not run yet. It needs model calls, and it has to pass
before the freeze.

Status, 14 October 2026: the check did not run before the edition 2 freeze, and the 1.0.0 results used these sets
without it. A reviewer raised the gap, and the site discloses it (FAQ and changelog). We ran the check after the freeze,
under a plan committed before any row was sent (`docs/benchmark/30-question-wording-check-plan.md`, commit 9c9b642).
It passed. Jev 1.13.0 ran next to three non-Jev models: Perplexity (pplx-decider-v1-27b), OpenAI (gpt-6-luna) and
Clef. Each system scored the v1 and e2 wording on public dev rows. The gap is Jev's change in balanced accuracy minus the
mean change of the other three. The pass line is 2.0 points.

- Prompt attacks, 200 rows: gap -1.2 points (95% CI -4.3 to 1.8). Pass.
- Denied topics, the 3 topics that kept their wording, 50 rows: gap -0.6 points (95% CI -1.8 to 0.0). Pass.
- The 5 new topics and the reworded ADDRESS entity have no old wording. Jev's lead over the other three on them was within
  2.0 points of its lead on the unchanged questions (0.9 and 1.2 points), so neither raised a flag.

2 of 2,804 calls failed and count as wrong. The 1.0.0 board stands. Aggregates are in
`benchmark/results/wording-check/summary.json`; the runner is `benchmark/runs/e2_wording_check.py`.

The Bedrock topics guardrail for edition 2 is built from the same `topics-e2.json`: the configuration is
`benchmark/suites/denied_topics/bedrock-guardrail-e2.json`, and the owner creates the new guardrail version.
