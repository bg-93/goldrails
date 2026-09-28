"""Convert the first benchmark's corrected leaderboard and bias results into the leaderboard page's format.

    uv run python benchmark/runs/site_results.py

Reads benchmark/results/first-benchmark/{leaderboard-corrected.json, bias.json, latency.jsonl} and writes
site/leaderboard/results.json (schema goldrails-leaderboard-site/0.1). No new numbers are computed here except
serial-latency percentiles; everything else is copied from the leaderboard and bias outputs. The three Bedrock arms
(InvokeGuardrailChecks, word-filter guardrail, grounding guardrail) are one implementation, Amazon Bedrock
Guardrails, with each entry's own configuration hash in its ledger block. Denied topics has no eligible test rows and
is listed as not evaluated, so there is no overall entry.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RES = REPO / "benchmark" / "results" / "first-benchmark"
V12 = (RES / "leaderboard-v1.2.json").exists()   # PII on Nemotron-PII (dataset v1.2); earlier views stay on disk
OUT = REPO / "site" / "leaderboard" / "results.json"
SUITE_ID = {"sensitive_info": "sensitive_information"}
PROFANITY_QS = "v1-f4-profanity"


def site_suite(a: dict) -> str:
    """Page suite id for an arm: word filters split into custom words and profanity, shown separately."""
    if a["suite"] == "word_filters" and a["question_set"] == PROFANITY_QS:
        return "profanity"
    return SUITE_ID.get(a["suite"], a["suite"])
IMPL = {
    "jev-1.13.0": ("jev", "Jev 1.13.0 (TypeSafe API)", "hosted_api", "jev-1.13.0", None),
    "kev-0-8b": ("kev-0-8b", "Kev 0.8B (self-hosted)", "self_hosted", "jaredpalmer/kev-0.8b", "g2-standard-24, 2x L4"),
    "kev-4b": ("kev-4b", "Kev 4B (self-hosted)", "self_hosted", "jaredpalmer/kev-4b", "g2-standard-24, 2x L4"),
    "kev-9b": ("kev-9b", "Kev 9B (self-hosted)", "self_hosted", "jaredpalmer/kev-9b", "g2-standard-24, 2x L4"),
    "open-jev-2b": ("open-jev-2b", "Open-Jev 2B (self-hosted)", "self_hosted", "ZefanCai/Open-Jev-2B", "g2-standard-24, 2x L4"),
    "laya": ("laya", "Laya (self-hosted)", "self_hosted", "convaiinnovations/laya", "g2-standard-24, 2x L4"),
    "bedrock-checks": ("bedrock", "Amazon Bedrock Guardrails", "managed_service", None, None),
    "bedrock-apply-words": ("bedrock", "Amazon Bedrock Guardrails", "managed_service", None, None),
    "bedrock-apply-grounding": ("bedrock", "Amazon Bedrock Guardrails", "managed_service", None, None),
    "bedrock-apply-topics": ("bedrock", "Amazon Bedrock Guardrails", "managed_service", None, None),
    "regex-baseline": ("regex", "Regex word list (baseline)", "code_baseline", None, "operator laptop CPU"),
}
ALL_SUITES = ("content", "prompt_attacks", "denied_topics", "word_filters", "sensitive_information", "grounding")


def jl(p: Path) -> list:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []


def pct(xs: list, q: float):
    if not xs:
        return None
    xs = sorted(xs)
    k = (len(xs) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(xs) - 1)
    return round(xs[lo] + (xs[hi] - xs[lo]) * (k - lo), 4)


def interval(ci: dict | None, method: str):
    if not ci or ci.get("low") is None:
        return None
    return {"low": round(ci["low"], 4), "high": round(ci["high"], 4), "level": 0.95, "method": method}


SERIAL: dict = {}   # (system, question_set) -> [latency_s], from the serial latency pass


def entry_for(a: dict, method: str) -> dict:
    subs = a["subtasks"]
    ev = [k for k, v in subs.items() if v["status"] == "evaluated"]
    n = defaultdict(int)
    rec_num = rec_den = pass_num = pass_den = 0
    sec_recall, sec_fpr = [], []
    for k in ev:
        s = subs[k]["n"]
        n["pos"] += s["positive"]; n["neg"] += s["negative"]; n["failed"] += s["failed"]; n["nod"] += s["no_decision"]
        n["tp"] += s["tp"]; n["fp"] += s["fp"]
        sec = subs[k].get("secondary") or {}
        if sec.get("held_out_recall") is not None:
            sec_recall.append(sec["held_out_recall"]); sec_fpr.append(sec["held_out_false_positive_rate"])
    rec = [subs[k]["recall"] for k in ev if subs[k].get("recall") is not None]
    bpr = [subs[k]["benign_pass_rate"] for k in ev if subs[k].get("benign_pass_rate") is not None]
    thr = [subs[k]["threshold"]["threshold"] for k in ev if (subs[k].get("threshold") or {}).get("threshold") is not None]
    c = a["cost"]
    lat = a["latency"]
    subs_cost = (c.get("subtasks") or {}).values()
    zero_tariff = (c.get("usd_per_1000") == 0 and bool(subs_cost)
                   and all(x.get("records_tariff_zero") == x.get("records") for x in subs_cost))
    return {
        "implementation": IMPL[a["system"]][0],
        "suite": site_suite(a),
        "track": None,
        # A word-filter arm answers one subtask and fills its own page row (custom words or profanity); the category
        # score is their equal-weight mean, composed in the overall. Any other incomplete arm stays failed.
        "status": "evaluated" if a["suite_score"]["complete"] or (a["suite"] == "word_filters" and ev) else "failed",
        "status_note": f"{a['system']} / {a['question_set']}; subtasks equal-weighted: {', '.join(ev)}",
        "quality": {"score": round(a["suite_score"]["value"], 4), "interval": interval(a["suite_score"].get("ci"), method),
                    "conditional_score": round(sum(subs[k]["conditional_task_score"] for k in ev) / len(ev), 2)},
        "violation_recall": round(sum(rec) / len(rec), 4) if rec else None,
        "benign_pass_rate": round(sum(bpr) / len(bpr), 4) if bpr else None,
        "recall_at_fpr_budget": ({"budget": 0.05, "recall": round(sum(sec_recall) / len(sec_recall), 4),
                                  "heldout_fpr": round(sum(sec_fpr) / len(sec_fpr), 4), "feasible": True}
                                 if sec_recall else None),
        "threshold": ({"value": round(thr[0], 4) if len(thr) == 1 else None, "selected_on": "tune",
                       "rule": "frozen before the test: maximise tuning task score"
                               + ("" if len(thr) == 1 else f"; one threshold per subtask ({', '.join(str(round(t, 3)) for t in thr)})")}
                      if thr else {"value": None, "selected_on": "fixed", "rule": "binary verdict, no threshold"}),
        "sample": {"total": a["sample_sizes"]["report_rows"], "positive": n["pos"], "negative": n["neg"],
                   "groups": a["sample_sizes"].get("report_groups")},
        "errors": {"missed_violations": n["pos"] - n["tp"], "false_positives": n["fp"]},
        "failures": {"failed": n["failed"], "no_decision": n["nod"], "retries": None,
                     "recovered_after_failure": a["sample_sizes"].get("recovered_after_failure", 0)},
        "coverage": {"subtasks_evaluated": ev, "subtasks_required": list(subs),
                     "note": ("one of the two word-filter subtasks; the category score is their equal-weight mean"
                              if a["suite"] == "word_filters" and not a["suite_score"]["complete"]
                              else a["suite_score"].get("coverage_note"))},
        "cost": {"usd_per_1000": None if c.get("usd_per_1000") is None else round(c["usd_per_1000"], 5),
                 "basis": c.get("basis"), "note": c.get("reason") or c.get("tariff"),
                 **({"zero_tariff": True} if zero_tariff else {})},
        "latency": serial_latency(a, lat),
        "bias": None,
        "ledger": {"path": ("benchmark/results/first-benchmark/pii-v12-test.jsonl" if V12 and a["suite"] == "sensitive_info"
                            else "benchmark/results/first-benchmark/ext-test.jsonl"
                            if (a.get("freeze") or {}).get("via") == "extension"
                            else "benchmark/results/first-benchmark/test.jsonl (+ test-rerun.jsonl)"),
                   "config_hash": a["config_hash"], "dataset_sha256": a["dataset"]["sha256"],
                   "rows": a["sample_sizes"]["report_rows"]},
    }


def serial_latency(a: dict, loaded: dict) -> dict:
    """Serial latency (one request at a time) for this arm from the dedicated latency pass, so systems compare on the
    same load. The test pass's latency ran under different concurrency per system and stays as a reference only."""
    xs = SERIAL.get((a["system"], a["question_set"])) or []
    p50, p95 = pct(xs, 0.5), pct(xs, 0.95)
    return {"p50_s": p50 or None, "p95_s": p95 or None, "throughput_per_s": None,   # sub-millisecond regex rounds to 0
            "basis": f"serial, one request at a time, {len(xs)} rows" if xs else "not measured serially",
            "loaded_p95_s": loaded.get("p95_s") or None}


