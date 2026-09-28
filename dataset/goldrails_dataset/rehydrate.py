"""Rebuild the text of ids-only rows in a published Gold Rails folder, from the original publishers. No upload.

    uv run python -m goldrails_dataset.rehydrate --data <folder with data/<config>/<split>.jsonl> --out <folder>

For each ids-only row whose source can be fetched publicly, this loads the source with its pinned loader, puts the
stripped fields (text, context, source, query, tool call) back, and checks the result against the row's
``canonical_row_hash``. A row is written only if its hash matches, so a rebuilt row is byte-for-byte the row the
benchmark used. Rows from sources that cannot be rebuilt from a public copy are left ids-only and listed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from .records import VOLATILE
from .release import STRIP
from .sources import SOURCES

# Sources with a public copy the loader can fetch at a pinned revision.
REBUILDABLE = {"ragtruth": {}, "civil_comments_identity": {"row_groups": list(range(0, 40))}}
PUBLISHED_ONLY = ("redistribution", "acquisition", "canonical_row_hash")


def row_hash(d: dict) -> str:
    """The same canonical form as records.canonical, applied to a published row."""
    d = {k: v for k, v in d.items() if k not in PUBLISHED_ONLY}
    d["provenance"] = {k: v for k, v in d["provenance"].items() if k not in VOLATILE}
    return hashlib.sha256(json.dumps(d, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--sources", nargs="*", default=sorted(REBUILDABLE))
    a = ap.parse_args(argv)
    files = sorted((a.data / "data").glob("*/*.jsonl"))
    rows = {p: [json.loads(line) for line in p.open(encoding="utf-8")] for p in files}
    wanted = {r["id"] for rs in rows.values() for r in rs
              if r.get("redistribution") == "ids_only" and r["provenance"]["source"] in a.sources}
    fresh = {}
    for s in a.sources:
        if s not in REBUILDABLE:
            raise SystemExit(f"{s} has no public rebuild path")
        for rec in SOURCES[s].load(**REBUILDABLE[s]):
            if rec.id in wanted:
                fresh[rec.id] = rec.to_dict()["state"]
    tally = Counter()
    for p, rs in rows.items():
        out = a.out / "data" / p.parent.name / p.name
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as fh:
            for r in rs:
                if r["id"] in wanted:
                    state = fresh.get(r["id"])
                    if state is None:
                        tally["not found upstream"] += 1
                    else:
                        filled = {**r, "state": {**r["state"], **{k: state.get(k) for k in STRIP if k in r["state"]}}}
                        if row_hash(filled) == r["canonical_row_hash"]:
                            r = {**filled, "redistribution": "rebuilt_locally"}
                            tally["rebuilt, hash matches"] += 1
                        else:
                            tally["hash differs, left ids-only"] += 1
                elif r.get("redistribution") == "ids_only":
                    tally[f"ids-only, no public rebuild ({r['provenance']['source']})"] += 1
                fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps(dict(tally), indent=1))
    return 1 if tally["hash differs, left ids-only"] or tally["not found upstream"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
