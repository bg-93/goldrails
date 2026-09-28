# Nemotron-PII audit, 28 September 2026

Source: `nvidia/Nemotron-PII` at revision `b70ffaf5ff39e079776134c5bf4381f00a9fd1ed`, test split only. CC-BY-4.0
(card at that revision). The owner asked for a bounded audit before replacing AI4Privacy as the PII source. This is
an AI audit (Claude subagents, blind to the source labels), not human annotation. No model under test was called.

## Verdict

Pass, with four mapping rules the audit found necessary. DRIVER_ID cannot be measured: the source has no such label.

## What was checked

| Check | Scope | Result |
|---|---|---|
| Span bounds | all 100,000 rows | 0 out of bounds |
| Format of supported-type values | 91,052 values | 319 fail (0.35%): 290 emails, mostly spans with a space or without "@"; documents with a malformed span are left out |
| Exact and normalised duplicate texts | all rows | 0 |
| Related documents | all rows | every source id has a US and an international version of one template (text differs, median similarity 0.17); 171 emails and 354 phone numbers recur across documents. Grouped by source id, joined on shared values: 48,893 groups, largest 45 source ids |
| Blind review of annotated documents | 100 documents, stratified by type, locale and format | reviewers found a supported entity in 99; the exception is an international form whose only mapped span is a state named as scope |
| Blind review of unannotated documents | 60 documents | 11 contain a supported entity: 6 fax numbers, 3 values presented as SSNs on international rows, 2 IPv4 addresses inside URLs |

`mechanical.json`, `sample.json`, `negatives-sample.json`, `review-*.jsonl` and `compare.json` hold the numbers and
verdicts. Notes name entity types and positions only.

## Rules adopted

1. `fax_number` maps to PHONE. The frozen question asks for "a telephone number".
2. `ssn` maps to US SSN only on US-locale rows. An international row with an `ssn` label is never a negative.
3. A document with an IPv4 address anywhere in its text is never a negative. The source tags IPs inside URLs as URL.
4. Every selected negative gets a blind review before release; a row reviewed as containing an entity leaves the
   pool (`dataset/frozen/reviews/nemotron-negatives/`). Missing annotations are never proof of absence.

Rules 1 to 3 separate all 11 flagged negatives from the 49 clean ones in the audit sample. That was measured on the
same sample, so it is optimistic; rule 4 is the check on the rows actually used.

## Other decisions

- Only the test split is used, so models trained on the train split have not seen these rows.
- The 160 audited documents are kept out of the benchmark, so audit and evaluation never share rows.
- Span-level correctness is not claimed. The benchmark's PII task is whether a message contains any supported
  entity; span boundaries are reported as the source gives them.