FEATURE_SUITE = {"F1": "content", "F2": "prompt_attacks", "F3": "denied_topics", "F4": "word_filters",
                 "F5": "sensitive_information", "F6": "grounding", "F7": "bias"}
SCOPE = {
    "content": ("Performance against a mixed-source reference: human labels for requests and JailbreakBench goals, "
                "LLM labels for every unsafe reply, automated OR-Bench labels for the over-refusal prompts.",
                "Not an independently human-validated safety standard. Sources define harm differently, and all 80 unsafe "
                "replies carry LLM labels. 32 of the 240 unsafe test rows fall under privacy (21) or specialised advice "
                "(11) in our taxonomy, so the score measures agreement with the sources' policies, not only the five "
                "content filters; a view without them is shown under the chart."),
    "prompt_attacks": ("Direct attacks from deepset, Gandalf and JailbreakBench artifacts, against deepset's benign prompts.",
                       "All 80 benign examples come from one source, so the result says little about legitimate "
                       "secret-related requests, quoted jailbreaks or real benign traffic. Differences between sources may "
                       "help separate the classes. Gandalf rows are instruction-override attempts selected by embedding "
                       "similarity, a noisy attack proxy with no per-row leakage label, so no leakage-specific claim is "
                       "made; a view without them is shown under the chart."),
    "denied_topics": ("Messages inside and just outside three written topic definitions, labelled by a single AI "
                      "reviewer (provisional).",
                      "Not independent human annotation: one AI reviewer, not independent of the benchmark design, no "
                      "inter-rater agreement. It may favour systems that reason like the reviewer. Three topics only; "
                      "labels are for these definitions, not for broader custom policies."),
    "profanity": ("Performance against our written profanity definition on real public comments (ordinary, quoted and "
                  "mild profanity, and clean messages with confusing words), labelled by a single AI reviewer "
                  "(provisional).",
                  "Not independent human annotation. Not agreement with AWS's undisclosed profanity vocabulary. Masked "
                  "spellings are a separate diagnostic outside the score. English only."),
    "word_filters": ("Perfect scores on the tested rules and templates.",
                     "The 160 rows come from 20 templates, so broad robustness is not established."),
    "sensitive_information": (("Detection of personal data in synthetic business, health and finance documents from NVIDIA "
                               "Nemotron-PII (CC-BY-4.0, test split), US and international formats; every negative "
                               "passed a screen and a blind review.",
                               "Synthetic text. Driver's licence numbers are not measured: the source has no such label. IP "
                               "address, password and SSN appear in 4 test rows each, so no per-type claim is made. Labels "
                               "are the source's generated spans, audited on a sample, not human annotation.") if V12 else
                              ("Detection of span-labelled synthetic personal data, with realistic-length negatives.",
                              "Synthetic text. Not independent held-out documents: fragments of 3 source documents cross "
                              "tuning and test (4 test rows). Negatives were read from empty source annotations; one blind AI "
                              "review of all 450 release negatives and a second review of the 63 it flagged or used as "
                              "controls marked 20 as containing a supported entity, 3 of them selected test rows. Eight test rows carry SSN labels inferred from number format "
                              "alone. Views without these rows are shown under the chart.")),
    "grounding": ("Human hallucination annotations across three task types and many source documents.",
                  "Scoped to this RAGTruth subset and to the mapping from hallucination spans to unsupported content. "
                  "Relevance is not measured."),
    "bias": ("Exploratory diagnostics only.",
             "discrim-eval: 50 cases over 31 scenarios, 19 with a single case and none for the full reference group, so "
             "group averages compare different scenarios. Civil Comments: 100 comments, with 1 to 18 per identity. Not a "
             "fairness ranking."),
}


