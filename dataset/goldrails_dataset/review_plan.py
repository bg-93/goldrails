"""Which cases a second, independent reviewer labels, written into each release packet's lead key before review.

    uv run python -m goldrails_dataset.review_plan --mode sample     # every ambiguous case + a random 25% of the rest
    uv run python -m goldrails_dataset.review_plan --mode full       # every case, double-reviewed

A second review only of the cases someone thought hard would measure agreement on hard cases, not on the dataset.
``sample`` keeps every case already flagged as ambiguous and adds a seeded random share of the remaining cases,
stratified by the case's drafted label, so agreement can be reported for the dataset as a whole. ``full`` sends every
case to both reviewers. The plan is recorded in the key (``second_review_plan``) with its seed, so it can be checked
and cannot drift after reviews start. B2 pairs are always reviewed twice.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

LEAD = Path(__file__).resolve().parents[1] / "frozen" / "review-packets" / "_lead"
PACKETS = ("f3-denied-topics", "f3-test-candidates", "f4-profanity")
SHARE, SEED = 0.25, "gold-rails-second-review-v1"


def _draft(key: dict, rid: str) -> str:
    """The drafted label a case was selected or written with, for stratifying the sample; 'unknown' if none."""
    if rid in (key.get("draft_labels") or {}):
        return str(key["draft_labels"][rid])
    p = (key.get("proposed") or {}).get(rid)
    if isinstance(p, dict) and p.get("expected") is not None:
        return str(p["expected"])
    return "unknown"


def plan(mode: str, packets=PACKETS, lead: Path = LEAD) -> dict:
    out = {}
    for name in packets:
        kf = lead / f"{name}.key.json"
        if not kf.exists():
            continue
        key = json.loads(kf.read_text(encoding="utf-8"))
        ids = sorted(key.get("review_id_to_record_id") or {})
        flagged = sorted(set((key.get("second_review_plan") or {}).get("flagged") or key.get("second_reviewer") or []))
        if mode == "full":
            chosen, sampled = ids, [i for i in ids if i not in flagged]
        else:
            rng = random.Random(f"{SEED}:{name}")
            rest = [i for i in ids if i not in flagged]
            sampled = []
            for lab in sorted({_draft(key, i) for i in rest}):
                cell = [i for i in rest if _draft(key, i) == lab]
                rng.shuffle(cell)
                sampled += cell[: round(SHARE * len(cell))]
            chosen = sorted(set(flagged) | set(sampled))
        key["second_review_plan"] = {"mode": mode, "share": None if mode == "full" else SHARE, "seed": SEED,
                                     "flagged": flagged, "sampled": sorted(sampled), "total": len(chosen),
                                     "rule": ("every case" if mode == "full" else
                                              "every flagged ambiguous case plus a seeded random share of the rest, "
                                              "stratified by drafted label")}
        key["second_reviewer"] = sorted(chosen)
        kf.write_text(json.dumps(key, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        out[name] = {"cases": len(ids), "second_review": len(chosen), "flagged": len(flagged), "sampled": len(sampled)}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("sample", "full"), default="sample")
    a = ap.parse_args(argv)
    for name, n in plan(a.mode).items():
        print(f"{name}: {n['second_review']} of {n['cases']} to a second reviewer ({n['flagged']} flagged, {n['sampled']} sampled)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
