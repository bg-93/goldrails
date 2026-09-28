"""Turn reviewers' filled label sheets into dataset/frozen/reviews.jsonl, which the build reads to mark rows reviewed.

    uv run python -m goldrails_dataset.reviews

Reviewers fill a copy of a packet's ``labels.template.jsonl`` (their name in ``reviewer``, every label true or false)
and drop it in ``dataset/frozen/reviews/incoming/``, one file per reviewer and packet. They never see model outputs.

For each case the reviewer's labels become a row label: ``yes`` if any label is true, else ``no`` (for a prompt-attack
case any attack type, for a denied-topics case any topic, for a PII case any entity or other personal information).
A case is final when:
- it is not flagged for a second reviewer and one reviewer labelled it, or
- it is flagged (the key's ``second_reviewer`` list) and two different reviewers agree, or
- an adjudication line settles it (``dataset/frozen/reviews/adjudications.jsonl``: review_id, label, adjudicator).
Disagreements without an adjudication stay open. The build then counts a row as reviewed only when the final label
equals the row's expected label; a reviewer who disagrees with the drafted label leaves the row a candidate, and the
draft is corrected in a new dataset version.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

FROZEN = Path(__file__).resolve().parents[1] / "frozen"
PACKETS = FROZEN / "review-packets"
INCOMING = FROZEN / "reviews" / "incoming"
ADJUDICATIONS = FROZEN / "reviews" / "adjudications.jsonl"
OUT = FROZEN / "reviews.jsonl"


def _jsonl(p: Path) -> list:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []


def keys() -> dict:
    """review_id -> (record_id, needs_second_reviewer)."""
    out = {}
    for k in sorted((PACKETS / "_lead").glob("*.key.json")):
        d = json.loads(k.read_text(encoding="utf-8"))
        second = set(d.get("second_reviewer") or [])
        for rid, rec in (d.get("review_id_to_record_id") or {}).items():
            out[rid] = (rec, rid in second)
    return out


def _yes(v) -> bool:
    return v is True or str(v).strip().lower() in ("true", "yes")


def row_label(labels: dict) -> str | None:
    """A reviewer's row label: yes if any question is yes, unclear if any is unclear (and none yes), no otherwise; None
    for an incomplete sheet. An unclear answer never counts as no: it goes to adjudication."""
    vals = list(labels.values())
    if not vals or any(v is None for v in vals):
        return None                      # incomplete sheet: not counted
    if any(_yes(v) for v in vals):
        return "yes"
    if any(str(v).strip().lower() == "unclear" for v in vals):
        return "unclear"
    return "no"


EXCLUDE = "exclude"


def compile_reviews(incoming: Path = INCOMING, adjudications: Path = ADJUDICATIONS) -> list:
    """Final human labels per case. A final label is yes or no (it replaces the draft in the next dataset version), or
    ``exclude`` when the reviewers agree the case cannot be judged (reason kept). Unclear answers and disagreements
    stay open until an adjudication line settles them."""
    key = keys()
    votes, notes = defaultdict(dict), defaultdict(dict)       # review_id -> {reviewer: label or exclude}
    for f in sorted(incoming.glob("*.jsonl")) if incoming.exists() else []:
        for line in _jsonl(f):
            who = (line.get("reviewer") or "").strip()
            if not who or line.get("review_id") not in key:
                continue
            lab = EXCLUDE if _yes(line.get("exclude_case")) else row_label(line.get("labels") or {})
            if lab:
                votes[line["review_id"]][who] = lab
                if line.get("note"):
                    notes[line["review_id"]][who] = line["note"]
    adj = {a["review_id"]: a for a in _jsonl(adjudications) if a.get("review_id")}
    out = []
    for rid, (rec, second) in sorted(key.items()):
        v = votes.get(rid, {})
        if rid in adj:
            label, final, basis = adj[rid]["label"], True, f"adjudicated by {adj[rid].get('adjudicator')}"
        elif not v:
            continue
        elif second:
            labels = set(v.values())
            agree = len(v) >= 2 and len(labels) == 1 and "unclear" not in labels
            label = labels.pop() if len(labels) == 1 else None
            final = agree
            basis = ("two reviewers agree" if final else
                     "unclear, needs adjudication" if label == "unclear" else
                     "disagreement, needs adjudication" if len(v) >= 2 else "awaiting second reviewer")
        else:
            label = next(iter(v.values()))
            final = label != "unclear"
            basis = "single reviewer" if final else "unclear, needs adjudication"
        excluded = final and label == EXCLUDE
        out.append({"review_id": rid, "id": rec, "label": None if excluded else label, "final": final, "excluded": excluded,
                    "reviewers": sorted(v), "basis": basis, "notes": notes.get(rid) or None})
    return out


B2_KEYS = PACKETS / "_lead" / "bias"
B2_OK = {"same_meaning_apart_from_group": "yes", "both_fluent": "yes", "register_or_dialect_changed": "no", "keep_pair": "yes"}
ACTION = {"flag": "yes", "pass": "no"}


def _yn(v):
    if v is None:
        return None
    v = str(v).strip().lower()
    return {"true": "yes", "false": "no"}.get(v, v)


def b2_verdict(labels: dict):
    """(keep, label) from one reviewer's B2 item: keep only when meaning, fluency and register survived, the reviewer
    kept the pair, and both texts get the same action; label is that action as yes (flag) or no (pass)."""
    if any(_yn(labels.get(k)) != v for k, v in B2_OK.items()):
        return False, None
    a, b = _yn(labels.get("expected_action_A")), _yn(labels.get("expected_action_B"))
    if a not in ACTION or b not in ACTION or a != b:
        return False, None
    return True, ACTION[a]


def compile_b2(incoming: Path = INCOMING, adjudications: Path = ADJUDICATIONS) -> list:
    """B2 pair reviews: a pair is final when two different reviewers both keep it with the same action, or an
    adjudication line (item, keep, action, adjudicator) settles it. Both texts of a kept pair get that label."""
    key = {}
    for k in sorted(B2_KEYS.glob("*.key.jsonl")) if B2_KEYS.exists() else []:
        for d in _jsonl(k):
            key[d["item"]] = d
    votes = defaultdict(dict)
    for f in sorted(incoming.glob("*.jsonl")) if incoming.exists() else []:
        for line in _jsonl(f):
            who = (line.get("reviewer") or "").strip()
            if who and line.get("item") in key and line.get("labels"):
                votes[line["item"]][who] = b2_verdict(line["labels"])
    adj = {a["item"]: a for a in _jsonl(adjudications) if a.get("item")}
    out = []
    for item, k in sorted(key.items()):
        v = votes.get(item, {})
        if item in adj:
            a = adj[item]
            keep, label, basis = bool(a.get("keep")), ACTION.get(_yn(a.get("action"))), f"adjudicated by {a.get('adjudicator')}"
            final = keep and label is not None
        elif len(v) >= 2 and len(set(v.values())) == 1:
            keep, label = next(iter(v.values()))
            final, basis = keep, "two reviewers agree" if keep else "two reviewers agree to drop"
        elif not v:
            continue
        else:
            keep, label, final = False, None, False
            basis = "awaiting second reviewer" if len(v) < 2 else "disagreement, needs adjudication"
        for side in ("A", "B"):
            out.append({"review_id": item, "id": k[side], "label": label, "final": bool(final and keep),
                        "kept": bool(keep), "reviewers": sorted(v), "basis": basis, "packet": "b2", "pair_id": k.get("pair_id")})
    return out


RELEASE_PACKETS = ("f3-denied-topics", "f3-test-candidates", "f4-profanity")


def status(incoming: Path = INCOMING, adjudications: Path = ADJUDICATIONS) -> dict:
    """Exactly which labels still need a person, per release packet: review ids with no label yet, awaiting a second
    reviewer, or in disagreement needing adjudication."""
    done = {r["review_id"]: r for r in compile_reviews(incoming, adjudications)}
    out = {}
    for packet in RELEASE_PACKETS:
        kf = PACKETS / "_lead" / f"{packet}.key.json"
        if not kf.exists():
            continue
        k = json.loads(kf.read_text(encoding="utf-8"))
        second = set(k.get("second_reviewer") or [])
        need = {"no_label": [], "second_reviewer": [], "adjudication": [], "final": 0,
                "total": len(k.get("review_id_to_record_id") or {}), "needs_two_reviewers": sorted(second)}
        for rid in sorted(k.get("review_id_to_record_id") or {}):
            r = done.get(rid)
            if r is None:
                need["no_label"].append(rid)
            elif r["final"]:
                need["final"] += 1
            elif r["basis"] == "awaiting second reviewer":
                need["second_reviewer"].append(rid)
            else:
                need["adjudication"].append(rid)
        out[packet] = need
    b2 = compile_b2(incoming, adjudications)
    items = {}
    for k in sorted(B2_KEYS.glob("*.key.jsonl")) if B2_KEYS.exists() else []:
        for d in _jsonl(k):
            items[d["item"]] = None
    for r in b2:
        items[r["review_id"]] = r
    out["b2"] = {"total": len(items), "final_kept": sum(1 for r in items.values() if r and r["final"]),
                 "decided_drop": sum(1 for r in items.values() if r and r["basis"].endswith("agree to drop")),
                 "no_label": sorted(i for i, r in items.items() if r is None),
                 "second_reviewer": sorted(i for i, r in items.items() if r and r["basis"] == "awaiting second reviewer"),
                 "adjudication": sorted(i for i, r in items.items() if r and r["basis"].startswith("disagreement")),
                 "needs_two_reviewers": "every item"}
    return out


def raw_votes(incoming: Path = INCOMING) -> dict:
    """review_id -> {reviewer: first submitted label (yes, no, unclear or exclude)}: the labels before adjudication."""
    key = keys()
    out = defaultdict(dict)
    for f in sorted(incoming.glob("*.jsonl")) if incoming.exists() else []:
        for line in _jsonl(f):
            who, rid = (line.get("reviewer") or "").strip(), line.get("review_id")
            if not who or rid not in key or who in out[rid]:
                continue
            lab = EXCLUDE if _yes(line.get("exclude_case")) else row_label(line.get("labels") or {})
            if lab:
                out[rid][who] = lab
    return out


def agreement(incoming: Path = INCOMING) -> dict:
    """Agreement between the two independent reviewers, before any adjudication, per packet: cases reviewed twice,
    raw agreement, and Cohen's kappa on the yes/no labels (unclear and exclude count as their own categories)."""
    key_all = keys()
    votes = raw_votes(incoming)
    by_packet = defaultdict(list)
    for rid, v in votes.items():
        if len(v) >= 2:
            a, b = [v[w] for w in sorted(v)[:2]]
            by_packet[rid.rsplit("-r", 1)[0]].append((a, b))
    out = {}
    for packet, pairs in sorted(by_packet.items()):
        n = len(pairs)
        po = sum(a == b for a, b in pairs) / n
        cats = sorted({x for p in pairs for x in p})
        pe = sum((sum(a == c for a, _ in pairs) / n) * (sum(b == c for _, b in pairs) / n) for c in cats)
        out[packet] = {"double_reviewed": n, "raw_agreement": round(po, 4),
                       "cohens_kappa": None if pe >= 1 else round((po - pe) / (1 - pe), 4),
                       "disagreements": sum(a != b for a, b in pairs)}
    return out


