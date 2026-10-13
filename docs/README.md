# docs

| File | What it holds |
|---|---|
<<<<<<< HEAD
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
| [25-offline-reliability.md](25-offline-reliability.md) | Deterministic, network-free failure simulation: architecture, scenarios, retry and backoff accounting, summary metrics, quality isolation, and how it prepares a later Jev-versus-guardrails reliability comparison |
| [26-robustness-diagnostics.md](26-robustness-diagnostics.md) | Frozen, diagnostic-only wording/order/state/input perturbations; separate derived data, provenance and freeze rules; matched flip, probability-delta, mean and worst-variant reporting |
| [appendix-vault-script-survey.md](appendix-vault-script-survey.md) | Earlier survey of the raxit-vault scripts for Jev opportunities |
| [reports/](reports/) | Published pages: content-filter explainer, decision memo, benchmark plan, golden dataset plan, system design |
| [specs/](specs/) | The original content-filter API design spec |
| [research-raw/](research-raw/README.md) | Raw last30days research dumps that 02 and 11 were distilled from |
| [ts-spikes/](ts-spikes/README.md) | The first TypeScript calls to Jev, before the benchmark moved to Python |
| [transcripts/](transcripts/) | Verbatim transcripts of the three practitioner videos cited in 11 |
| [prior-art/](prior-art/README.md) | OWASP skills checklist and the community guardrail repos' questions and cases |
| [typesafe-reference/](typesafe-reference/README.md) | Local Markdown copies of the live TypeSafe docs: API, models, SDKs, guardrails cookbook, jaggedness |
=======
| [benchmark/26-edition-2-plan.md](benchmark/26-edition-2-plan.md) | The plan the benchmark follows: fixed decision rule, dataset build, integrity checks, onboarding a model |
| [benchmark/27-evaluation-contract-v2.md](benchmark/27-evaluation-contract-v2.md) | The evaluation contract in prose; `benchmark/contracts/v2.0.json` is the version the scorer reads |
| [benchmark/28-new-decision-models-research.md](benchmark/28-new-decision-models-research.md) | Research on the hosted decision models added to the roster, with the price pages the tariffs cite |
| [benchmark/29-owner-rulings-2026-10-03.md](benchmark/29-owner-rulings-2026-10-03.md) | The decisions that settled open questions in the contract and the dataset |
| [benchmark/30-content-sample-labelling.md](benchmark/30-content-sample-labelling.md) | How the content suite's second-label sample is drawn and labelled |
| [benchmark/RELEASE-HANDOVER-2026-10-07.md](benchmark/RELEASE-HANDOVER-2026-10-07.md) | Release-day steps and where the results are kept |
>>>>>>> 38b70dc2991e52b62b1e05def887e268e5ac4a7c

## Vendor docs

Copies of documentation published by the benchmarked vendors. `goldrails_dataset.vendor_overlap` scans them for
dataset rows a vendor printed (`dataset/edition2/VENDOR-OVERLAP.md`), and `benchmark/goldrails_bench/tariffs.json`
cites some of them as its price source. Their paths are part of those records, so they stay where they are.

- TypeSafe (Jev): `reference/typesafe/`, `typesafe-reference/models.md`, `research/early-2026-09-18/01-jev-primer.md`,
  `research/early-2026-09-18/08-sources.md`
- AWS (Bedrock Guardrails): `09-bedrock-guardrails-feature-inventory.md` (a pointer),
  `research/early-2026-09-18/05-bedrock-guardrails-mapping.md`,
  `research/early-2026-09-18/09-bedrock-guardrails-feature-inventory.md`, `archive/2026-09-28-bedrock-feature-map/`,
  and `../research_notes/Profanity and denied topic references/bedrock_equivalence.md`
- OpenAI (gpt-6-luna): `reference/openai/decisions-api.md`

Terminology: a *question set* is the fixed set of typed questions sent to a decision model with each row.
