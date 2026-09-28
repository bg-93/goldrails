# First benchmark: evidence for sign-off

Generated from the repository. It shows evidence for sign-off; it is not the sign-off itself.

## Code and contract

- Freeze manifest: `benchmark/subsets/first-benchmark/freeze-manifest.json`, commit 6f5390a (23 Sep 2026 05:18 UTC),
  scoring code sha256 f1abaf9a..., contract hash 29085f28aec4a4a9.
- Scoring code now: sha256 92a74bcc31c2..., commit 0744223.
- Tests at this commit: `298 passed, 1 skipped in 11.39s`.

Commits that touched scoring code, the contract or the first-benchmark manifests since the freeze:

```
ed79005 2026-09-23 Approval 4 recorded for scoring code 0744223 and contract v1.1; awaiting the owner's confirmation
0744223 2026-09-23 Review response: second-review sample plan and agreement report, frozen profanity reserves, composed cost as a sum, confirmed approvals, live guardrail policy, bias licence note
39d0a50 2026-09-23 First benchmark: consolidated approval 3 (final scoring code 5e7874a and declared contract v1.1); approvals 1 and 2 kept as history
5e7874a 2026-09-23 Profanity subtask and denied-topics completion: reviewed-label replacement, profanity packet, contract v1.1 and composed word filters
cb2b907 2026-09-23 First benchmark: consolidated approval of the corrected analysis for the final scoring code (cb0a986); approval 1 kept as history
cb0a986 2026-09-23 Release completion: B2 pair clearance, review status report, pre-registered overall implementations, unpriced baseline disclosed, overall on the page
ea15e6a 2026-09-23 Freeze: extension manifests add later-eligible arms (such as reviewed denied topics) beside the primary
39d3d68 2026-09-23 First benchmark: owner approval of the corrected analysis (scoring fixes 5ab9d5e, 983ed67, 23792fb; frozen questions and thresholds unchanged)
c7f1c97 2026-09-23 Leaderboard: a committed approval can accept changed scoring code as a labelled corrected analysis
23792fb 2026-09-23 Data review: PII sensitivity view without format-inferred SSN labels, bias marked exploratory, data-scope table on the page
983ed67 2026-09-23 Review fixes: serving windows from completion minus latency, rerun GPU time charged, 'no clear difference' wording, serial latency on the page
5ab9d5e 2026-09-23 Leaderboard: a successful re-attempt in another ledger supersedes the failed original
```

Contract diff, v1.0 to v1.1. The only change is profanity joining word filters with equal weight:

```diff
--- contract v1.0 (DEFAULT_CONTRACT)
+++ benchmark/contracts/v1.1.json
@@ -16,2 +16,6 @@
   "seed": 20260923
+ },
+ "change_from": {
+  "change": "word_filters gains a profanity subtask, equal weight with custom words; profanity_obfuscated is a diagnostic outside the score; nothing else changes",
+  "version": "v1.0-draft"
  },
@@ -108,2 +112,7 @@
    "subtasks": {
+    "profanity": {
+     "tags": [
+      "profanity"
+     ]
+    },
     "word": {
@@ -116,3 +125,3 @@
  },
- "version": "v1.0-draft"
+ "version": "v1.1-draft"
 }
```

## Tuning-only selection and thresholds

- The first benchmark's question-set choice and thresholds come from `tune.jsonl` alone. The splits in that file are
  ['tune'], across 3942 records. Tuning mode
  fits and reports only rows recorded as tune.
- The extension freeze (`benchmark/runs/extension_run.py freeze`) refuses to run if `ext-tune.jsonl` holds any
  non-tuning record.
- The runner refuses every test row until a committed manifest lists the exact arm.

## Historical scores

Rebuilding `leaderboard-original.json`, `leaderboard-corrected.json` and `leaderboard-pii-strict.json` under the
current code gave 0 differences in any score, interval or cost across 36 arms each, compared with the previously
committed files. The v1.0 word-filters score, custom words only, stays published as historical.

## The any_word defect

`benchmark/runs/check_any_word.py` read every stored raw Bedrock response of the frozen custom-word arm. It found
260 rows, 0 managed-profanity detections, and 0 rows where
`any_word` differed from the maximum over the four custom words. No result was affected. The output is in
`any-word-check.json`.

## Approvals

The approval files let the evaluator score the corrected analysis. None is the owner's sign-off until the owner
confirms it, and the evaluator keeps a publication blocker until then.

| Approval | Scoring code | Contract | Recorded by | Owner confirmation |
|---|---|---|---|---|
| 1 | 3e9624800a7e | v1.0 unchanged | Claude (developer), from the owner written instructions | not confirmed |
| 2 | 06bf97aca4b1 | v1.0 unchanged | Claude (developer), from the owner written instructions | not confirmed |
| 3 | 4388091ba39d | 463b3349d8c7de6e | Claude (developer), from the owner written instructions | not confirmed |
| 4 | 92a74bcc31c2 | 463b3349d8c7de6e | Claude (developer), from the owner's written instructions of 23 September 2026 | not confirmed |

Approvals 1 to 3 approved earlier code versions and are kept as history. Approval 4 matches the current code.

## Release check (24 September 2026)

No model calls. Everything below reads committed files.

- **The frozen results reproduce.** Rebuilding the leaderboard from the committed ledgers, manifests and approval 4
  in a clean worktree gives the same 50 arms and the same overall as `leaderboard-provisional.json`.
- **The page matches them.** `benchmark/runs/check_page.py` passes 14 of 14 checks (`page-check.json`). Every
  arm appears once with its frozen score, interval, cost, rows and threshold. Every threshold equals its freeze
  manifest's, and the three manifests are committed and unchanged. Both extension manifests were committed before the
  test rows they govern. The overall matches the frozen overall block, with its cost the mean of the six category
  costs and word filters the sum of its two checks. The five core categories equal the corrected five-category view
  in all 36 arms. Denied topics, profanity and the overall are marked provisional. Bias matches `bias.json` and stays
  outside the overall. Every correction on the page is in `CORRECTIONS.md`. The page carries the leaderboard's
  blockers.
- **The rendered page matches the data.** `benchmark/runs/check_page_dom.js`, run on the served page, compared 113
  plotted and tabled scores with `results.json` and found no mismatch.
- **Sign-off path tested.** In a throwaway worktree, with a placeholder name, `benchmark/runs/sign_off.py` signed
  contract v1.1 and wrote approvals 5, 5-ext1 and 5-ext2. The rebuilt leaderboard had no publication blockers and
  identical arms and overall. Signing the contract by hand without those approvals leaves three blockers, because
  each freeze manifest pinned an earlier contract hash. The real files are untouched.
