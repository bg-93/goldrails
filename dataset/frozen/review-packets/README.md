# Reviewer instructions: blind review of authored cases

Gold Rails scores guardrails against labelled cases. Most cases come from published datasets. The ones in these
packets were written for the benchmark by an AI model, and nobody has checked them yet. Your labels decide whether
each case keeps its place in the dataset and what the right answer is.

## What you get

One folder per packet. Each has two files:

- `packet.md`: the task definition, the questions, and every case with an empty answer table.
- `labels.template.jsonl`: one line per case with the same questions set to `null`. Fill this in if you prefer
  a file to the tables. Either is fine; do not fill in both.

| Packet | Cases | What you judge |
|---|---|---|
| `f2-prompt-attacks` | 20 | Whether a user message is a prompt injection, a jailbreak, or a prompt-leakage attempt |
| `f3-denied-topics` | 28 | Whether a user message falls within each of three written topic definitions |
| `f5-sensitive-information` | 20 | Whether a text contains each of nine kinds of personal information |

The packet does not tell you what anyone expects the answer to be. Do not assume anything about how many cases are
positive. It could be most of them, none, or anything in between.

## How to label

1. Read the task definition at the top of the packet before the first case, and go back to it whenever you hesitate.
   Judge against the definition as written, even where you would have written it differently. If you think the
   definition itself is wrong, say so in the note.
2. Answer every question for every case: `yes`, `no`, or `unclear`.
3. Use `unclear` when the definition does not settle the case or the text supports two readings. Write a note saying
   which readings you see. An `unclear` with a good note is more useful than a guess.
4. Judge the text as it stands. Do not look the case up, run it through a model or a guardrail, or ask anyone about it.
5. Work alone. Do not compare answers with another reviewer until both of you have submitted.
6. Put your name or initials in `reviewer` and the date in `submitted_at` on every line you return.

If a case is still undecided after a few minutes, mark it `unclear`, write why, and move on.

## Returning your labels

Send your filled `labels.template.jsonl` (or `packet.md`) back to the lead. Keep a copy. Do not edit the packet text
or the case order.

## For the lead

Send reviewers the packet folders and this file only. The `_lead/` folder maps each review id (`f3-r07`) back to the
dataset record id. Keep it to yourself until the labels are in.

Before sending:

- Settle the prompt-injection definition. The `f2` packet shows the `v1/f2-attacks` question wording verbatim. That
  wording counts "add to the instructions it already has" as injection, while several f2 cases are ordinary user
  preferences phrased as "from now on" or "new rule". Either keep the wording and accept that reviewers may call them
  injections, or change the question set first and regenerate. `docs/20-source-audit.md` has the details.
- Regenerate with `uv run python -m goldrails_dataset.audit --packets` if any control loader, `topics.json` or a
  question set changed. `packet-manifest.json` records the hash of each input, so a mismatch shows the packet is stale.
- Pick two reviewers who did not write the cases and are not tuning thresholds or questions.

After both reviewers return:

- Compare per question. Where they agree, that is the reviewed label. Where they disagree or either said `unclear`,
  adjudicate with a third person, and record the case as unresolved if that fails. Unresolved cases stay out of
  scoring and are counted in the release notes.
- Record results in the dataset through the loaders, with `label_basis` set to `human` only for cases that two
  reviewers agreed on or that adjudication resolved. Keep both reviewers' raw labels in a file beside this one.
- These cases are on the examined list whatever the outcome, so they stay in the tune split. Reviewing them makes
  the tuning labels trustworthy. It does not make them test cases.
