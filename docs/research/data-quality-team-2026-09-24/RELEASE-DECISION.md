# Release assessment

24 September 2026. Technical/scientific assessment by Codex; not an owner signature, legal determination or publication action.

## Verdict

Proceed with a provisional research release after a bounded export-preparation pass. No further model run or larger dataset is required for that claim. Do not make the existing working repository public as-is.

## Evidence checked

- Full test suite run: 303 passed, 1 skipped.
- Release checker: 15/15 passed in the immediately preceding review.
- Independently checked every staged JSONL file against staging-report.json: 8,085 rows, matching byte hashes/counts, zero AI4Privacy rows.
- B2 staging: 16 rows (8 retained pairs), with text withheld. The packet's 22 released pairs is inaccurate: 22 were candidates, 4 retained pairs are test cases.
- Current contract, dataset card, reconstruction instructions, permission draft and sign-off mechanism inspected.

## Decisions recommended

1. Accept the current contract's balanced-accuracy score, equal category weights and frozen settings for this descriptive benchmark. The overall is a benchmark index, not an estimated production safety rate.
2. Retain PII as a qualified historical result. Disclose document overlap, annotation omissions and post-hoc sensitivity views. Do not spend on a confirmation run until its intended claim and source access are settled.
3. Keep bias exploratory and preserve the current IDs-only export. There is no reason to expand distribution rights now.
4. Use gold-rails as the proposed public repository name. Publish an explicitly curated export, not the development repository/history.
5. Preserve the staged dataset's exclusion of AI4Privacy data and annotations. Distinguish the full internal release from the 8,085-row public package and identify the restricted portion needed for full reproduction.
6. Retain non-commercial research intent and upstream attribution. The permission draft should explicitly ask about completed and future processing through hosted services as well as publication; do not represent unanswered permission as granted.

## Concrete public-repository blocker

Reading committed HEAD blobs confirms:

| Tracked file | AI4Privacy rows with source text |
|---|---:|
| dataset/samples/sample-1k/F5.test.jsonl | 152 |
| dataset/samples/sample-1k/F5.tune.jsonl | 28 |

These 180 records remain in the repository even though the HF stage withholds AI4Privacy. Other tracked review packets, per-row corrections and raw ledgers may also contain restricted material. This review has not exhaustively classified every tracked file or historical commit.

Before public upload, produce an allowlisted release export containing cleared code, documents, notices and permitted result artifacts. Retain the original development repository privately with its freeze evidence. A file deletion in the next commit does not remove earlier blobs from public Git history. Do not rewrite the private evidence history merely to publish code.

The public export should disclose its relationship to the private source commit and retain permitted manifest/timing evidence without pretending its new public commit proves the historical freeze. Fill reconstruction instructions with the actual public URL and reachable export commit; the current placeholder URL and private-history checkout are not a public reproduction path.

## Developer completion criteria

- Audit reports/evidence included in the approved public document set; downloaded transcript/vendor archives excluded.
- B2 counts corrected.
- Clean export inspected across all included files, including source snippets in logs/packets; no withheld data or annotations inadvertently published.
- HF README and reconstruction instructions reference the real public export.
- Regenerated page still passes release checks, with provisional labels retained after sign-off.
- Owner authorization recorded with its actual date and attribution. No automatic conversion of this assessment into a signature in the owner's name.

These are packaging and claim corrections. They do not justify rerunning the six-category evaluation.
