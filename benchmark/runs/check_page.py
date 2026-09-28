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
MANIFESTS = ("freeze-manifest.json", "freeze-extension-1.json", "freeze-extension-2.json", "freeze-extension-3.json")
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
    pick = next(p for p in (RES / "leaderboard-final.json", RES / "leaderboard-v1.2.json", RES / "leaderboard-provisional.json")
                if p.exists())
    v12 = pick.name == "leaderboard-v1.2.json"   # PII replaced; the corrected view's PII arms are the old source
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
    check("extension manifests committed before the test rows they govern", not bad,
          "; ".join(bad) or f"ext1 {ext1.split()[1]} before {first_ext_test.split()[1]}; ext2 {ext2.split()[1]} before {later[0].split()[1]}")

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
        if len(parts) != 2 or not close(sum(p["cost"]["usd_per_1000"] for p in parts), wf["usd_per_1000"], 1e-6):
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
    check("denied topics, profanity and overall are marked provisional", {"denied_topics", "profanity", "overall"} <= prov,
          ", ".join(sorted(prov)))
    dq = {q["suite"]: q for q in site.get("data_quality") or []}
    llm = all(s["label_basis"] == "llm" for k in ("denied_topics", "profanity") for s in dq.get(k, {}).get("sources", [])) \
        and all(dq.get(k, {}).get("test_cases") for k in ("denied_topics", "profanity"))
    check("data scope shows the AI-labelled rows with label basis llm", llm,
          f"denied topics {dq.get('denied_topics', {}).get('test_cases')}, profanity {dq.get('profanity', {}).get('test_cases')}")

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
    check("page carries exactly the leaderboard's publication blockers, and says not for publication while any stand",
          site.get("blockers") == lb["publication_blockers"] and (("Not for publication" in site.get("notice", "")) == blocked),
          "; ".join(site.get("blockers") or []) or "no blockers")

    out = {"checked_at_commit": git("rev-parse", "--short", "HEAD"), "results": str(SITE.relative_to(REPO)),
           "frozen": str(pick.relative_to(REPO)),
           "passed": sum(c["ok"] for c in checks), "failed": sum(not c["ok"] for c in checks), "checks": checks}
    (RES / "page-check.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    for c in checks:
        print(("PASS " if c["ok"] else "FAIL ") + c["check"] + (f"  [{c['detail']}]" if c["detail"] else ""))
    return 0 if out["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
