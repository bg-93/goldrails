# Jev-powered guardrails: research docs

Research captured on 18 September 2026, three days after TypeSafe AI released Jev. Everything here is desk research plus design thinking. Nothing has been built or benchmarked yet.

| File | What it holds |
|---|---|
| [01-jev-primer.md](01-jev-primer.md) | What Jev is, the three question types, pricing, limits, known weaknesses |
| [02-community-research.md](02-community-research.md) | What people said about Jev in its first 72 hours (HN, Reddit, X, YouTube) |
| [03-cybersecurity-decision-map.md](03-cybersecurity-decision-map.md) | Where in cybersecurity a decision model fits, rated |
| [04-ir-showcase-ideas.md](04-ir-showcase-ideas.md) | Incident response and raxIT showcase ideas, rated |
| [05-bedrock-guardrails-mapping.md](05-bedrock-guardrails-mapping.md) | Bedrock Guardrails policy by policy, rebuilt on Jev, with gaps and cost |
| [06-product-design.md](06-product-design.md) | The combined product: Bedrock-compatible API plus action guardrails |
| [07-poc-plan.md](07-poc-plan.md) | POC scope, go/no-go criteria, then the UI phase |
| [08-sources.md](08-sources.md) | Links to everything cited |
| [09-bedrock-guardrails-feature-inventory.md](09-bedrock-guardrails-feature-inventory.md) | Every Bedrock Guardrails policy, API, tier, limit, and price, verified 18 Sep 2026, plus what the June 2026 agentic additions do to our pitch |
| [10-evaluation-datasets.md](10-evaluation-datasets.md) | Hugging Face datasets per check type, with the POC sampling plan |
| [11-defence-in-depth-and-prior-art.md](11-defence-in-depth-and-prior-art.md) | Four-tier guardrail architecture, what three practitioner benchmarks and the community repos taught us, and the slop-detection showcase |
| [12-jev-inside-the-runtime-engine.md](12-jev-inside-the-runtime-engine.md) | The recommendation: Jev as the semantic uplift behind runtime-security-core's existing seams, skills as the wedge, mapped to the OWASP Agentic Skills Top 10 |
| [13-jevbench-learnings.md](13-jevbench-learnings.md) | How JevBench is built and scored, what it found, and which of its rules we adopt for the guardrail benchmark |
| [14-gold-rails-v1-spec.md](14-gold-rails-v1-spec.md) | Gold Rails v1: 10k rows, composition per feature, HF layout, harness adapters, landing page, under $100 in API and GPU spend, eight weeks |
| [15-grayzonebench-learnings.md](15-grayzonebench-learnings.md) | How our 2025 GrayZoneBench was run and published, what to reuse (org, site, publish shape, moderation client) and what to change (labels not judges, hashes, ledger, no windows) |
| [16-evaluation-contract.md](16-evaluation-contract.md) | After the pilot review: what a run may claim, claims withdrawn, fixes made, and the contract before the next run |
| [17-guardrail-policy-v0.md](17-guardrail-policy-v0.md) | Policy v0.1 for review: two comparisons kept apart, separate labels for topic, harmful assistance, actionable and harmful detail, unsafe replies and instruction overrides; request routing vs reply enforcement; twelve rows proposed with full text in dataset/frozen |
| [18-benchmark-structure.md](18-benchmark-structure.md) | Six suites (content, prompt attacks, denied topics, word filters, sensitive information, grounding), Automated Reasoning excluded; one harness, one results format, the leaderboard plot, sources per suite, current coverage, order of work |
| [19-evaluation-contract-v1.md](19-evaluation-contract-v1.md) | Evaluation contract v1, draft pending sign-off: six-suite scope, balanced-accuracy task score with tuning-only thresholds, equal weights, failure and coverage rules, group bootstrap, measured cost and p95 latency, freeze-before-test, size and budget, and the six review decisions. Supersedes the conflicting parts of 14, 16 and 18 |
| [appendix-vault-script-survey.md](appendix-vault-script-survey.md) | Earlier survey of the raxit-vault scripts for Jev opportunities |
| [reports/](reports/) | Published pages: content-filter explainer, decision memo, benchmark plan, golden dataset plan, system design |
| [specs/](specs/) | The original content-filter API design spec |
| [research-raw/](research-raw/README.md) | Raw last30days research dumps that 02 and 11 were distilled from |
| [ts-spikes/](ts-spikes/README.md) | The first TypeScript calls to Jev, before the benchmark moved to Python |
| [transcripts/](transcripts/) | Verbatim transcripts of the three practitioner videos cited in 11 |
| [prior-art/](prior-art/README.md) | OWASP skills checklist and the community guardrail repos' questions and cases |
| [typesafe-reference/](typesafe-reference/README.md) | Local Markdown copies of the live TypeSafe docs: API, models, SDKs, guardrails cookbook, jaggedness |

Read 01, 05, 06, 07 in that order if you only have ten minutes.


Terminology: a *question set* is the fixed set of typed questions sent to a decision model with each row (TypeSafe's cookbook calls this a battery; we do not).