def main(argv=None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if "--status" in argv:
        st = status()
        for packet, s in st.items():
            open_ = len(s["no_label"]) + len(s["second_reviewer"]) + len(s["adjudication"])
            print(f"{packet}: {s['total']} cases; {open_} still need a person "
                  f"({len(s['no_label'])} unlabelled, {len(s['second_reviewer'])} awaiting a second reviewer, "
                  f"{len(s['adjudication'])} for adjudication)")
        ag = agreement()
        for packet, a in ag.items():
            print(f"  agreement before adjudication, {packet}: {a['double_reviewed']} cases, raw {a['raw_agreement']:.0%}, kappa {a['cohens_kappa']}")
        excl = [r for r in compile_reviews() if r.get("excluded")]
        (FROZEN / "reviews").mkdir(parents=True, exist_ok=True)
        (FROZEN / "reviews" / "status.json").write_text(json.dumps(
            {"open": st, "agreement_before_adjudication": ag,
             "exclusions": [{"review_id": r["review_id"], "basis": r["basis"], "notes": r["notes"]} for r in excl]},
            indent=1) + "\n", encoding="utf-8")
        return 0
    rows = compile_reviews() + compile_b2()
    OUT.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    final = sum(r["final"] for r in rows)
    print(f"{len(rows)} cases with reviews, {final} final; wrote {OUT.relative_to(FROZEN.parent.parent)}")
    for r in rows:
        if not r["final"]:
            print(f"  open: {r['review_id']} ({r['basis']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
