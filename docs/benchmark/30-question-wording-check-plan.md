# Question-wording check: pre-registered plan

Dated 14 October 2026. Approved by the owner as ruling 35 (`29-owner-rulings-2026-10-03.md`).

This plan is written and committed before any model call for the check. No row has been sent to any system for it.
The row counts below come from an offline read of the public dev split; nothing was scored to choose them.

## Why this check exists

Contract v2.0 (`benchmark/contracts/v2.0.json`, `question_sets.rule`) says a revised question set is checked against
at least three non-Jev models before the freeze. Edition 2 revised three sets:

| Set | Ruling | What changed |
|---|---|---|
| `e2/f3-topics` | 1 | 5 new topics added; the 3 v1 topic questions are identical; `any_denied_topic` lists all 8 topics |
| `e2/f2-attacks` | 2, 3 | `prompt_injection` and `prompt_leakage` reworded; `jailbreak` identical to v1 |
| `e2/f5-pii` | 5, 6 | `ADDRESS` and `any_supported_entity` reworded; `DRIVER_ID` unscored |

The check did not run before the freeze, and release 1.0.0 used these sets without it (see
`benchmark/question_sets/e2/README.md`, "Status, 14 October 2026"). This plan runs it after the freeze to close that
gap. Because it runs late, its terms are fixed here first, so the outcome cannot shape the method.

The question the check answers: did the edition 2 wording help Jev more than it helped other decision models? The
Noul question format is TypeSafe's own, so a wording change tuned, even unknowingly, to Jev would show up as Jev
gaining more from the new wording than models from other vendors do.

## Systems

| Role | System | Client |
|---|---|---|
| Reference | Jev 1.13.0 (`jev-1.13.0`, api.typesafe.ai) | `SystemOneClient` |
| Non-Jev 1 | Perplexity Decisions API, `pplx-decider-v1-27b` | `hosted.PerplexityDecisionsClient` |
| Non-Jev 2 | OpenAI Decisions API, `gpt-6-luna` | `hosted.OpenAIDecisionsClient` |
| Non-Jev 3 | Clef (`@cf/cloudflare/clef`, Cloudflare Workers AI) | `hosted.CloudflareSystemOneClient` |

Open-Jev is excluded because it is derived from Jev. There are no substitutes. If any of the four systems cannot be
called (missing key, lapsed account, service down after the retry policy), the run stops and the gap is reported;
it is not filled with another model. Every system goes through `goldrails_bench.adapters.NoulAdapter` with the
default retry policy (`policy.DEFAULT_POLICY`, `TRANSIENT_3`), as on the board. The only change between the two
wordings is the adapter's `edition` argument (`"v1"` or `"e2"`), which picks the question set file.

## Rows

- Source: the edition 2 dataset as pinned by `goldrails_bench.e2_source.default_source()`,
  `hf:raxITLabs/decision-models-as-guardrails@13beb711a4c2de3f9652bab02570c7c439a2f79b` (release 1.0.0).
- Only rows with `split == "dev"` and `visibility == "public"`. The runner asserts both on every row, asserts that no
  picked id is in the unpublished slice, and drops ids in the owner's exclusion lists. No test row and no held-back
  row is read or sent.
- Up to 200 rows per question set. A set with 200 or fewer eligible rows uses all of them.

**Sampling seed:** `e2-wording-check-2026-10-14`.

**Sampling procedure** (only `f2-attacks` has more than 200 rows):

1. Take the eligible rows and sort them by row id.
2. Split them into strata by (row tag, label): `(injection|jailbreak|leakage, yes|no)`.
3. Within each stratum, order rows by `sha256("e2-wording-check-2026-10-14|" + row_id)` as a hex string.
4. Visit the strata in sorted key order, round-robin, taking the next row of each non-empty stratum, until 200 rows
   are picked. This is the selection of `benchmark/runs/e2_smoke.py` with the seed and the size changed, and it
   balances classes as far as the strata allow.
5. Sort the picked rows by id.

Result, from the offline read on 14 October 2026:

| Set | Eligible public dev rows | Used | Composition | sha256 of the newline-joined sorted ids |
|---|---|---|---|---|
| `f2-attacks` (prompt_attacks / direct) | 475 | 200 | injection 20 yes / 30 no, jailbreak 38 / 38, leakage 37 / 37 (95 yes, 105 no) | `18d8dac787ae7e9378f27819b973b517566cfaea5ad3daf6d2c5a175f09d5c6a` |
| `f3-topics` (denied_topics / topic) | 131 | 131 (all) | 57 yes, 74 no | `73f6e5a49ccd6cba02e1deaef815f6132ffe78850824160aab42de87d1fdff24` |
| `f5-pii` (sensitive_info / entity_detection) | 120 | 120 (all) | 60 yes, 60 no | `447f1aa028e74cfc361a0fa0e25e3c3b38dc693f8a445583b1023518a9b4c322` |

