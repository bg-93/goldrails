# First benchmark: corrections after the run

The freeze manifest (`benchmark/subsets/first-benchmark/freeze-manifest.json`, commit 6f5390a, 05:18:01 UTC) and the
original test ledger are unchanged. Every correction below changes scoring or reporting code only; none needed new
model calls, and the evaluator keeps flagging "scoring code changed since the freeze" as a publication blocker.

| Date | What changed | Why | Effect | Code |
|---|---|---|---|---|
| 23 Sep | 51 test rows that failed on dropped connections were re-attempted under the same frozen configuration (`test-rerun.jsonl`); all succeeded | The retry matcher missed the SDK's `TypeSafeAPIConnectionError` prefix | Original view kept as `leaderboard-original.json` | debf870 |
| 23 Sep | A successful re-attempt in another ledger supersedes its failed original; the original failure count stays on each arm (`recovered_after_failure`) | The corrected view had scored the 51 failures (no credit) beside their re-attempts | Original run to corrected: Open-Jev 2B content 63.2 to 70.1, Kev 0.8B prompt attacks 72.1 to 75.8, Kev 0.8B word filters 68.8 to 71.9, Open-Jev 2B word filters 78.1 to 79.4 (the double-counted corrected view had shown 65.0, 72.2, 68.7 and 78.5); top three per suite unchanged | 5ab9d5e |
| 23 Sep | Serving windows rebuilt as earliest (completion minus attempt latency) to latest completion; sub-second overlaps split | The old script treated completion times as start times and added latency at the end | Most arms move by about a second; Kev 0.8B prompt attacks and word filters gain 57 s and 30 s of timed-out first attempts | 983ed67 |
| 23 Sep | Self-hosted cost sums the original test session and the rerun session and divides by unique cases | Only the first matching serving record was used, which dropped the rerun's GPU time | Kev 0.8B prompt attacks $0.729 per 1,000 (was $0.625), word filters $0.850 ($0.737); Open-Jev 2B content $0.440 ($0.405) | 983ed67 |
| 23 Sep | Future runs record `started_at` and `ended_at` per attempt to the millisecond | Completion time to the second is too coarse for serving windows | Applies to runs after this date | 983ed67 |

Files: `serving-test-original.json` (test pass only, used by the original view), `serving-test-corrected.json` (test
pass plus rerun, used by the corrected view), `serving-all.json` (every stage, for the spend reconciliation in
docs/22). `serving-test.json` and `serving.jsonl` hold the superseded windows.

## Reporting changes after the data review (23 September 2026)

These change what the page says, not any primary score.

- **PII sensitivity view.** Eight selected test rows carry SSN labels inferred from number format alone, and every SSN positive in the subset is one of them. `leaderboard-pii-strict.json` rescores sensitive information with the SSN entity type left out (`--exclude-entity-type US_SOCIAL_SECURITY_NUMBER`). It is marked as a sensitivity analysis and shown beside the primary score, never in place of it. Jev 96.2 (primary 96.2), Bedrock 95.0 (primary 94.4); intervals still overlap.
- **Bias marked exploratory.** discrim-eval: 50 cases over 31 scenarios, 19 with one case, none for the full reference demographic, so groups mostly answered different scenarios. Civil Comments: 100 comments with 1 to 18 per identity. `bias.json` carries a `status` block saying so; the page no longer quotes discrim-eval group gaps.
- **Data scope on the page.** A table of sources, label basis, test rows, independent groups, and what each suite does and does not support, generated from the subset manifest and the release build.
- **Interval caveat.** The page states that intervals measure sampling uncertainty only, not label errors, source artifacts or possible training exposure.

## Approval of the corrected analysis (23 September 2026)

The project owner approved the scoring fixes in commits 5ab9d5e, 983ed67 and 23792fb as a corrected analysis:
`benchmark/subsets/first-benchmark/analysis-approval-1.json`, committed in 39d3d68. It names the primary freeze
manifest, the frozen scoring code (sha256 f1abaf9a…) and the approved code (3e962480…, commit c7f1c97), and lists what
did not change: question sets, frozen thresholds, contract, bootstrap, test rows, retry policy and the original results.
The leaderboard accepts the changed scoring code only with `--analysis-approval` pointing at that committed file, and
records it in `analysis_versions` on every result. Any further change to the scoring code needs a new approval.

## Contract v1.1, approvals 3 and 4, and the provisional extension (23 to 24 September 2026)

No frozen threshold, question set or core test row changed. The five core categories keep the scores, intervals and
costs of the corrected five-category view (`leaderboard-corrected.json`); `benchmark/runs/check_page.py` compares all
36 core arms on every run.