def subset_manifest() -> Path:
    """The newest subset the results were scored on: v1.1 (human-reviewed, a later version), else v1.1-ai, else v1.0."""
    for name in (("first-benchmark-v1.2",) if V12 else ()) + ("first-benchmark-v1.1", "first-benchmark-v1.1-ai", "first-benchmark"):
        p = REPO / "benchmark/subsets" / name / "manifest.json"
        if p.exists():
            return p
    raise FileNotFoundError("no subset manifest")


def data_quality() -> list:
    """What each suite's test rows are made of, read from the subset manifest and the release build."""
    man = json.loads(subset_manifest().read_text(encoding="utf-8"))
    want = {r["id"] for r in man["rows"] if r["split"] == "test"}
    rows = []
    build = REPO / "dataset/release" / man["release"] / "build"
    if not any(build.glob("*.test.jsonl")):   # generated, not committed: rebuild rather than publish empty scope rows
        raise SystemExit(f"{build.relative_to(REPO)} is missing; rebuild it with "
                         f"uv run python -m goldrails_dataset.release --version {man['release']}")
    for p in sorted(build.glob("*.test.jsonl")):
        rows += [r for r in jl(p) if r["id"] in want]
    out = []
    groups = [(f, suite, None) for f, suite in FEATURE_SUITE.items() if f != "F4"]
    groups.insert(3, ("F4", "word_filters", {"word"}))
    groups.insert(4, ("F4", "profanity", {"profanity", "profanity_obfuscated"}))
    for f, suite, subs in groups:
        rs = [r for r in rows if r["feature"] == f and (subs is None or r["subtask"] in subs)]
        src = defaultdict(int)
        for r in rs:
            role = "violations" if r.get("expected") == "yes" else "benign" if r.get("expected") == "no" else "decision task"
            if f == "F7":
                role = r["subtask"]
            if r["subtask"] == "profanity_obfuscated":
                role += ", masked spelling (diagnostic)"
            src[(r["provenance"]["source"], r["provenance"].get("label_basis") or "unknown", role)] += 1
        extra = ""
        if f == "F6":
            tt = defaultdict(int)
            for r in rs:
                tt[json.loads(r["provenance"].get("notes") or "{}").get("task_type", "unknown")] += 1
            extra = " Task types: " + ", ".join(f"{k} {v}" for k, v in sorted(tt.items())) + "."
        supports, limits = SCOPE[suite]
        out.append({"suite": suite, "test_cases": len(rs), "groups": len({r["group"] for r in rs}),
                    "sources": [{"source": a, "label_basis": b, "role": c, "n": n} for (a, b, c), n in sorted(src.items())],
                    "supports": supports + extra, "limits": limits})
    return out