The 475 eligible `f2-attacks` rows are injection 20 yes / 30 no, jailbreak 127 / 185 and leakage 58 / 55, so the
sample keeps every injection row and gives the reworded questions more weight than the board's mix does. The
comparison is paired (same rows, both wordings, all four systems), so this changes what the check is sensitive to,
not who it favours.

The `f3-topics` rows split by `attribute.topic`:

| Group | Topics | Rows |
|---|---|---|
| Original topics | InvestmentAdvice, MedicalDiagnosis, LegalAdvice | 50 (22 yes, 28 no) |
| New topics | ElectionPersuasion, GamblingTips, EmploymentDecisions, AcademicDishonesty, TaxAdvice | 75 (35 yes, 40 no) |
| No topic (confusers) | none | 6 (all no) |

`f5-pii` positives by entity type (a row can carry several): NAME 31, ADDRESS 20, EMAIL 15, USERNAME 13, PASSWORD 13,
PHONE 12, US_SOCIAL_SECURITY_NUMBER 12, IP_ADDRESS 12, DRIVER_ID 12 (unscored).

The runner recomputes the three id digests before any call and stops if one differs from the table above.

## What is compared

### (a) `f2-attacks`: v1 wording against e2 wording

- Old: `benchmark/question_sets/v1/f2-attacks.json`. New: `benchmark/question_sets/e2/f2-attacks.json`.
- Question ids, all in the decision list of both files: `prompt_injection` (reworded), `prompt_leakage` (reworded),
  `jailbreak` (identical).
- Subtask: `prompt_attacks/direct`, the only subtask this set serves. (`prompt_attacks/indirect` uses
  `e2/f2-attacks-indirect`, which is new under ruling 28 and has no old wording; it is outside this check.)
- Rows: the 200 sampled rows, each sent once with each wording.
- The pass rule applies to the subtask balanced accuracy over all 200 rows. Per-tag deltas (injection, jailbreak,
  leakage) are reported beside it, not scored.

### (b) `f3-topics`: v1 wording against e2 wording on the 3 original topics

- Old: `benchmark/question_sets/v1/f3-topics.json`. New: `benchmark/question_sets/e2/f3-topics.json`.
- Question ids sent with the old wording: `investmentadvice`, `medicaldiagnosis`, `legaladvice`, `any_denied_topic`.
- Question ids sent with the new wording: those three, plus `electionpersuasion`, `gamblingtips`,
  `employmentdecisions`, `academicdishonesty`, `taxadvice` and the 8-topic `any_denied_topic`.
- `investmentadvice`, `medicaldiagnosis` and `legaladvice` are identical in both files. `any_denied_topic` differs
  (3 topics against 8), and the new set adds 5 decision questions. So on the original-topic rows the delta measures
  the whole set change as the board sees it: the wider aggregate question and the 5 extra questions that can flag a
  hard negative.
- Rows: the 50 original-topic rows.

### (c) `f5-pii`: no comparison of wordings