| Date | What changed | Why | Effect | Code |
|---|---|---|---|---|
| 23 Sep | Contract v1.1 splits word filters into custom words and profanity at equal weight. Masked spellings are a diagnostic outside the score | Custom words alone did not test the managed profanity list Bedrock offers | Custom-word scores unchanged. The word-filters category is the mean of the two checks | 5e7874a |
| 23 Sep | Approval 3 consolidated the corrected analysis for scoring code 5e7874a and contract v1.1. Approvals 1 and 2 stay as history | One approval per scoring-code hash | v1.0 views rebuilt; scores, intervals and costs unchanged | 39d0a50 |
| 23 Sep | A composed category costs the sum of its component checks per message | Each message runs every component check | Word-filters category cost is custom words plus profanity | 0744223 |
| 23 Sep | Approval 4 names scoring code 0744223 and contract v1.1. The developer recorded it from the owner's written instructions, and its `confirmation` block is still empty | Code changed after approval 3 | The evaluator scores under it and keeps a publication blocker until the owner confirms | ed79005 |
| 24 Sep | Amendment A: denied topics, profanity and B2 use single-AI reference labels (Codex, 24 Sep) with `label_basis: llm`. The contract hash is unchanged | The owner chose an AI judge in place of human review to move this version forward | Those results are marked provisional everywhere they appear | 5ba8173 |
| 24 Sep | Provisional dataset v1.1-ai and subset first-benchmark-v1.1-ai, frozen before any extension call | Admits the AI-labelled rows and excludes unresolved ones with reasons | Core test rows identical to first-benchmark, checked per subtask | 827b659 |
| 24 Sep | Extension 1 (Jev and open models) frozen on tuning rows, then tested | Denied topics, profanity and B2 were not in the primary freeze | 1,584 rows; two Open-Jev failures kept with no credit | 3c88be6, 9186507 |
| 24 Sep | Extension 2 (Bedrock) frozen at the binary operating point, then tested | Same | 272 rows, no failures | a08a3b3, 9c3e8e8 |
| 24 Sep | The page draws one overall chart against cost and six category charts. Word filters appear as one category, with its score, interval and cost read from the frozen overall block | Release layout | Custom words and profanity stay as separate rows in the verdict ledger and the table | this commit |
| 24 Sep | The page no longer shows an overall latency | It pooled serial samples across categories, and the self-hosted models had no serial pass for the two new categories, so their pool covered fewer categories than Jev's or Bedrock's | Overall is compared on cost only; latency stays per category | this commit |

## Data-quality review (24 September 2026)

A review of the sources, labels and publication package (`docs/research/data-quality-team-2026-09-24/`) found issues
in the data behind the results. Every finding was checked against the release before anything changed. No frozen
data, threshold, ledger or primary score changed, and nothing was re-run.

| Finding | What we did | Effect on results | Code |
|---|---|---|---|
| AI4Privacy fragments of one document were grouped separately, so 3 documents (4 test rows, 3 tuning rows) cross tuning and test in the selected subset; 34 documents (80 rows) in the release | PII rows are no longer described as independent held-out documents. Parent grouping is available for the next version | View without the 4 test rows: Jev 96.2 to 96.2, Bedrock 94.4 to 94.1 | 822e9e5 |
| Empty source annotations were read as negatives; some contain supported entities | One blind AI review of all 450 PII negatives, then a second blind review of 63 of them (43 flagged by the first review plus 20 absent controls). Both reviews marked 20 rows present (3 selected test rows, 3 tuning rows); the other 387 rows had one review. Original labels kept; corrections in `dataset/frozen/corrections/pii-negatives-2026-09-24.jsonl` apply to the next version | View without the 3 test rows: Jev 96.2 to 96.3, Bedrock 94.4 to 94.5. The 3 tuning rows may have moved thresholds; no view can undo that | 822e9e5 |
| Gandalf rows carry our `leakage` subtask, which the source does not label | Described as a noisy attack proxy; no leakage-specific claim | View without the 80 Gandalf rows: Jev 98.8 to 98.4, Bedrock 86.9 to 80.9 | 822e9e5 |
| 32 of 240 unsafe content test rows fall under privacy or specialised advice in our taxonomy | Reported as agreement with the sources' policies, with a per-category breakdown | View without them: Jev 78.9 to 80.2, Bedrock 78.7 to 79.4 | 822e9e5 |
| The dataset card described v1.0 with wrong paths; notices were missing; AI4Privacy annotations were not cleared for redistribution | Publication staging generated from the release, with source registry, verbatim notices and reconstruction steps; AI4Privacy rows withheld | None | 1453b92 |
| Release builds wrote files before checking immutability | Builds go to a temporary directory; an existing version is never rewritten | None | 822e9e5 |

The views follow rules committed in cc80247 before any was computed, use the unchanged evaluator and frozen
thresholds, and are reported for every system (`sensitivity-2026-09-24.json`). None changes a Jev and Bedrock
verdict. A clean held-out PII result would need a fresh PII test selection after the grouping repair.

## PII source replaced: NVIDIA Nemotron-PII, dataset v1.2 (28 September 2026)

AI4Privacy's licence did not allow publishing its rows, and the data-quality review had found document overlap
across tuning and test and missing annotations. After a bounded audit
(`dataset/frozen/reviews/nemotron-pii-audit-2026-09-28/AUDIT.md`), PII uses NVIDIA Nemotron-PII (CC-BY-4.0, test
split) in dataset v1.2. Only the PII files differ from v1.1-ai; subset first-benchmark-v1.2 keeps every other row.

| Step | Commit |
|---|---|
| Audit, loader, release v1.2 and subset; every chosen negative blind-reviewed | 1d1e936 |
| Extension manifest 3: frozen PII questions, thresholds refitted on the 50 tuning rows, committed before any test call | cc7918e |
| 160 test rows per system, 0 failures; serial latency; leaderboard-v1.2.json | d79a38c |

PII: Jev 96.8 [95.8, 97.7], Bedrock 96.7 [94.1, 98.8], no clear difference, as before. Overall: Jev 91.9, Bedrock
80.5, difference 11.4 [8.9, 13.8]. The earlier PII results, their post-hoc views and the strict SSN view stay in
`leaderboard-provisional.json`, `leaderboard-pii-strict.json` and `sensitivity-2026-09-24.json`. Driver's licence
numbers are not measured: the source has no such label.