def strict_pii() -> dict:
    """The declared sensitivity view for sensitive information: the SSN type, labelled from number format alone, left out."""
    p = RES / "leaderboard-pii-strict.json"
    if not p.exists():
        return {}
    doc = json.loads(p.read_text(encoding="utf-8"))
    out = {}
    for a in doc["arms"]:
        if a["suite"] == "sensitive_info":
            ci = a["suite_score"].get("ci") or {}
            out[a["system"]] = {"label": "Without format-inferred SSN labels (sensitivity analysis)",
                                "score": round(a["suite_score"]["value"], 4),
                                **({"interval": {"low": round(ci["low"], 4), "high": round(ci["high"], 4), "level": 0.95,
                                                 "method": "paired group bootstrap"}} if ci.get("low") is not None else {})}
    return out


OVERALL_ID = {"bedrock-guardrails": "bedrock"}


SENS_SUITE = {"sensitive_info": "sensitive_information"}


def sensitivity_block() -> dict | None:
    """Post-hoc views from benchmark/runs/sensitivity_views.py, per suite, for every system. Never a primary score."""
    p = RES / "sensitivity-2026-09-24.json"
    if not p.exists():
        return None
    doc = json.loads(p.read_text(encoding="utf-8"))
    out = {"status": doc["status"], "rules": doc["rules"], "views": []}
    for name, v in doc["views"].items():
        if V12 and name.startswith("pii-"):   # those views concerned AI4Privacy rows, which v1.2 no longer scores
            continue
        out["views"].append({"id": name, "suite": SENS_SUITE.get(v["rule"]["suite"], v["rule"]["suite"]),
                             "label": {"pii-independent-documents": "without PII test rows whose source document was also in tuning",
                                       "pii-disputed-negatives": "without PII negatives the audit found to contain an entity",
                                       "pii-both": "without both",
                                       "content-five-categories": "without the 32 privacy and specialised-advice rows",
                                       "attacks-without-gandalf": "without the 80 Gandalf rows"}[name],
                             "rows_dropped": v["n_dropped"],
                             "scores": {k: x["score"] for k, x in v["suite"].items()},
                             "primary": {k: x["score"] for k, x in v["primary"]["suite"].items()}})
    return out


def notice(lb: dict) -> str:
    blocked = bool(lb["publication_blockers"])
    version = lb["contract"]["version"]
    if not provisional_block():
        return ("INTERIM. Five of six suites evaluated (denied topics awaits reviewed rows), so there is no overall "
                f"rank. Evaluation contract {version} is a draft without sign-off. Not for publication.")
    head = ("INTERIM AND PROVISIONAL. " if blocked else "PROVISIONAL. ") + (
        "All six categories are scored; denied topics and profanity use single-AI reference labels. ")
    return head + (f"Evaluation contract {version} is a draft without sign-off. Not for publication." if blocked
                   else f"Evaluation contract {version} is signed and the corrected analysis is confirmed.")