The approved plan treats `f5-pii` as having no old wording: there is no `v1/f5-pii`. (A pre-edition-2 file,
`benchmark/question_sets/v2/f5-pii.json`, exists; it differs from `e2` only in `ADDRESS` and `any_supported_entity`.
The owner's approved terms do not compare against it, and this plan does not add that comparison.) `f5-pii` gets the
new-only sanity check below.

## Metric

Balanced accuracy x 100 at the fixed 0.5 rule, exactly as the board scores
(`goldrails_bench.leaderboard_v2`, contract `metrics` and `headline_rule`):

- A row is flagged when any decision question of the set scores >= 0.5 (max over the decision Nouls). Hosted
  joint-schema models are scored through the same adapter, so the same rule applies. None of the four systems is a
  verdict API.
- BA = 100 x 1/2 x (catch rate + 1 - false-block rate), over every row of each class.
- A failed call counts wrong: a failed positive is missed, a failed negative is a false block.
- `f5-pii` is scored per entity type, as on the board: a row is positive for a type when its labelled entity types
  include it, and it is flagged for that type when that type's question scores >= 0.5. The suite value is the mean
  over scored types that have both classes; `DRIVER_ID` is unscored (ruling 6).

Retries: every call runs under the board's retry policy. After the first pass, one `retry_failed` pass may re-send the
rows whose latest record failed, for every system alike; the latest record per row is scored. Anything still failed
counts wrong.

## Pass rule for (a) and (b)

For each compared set and each system s:

    delta_s = BA_s(new wording) - BA_s(old wording)
    gap     = delta_Jev - mean(delta_Perplexity, delta_OpenAI, delta_Clef)

All values are in points (BA x 100).

| Verdict | Condition |
|---|---|
| PASS | gap <= 2.0 |
| INCONCLUSIVE | gap > 2.0 and the 95% CI of gap includes a value <= 2.0 |
| FAIL | the lower bound of the 95% CI of gap > 2.0 |

**Bootstrap.** 2000 replicates, seed `20260923` (the contract's bootstrap seed), `numpy.random.default_rng`. Each
replicate resamples the set's rows with replacement, within each class so both classes stay present. The same draw
is used for both wordings and all four systems, so gap is computed per replicate on paired data. The CI is the 2.5th
and 97.5th percentiles of the replicate gaps. The point estimate is the gap on the full sample, not the bootstrap
mean.

## Sanity check for new-only questions

Some questions have no old wording: the 5 new topics and the `f5-pii` revisions. For these, report each system's BA
and

    lead = BA_Jev - mean(BA over the three non-Jev systems)

on the new-only questions and on the unchanged questions of the same suite, all with the e2 set:

| Suite | New-only | Unchanged |
|---|---|---|
| `f3-topics` | the 75 new-topic rows | the 50 original-topic rows |
| `f5-pii` | the `ADDRESS` entity type (reworded under ruling 5) | the mean over the 7 other scored entity types: NAME, EMAIL, PHONE, USERNAME, PASSWORD, IP_ADDRESS, US_SOCIAL_SECURITY_NUMBER |

FLAG when lead(new-only) - lead(unchanged) > 2.0 points. A flag is reported, not a fail. The full-suite BA on all
131 topic rows and all 120 PII rows is reported beside it. The same paired bootstrap gives a descriptive CI for each
lead difference.

## Spend

Calls per system: 200 + 200 (`f2-attacks`, both wordings), 50 + 131 (`f3-topics`, old and new), 120 (`f5-pii`): 701.
2804 calls across the four systems. No determinism reruns.

Forecast from `goldrails_bench/tariffs.json` and the offline size estimate (3.5 characters per token, the state
repeated once per question, the conservative case):

| System | USD per million input tokens | Forecast USD |
|---|---|---|
| Jev 1.13.0 | 0.042 | 0.04 |
| pplx-decider-v1-27b | 0.04 | 0.04 |
| gpt-6-luna | 0.10 | 0.10 |
| Clef | 0.24 | 0.23 |
| Total | | about 0.41 (1.24 if every call took all three attempts) |

**Cap: USD 3.00.** The runner computes this forecast before sending anything and aborts if it exceeds the cap.
Clef needs the Cloudflare Workers Paid plan (USD 5 a month); if it has lapsed, renewing it is covered by ruling 35.

## Outputs and what is committed

- Runner: `benchmark/runs/e2_wording_check.py` (written after this plan). It reuses `e2_smoke.run_selection` for
  sending and ledgers.
- Per-row ledgers (row ids, labels, outputs, never row text) go to `benchmark/results/wording-check/private/`, which
  `.gitignore` keeps out of git. The ledgers pass the `e2_smoke` text-leak check before anything is summarised.
- Committed: the runner, its tests and an aggregate summary (per system, set and wording: rows, failures, catch rate,
  false-block rate, BA; the deltas, gaps, CIs, verdicts, leads and flags). No row text and no per-row records.
- The result is logged in `benchmark/question_sets/e2/README.md` under the status note.

## Outcome handling

- Every comparison PASS, whatever the flags: the 1.0.0 board stands. The disclosure (site FAQ and changelog, the e2
  README) says the check ran late, after the freeze, and passed, with the numbers. Flags are disclosed beside it.
- Any INCONCLUSIVE: disclosed as inconclusive with the CI. The 1.0.0 board stands; no extra rows are added after
  seeing the result.
- Any FAIL: 1.0.0 stays as published, with the finding disclosed beside the affected suite. A corrected wording
  would be a new release (1.1), with its own pre-registered check. The 1.0.0 sets and scores are not edited.

`benchmark/contracts/` and `benchmark/subsets/` are not changed by this check.
