# PII audit annotations

These sit beside the data. No label or split in `data/` is changed.

- `nemotron-pii-audit.md` and `nemotron-pii-audit-mechanical.json`: the audit of NVIDIA Nemotron-PII that preceded its use (AI reviewers, blind to the source labels; not human annotation).
- `pii-negative-reviews.jsonl`: the blind review of every negative the release selected. Rows reviewed as present or unclear were replaced and are not in `data/`.