def provisional_block() -> dict | None:
    """Denied topics, profanity and the overall are provisional when the extension subset admits single-AI labels."""
    exts = sorted((REPO / "benchmark" / "subsets" / "first-benchmark").glob("freeze-extension-*.json"))
    for p in exts:
        subset = json.loads(p.read_text(encoding="utf-8"))["extends"].get("subset")
        man = REPO / "benchmark" / "subsets" / (subset or "") / "manifest.json"
        if subset and man.exists() and json.loads(man.read_text(encoding="utf-8")).get("provisional_ai_reference"):
            return {"suites": ["denied_topics", "profanity", "overall"],
                    "note": ("Provisional: denied topics and profanity use single-AI reference labels (Codex, 24 Sep 2026), "
                             "not independent human review. See benchmark/contracts/v1.1-amendment-ai-reference.md.")}
    return None


def overall_entries(lb: dict, method: str) -> list:
    """The equal-weight six-suite overall, per declared implementation. Ranked only when all six suites are complete;
    otherwise listed with the reason, never computed from fewer suites."""
    out = []
    arms = {a["arm_id"]: a for a in lb["arms"]}
    for imp in (lb.get("overall") or {}).get("implementations", []):
        name = imp["implementation"]
        iid = OVERALL_ID.get(name) or (IMPL[name][0] if name in IMPL else None)
        if iid is None or iid == "regex":
            continue
        if not imp.get("ranked"):
            out.append({"implementation": iid, "suite": "overall", "track": None, "status": "not_evaluated",
                        "status_note": "Needs all six categories: " + (imp.get("not_ranked_reason") or "incomplete")})
            continue
        ci = imp.get("ci") or {}
        out.append({"implementation": iid, "suite": "overall", "track": None, "status": "evaluated",
                    "status_note": "Equal-weight mean of the six category scores.",
                    "suites": {SUITE_ID.get(su, su): {"task_score": v.get("task_score"), "ci": v.get("ci"),
                                                       "usd_per_1000": v.get("usd_per_1000"),
                                                       "subtask_arms": v.get("subtask_arms"),
                                                       "composition": v.get("composition")}
                               for su, v in imp["suites"].items()},
                    "quality": {"score": round(imp["overall_score"], 4),
                                "interval": interval(ci, method) if ci.get("low") is not None else None},
                    "cost": {"usd_per_1000": None if imp.get("usd_per_1000") is None else round(imp["usd_per_1000"], 5),
                             "basis": "equal-weight mean of the six category costs",
                             "note": imp.get("cost_reason") or (
                                 "A composition of separately measured checks, not the price of one call: the mean of "
                                 "the six category costs per 1,000 checks, where word filters count both of their "
                                 "checks (custom words and profanity).")},
                    # Overall is compared on cost only. No single call spans six categories, and a pooled latency
                    # would mix categories measured for some systems and not others.
                    "latency": None})
    return out


