"""Select the first benchmark subset from a frozen dataset release, before any model output is seen.

    uv run python -m goldrails_bench.subset --release v1.0 --name first-benchmark

Rules (handoff of 23 September 2026 and docs/19):
- Only eligible rows: review_status source_label, deterministic or reviewed. Candidates never enter a scored subset.
- Tuning rows come from the release's tune split and test rows from its test split; nothing is promoted, and rows
  already examined stay tuning-only because the release put them there.
- Stratified by (feature, subtask, class) with fixed per-cell quotas, taking every row when a cell is smaller, and a
  seeded shuffle per cell so the choice is reproducible and independent of other cells.
- The manifest records the release version and hash, the seed, the quotas, every selected id with its group, and
  counts by suite, subtask, split and class. It is committed before any test call; the freeze manifest refers to it.

The quotas give roughly 1,000 to 2,000 core cases plus a modest bias subset: a planning range, not a statistical
guarantee. Sample sizes and intervals are disclosed with every result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from goldrails_dataset.records import dataset_hash, read_jsonl

REPO = Path(__file__).resolve().parents[2]
ELIGIBLE = ("source_label", "deterministic", "reviewed")
SUITES = {"F1": "content", "F2": "prompt_attacks", "F3": "denied_topics", "F4": "word_filters",
          "F5": "sensitive_info", "F6": "grounding", "F7": "bias"}
# rows per (feature, subtask, class) cell
QUOTAS = {"core": {"tune": 25, "test": 80}, "F7": {"tune": 15, "test": 50},
          # per (feature, subtask) where the plan fixes sizes: profanity 40 tuning and 160 test, balanced by class
          "cells": {"F4:profanity": {"tune": 20, "test": 80}}}
SUBSETS = REPO / "benchmark" / "subsets"


def release_rows(release: str) -> tuple[list, dict]:
    base = REPO / "dataset" / "release" / release
    man = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
    rows = []
    for p in sorted((base / "build").glob("*.jsonl")):
        rows += read_jsonl(p)
    if dataset_hash(rows) != man["release_sha256"]:
        raise SystemExit(f"release {release} build does not match its manifest; rebuild it first")
    return rows, man


def select(rows: list, seed: int = 20260923, quotas: dict = QUOTAS, eligible=ELIGIBLE) -> list:
    cells = defaultdict(list)
    for r in rows:
        if r.review_status in eligible:
            cells[(r.feature, r.subtask, str(r.expected), r.split)].append(r)
    chosen = []
    for key in sorted(cells):
        feature, subtask, cls, split = key
        q = ((quotas.get("cells") or {}).get(f"{feature}:{subtask}")
             or (quotas["F7"] if feature == "F7" else quotas["core"]))[split]
        pool = sorted(cells[key], key=lambda r: r.id)
        random.Random(f"{seed}:" + ":".join(key)).shuffle(pool)
        chosen += pool[:q]
    return chosen


def counts(rows: list) -> list:
    c = Counter((SUITES[r.feature], r.subtask, r.split, str(r.expected)) for r in rows)
    return [{"suite": a, "subtask": b, "split": s, "class": k, "n": n} for (a, b, s, k), n in sorted(c.items())]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", default="v1.0")
    ap.add_argument("--name", default="first-benchmark")
    ap.add_argument("--seed", type=int, default=20260923)
    ap.add_argument("--allow-ai-reviewed", action="store_true",
                    help="provisional subset: also admit rows labelled by a single AI reviewer (review_status ai_reviewed)")
    ap.add_argument("--carry-over", help="an earlier subset whose frozen test results this one must keep: every test "
                    "row of every feature listed in --carry-features must be identical, or nothing is written")
    ap.add_argument("--carry-features", default="F1,F2,F4,F5,F6")
    ap.add_argument("--cell-quota", action="append", default=[], metavar="FEATURE:SUBTASK=TUNE,TEST",
                    help="rows per class for one cell, overriding the default quotas (e.g. F4:profanity=25,80)")
    a = ap.parse_args(argv)
    quotas = json.loads(json.dumps(QUOTAS))
    for q in a.cell_quota:
        cell, sizes = q.split("=")
        tune, test = (int(x) for x in sizes.split(","))
        quotas["cells"][cell] = {"tune": tune, "test": test}
    rows, man = release_rows(a.release)
    eligible = ELIGIBLE + (("ai_reviewed",) if a.allow_ai_reviewed else ())
    chosen = select(rows, a.seed, quotas=quotas, eligible=eligible)
    if a.carry_over:
        problems = carry_over_problems(chosen, a.carry_over, a.carry_features.split(","))
        if problems:
            raise SystemExit("subset would change frozen test rows: " + "; ".join(problems))
    out = SUBSETS / a.name / "manifest.json"
    ineligible = Counter((SUITES[r.feature], r.review_status) for r in rows if r.review_status not in eligible)
    suites_present = {SUITES[r.feature] for r in chosen if r.split == "test"}
    doc = {"name": a.name, "release": a.release, "release_sha256": man["release_sha256"], "seed": a.seed, "quotas": quotas,
           "eligible_review_statuses": list(eligible), "selected_before_any_model_output": True,
           "provisional_ai_reference": a.allow_ai_reviewed,
           "subset_sha256": dataset_hash(chosen),
           "totals": {"core_tune": sum(1 for r in chosen if r.feature != "F7" and r.split == "tune"),
                      "core_test": sum(1 for r in chosen if r.feature != "F7" and r.split == "test"),
                      "bias_tune": sum(1 for r in chosen if r.feature == "F7" and r.split == "tune"),
                      "bias_test": sum(1 for r in chosen if r.feature == "F7" and r.split == "test")},
           "suites_without_eligible_test_rows": sorted(set(SUITES.values()) - suites_present),
           "ineligible_rows": [{"suite": s, "review_status": st, "n": n} for (s, st), n in sorted(ineligible.items())],
           "counts": counts(chosen),
           "rows": [{"id": r.id, "feature": r.feature, "subtask": r.subtask, "split": r.split, "expected": r.expected,
                     "group": r.group, "source": r.provenance.source} for r in sorted(chosen, key=lambda r: r.id)]}
    if out.exists():
        old = json.loads(out.read_text(encoding="utf-8"))
        if old["subset_sha256"] != doc["subset_sha256"]:
            raise SystemExit(f"subset {a.name} already exists with different rows; choose a new name")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(doc["totals"]), "missing:", doc["suites_without_eligible_test_rows"])
    return 0


def carry_over_problems(chosen: list, earlier: str, features) -> list:
    """Differences between this selection's test rows and an earlier subset's, per feature. The earlier subset's
    results were frozen on those rows; a new release version may add rows elsewhere but must not move these."""
    old = json.loads((SUBSETS / earlier / "manifest.json").read_text(encoding="utf-8"))
    out = []
    for f in features:
        subs = {x["subtask"] for x in old["rows"] if x["feature"] == f}     # a new subtask may join; old ones may not move
        was = {x["id"] for x in old["rows"] if x["feature"] == f and x["split"] == "test"}
        now = {r.id for r in chosen if r.feature == f and r.split == "test" and r.subtask in subs}
        if was != now:
            out.append(f"{f}: {len(now - was)} added, {len(was - now)} removed")
    return out


def load_subset_rows(name: str, feature: str, split: str) -> list:
    """The selected rows of one feature and split, read from the release build and checked against the manifest."""
    man = json.loads((SUBSETS / name / "manifest.json").read_text(encoding="utf-8"))
    rows, rman = release_rows(man["release"])
    if rman["release_sha256"] != man["release_sha256"]:
        raise SystemExit("release changed beneath the subset")
    want = {x["id"] for x in man["rows"] if x["feature"] == feature and x["split"] == split}
    out = [r for r in rows if r.id in want]
    tag = {"source": f"subset:{name}", "release": man["release"], "feature": feature, "split": split,
           "sha256": dataset_hash(out), "subset_sha256": man["subset_sha256"]}
    for r in out:
        r.dataset = tag
    return out


if __name__ == "__main__":
    raise SystemExit(main())
