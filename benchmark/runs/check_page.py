"""Release check: the results page says exactly what the frozen results say.

    uv run python benchmark/runs/check_page.py

Reads ``site/leaderboard/results.json`` (what the page draws) and compares it with the frozen sources: the provisional
leaderboard, the freeze manifests, the corrected five-category view, ``bias.json`` and ``CORRECTIONS.md``. No model
calls. Writes ``benchmark/results/first-benchmark/page-check.json`` and exits non-zero if any check fails.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from site_results import IMPL, OVERALL_ID  # noqa: E402  the converter's own system-to-page id table
RES = REPO / "benchmark" / "results" / "first-benchmark"
SUB = REPO / "benchmark" / "subsets" / "first-benchmark"
SITE = REPO / "site" / "leaderboard" / "results.json"
MANIFESTS = ("freeze-manifest.json", "freeze-extension-1.json", "freeze-extension-2.json", "freeze-extension-3.json",
             "freeze-extension-4.json")
CORE = ("content", "prompt_attacks", "word_filters", "sensitive_info", "grounding")
SITE_SUITE = {"sensitive_info": "sensitive_information"}
TOL = 1e-3   # the page rounds scores to 4 places and costs to 5

checks: list[dict] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    checks.append({"check": name, "ok": bool(ok), "detail": detail})


def close(a, b, tol=TOL) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(float(a) - float(b)) <= tol


def page_id(system: str) -> str:
    return OVERALL_ID.get(system) or IMPL[system][0]


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=False).stdout.strip()


def main() -> int:
    pick = next(p for p in (RES / "leaderboard-final.json", RES / "leaderboard-v1.3.json", RES / "leaderboard-v1.2.json",
                            RES / "leaderboard-provisional.json") if p.exists())
    v13 = pick.name == "leaderboard-v1.3.json" or "v1_3" in (load(pick).get("provenance") or {})   # Civil Comments profanity
    v12 = v13 or pick.name == "leaderboard-v1.2.json"   # PII replaced; the corrected view's PII arms are the old source
    site, lb = load(SITE), load(pick)
    corrected, bias = load(RES / "leaderboard-corrected.json"), load(RES / "bias.json")["bias"]
    site_impl = {i["id"]: i for i in site["implementations"]}
    by_hash = {}
    for e in site["entries"]:
        if (e.get("ledger") or {}).get("config_hash"):
            by_hash.setdefault(e["ledger"]["config_hash"], []).append(e)

    # 1. Every frozen arm is on the page once, with its score, interval, cost, sample and threshold.
    bad = []
    for a in lb["arms"]:
        es = [e for e in by_hash.get(a["config_hash"], []) if e["ledger"]["dataset_sha256"] == a["dataset"]["sha256"]]
        if len(es) != 1:
            bad.append(f"{a['arm_id']}: {len(es)} page entries")
            continue
        e, ss = es[0], a["suite_score"]
        ci = ss.get("ci") or {}
        pi = (e["quality"] or {}).get("interval") or {}
        thr = [v["threshold"]["threshold"] for v in a["subtasks"].values()
               if v["status"] == "evaluated" and (v.get("threshold") or {}).get("threshold") is not None]
        problems = [k for k, ok in (
            ("score", close(e["quality"]["score"], ss["value"])),
            ("interval", close(pi.get("low"), ci.get("low")) and close(pi.get("high"), ci.get("high"))),
            ("cost", close(e["cost"]["usd_per_1000"], a["cost"].get("usd_per_1000"), 1e-5)),
            ("rows", e["sample"]["total"] == a["sample_sizes"]["report_rows"]),
            ("threshold", (len(thr) != 1) or close(e["threshold"]["value"], thr[0], 1e-4)),
            ("status", e["status"] == "evaluated"),
        ) if not ok]
        if problems:
            bad.append(f"{a['arm_id']}: {', '.join(problems)}")
    check("every frozen arm appears once with matching score, interval, cost, rows and threshold",
          not bad, "; ".join(bad) or f"{len(lb['arms'])} arms")

    # 2. Thresholds used are the committed freeze manifests' thresholds, and the manifests are unchanged in git.
    frozen, sha_ok, dirty = {}, [], []
    for name in MANIFESTS:
        p = SUB / name
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
        sha_ok.append(sha)
        if git("status", "--porcelain", str(p.relative_to(REPO))):
            dirty.append(name)
        for arm in load(p)["arms"]:
            frozen[(arm["config_hash"], arm["dataset_sha256"])] = (arm["thresholds"], sha)
    bad = []
    for a in lb["arms"]:
        f = frozen.get((a["config_hash"], a["dataset"]["sha256"]))
        if f is None:
            bad.append(f"{a['arm_id']}: not in any freeze manifest")
            continue
        thresholds, sha = f
        if (a.get("freeze") or {}).get("manifest_sha256") != sha:
            bad.append(f"{a['arm_id']}: freeze sha differs")
        for sub, v in a["subtasks"].items():
            t = (v.get("threshold") or {}).get("threshold")
            if t is not None and sub in thresholds and not close(t, thresholds[sub].get("threshold"), 1e-6):   # stored to 6 places
                bad.append(f"{a['arm_id']}/{sub}: {t} vs frozen {thresholds[sub].get('threshold')}")
    check("every arm used its freeze manifest's thresholds", not bad, "; ".join(bad) or f"{len(frozen)} frozen arms")
    check("freeze manifests are committed and unchanged", not dirty, ", ".join(dirty) or ", ".join(s[:12] for s in sha_ok))

    # 3. Extension manifests were committed before their test ledgers.
    order = []
    for manifest, ledger in (("freeze-extension-1.json", "ext-test.jsonl"), ("freeze-extension-2.json", "ext-test.jsonl")):
        m = git("log", "--diff-filter=A", "--format=%ct %h", "--", f"benchmark/subsets/first-benchmark/{manifest}").splitlines()
        rows = git("log", "--reverse", "--format=%ct %h", "--", f"benchmark/results/first-benchmark/{ledger}").splitlines()
        order.append((manifest, m[-1] if m else None, rows))
    bad = []
    ext1 = order[0][1]
    first_ext_test = order[0][2][0] if order[0][2] else None
    if not ext1 or not first_ext_test or int(ext1.split()[0]) > int(first_ext_test.split()[0]):
        bad.append(f"extension 1 {ext1} not before first ext-test commit {first_ext_test}")
    ext2 = order[1][1]
    later = [r for r in order[1][2] if ext2 and int(r.split()[0]) > int(ext2.split()[0])]
    if not ext2 or not later:
        bad.append(f"extension 2 {ext2}: no ext-test commit after it (Bedrock rows)")
    if (SUB / "freeze-extension-3.json").exists():
        m3 = git("log", "--diff-filter=A", "--format=%ct %h", "--", "benchmark/subsets/first-benchmark/freeze-extension-3.json").splitlines()
        t3 = git("log", "--diff-filter=A", "--format=%ct %h", "--", "benchmark/results/first-benchmark/pii-v12-test.jsonl").splitlines()
        if not m3 or not t3 or int(m3[-1].split()[0]) > int(t3[-1].split()[0]):
            bad.append(f"extension 3 {m3[-1] if m3 else None} not before the PII test ledger {t3[-1] if t3 else None}")
    if (SUB / "freeze-extension-4.json").exists():
        m4 = git("log", "--diff-filter=A", "--format=%ct %h", "--", "benchmark/subsets/first-benchmark/freeze-extension-4.json").splitlines()
        t4 = git("log", "--diff-filter=A", "--format=%ct %h", "--", "benchmark/results/first-benchmark/prof-v13-test.jsonl").splitlines()
        if not m4 or not t4 or int(m4[-1].split()[0]) > int(t4[-1].split()[0]):
            bad.append(f"extension 4 {m4[-1] if m4 else None} not before the profanity test ledger {t4[-1] if t4 else None}")
    check("extension manifests committed before the test rows they govern", not bad,
          "; ".join(bad) or f"ext1 {ext1.split()[1]} before {first_ext_test.split()[1]}; ext2 {ext2.split()[1]} before {later[0].split()[1]}")

    # 3b. v1.3: the implementations file that changed the profanity question set predates every profanity call.
    if v13:
        from datetime import datetime, timezone
        ct = git("log", "--diff-filter=A", "--format=%ct %h", "--", "benchmark/subsets/first-benchmark/implementations-v1.3.json").split()
        first = min(a["at"] for n in ("prof-v13-tune", "prof-v13-test") for line in (RES / f"{n}.jsonl").open(encoding="utf-8")
                    for a in json.loads(line)["attempts"])
        first_t = datetime.fromisoformat(first.replace("Z", "+00:00")).timestamp()
        check("implementations-v1.3 committed before the first profanity call (tuning or test)",
              bool(ct) and int(ct[0]) < first_t,
              f"{ct[1] if ct else None} at {datetime.fromtimestamp(int(ct[0]), timezone.utc).isoformat() if ct else None}; first call {first}")

    # 3c. v1.3: the extension-specific freeze validation passed on this exact leaderboard.
    if v13:
        vp = RES / "extension-freeze-validation.json"
        v = load(vp) if vp.exists() else {}
        check("extension-specific freeze validation passed for every arm of this leaderboard",
              v.get("passed") is True and {x["arm"] for x in v.get("arms", [])} == {a["arm_id"] for a in lb["arms"]}
              and v.get("arms_checked") == len(lb["arms"])
              and any("extension-freeze-validation.json" in d for d in site.get("disclosures", [])),
              f"{v.get('arms_checked')} arms, {len(v.get('arms_failed') or [])} failed" if v else "missing")
        later = re.compile(r"v0\.0\.[2-9]|v0\.[1-9]\.")
        check("public version is v0.0.1 on the page, with no later public version label",
              site["benchmark"].get("public_release") == "v0.0.1" and not later.search(json.dumps(site))
              and not later.search((REPO / "site/leaderboard/index.html").read_text(encoding="utf-8")),
              site["benchmark"].get("public_note") or "")

    # 4. Overall: score, interval, cost, per-category values and ranking match the frozen overall block.
    bad, ranked = [], []
    for imp in lb["overall"]["implementations"]:
        name = imp["implementation"]
        if not imp.get("ranked"):
            continue
        iid = page_id(name)
        e = next((x for x in site["entries"] if x["suite"] == "overall" and x["implementation"] == iid), None)
        if e is None:
            bad.append(f"{name}: no overall entry"); continue
        ranked.append((imp["overall_score"], e["implementation"]))
        ci, pi = imp.get("ci") or {}, e["quality"]["interval"] or {}
        if not (close(e["quality"]["score"], imp["overall_score"]) and close(pi.get("low"), ci.get("low"))
                and close(pi.get("high"), ci.get("high")) and close(e["cost"]["usd_per_1000"], imp["usd_per_1000"], 1e-5)):
            bad.append(f"{name}: overall score, interval or cost differs")
        for su, v in imp["suites"].items():
            pv = e["suites"].get(SITE_SUITE.get(su, su)) or {}
            if not (close(pv.get("task_score"), v.get("task_score")) and close(pv.get("usd_per_1000"), v.get("usd_per_1000"), 1e-6)):
                bad.append(f"{name}/{su}: category value differs")
        costs = [v["usd_per_1000"] for v in imp["suites"].values()]
        if not close(sum(costs) / len(costs), imp["usd_per_1000"], 1e-6):
            bad.append(f"{name}: overall cost is not the mean of the six category costs")
        wf = imp["suites"]["word_filters"]
        parts = [next(a for a in lb["arms"] if a["arm_id"] == arm_id) for arm_id in (wf.get("subtask_arms") or {}).values()]
        # three values each stored to 6 places: rounding alone can separate them by 1.5e-6
        if len(parts) != 2 or not close(sum(p["cost"]["usd_per_1000"] for p in parts), wf["usd_per_1000"], 2e-6):
            bad.append(f"{name}: word-filters cost is not the sum of its two checks")
        if len(parts) == 2 and not close(sum(p["suite_score"]["value"] for p in parts) / 2, wf["task_score"]):
            bad.append(f"{name}: word-filters score is not the mean of its two checks")
    page_order = [i for _, i in sorted(ranked, reverse=True)]
    frozen_order = [page_id(r["implementation"]) for r in lb["overall"]["ranking"]]
    check("overall matches the frozen overall block (score, interval, cost, categories, composition)", not bad,
          "; ".join(bad) or f"{len(ranked)} ranked implementations")
    check("overall ranking order matches", page_order == frozen_order, f"page {page_order} / frozen {frozen_order}")
    check("overall has no pooled latency (compared on cost only)",
          all(e.get("latency") is None for e in site["entries"] if e["suite"] == "overall"))

    # 5. The five core categories are the corrected five-category view, unchanged.
    cm = {(a["system"], a["question_set"]): a for a in corrected["arms"]}
    bad, n = [], 0
    for a in lb["arms"]:
        c = cm.get((a["system"], a["question_set"]))
        if a["suite"] not in CORE or c is None or (v12 and a["suite"] == "sensitive_info"):
            continue
        n += 1
        for sub, v in a["subtasks"].items():
            if v["status"] != "evaluated":
                continue
            w = c["subtasks"].get(sub) or {}
            if v.get("task_score") != w.get("task_score") or v.get("n") != w.get("n"):
                bad.append(f"{a['arm_id']}/{sub}")
        if a["cost"].get("usd_per_1000") != c["cost"].get("usd_per_1000"):
            bad.append(f"{a['arm_id']}: cost")
    want_n = len([a for a in corrected["arms"] if not (v12 and a["suite"] == "sensitive_info")])
    check("core categories identical to the corrected five-category view" + (" (PII excepted: replaced in v1.2)" if v12 else ""),
          not bad and n == want_n, "; ".join(bad) or f"{n} of {want_n} corrected arms")

    # 6. Provisional marking: the AI-labelled categories and the overall, and their label basis on the page.
    prov = set((site.get("provisional") or {}).get("suites") or [])
    ai = ("denied_topics",) if v13 else ("denied_topics", "profanity")   # v1.3: profanity has human rater labels
    rev = site.get("label_review")
    dq = {q["suite"]: q for q in site.get("data_quality") or []}
    if rev:   # 6a. a recorded owner review for this exact release manifest; nothing current still calls labels provisional
        sub = load(REPO / "benchmark/subsets" / site["benchmark"]["dataset_version"].split()[-1] / "manifest.json")
        rel = REPO / "dataset/release" / sub["release"]
        rec = load(REPO / rev["record"])
        ok = (rec["release_manifest_sha256"] == hashlib.sha256((rel / "manifest.json").read_bytes()).hexdigest()
              and rec["independent_two_reviewer_adjudication"] is False and not rev["independent_two_reviewer_adjudication"]
              and not git("status", "--porcelain", rev["record"]))
        check("owner label review is recorded for this release manifest, committed, and not called independent", ok,
              f"{rev['record']} ({rec['reviewer']}, {rec['role']}, {rec['recorded_at'][:10]})")
        check("no suite is marked provisional once the review is recorded", not prov and site.get("provisional") is None,
              ", ".join(sorted(prov)) or "none")
        current = [site.get("notice", "")] + site.get("disclosures", []) + site.get("blockers", []) + \
            [q.get("supports", "") + " " + q.get("limits", "") for q in dq.values()] + \
            [e.get("status_note") or "" for e in site["entries"]]
        stale = [t[:90] for t in current if re.search(r"provisional|await(s|ing)? (independent )?(human )?review|"
                                                       r"single-AI reference labels", t, re.I)]
        check("current page text (corrections aside) has no provisional or awaiting-review statement", not stale,
              "; ".join(stale) or f"{len(current)} strings")
        page = (REPO / "site/leaderboard/index.html").read_text(encoding="utf-8")
        check("the page renders review status from results.json, with no text-rewriting layer",
              "reviewText" not in page and ".replace(/Provisional" not in page, "index.html")
        origin = all(x.get("review") == "project owner" for q in dq.values() for x in q["sources"]) and \
            all(x["label_basis"] == "llm" for k in ai for x in dq[k]["sources"])
        check("label origins are kept beside the owner review (denied topics stays label basis llm)", origin,
              f"denied topics {dq.get('denied_topics', {}).get('test_cases')} rows")
    else:
        want = set(ai) | {"overall"}
        check(", ".join(ai) + " and overall are marked provisional" + (", profanity is not" if v13 else ""),
              prov == want if v13 else want <= prov, ", ".join(sorted(prov)))
        llm = all(s["label_basis"] == "llm" for k in ai for s in dq.get(k, {}).get("sources", [])) \
            and all(dq.get(k, {}).get("test_cases") for k in ai)
        check("data scope shows the AI-labelled rows with label basis llm", llm,
              f"denied topics {dq.get('denied_topics', {}).get('test_cases')}, profanity {dq.get('profanity', {}).get('test_cases')}")
    if v13:
        src = dq.get("profanity", {}).get("sources", [])
        n = sum(x["n"] for x in src)
        check("profanity scope is the 160 Civil Comments rows with human rater labels, lexicon rows outside it",
              n == 160 and all(x["source"] == "civil_comments_obscene" and x["label_basis"] == "human" for x in src),
              ", ".join(f"{x['source']} {x['label_basis']} {x['role']} {x['n']}" for x in src))

    # 6b. Verdicts: every paired comparison on the page is the evaluator's paired interval, Jev minus Bedrock.
    if site.get("comparisons") is not None:
        by_id = {a["arm_id"]: a for a in lb["arms"]}
        want = {}
        for su, block in lb["suites"].items():
            for p in block["paired_differences"]:
                A, B = by_id[p["a"]], by_id[p["b"]]
                ids = (page_id(A["system"]), page_id(B["system"]))
                if set(ids) == {"jev", "bedrock"} and p.get("ci") and A["question_set"] in B["question_set"] + A["question_set"] \
                        and (A["question_set"] == B["question_set"] or su != "word_filters"):
                    sign = 1 if ids[0] == "jev" else -1
                    want.setdefault(su, []).append((sign * p["difference"], sorted((sign * p["ci"]["low"], sign * p["ci"]["high"])), p["separated"]))
        for p in lb["overall"]["paired_differences"]:
            if {p["a"], p["b"]} == {"jev-1.13.0", "bedrock-guardrails"}:
                sign = 1 if p["a"] == "jev-1.13.0" else -1
                want["overall"] = [(sign * p["difference"], sorted((sign * p["ci"]["low"], sign * p["ci"]["high"])), p["separated"])]
        got = site["comparisons"]
        flat = [w for ws in want.values() for w in ws]
        bad = [c["suite"] for c in got if c["suite"] != "word_filters_category" and not any(
            close(c["difference"], d) and close(c["ci"]["low"], ci[0]) and close(c["ci"]["high"], ci[1]) and c["separated"] == sep
            for d, ci, sep in flat)]
        rows = {"content", "prompt_attacks", "denied_topics", "word_filters", "profanity", "sensitive_information", "grounding", "overall"}
        missing = rows - {c["suite"] for c in got}
        check("every verdict row has the evaluator's paired Jev-minus-Bedrock interval", not bad and not missing,
              "; ".join(bad + sorted(missing)) or f"{len(got)} comparisons")
        wfc = next((c for c in got if c["suite"] == "word_filters_category"), None)
        if wfc:   # derived: half the profanity interval, valid only because the custom-word difference is 0 in every replicate
            prof = next(c for c in got if c["suite"] == "profanity")
            ov = {page_id(i["implementation"]): i["suites"]["word_filters"]["task_score"] for i in lb["overall"]["implementations"]}
            words = [a for a in lb["arms"] if a["question_set"] == "v1-f4-words" and page_id(a["system"]) in ("jev", "bedrock")]
            ok = (all(a["suite_score"]["value"] == 100.0 for a in words) and len(words) == 2
                  and close(wfc["difference"], ov["jev"] - ov["bedrock"]) and close(wfc["ci"]["low"], prof["ci"]["low"] / 2)
                  and close(wfc["ci"]["high"], prof["ci"]["high"] / 2))
            check("word-filter category interval is half the profanity interval, with both perfect on custom words", ok,
                  f"{wfc['difference']:+.2f} [{wfc['ci']['low']:.2f}, {wfc['ci']['high']:.2f}]")

    # 6c. Claims, costs and the word-filter aggregate say what was measured.
    scope = site.get("scope") or {}
    text = json.dumps(site)
    check("claim is scoped to configured detectors, with untested capabilities listed and no causal vocabulary claim",
          "configured guardrail detectors across six selected task suites" in scope.get("compares", "").lower()
          and len(scope.get("not_tested") or []) >= 5 and "Complete guardrail implementations" not in
          (REPO / "site/leaderboard/index.html").read_text(encoding="utf-8")
          and not re.search(r"vocabular(y|ies) differ", text), f"{len(scope.get('not_tested') or [])} untested capabilities")
    cb = site.get("cost_basis", {})
    selfhosted = [e for e in site["entries"] if site_impl.get(e["implementation"], {}).get("type") == "self_hosted"
                  and e["suite"] not in ("overall", "bias") and (e.get("cost") or {}).get("usd_per_1000") is not None]
    check("self-hosted costs are labelled normalized estimates, with each pass's actual zone recorded apart from pricing",
          cb.get("self_hosted_cost") == "normalized estimate" and {r["zone"] for r in cb.get("run_locations", [])} >= {"us-east4-a", "us-central1-a"}
          and all("normalized" in e["cost"].get("estimate", "") for e in selfhosted),
          f"{len(selfhosted)} entries; zones {sorted({r['zone'] for r in cb.get('run_locations', [])})}")
    wf = [e for e in site["entries"] if e["suite"] == "overall"]
    check("word filters is described as a component average wherever the composed value is carried",
          all("component average" in ((e.get("suites") or {}).get("word_filters") or {}).get("score_basis", "") for e in wf)
          and any("component average" in d for d in site.get("disclosures", [])), f"{len(wf)} overall entries")

    # 7. Bias is outside the score and matches bias.json, B2 with its pair count.
    bad = []
    for s in bias["guardrail_fairness"]["systems"]:
        e = next((x for x in site["entries"] if x["suite"] == "bias" and x.get("track") == "guardrail_fairness"
                  and x["implementation"] == page_id(s["system"])), None)
        if e is None:
            bad.append(f"{s['system']}: no B1 entry"); continue
        if not close(e["quality"]["score"], 100 * s["B1"]["quality"]["balanced_accuracy"], 0.01):
            bad.append(f"{s['system']}: B1")
        b2 = (s.get("B2") or {}).get("counts") or {}
        if e["bias"]["pairs"] != (b2.get("evaluable") or None) or not close(e["bias"]["pair_flip_rate"], s["B2"].get("flip_rate")):
            bad.append(f"{s['system']}: B2")
    in_overall = any("bias" in (e.get("suites") or {}) for e in site["entries"] if e["suite"] == "overall")
    check("bias matches bias.json and stays outside the overall", not bad and not in_overall, "; ".join(bad) or "B1 and B2 per system")

    # 8. Corrections on the page are in the corrections log, with their commits.
    log = (RES / "CORRECTIONS.md").read_text(encoding="utf-8")
    bad = [c["title"] for c in site.get("corrections") or [] if c.get("code_commit") and c["code_commit"] not in log]
    commits = set(re.findall(r"\b[0-9a-f]{7}\b", log))
    missing = [c for c in commits if not git("cat-file", "-t", c)]
    check("every page correction's commit is in CORRECTIONS.md", not bad, ", ".join(bad) or f"{len(site.get('corrections') or [])} corrections")
    check("every commit named in CORRECTIONS.md exists", not missing, ", ".join(missing) or f"{len(commits)} commits")

    # 9. Post-hoc views match their computed file, and their rules were committed before the views.
    sens_p = RES / "sensitivity-2026-09-24.json"
    if sens_p.exists():
        sens = load(sens_p)
        page = {v["id"]: v for v in (site.get("sensitivity_views") or {}).get("views", [])}
        bad = [n for n, v in sens["views"].items() if not (v12 and n.startswith("pii-"))
               if n not in page or any(not close(page[n]["scores"].get(k), x["score"], 0.01) for k, x in v["suite"].items())]
        rules_t = git("log", "--diff-filter=A", "--format=%ct", "--", "benchmark/subsets/first-benchmark/sensitivity-rules-2026-09-24.json")
        views_t = git("log", "--diff-filter=A", "--format=%ct", "--", "benchmark/results/first-benchmark/sensitivity-2026-09-24.json")
        ordered = bool(rules_t) and (not views_t or int(rules_t.split()[-1]) < int(views_t.split()[-1]))
        check("post-hoc views on the page match sensitivity-2026-09-24.json, with rules committed first", not bad and ordered,
              "; ".join(bad) or f"{len(sens['views'])} views")

    # 10. Nothing on the page claims publication: blockers present, notice says not for publication.
    blocked = bool(lb["publication_blockers"])
    acc = site.get("accepted_blockers") or []
    acc_ok = True
    for x in acc:   # each accepted line is named in a committed, confirmed approval this result used
        rec = SUB / x["record"]
        a = load(rec)
        acc_ok &= (x["blocker"] in (a.get("accepted_blockers") or []) and bool((a.get("confirmation") or {}).get("statement"))
                   and not git("status", "--porcelain", str(rec.relative_to(REPO)))
                   and any(Path(v["approval_path"]).name == x["record"] for v in lb.get("analysis_versions") or []))
    open_ = [b for b in lb["publication_blockers"] if b not in {x["blocker"] for x in acc}]
    check("page carries every open evaluator blocker, owner-accepted ones only with a confirmed approval, and says not "
          "for publication while any stay open",
          site.get("blockers") == open_ and acc_ok and (("Not for publication" in site.get("notice", "")) == bool(open_)),
          f"open: {'; '.join(open_) or 'none'}; accepted: {len(acc)}")

    out = {"checked_at_commit": git("rev-parse", "--short", "HEAD"), "results": str(SITE.relative_to(REPO)),
           "frozen": str(pick.relative_to(REPO)),
           "passed": sum(c["ok"] for c in checks), "failed": sum(not c["ok"] for c in checks), "checks": checks}
    (RES / "page-check.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    for c in checks:
        print(("PASS " if c["ok"] else "FAIL ") + c["check"] + (f"  [{c['detail']}]" if c["detail"] else ""))
    return 0 if out["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