def bias_entries(bias: dict) -> list:
    out = []
    for s in bias["guardrail_fairness"]["systems"]:
        b1 = s.get("B1")
        if not b1:
            continue
        q, o = b1["quality"], b1["overall"]
        groups = [{"group": "all B1 rows", "fpr": o["fpr"], "fnr": o["fnr"], "n_benign": o["fpr_denominator"],
                   "n_harmful": o["fnr_denominator"]}]
        for g in b1["identities"]:
            m = g["mentioned"]
            groups.append({"group": f"mentions {g['identity']}" + (" (low support)" if g["low_support"] else ""),
                           "fpr": m["fpr"], "fnr": m["fnr"], "n_benign": m["fpr_denominator"], "n_harmful": m["fnr_denominator"]})
        b2 = (s.get("B2") or {}).get("counts") or {}
        b2n = b2.get("evaluable") or 0
        out.append({"implementation": IMPL[s["system"]][0], "suite": "bias", "track": "guardrail_fairness",
                    "status": "evaluated",
                    "status_note": ("Exploratory. B1: 100 Civil Comments identity mentions, 1 to 18 per identity, too few "
                                    "for group comparisons. "
                                    + (f"B2: {b2n} counterfactual test pairs with single-AI reference labels (provisional); "
                                       "hard and unresolved pairs were omitted, so this is an anecdote, not a rate. "
                                       if b2n else "B2 pairs await review. ")
                                    + "Not a fairness ranking."),
                    "quality": {"score": round(100 * q["balanced_accuracy"], 2)},
                    "violation_recall": q["harmful_recall"], "benign_pass_rate": q["benign_pass_rate"],
                    "threshold": {"value": s["threshold"], "selected_on": "tune", "rule": "the system's frozen content request threshold"},
                    "coverage": {"subtasks_evaluated": ["b1_disparate_fpr"] + (["b2_counterfactual"] if b2n else []),
                                 "subtasks_required": ["b1_disparate_fpr", "b2_counterfactual"],
                                 "note": f"B2 reported separately: {b2n} pairs, provisional" if b2n else "B2 not evaluated"},
                    "bias": {"groups": groups, "pairs": b2n or None,
                             "pair_flip_rate": s["B2"]["flip_rate"] if b2n else None,
                             "paired_correctness": round(b2["all_correct"] / b2n, 4) if b2n else None,
                             "source_metric": None, "source_metric_value": None}})
    seen = defaultdict(dict)
    for s in bias["decision_bias"]["systems"]:
        if s["status"] == "evaluated":
            seen[s["system"]].update({k: s[k] for k in ("bbq", "discrim_eval") if k in s})
        elif s["status"] == "not_applicable":
            seen.setdefault(s["system"], None)
    for system, d in sorted(seen.items()):
        if d is None:
            out.append({"implementation": IMPL[system][0], "suite": "bias", "track": "decision_bias", "status": "not_applicable",
                        "status_note": "A managed guardrail does not answer decision or QA tasks."})
            continue
        cats = d["bbq"]["categories"]
        amb = [c["ambig"] for c in cats.values() if "ambig" in c]
        acc = sum(c["correct"] for c in amb) / sum(c["n"] for c in amb)
        out.append({"implementation": IMPL[system][0], "suite": "bias", "track": "decision_bias", "status": "evaluated",
                    "status_note": ("Exploratory. BBQ ambiguous-context accuracy (choosing 'unknown' when the context "
                                    "does not say), 88 questions from 95 templates. discrim-eval group gaps are not shown: "
                                    "the 50 selected cases span 31 scenarios, so demographic groups mostly answered "
                                    "different scenarios and a gap can reflect scenario difficulty rather than demographic "
                                    "sensitivity. Diagnostics are in benchmark/results/first-benchmark/bias.json."),
                    "quality": {"score": round(100 * acc, 2)},
                    "sample": {"total": sum(c["n"] for c in amb), "positive": None, "negative": None,
                               "groups": len(cats)},
                    "coverage": {"subtasks_evaluated": ["b3_decision"], "subtasks_required": ["b3_decision"], "note": None},
                    "bias": {"groups": [], "pairs": None, "pair_flip_rate": None, "paired_correctness": None,
                             "source_metric": "BBQ accuracy, ambiguous contexts",
                             "source_metric_value": round(acc, 4)}})
    return out


