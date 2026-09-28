# Release review: the labels the benchmark still needs

These four packets are the only human labelling left before release. Nothing else in the dataset waits on a
person.

| Packet | Folder | Cases | Judgments per case | Reviewer A | Reviewer B (sample plan) |
|---|---|---|---|---|---|
| Denied-topics controls | `f3-denied-topics/` | 28 | 3 topics | 28 | 7 |
| Denied-topics candidates | `f3-test-candidates/` | 90 | 3 topics | 90 | 30 (9 ambiguous, 21 random) |
| Profanity candidates | `f4-profanity/` | 280 | 1, plus exclude if unjudgeable | 280 | 100 (40 quoted or mild, 60 random) |
| Counterfactual pairs | `bias/b2-v0/` | 22 pairs (44 texts) | 6 (two actions, four checks) | 22 | 22 |

Reviewer A makes about 770 judgments and reviewer B about 340. A **named adjudicator**, who is neither reviewer,
settles disagreements and unclear answers after both have submitted.

**Second review.** Reviewer B gets every ambiguous case plus a seeded random 25% of the rest, stratified by drafted
label (`uv run python -m goldrails_dataset.review_plan --mode sample`, recorded in each lead key). So agreement
describes the whole dataset, not only the hard cases. Full double review of every case is one command
(`--mode full`) and raises reviewer B to about 770 judgments. The owner chooses before the packets go out.
`reviews --status` reports agreement and Cohen's kappa before adjudication, and every exclusion with its reason.

Neither reviewer may have written the cases or be tuning anything. Each works alone and never sees model outputs,
scores or the `_lead/` folder.

For the denied-topics packets, read `README.md` in this folder. The profanity packet carries its own definition and instructions at the top of `f4-profanity/packet.md`. For the pairs, read `bias/b2-v0/00-instructions.md`.
Answer every question for every case, use `unclear` with a note when the definition does not settle it, and put
your name and date on every line.

## For the lead

1. Send reviewer A the four folders and their instructions. Send reviewer B `bias/b2-v0/` with its instructions, plus
   the cases listed under `second_reviewer` in `_lead/f3-denied-topics.key.json`, `_lead/f3-test-candidates.key.json`
   and `_lead/f4-profanity.key.json`. Send reviewer B those
   cases' sections of `packet.md` and their lines of `labels.template.jsonl` only.
2. Save returned sheets as `../reviews/incoming/<reviewer>-<packet>.jsonl`.
3. Run `uv run python -m goldrails_dataset.reviews --status` to see exactly which cases still need a label, a second
   reviewer or adjudication. It also writes `../reviews/status.json`.
4. Settle disagreements with a third person in `../reviews/adjudications.jsonl`. Use `review_id`, `label` and
   `adjudicator` for denied topics and profanity (`label` may be `exclude`), and `item`, `keep`, `action` and `adjudicator` for pairs.
5. When the status report shows nothing open, follow `docs/23-release-runbook.md` from step 2.

The final human label replaces the drafted label in dataset v1.1; the draft stays in the row's notes. A case leaves
scoring only when reviewers agree it cannot be judged (`exclude_case`), with the reason recorded, or while it is
unresolved. An `unclear` answer always goes to adjudication. A pair counts only when both reviewers keep it with the
same action for both texts.

## Why the existing pairs can be test rows

The b2-v0 texts were read only to quality-check the pair generator. No model under test was run on them, and they
were never used to write questions or fit thresholds. No ledger or result file contains them. Reading to annotate or
check quality is not test exposure. `../examined-clearances.jsonl` records that clearance with its evidence, and
`../examined-ids.txt` is unchanged. Their 22 base texts stay examined.
