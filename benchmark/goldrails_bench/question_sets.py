"""Question sets are the versioned question sets sent to decision models. They live
in question_sets/<version>/<name>.json and are loaded, never edited, by code."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "question_sets"


def load(version: str, name: str) -> dict:
    return json.loads((ROOT / version / f"{name}.json").read_text(encoding="utf-8"))


def available(version: str = "v1") -> list:
    return sorted(p.stem for p in (ROOT / version).glob("*.json"))


SEP = "__"


def merge(qsets: dict) -> dict:
    """Several question sets -> one questions dict for a single call, keys namespaced ``<set>__<question>``.

    System One evaluates every question in a call independently and in parallel (TypeSafe: "adding more questions to a
    call typically doesn't add any latency"), so one call per row carrying every question set replaces one call per
    row per set. ``split`` puts the answers back under their own set. Set names must not contain the separator."""
    out = {}
    for sname, qs in qsets.items():
        if SEP in sname:
            raise ValueError(f"question set name {sname!r} must not contain {SEP!r}")
        for qname, q in qs["questions"].items():
            out[f"{sname}{SEP}{qname}"] = q
    return out


def split(answers: dict) -> dict:
    """Inverse of ``merge``: {set: {question: answer}}."""
    out: dict = {}
    for key, a in (answers or {}).items():
        sname, qname = key.split(SEP, 1)
        out.setdefault(sname, {})[qname] = a
    return out