def main() -> int:
    # six categories once the extension has run: the final view (built after the owner's sign-off) if it exists, else
    # the provisional one; the five-category corrected view stays in leaderboard-corrected.json either way
    pick = next(p for p in (RES / "leaderboard-final.json", RES / "leaderboard-v1.2.json", RES / "leaderboard-provisional.json",
                            RES / "leaderboard-corrected.json")
                if p.exists())
    lb = json.loads(pick.read_text(encoding="utf-8"))
    bias = json.loads((RES / "bias.json").read_text(encoding="utf-8"))["bias"]
    method = f"paired group bootstrap, {lb['bootstrap']['replicates']} replicates, seed {lb['bootstrap']['seed']}"
    serial = defaultdict(list)
    lat = jl(RES / "latency.jsonl") + jl(RES / "ext-latency.jsonl")
    if V12:   # PII latency comes from the Nemotron pass; the old PII rows ran the same question set on other text
        lat = [r for r in lat if not r.get("id", "").startswith("f5-")] + jl(RES / "pii-v12-latency.jsonl")
    for r in lat:
        if r.get("ok") and r.get("latency_s") is not None:
            serial[IMPL[r["system"]][0]].append(r["latency_s"])
            SERIAL.setdefault((r["system"], r["question_set"]), []).append(r["latency_s"])
    impls = {}
    for a in lb["arms"]:
        iid, label, typ, model, hw = IMPL[a["system"]]
        s = serial.get(iid) or []
        fmt = lambda v: "under 1 ms" if v is not None and v < 0.001 else f"{v} s"
        note = (f"serial latency (one request at a time) over {len(s)} rows across its suites: p50 {fmt(pct(s, .5))}, p95 {fmt(pct(s, .95))}" if s else None)
        impls.setdefault(iid, {"id": iid, "label": label, "type": typ, "frozen": True, "model": model, "hardware": hw,
                               "sweep": None,
                               "configuration": {"config_hash": "per suite, see each entry's ledger block",
                                                 "question_set": "per suite, chosen on tuning rows",
                                                 "decision_rule": "max over decision questions" if typ != "code_baseline" else "whole-word, case-insensitive match",
                                                 "guardrail": "InvokeGuardrailChecks; ApplyGuardrail topic, word and grounding guardrails (v1)" if iid == "bedrock" else None,
                                                 "notes": note}})
    entries = [entry_for(a, method) for a in lb["arms"]]
    strict = {} if V12 else strict_pii()   # the SSN-format view concerned AI4Privacy rows only
    for e, a in zip(entries, lb["arms"]):
        if a["suite"] == "sensitive_info" and a["system"] in strict:
            e["sensitivity"] = strict[a["system"]]
    for suite, note in (("denied_topics", "No reviewed denied-topics rows yet; this suite waits for human review."),
                        ("profanity", "No reviewed profanity rows yet; this subtask waits for human review.")):
        scored = {e["implementation"] for e in entries if e["suite"] == suite}
        for iid in impls:
            if iid not in scored and iid != "regex":
                entries.append({"implementation": iid, "suite": suite, "track": None, "status": "not_evaluated",
                                "status_note": note})
    entries += overall_entries(lb, method)
    sub = json.loads(subset_manifest().read_text(encoding="utf-8"))
    entries += bias_entries(bias)
    doc = {
        "schema_version": "goldrails-leaderboard-site/0.1",
        "placeholder": False,
        "notice": notice(lb),
        "benchmark": {"name": "Gold Rails, first benchmark" + (" (interim)" if lb["publication_blockers"] else ""),
                      "dataset_version": f"{sub['release']} subset {sub['name']}",
                      "dataset_sha256": sub["subset_sha256"],
                      "dataset_url": None, "split": "test",
                      "evaluation_contract": f"{lb['contract']['version']} ({lb['contract']['status']})",
                      "release_manifest": f"dataset/release/{sub['release']}/manifest.json",
                      "generated_at": "2026-09-28" if V12 else "2026-09-24",
                      "headline_metric": "Task score = 100 x 0.5 x (violation recall + benign pass rate)",
                      "aggregation": "Subtasks equal within a suite; six suites equal in Overall; Bias outside the aggregate",
                      "fpr_budget": 0.05},
        "cost_basis": {"unit": "usd_per_1000_evaluations", "tariff_date": "2026-09-23", "region": "us-east-1 (AWS), us-east4 (GCP)",
                       "notes": ("Jev: measured tokens x list price. Bedrock: text units x list price. Self-hosted: whole-VM "
                                 "serving windows x g2-standard-24 on-demand rate (third-party price list), one model at a time, "
                                 "summed over the original test pass and the correction rerun and divided by unique cases. "
                                 "Windows are reconstructed from completion times recorded to the second, minus each attempt's "
                                 "latency, so they carry about a second of uncertainty each. Setup and idle VM time are excluded "
                                 "here and counted in the project spend. Regex baseline: cost not measured, shown without a cost point. List prices, not "
                                 "reconciled against a bill.")},
        "latency_basis": {"unit": "seconds", "concurrency": None,
                          "client_location": "operator laptop in Australia; IAP tunnels to us-east4-a; Bedrock us-east-1",
                          "notes": "Serial latency: a dedicated pass sending one request at a time to every system, 50 to 100 rows per suite, so systems compare under the same load. The test pass ran under different concurrency per system (Jev 8, Bedrock 1, GPU lane 2); its p95 is kept in each entry for reference only. Regex is sub-millisecond and shown as blank."},
        "disclosures": lb.get("disclosures", []) + [
            "51 test rows failed on dropped connections and were re-attempted under the same frozen configuration; the "
            "original and corrected results are both kept",
            "the freeze manifests' commit times are local Git evidence until the repository is published",
            "Gold Rails is a non-commercial research benchmark, published for research with credit to every upstream "
            "source; each source's rows stay under that source's licence. AI4Privacy's rows are not in the public "
            "dataset while its research and redistribution terms are clarified"]
            + ([provisional_block()["note"],
                "The five core categories (content, prompt attacks, custom words, sensitive information, grounding) use "
                "the same test rows, frozen thresholds, scores and costs as the corrected five-category view "
                "(benchmark/results/first-benchmark/leaderboard-corrected.json), which stays published unchanged.",
                "Serial latency for denied topics and profanity was measured for Jev and Bedrock only; the self-hosted "
                "models have no serial latency point there (their loaded test-pass p95 is in each entry's details).",
                "Bedrock's profanity score is against a written definition, not AWS's undisclosed managed list; its low "
                "recall reflects that mismatch as much as detection quality."] if provisional_block() else []),
        "blockers": lb["publication_blockers"] + (
            [] if any(e["suite"] == "denied_topics" and e["status"] == "evaluated" for e in entries)
            else ["denied topics and bias B2 counterfactual pairs await independent human review"]),
        "sensitivity_views": sensitivity_block(),
        "corrections": ([
            {"date": "2026-09-28", "title": "PII source replaced: NVIDIA Nemotron-PII (dataset v1.2)",
             "detail": ("AI4Privacy's licence did not allow publishing its rows, and its data had document overlap across "
                        "tuning and test and missing annotations. After a bounded audit, PII now uses NVIDIA Nemotron-PII "
                        "(CC-BY-4.0, test split). Every system kept its frozen PII questions, refitted its threshold on 50 "
                        "new tuning rows under a manifest committed first, and ran 160 new test rows once. The other five "
                        "categories are unchanged. The earlier PII results stay in leaderboard-provisional.json."),
             "code_commit": "d79a38c"}] if V12 else []) + [
            {"date": "2026-09-24", "title": "Data-quality review: known issues and post-hoc views",
             "detail": ("A review of sources, labels and the publication package found PII document fragments across "
                        "tuning and test, PII negatives with missing upstream annotations, a Gandalf subtype the source "
                        "does not support, and 32 content rows outside the five content categories. Primary scores are "
                        "unchanged. Views without the affected rows, under rules committed before computing them, are "
                        "shown under the charts; none changes a Jev and Bedrock verdict. A clean held-out PII result "
                        "would need a fresh PII test selection."),
             "code_commit": "822e9e5"},
            {"date": "2026-09-24", "title": "Overall compared on cost only",
             "detail": ("The page had shown an overall latency pooled across categories. The self-hosted models had no "
                        "serial pass for denied topics and profanity, so their pool covered fewer categories than Jev's or "
                        "Bedrock's. Overall latency is removed; latency stays per category."),
             "code_commit": None},
            {"date": "2026-09-24", "title": "Provisional extension: denied topics, profanity and B2",
             "detail": ("Under contract v1.1 amendment A these use single-AI reference labels (Codex, 24 September) and "
                        "are marked provisional. Two extension manifests froze their thresholds on tuning rows before any "
                        "test call. The five core categories are unchanged from the corrected five-category view."),
             "code_commit": "5ba8173"},
            {"date": "2026-09-23", "title": "Contract v1.1 and analysis approval 4, awaiting confirmation",
             "detail": ("Word filters became custom words plus profanity at equal weight, with a composed cost that sums "
                        "the two checks. Approval 4 names scoring code 0744223 and contract v1.1. The developer recorded it "
                        "from the owner's written instructions, and it stays a publication blocker until the owner "
                        "confirms it."),
             "code_commit": "ed79005"},
            {"date": "2026-09-23", "title": "Corrected analysis approved",
             "detail": ("The project owner approved the scoring fixes above as a corrected analysis "
                        "(benchmark/subsets/first-benchmark/analysis-approval-1.json). Questions, frozen thresholds, "
                        "contract, bootstrap and test rows are unchanged, and the original results stay published beside "
                        "the corrected ones. The evaluator accepts the changed scoring code only under that committed "
                        "approval and records it with each result."),
             "code_commit": "39d3d68"},
            {"date": "2026-09-23", "title": "Serving cost reconstruction and retry accounting",
             "detail": ("Self-hosted serving windows now start at the first attempt's completion time minus its latency; "
                        "the earlier method treated completion times as start times and added latency at the end. Cost now "
                        "sums the original test session and the correction rerun and divides by unique cases, so re-attempts "
                        "are charged. Quality scores are unchanged by this."),
             "code_commit": "983ed67"},
            {"date": "2026-09-23", "title": "Re-attempted rows replace their failed originals in the corrected view",
             "detail": ("The corrected leaderboard had scored 51 failed originals (no credit) beside their successful "
                        "re-attempts. A successful re-attempt now supersedes its failed original; the original failure "
                        "count stays on each entry. Four arms changed from the original run: Open-Jev 2B content 63.2 to 70.1, "
                        "Kev 0.8B prompt attacks 72.1 to 75.8, Kev 0.8B word filters 68.8 to 71.9, Open-Jev 2B word filters "
                        "78.1 to 79.4. "
                        "This is a post-run scoring correction: the freeze manifest (commit 6f5390a) and the original "
                        "leaderboard are unchanged."),
             "code_commit": "5ab9d5e"}],
        "data_quality": data_quality(),
        "provisional": provisional_block(),
        "implementations": list(impls.values()),
        "entries": entries,
    }
    OUT.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    print(f"{len(impls)} implementations, {len(entries)} entries; wrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
