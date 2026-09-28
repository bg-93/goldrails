"""Move ledger records to the current dataset version only when the row's content is provably unchanged.

For every record, the origin dataset version is the recorded ``dataset.sha256`` (or ``dataset.rehashed_from`` if an
earlier, weaker rehash already moved it). The origin rows are recovered from Git history of the sample file (every
committed version is tried under both the old hash rule, which included import timestamps, and the current one).
A record moves to the current version only if its row's canonical content (text, context, source, query, labels,
spans, category, provenance minus timestamps) is identical in the origin and in the current file; ``row_hash`` on
newer records is checked against the origin too. Otherwise the record keeps, or is reverted to, its origin version
and says why. Nothing is deleted: attempt history stays in the file, and the scorer's dedupe keeps the last record
per arm and row while reporting how many earlier attempts, and how many failures, it superseded.

    uv run python -m goldrails_bench.rehash_ledger benchmark/results/smoke-*.jsonl
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from goldrails_dataset.records import Record, canonical, dataset_hash

REPO = Path(__file__).resolve().parents[2]


def old_hash(rows) -> str:
    h = hashlib.sha256()
    for blob in sorted(r.to_json() for r in rows):
        h.update(blob.encode("utf-8")); h.update(b"\n")
    return h.hexdigest()


def rows_of(text: str) -> list:
    return [Record.from_dict(json.loads(l)) for l in text.splitlines() if l.strip()]


def git_versions(rel_path: str) -> list[dict]:
    """Every version of a sample file: the working copy first, then each commit, as
    {sha_old, sha_new, rows: {id: canonical hash}, ref}."""
    out = []
    p = REPO / rel_path
    if p.exists():
        rows = rows_of(p.read_text(encoding="utf-8"))
        out.append({"ref": "working", "sha_old": old_hash(rows), "sha_new": dataset_hash(rows), "rows": {r.id: _rh(r) for r in rows}})
    log = subprocess.run(["git", "log", "--format=%H", "--", rel_path], cwd=REPO, capture_output=True, text=True).stdout.split()
    for commit in log:
        try:
            text = subprocess.run(["git", "show", f"{commit}:{rel_path}"], cwd=REPO, capture_output=True, text=True, check=True).stdout
        except subprocess.CalledProcessError:
            continue
        rows = rows_of(text)
        out.append({"ref": commit[:10], "sha_old": old_hash(rows), "sha_new": dataset_hash(rows), "rows": {r.id: _rh(r) for r in rows}})
    return out


def _rh(r) -> str:
    return hashlib.sha256(canonical(r).encode()).hexdigest()[:16]


def main(paths):
    cache: dict[str, list] = {}
    for path in paths:
        p = Path(path)
        recs = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
        counts = {"moved": 0, "kept": 0, "reverted": 0, "unknown_origin": 0, "already_current": 0}
        moved_arms = set()
        for r in recs:
            d = r.get("dataset") or {}
            if not (d.get("source") and d.get("feature") and d.get("split")):
                counts["unknown_origin"] += 1; continue
            rel = f"{d['source']}/{d['feature']}.{d['split']}.jsonl"
            versions = cache.setdefault(rel, git_versions(rel))
            current = versions[0] if versions and versions[0]["ref"] == "working" else None
            origin_sha = d.get("rehashed_from") or d.get("sha256")
            origin = next((v for v in versions if origin_sha in (v["sha_old"], v["sha_new"])), None)
            if current and origin_sha == current["sha_new"] and not d.get("rehashed_from"):
                counts["already_current"] += 1; continue
            if origin is None:
                if d.get("rehashed_from"):        # an earlier rehash moved it without proof: put it back
                    d["sha256"] = d.pop("rehashed_from"); d["rehash_note"] = "reverted: origin version not in git, content unverifiable"
                    counts["reverted"] += 1
                else:
                    d["rehash_note"] = "kept: origin version not in git"; counts["unknown_origin"] += 1
                continue
            o_rh = origin["rows"].get(r["id"]); c_rh = current["rows"].get(r["id"]) if current else None
            if r.get("row_hash") and o_rh and r["row_hash"] != o_rh:
                d["rehash_note"] = "kept: record row_hash disagrees with the origin version"; counts["kept"] += 1; continue
            if o_rh and c_rh and o_rh == c_rh:
                if d.get("sha256") != current["sha_new"]:
                    d["rehashed_from"] = origin_sha; d["sha256"] = current["sha_new"]; d["rehash_note"] = f"moved: content identical to origin {origin['ref']}"
                    counts["moved"] += 1; moved_arms.add((r.get("config_hash"), origin_sha, current["sha_new"]))
                else:
                    d["rehashed_from"] = origin_sha; d["rehash_note"] = f"verified: content identical to origin {origin['ref']}"; counts["already_current"] += 1
            else:
                if d.get("rehashed_from"):
                    d["sha256"] = d.pop("rehashed_from"); d["rehash_note"] = "reverted: content differs from the current file"; counts["reverted"] += 1
                else:
                    d["rehash_note"] = "kept: content differs from the current file"; counts["kept"] += 1
        p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs), encoding="utf-8")
        arms = p.with_name(p.stem + ".arms.jsonl")
        if arms.exists() and moved_arms:
            al = [json.loads(l) for l in arms.read_text(encoding="utf-8").splitlines() if l.strip()]
            have = {(a["config_hash"], (a.get("dataset") or {}).get("sha256")) for a in al}
            add = []
            for cfg, old, new in moved_arms:
                src = next((a for a in al if a["config_hash"] == cfg and (a.get("dataset") or {}).get("sha256") in (old, None)), None)
                if src and (cfg, new) not in have:
                    a2 = json.loads(json.dumps(src)); a2.setdefault("dataset", {}); a2["dataset"] = {**(a2["dataset"] or {}), "sha256": new, "rehashed_from": old}
                    add.append(a2); have.add((cfg, new))
            if add:
                arms.write_text("".join(json.dumps(a, ensure_ascii=False) + "\n" for a in al + add), encoding="utf-8")
        print(f"{p.name}: {counts}")


if __name__ == "__main__":
    main(sys.argv[1:])
