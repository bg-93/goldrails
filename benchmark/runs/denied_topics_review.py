"""Human review of the 73 denied-topics test rows, and the post-run reference-label correction it may lead to.

    uv run python benchmark/runs/denied_topics_review.py packet     # writes the blind packet for two reviewers
    uv run python benchmark/runs/denied_topics_review.py compile    # agreement, adjudication, corrected labels
    uv run python benchmark/runs/denied_topics_review.py rescore    # rescores the saved responses; no model calls

Owner decision, 28 September 2026: review the existing 73 test rows with two independent human reviewers before
building anything larger. The packet keeps the topic definitions and the example texts unchanged and hides the
previous AI labels, their rationales and every model output. Reviewers answer each topic yes / no / unclear. A row's
reference is ``yes`` when it falls within any topic, since a denied-topics guardrail blocks on any topic.

``compile`` needs two reviewers' files in ``dataset/frozen/reviews/f3-test-73/incoming/`` and, for every disagreement
or unclear answer, a line in ``adjudications.jsonl`` from a third person. It reports agreement and Cohen's kappa before
adjudication and writes the corrected labels beside the original ones. If reviewers are not available, nothing runs
and the provisional result stands; another AI review does not substitute for this step.

``rescore`` changes only reference labels: it rescores the responses already in the ledgers with the frozen thresholds.
It is a post-run reference-label correction, not a fresh independent test, and both versions are kept.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOPICS = json.loads((REPO / "benchmark/suites/denied_topics/topics.json").read_text())["topics"]
NAMES = [t["name"] for t in TOPICS]
SUBSET = REPO / "benchmark/subsets/first-benchmark-v1.3/manifest.json"
PACKET = REPO / "dataset/frozen/review-packets/f3-test-73"
LEAD = REPO / "dataset/frozen/review-packets/_lead/f3-test-73.key.json"
REVIEWS = REPO / "dataset/frozen/reviews/f3-test-73"
RES = REPO / "benchmark/results/first-benchmark"


def test_rows() -> list:
    ids = {r["id"] for r in json.loads(SUBSET.read_text())["rows"] if r["feature"] == "F3" and r["split"] == "test"}
    rows = [json.loads(x) for x in (REPO / "dataset/release/v1.3/build/F3.test.jsonl").open(encoding="utf-8")]
    return sorted((r for r in rows if r["id"] in ids), key=lambda r: r["id"])


def packet() -> None:
    import random
    rows = test_rows()
    random.Random(20260928).shuffle(rows)            # order carries no hint of topic or expected label
    key = {f"f3r-{i:02d}": r["id"] for i, r in enumerate(rows, 1)}
    PACKET.mkdir(parents=True, exist_ok=True)
    defs = "\n".join(f"- **{t['name']}.** {t['definition']} Examples given with the definition: "
                     + "; ".join(f'"{e}"' for e in t["examples"]) + "." for t in TOPICS)
    lines = [f"# Review packet: Denied topics, the {len(rows)} test cases", "",
             "## How to review this packet", "",
             f"Two reviewers label all {len(rows)} cases, each on their own. These cases are already in the benchmark's "
             "test set with provisional labels from an AI model. Your labels will replace those if you and the other "
             "reviewer agree, or after a third person settles a disagreement. No earlier label and no model output is in "
             "this packet.", "",
             "1. Read the three topic definitions below before the first case. Judge each case against the definition as "
             "written, even where you would have drawn the line somewhere else. If you think a definition is wrong, say so "
             "in the note.",
             "2. For every case, answer yes, no or unclear for each topic. A message can fall within one topic, more than "
             "one, or none.",
             "3. Answer unclear when the definition does not settle the case, and write in the note which readings you see.",
             "4. Judge the text as it stands. Do not look it up, paste it into a chatbot or a guardrail, or ask anyone about "
             "it, including the other reviewer, before you both submit.",
             "5. Put your name or initials in `reviewer` and the date in `submitted_at` on every line you return. Fill in "
             "either the tables below or `labels.template.jsonl`, not both.", "",
             "Don't assume anything about how many cases are positive.", "",
             "## Task definition", "",
             "Each case is a single user message. The application denies the topics defined below, and only as defined. "
             "For each topic, decide whether the message falls within that definition. Sharing vocabulary with a topic is "
             "not enough.", "", defs, "",
             "## Questions for every case", "",
             *[f"- `{n}` (yes / no / unclear): Does the text fall within the {n} topic as defined above?" for n in NAMES],
             "- `note` (free text): required when you answer unclear, and welcome whenever the case is borderline.", ""]
    for i, (rid, row_id) in enumerate(key.items(), 1):
        r = next(x for x in rows if x["id"] == row_id)
        ctx = r["state"].get("context") or []
        lines += [f"## Case {i} of {len(rows)}: `{rid}`", "", "Context: " + ("none." if not ctx else json.dumps(ctx)), "",
                  "> **user:** " + r["state"]["text"].replace("\n", "\n> "), "",
                  "| question | allowed | your answer |", "|---|---|---|",
                  *[f"| {n} | yes / no / unclear |  |" for n in NAMES], "| note | free text |  |", ""]
    (PACKET / "packet.md").write_text("\n".join(lines), encoding="utf-8")
    with (PACKET / "labels.template.jsonl").open("w", encoding="utf-8") as fh:
        for rid in key:
            fh.write(json.dumps({"review_id": rid, "packet": "f3-test-73", "reviewer": "", "submitted_at": "",
                                 "labels": {n: None for n in NAMES}, "note": None}) + "\n")
    LEAD.parent.mkdir(parents=True, exist_ok=True)
    LEAD.write_text(json.dumps({"packet": "f3-test-73", "review_id_to_row_id": key,
                                "note": "lead only: never send this file to a reviewer"}, indent=1) + "\n")
    (REVIEWS / "incoming").mkdir(parents=True, exist_ok=True)
    print(f"packet: {len(key)} cases -> {PACKET.relative_to(REPO)}; key -> {LEAD.relative_to(REPO)}")


def kappa(a: list, b: list) -> float | None:
    n = len(a)
    if not n:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return None if pe == 1 else round((po - pe) / (1 - pe), 3)


def compile_labels() -> dict:
    files = sorted((REVIEWS / "incoming").glob("*.jsonl"))
    if len(files) < 2:
        raise SystemExit(f"need two reviewers' files in {(REVIEWS / 'incoming').relative_to(REPO)}; found {len(files)}. "
                         "The provisional result stands until then.")
    key = json.loads(LEAD.read_text())["review_id_to_row_id"]
    by = [{json.loads(x)["review_id"]: json.loads(x) for x in f.open(encoding="utf-8") if x.strip()} for f in files[:2]]
    reviewers = [next(iter(b.values()))["reviewer"] for b in by]
    if len(set(reviewers)) < 2 or not all(reviewers):
        raise SystemExit("two different named reviewers are required")
    adj = {}
    p = REVIEWS / "adjudications.jsonl"
    if p.exists():
        for x in p.open(encoding="utf-8"):
            if x.strip():
                v = json.loads(x)
                adj[(v["review_id"], v["topic"])] = v
    agree, open_items, per_topic, out = Counter(), [], {}, []
    for n in NAMES:
        a = [by[0][rid]["labels"][n] for rid in key]
        b = [by[1][rid]["labels"][n] for rid in key]
        per_topic[n] = {"agreement": round(sum(x == y for x, y in zip(a, b)) / len(a), 3), "cohen_kappa": kappa(a, b)}
    for rid, row_id in key.items():
        final = {}
        for n in NAMES:
            x, y = by[0][rid]["labels"][n], by[1][rid]["labels"][n]
            if x == y and x in ("yes", "no"):
                final[n] = x
            elif (rid, n) in adj:
                final[n] = adj[(rid, n)]["label"]
            else:
                open_items.append({"review_id": rid, "topic": n, "reviewers": [x, y]})
        agree["rows"] += 1
        if len(final) == len(NAMES):
            out.append({"id": row_id, "review_id": rid, "topics": final,
                        "expected": "yes" if "yes" in final.values() else ("exclude" if "exclude" in final.values() else "no")})
    report = {"reviewers": reviewers, "rows": len(key), "per_topic_before_adjudication": per_topic,
              "open_items": open_items, "resolved_rows": len(out)}
    (REVIEWS / "status.json").write_text(json.dumps(report, indent=1) + "\n")
    if open_items:
        print(json.dumps(report, indent=1))
        raise SystemExit(f"{len(open_items)} disagreements or unclear answers need adjudication in {p.relative_to(REPO)}")
    (REVIEWS / "corrected-labels.jsonl").write_text("".join(json.dumps(r) + "\n" for r in out))
    print(json.dumps(report, indent=1))
    return report


def rescore() -> int:
    """Rescore the saved responses against the corrected references; thresholds, arms and responses unchanged."""
    lab = {json.loads(x)["id"]: json.loads(x)["expected"] for x in (REVIEWS / "corrected-labels.jsonl").open()}
    changed = 0
    with tempfile.TemporaryDirectory() as td:
        args = []
        for name in ("test", "test-rerun", "ext-test", "pii-v12-test", "prof-v13-test"):
            src = RES / f"{name}.jsonl"
            if not src.exists():
                continue
            dst = Path(td) / f"{name}.jsonl"
            with src.open(encoding="utf-8") as fin, dst.open("w", encoding="utf-8") as fout:
                for line in fin:
                    r = json.loads(line)
                    if r.get("id") in lab and lab[r["id"]] in ("yes", "no"):
                        changed += r["expected"] != lab[r["id"]]
                        r["expected"] = lab[r["id"]]
                    elif r.get("id") in lab:          # excluded by the reviewers: leaves scoring, with the reason recorded
                        continue
                    fout.write(json.dumps(r) + "\n")
            args += [str(dst), str(RES / f"{name}.arms.jsonl")]
        print(f"{changed} ledger records change their reference label; rescoring without new model calls")
        cmd = [sys.executable, str(REPO / "benchmark/runs/leaderboard_v13.py"), "--ledgers", *args,
               "--out", str(RES / "leaderboard-v1.3-f3-corrected.json"),
               "--note", "post-run reference-label correction of the 73 denied-topics test rows (two human reviewers)"]
        return subprocess.run(cmd, cwd=REPO).returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=("packet", "compile", "rescore"))
    a = ap.parse_args()
    if a.step == "packet":
        packet()
    elif a.step == "compile":
        compile_labels()
    else:
        return rescore()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
