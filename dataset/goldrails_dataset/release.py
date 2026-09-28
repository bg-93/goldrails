"""Build and package a versioned Gold Rails dataset release. No uploads.

    uv run python -m goldrails_dataset.release --version v1.0

Steps: build the full release sample with the pinned sources (per-cell cap and seed fixed per version), run the
integrity and leakage audit (must pass), then write

- ``dataset/release/<version>/build/``: the canonical records, one file per feature and split (gitignored; the build
  is deterministic, so the manifest's hashes prove any rebuild is the same data),
- ``dataset/release/<version>/hf/``: the Hugging Face layout, one config per suite plus ``bias`` and ``candidates``
  (gitignored until the upload is approved). Rows from sources whose redistribution is not cleared in
  ``dataset/release/redistribution.json`` ship ids-only: text, context, source and query are removed and an
  ``acquisition`` block says how to rebuild them,
- ``dataset/release/<version>/manifest.json`` and ``counts.md`` (committed): version, build parameters, code commit,
  per-file row counts and hashes, counts by suite, subtask, split, class and review status, redistribution mode per
  source, the audit status and the declared exclusions.

A release is immutable: later additions make a new version and never change data beneath an existing result. Every
build goes to a temporary directory first. A new version is promoted only after the audit passes. For an existing
version the command never rewrites anything: it checks the rebuild's canonical hashes against the committed manifest
and only restores ``build/`` or ``hf/`` if they are missing (both are gitignored). Byte hashes can differ on a rebuild
because rows record their import time; the canonical ``dataset_sha256`` values cannot.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

from .build import build, write
from .records import canonical, dataset_hash, read_jsonl

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
SUITES = {"F1": "content", "F2": "prompt_attacks", "F3": "denied_topics", "F4": "word_filters",
          "F5": "sensitive_information", "F6": "grounding", "F7": "bias"}
# v1.1 is v1.0 plus the rows that human review clears (denied topics, B2 pairs). Build it only after the reviews are
# compiled into dataset/frozen/reviews.jsonl: a release is immutable, so building it early would freeze v1.0's data.
VERSIONS = {"v1.0": {"per_cell": 450, "seed": 7}, "v1.1": {"per_cell": 450, "seed": 7},
            # Provisional: denied topics, profanity and B2 labelled by a single AI reviewer on the owner's instruction
            # (24 September 2026) in place of the human review v1.1 requires. Never renamed or merged into v1.1.
            "v1.1-ai": {"per_cell": 450, "seed": 7, "ai_reference": "dataset/frozen/reviews/ai-codex-2026-09-24",
                        "label_policy": ("provisional: denied topics, profanity and B2 pairs carry single-AI reference labels "
                                         "(label_basis llm, review_status ai_reviewed); the human-review requirement is replaced "
                                         "for this provisional extension only, by the owner's instruction to use an AI judge; "
                                         "not independent human annotation and not publication approval")},
            # v1.2: v1.1-ai with the PII source replaced by NVIDIA Nemotron-PII (CC-BY-4.0) after its audit (owner
            # decision, 28 September 2026). Every other cell draws the same rows (per-cell generators).
            "v1.2": {"per_cell": 450, "seed": 7, "ai_reference": "dataset/frozen/reviews/ai-codex-2026-09-24",
                     "plan_overrides": {"F5:pii": ["nemotron_pii", "f5_controls"]},
                     "cell_caps": {"F5:pii": 250},
                     "negative_reviews": "dataset/frozen/reviews/nemotron-negatives",
                     # rows labelled by the AI reference carry v1.1-ai's authorization text unchanged, so every
                     # non-PII row is byte-for-byte the v1.1-ai row
                     "ai_authorization_from": "v1.1-ai",
                     "label_policy": ("provisional: denied topics, profanity and B2 pairs carry single-AI reference labels "
                                      "(label_basis llm, review_status ai_reviewed). PII comes from NVIDIA Nemotron-PII "
                                      "source spans; every negative passed the audit's screen and a blind AI review. Not "
                                      "independent human annotation and not publication approval")},
            # v1.3: v1.2 with the profanity subtask's main sample from Civil Comments' original obscene rater labels
            # (owner decision, 28 September 2026): "Profanity or obscenity — Civil Comments". The lexicon-selected set
            # stays as its separate masked-spelling diagnostic; every other cell draws the same rows.
            "v1.3": {"per_cell": 450, "seed": 7, "ai_reference": "dataset/frozen/reviews/ai-codex-2026-09-24",
                     "plan_overrides": {"F5:pii": ["nemotron_pii", "f5_controls"], "F4:profanity": ["civil_comments_obscene"]},
                     "cell_caps": {"F5:pii": 250, "F4:profanity": 250},
                     "negative_reviews": "dataset/frozen/reviews/nemotron-negatives",
                     "ai_authorization_from": "v1.1-ai",
                     "label_policy": ("provisional: denied topics and B2 pairs carry single-AI reference labels (label_basis "
                                      "llm, review_status ai_reviewed). Profanity uses Civil Comments' original obscene "
                                      "rater fractions as a derived binary label (>= 0.5 yes, 0 no, intermediate excluded). "
                                      "PII comes from NVIDIA Nemotron-PII source spans with every negative blind-reviewed. "
                                      "Not publication approval")}}
EXCLUSIONS = [
    "Automated Reasoning: formal verification is not detection.",
    "Indirect prompt attacks: every LLMail-Inject set tested is separable by trivial baselines (char n-gram AUROC 0.96 to 0.99); diagnostic only.",
    "Grounding query relevance: no labelled source yet; deferred.",
    "Masking: scored separately from detection; not part of the detection release's critical path.",
    "Enumerating a managed service's proprietary profanity vocabulary (profanity detection itself is evaluated), images, "
    "non-English text, streaming and deployment controls.",
    "Bias B2 counterfactual pairs: exploratory diagnostics outside every score.",
]
STRIP = ("text", "context", "source", "query", "tool_call")


def _file_sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _git(*args) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True).stdout.strip()


def redistribution() -> dict:
    return json.loads((ROOT / "release" / "redistribution.json").read_text(encoding="utf-8"))


def mode_of(source: str, policy: dict) -> str:
    s = policy["sources"].get(source)
    if not s:
        return policy["default"]
    return "text" if s["mode"] == "text" and s.get("reviewed") else "ids_only"


def to_hf_row(r, policy: dict) -> dict:
    d = r.to_dict()
    d["canonical_row_hash"] = hashlib.sha256(canonical(r).encode()).hexdigest()
    mode = mode_of(r.provenance.source, policy)
    d["redistribution"] = mode
    if mode == "ids_only":
        for k in STRIP:
            if k in d["state"]:
                d["state"][k] = None
        d["acquisition"] = {"source": r.provenance.source, "source_id": r.provenance.source_id,
                            "rebuild": "uv run python -m goldrails_dataset.release --version <version> (rebuilds text locally from the pinned source)"}
    return d


def package(version: str, out: Path, records: list) -> dict:
    policy = redistribution()
    hf = out / "hf"
    groups = defaultdict(list)
    for r in records:
        config = "candidates" if r.review_status == "candidate" else SUITES[r.feature]
        groups[(config, r.split)].append(r)
    files = []
    for (config, split), rows in sorted(groups.items()):
        p = hf / config / f"{split}.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as fh:
            for r in sorted(rows, key=lambda x: x.id):
                fh.write(json.dumps(to_hf_row(r, policy), ensure_ascii=False, sort_keys=True) + "\n")
        files.append({"path": str(p.relative_to(out)), "config": config, "split": split, "n": len(rows),
                      "dataset_sha256": dataset_hash(rows), "file_sha256": _file_sha(p)})
    return {"files": files, "modes": {s: mode_of(s, policy) for s in sorted({r.provenance.source for r in records})}}


def counts(records: list) -> dict:
    by = Counter((SUITES[r.feature], r.subtask, r.split, str(r.expected), r.review_status) for r in records)
    rows = [{"suite": su, "subtask": st, "split": sp, "class": c, "review_status": rs, "n": n}
            for (su, st, sp, c, rs), n in sorted(by.items())]
    return {"total": len(records), "by_suite": dict(Counter(SUITES[r.feature] for r in records)),
            "by_review_status": dict(Counter(r.review_status for r in records)), "rows": rows}


def counts_md(man: dict) -> str:
    lines = [f"# Gold Rails {man['version']} counts", "",
             f"Generated from `dataset/release/{man['version']}/manifest.json`. {man['counts']['total']} rows.", "",
             "| Suite | Subtask | Split | Class | Review status | Rows |", "|---|---|---|---|---|---|"]
    for r in man["counts"]["rows"]:
        lines.append(f"| {r['suite']} | {r['subtask']} | {r['split']} | {r['class']} | {r['review_status']} | {r['n']} |")
    lines += ["", "## Redistribution", "", "| Source | Mode |", "|---|---|"]
    lines += [f"| {s} | {m} |" for s, m in man["redistribution"].items()]
    lines += ["", "## Exclusions", ""] + [f"- {e}" for e in man["exclusions"]]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="v1.0", choices=sorted(VERSIONS))
    a = ap.parse_args(argv)
    params = VERSIONS[a.version]
    out = ROOT / "release" / a.version
    manifest_path = out / "manifest.json"
    existing = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None
    ai_dir = REPO / params["ai_reference"] if params.get("ai_reference") else None
    reviews = None
    if params.get("negative_reviews"):
        reviews = defaultdict(dict)
        for p in sorted((REPO / params["negative_reviews"]).glob("*.jsonl")):
            for line in p.open(encoding="utf-8"):
                v = json.loads(line)
                reviews[v["source"]][v["id"]] = v["verdict"]
        reviews.setdefault("nemotron_pii", {})
    records = build(params["per_cell"], params["seed"], ai_reference_dir=ai_dir,
                    ai_authorization=VERSIONS[params["ai_authorization_from"]]["label_policy"]
                    if params.get("ai_authorization_from") else params.get("label_policy"), pii_parent_groups=params.get("pii_parent_groups", False),
                    plan_overrides={tuple(k.split(":")): v for k, v in (params.get("plan_overrides") or {}).items()},
                    cell_caps=params.get("cell_caps"),
                    negative_reviews=reviews)
    from .build import build as _built
    if getattr(_built, "unverified", None):
        pending = REPO / params["negative_reviews"] / "pending.json"
        pending.parent.mkdir(parents=True, exist_ok=True)
        pending.write_text(json.dumps(sorted(_built.unverified), indent=1) + "\n", encoding="utf-8")
        raise SystemExit(f"{len(_built.unverified)} chosen negatives have no blind review yet; ids in "
                         f"{pending.relative_to(REPO)}; nothing written")
    release_sha = dataset_hash(records)
    if existing and existing.get("release_sha256") != release_sha:
        raise SystemExit(f"{a.version} already exists with different data ({existing['release_sha256'][:12]}, rebuild "
                         f"{release_sha[:12]}); nothing written; make a new version")
    (ROOT / "release").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{a.version}-", dir=ROOT / "release") as tmpd:
        tmp = Path(tmpd)
        write(records, tmp / "build")
        from .audit import main as audit_main
        rc = audit_main(["--sample", str(tmp / "build"), "--out", str(tmp / "audit-report.json")])
        audit = json.loads((tmp / "audit-report.json").read_text(encoding="utf-8"))
        if audit["status"] != "pass":
            raise SystemExit(f"audit failed: {audit['failed_gates']}; nothing written")
        build_files = [{"path": f"build/{p.name}", "n": sum(1 for _ in p.open()), "dataset_sha256": dataset_hash(read_jsonl(p)),
                        "file_sha256": _file_sha(p)} for p in sorted((tmp / "build").glob("*.jsonl"))]
        pkg = package(a.version, tmp, records)
        if existing:
            want = {f["path"]: f["dataset_sha256"] for f in existing["build_files"] + existing["hf_files"]}
            got = {f["path"]: f["dataset_sha256"] for f in build_files + pkg["files"]}
            bad = sorted(p for p in set(want) | set(got) if want.get(p) != got.get(p))
            if bad:
                raise SystemExit(f"{a.version}: rebuild differs from the committed manifest in {bad[:5]}; nothing written")
            restored = [d for d in ("build", "hf") if not (out / d).exists()]
            for d in restored:
                shutil.copytree(tmp / d, out / d)
            print(f"{a.version}: rebuild matches the committed manifest (release sha {release_sha[:12]}); manifest unchanged; "
                  + (f"restored {', '.join(restored)}" if restored else "nothing restored"))
            return 0 if rc == 0 else rc
        from .build import build as _b
        man = {"version": a.version, "immutable": True, "label_policy": params.get("label_policy", "source labels and human review"),
               "ai_reference": params.get("ai_reference"), "review_counts": getattr(_b, "review_counts", None),
               "build": {"command": f"uv run python -m goldrails_dataset.release --version {a.version}", **params,
                         "code_commit": _git("rev-parse", "HEAD"), "loaders_dirty": bool(_git("status", "--porcelain", "dataset/goldrails_dataset"))},
               "release_sha256": release_sha, "audit": {"status": audit["status"], "failed_gates": audit["failed_gates"],
                                                        "warnings": sorted({w["kind"] for w in audit["warnings"]})},
               "counts": counts(records), "build_files": build_files, "hf_files": pkg["files"], "redistribution": pkg["modes"],
               "exclusions": EXCLUSIONS}
        out.mkdir(parents=True)
        for name in ("build", "hf", "audit-report.json"):
            shutil.move(str(tmp / name), str(out / name))
    manifest_path.write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")
    (out / "counts.md").write_text(counts_md(man), encoding="utf-8")
    print(f"{a.version}: {man['counts']['total']} rows, release sha {man['release_sha256'][:12]}, audit {audit['status']}")
    print(json.dumps(man["counts"]["by_suite"]), json.dumps(man["counts"]["by_review_status"]))
    return 0 if rc == 0 else rc


if __name__ == "__main__":
    raise SystemExit(main())
