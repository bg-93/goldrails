# Known issues in v1.2

Found after the benchmark ran, mostly by the data-quality review of 24 September 2026. The released rows, labels and splits are unchanged; each issue says what it changes and where the correction lives.

- **pii-source.** PII rows come from NVIDIA Nemotron-PII (CC-BY-4.0, test split), replacing AI4Privacy. Labels are the source's generated spans, mapped to nine entity types and audited on a 100-document sample (99 confirmed). Every negative passed a screen for gaps the audit found (fax numbers, SSNs on international rows, IPs inside URLs) and a blind AI review. Driver's licence numbers are not measured: the source has no such label. IP address, password and SSN appear in few test rows, so no per-type claim is made. The review was AI, not human.
- **gandalf-subtype.** All Gandalf rows are mapped to subtask leakage. The source selects instruction-override attempts by embedding similarity and has no per-row leakage label. Treat as a noisy attack proxy; no leakage-specific claim.
- **content-taxonomy.** 32 of 240 selected content test positives map in our taxonomy to PII (21) or TOPIC (11) rather than the five content categories. Content measures agreement with the sources' policies, not only the five content filters.
- **single-ai-labels.** Denied topics, profanity and B2 pairs carry single-AI reference labels (label_basis llm, review_status ai_reviewed). Provisional; not independent human annotation.
- **b2-size.** B2 has 8 kept pairs: 4 test pairs in 3 groups. Individual cases, not a rate.
