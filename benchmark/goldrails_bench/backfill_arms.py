"""Reconstruct the arms sidecar for a ledger written before the runner recorded one. No inference calls.

    uv run python -m goldrails_bench.backfill_arms benchmark/results/smoke-prompt-attacks.jsonl

For every arm in the ledger, the complete original config hash (system, model, identity, endpoint, exact questions)
is recomputed from the current question-set file and the endpoint and identity the system would have had. An entry
is written as ``reconstructed: true`` only when the recomputed hash equals the recorded one, which proves the wording
and identity are the ones that were sent. Anything else is written as ``status: unknown`` with the reason.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

from .question_sets import load
from .runner import config_hash


def candidates(system: str, records: list[dict]) -> list[SimpleNamespace]:
    """Plausible client identities for a system name, in the order they would have been used."""
    model = next((r.get("model") for r in records if r.get("model")), None)
    out = []
    if system.startswith("jev"):
        out.append(SimpleNamespace(system=system, model=model, identity={"model": model, "provider": "api.typesafe.ai"}, client=SimpleNamespace(base_url=None)))
    elif system == "bedrock-checks":
        from .bedrock import MODEL
        for date in sorted({time.strftime("%Y-%m-%d", time.gmtime(os.path.getmtime(p))) for p in [Path(sys.argv[1])]} | {time.strftime("%Y-%m-%d")}):
            for region in (os.environ.get("AWS_REGION") or "us-east-1", "us-east-1", "ap-southeast-2"):
                out.append(SimpleNamespace(system=system, model=MODEL, identity={"api": "InvokeGuardrailChecks", "region": region, "versioned": False, "date": date}, client=SimpleNamespace(base_url=None)))
    else:
        try:
            from .endpoints import describe, model_alias
            for m in describe()["models"]:
                if m["name"] == system:
                    out.append(SimpleNamespace(system=system, model=model_alias(m), identity={"ref": m.get("ref"), "revision": m.get("revision"), "kind": m["kind"]},
                                               client=SimpleNamespace(base_url=f"http://localhost:{m['port']}")))
        except Exception as e:  # noqa: BLE001
            print(f"{system}: cannot resolve served identity ({type(e).__name__}); will be unknown")
    return out


def main(path: str):
    p = Path(path)
    ledger = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    arms_path = p.with_name(p.stem + ".arms.jsonl")
    have = {}
    if arms_path.exists():
        for l in arms_path.read_text(encoding="utf-8").splitlines():
            if l.strip():
                a = json.loads(l); have[(a["config_hash"], (a.get("dataset") or {}).get("sha256"))] = a
    seen = {}
    for r in ledger:
        key = (r["system"], r["question_set"], r.get("config_hash"), (r.get("dataset") or {}).get("sha256"))
        seen.setdefault(key, []).append(r)
    written = []
    for (system, qname, cfg, dsha), rs in seen.items():
        if (cfg, dsha) in have:
            continue
        entry = {"config_hash": cfg, "system": system, "question_set": qname, "dataset": rs[0].get("dataset"),
                 "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "reconstructed": True}
        if not cfg:
            entry.update(status="unknown", reason="ledger predates config hashes; wording and identity not recoverable", reconstructed=False)
        else:
            sets = rs[0].get("question_sets") or [qname]
            try:
                qsets = {n: load(*n.split("-", 1)) for n in sets}
                from .question_sets import merge
                qs = {"questions": merge(qsets)} if (len(sets) > 1 or qname == "all") else qsets[sets[0]]
            except Exception as e:  # noqa: BLE001
                qs = None; entry.update(status="unknown", reason=f"question set file missing: {e}", reconstructed=False)
            match = None
            if qs:
                for c in candidates(system, rs):
                    if config_hash(c, qs) == cfg:
                        match = c; break
            if match:
                entry.update(model=match.model, identity=match.identity, base_url=match.client.base_url, questions=qs["questions"], status="reconstructed",
                             verified="recomputed config hash equals the recorded hash: system, model, identity, endpoint and wording all match")
            elif "status" not in entry:
                entry.update(status="unknown", reason="no candidate identity reproduces the recorded config hash", reconstructed=False)
        with arms_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        written.append((system, qname, entry["status"]))
    for w in written:
        print(*w)
    print(f"wrote {len(written)} arms to {arms_path}")


if __name__ == "__main__":
    main(sys.argv[1])
