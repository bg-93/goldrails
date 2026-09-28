"""Evidence that the frozen Bedrock custom-word arm's any_word defect changed no result.

    uv run python benchmark/runs/check_any_word.py

The adapter's ``any_word`` answer for the words guardrail took the maximum over the custom words and the managed
profanity flag, so a managed-profanity hit could have raised it on a custom-word row. This reads every stored raw
response of ``bedrock-apply-words`` in the first benchmark's ledgers and reports how many reported a managed-list
detection, and whether ``any_word`` ever differed from the maximum over the custom words alone. Writes
``benchmark/results/first-benchmark/any-word-check.json``.
"""
from __future__ import annotations

import json
from pathlib import Path

RES = Path(__file__).resolve().parents[2] / "benchmark" / "results" / "first-benchmark"
LEDGERS = ("tune.jsonl", "test.jsonl", "test-rerun.jsonl", "latency.jsonl")
CUSTOM = ("project_falcon", "acme_secret_sauce", "internal_codename_bluebird", "confidential_roadmap")


def main() -> int:
    out = {"ledgers": {}, "rule": "any_word must equal the max over the four custom words on every row"}
    for name in LEDGERS:
        p = RES / name
        if not p.exists():
            continue
        n = managed = differs = 0
        for line in p.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r.get("system") != "bedrock-apply-words" or not r.get("ok"):
                continue
            n += 1
            raws = r["raw"] if isinstance(r.get("raw"), list) else [r.get("raw")]
            for raw in raws:
                for block in (raw or {}).get("assessments") or []:
                    managed += sum(1 for m in (block.get("wordPolicy") or {}).get("managedWordLists", []) if m.get("detected"))
            a = {k.split("/")[-1]: v.get("noul") for k, v in (r.get("answers") or {}).items()}
            if "any_word" in a and max(a.get(w, 0.0) for w in CUSTOM) != a["any_word"]:
                differs += 1
        out["ledgers"][name] = {"rows": n, "managed_profanity_detections": managed, "any_word_differs_from_custom_max": differs}
    out["affected_results"] = sum(v["any_word_differs_from_custom_max"] for v in out["ledgers"].values())
    (RES / "any-word-check.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
