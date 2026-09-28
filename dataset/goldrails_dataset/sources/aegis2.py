"""NVIDIA Aegis AI Content Safety Dataset 2.0, test split. CC-BY-4.0.
Prompts are human-labelled; responses are labelled by humans or an LLM jury
(recorded in label_basis). Rows whose prompt is REDACTED are skipped.
Response rows carry their prompt as context, because a reply is only judgeable
next to the request that caused it.
"""
from __future__ import annotations

from ..records import Category, Provenance, Record, State, make_id
from ..taxonomy import AEGIS2, bedrock_for
from .base import now

NAME, LICENCE = "aegis2", "cc-by-4.0"
REVISION = "d86bb8bedff51d25ac834ab7838f1cc61acb7a2c"   # pinned Hugging Face dataset revision
URL = "https://huggingface.co/datasets/nvidia/Aegis-AI-Content-Safety-Dataset-2.0"


def _first_category(violated: str) -> tuple[str | None, str | None]:
    for raw in [c.strip() for c in (violated or "").split(",") if c.strip()]:
        mapped = AEGIS2.get(raw)
        if mapped:
            return mapped, raw
    return None, (violated or None)


def load(limit=None) -> list:
    from datasets import load_dataset
    ds = load_dataset("nvidia/Aegis-AI-Content-Safety-Dataset-2.0", split="test", revision=REVISION)
    out = []
    for row in ds:
        if row["prompt"] == "REDACTED" or not row["prompt"]:
            continue
        cats = row["violated_categories"] or ""
        needs_caution = "Needs Caution" in cats
        ail, src_label = _first_category(cats)
        unsafe = row["prompt_label"] == "unsafe"
        cat = Category(ailuminate=ail if unsafe else "benign", bedrock=bedrock_for(ail) if unsafe else "NONE", source_label=src_label)
        out.append(Record(
            id=make_id("F1", NAME, f"{row['id']}:prompt"), feature="F1", subtask="input",
            state=State(role="user", text=row["prompt"]), category=cat,
            labels=["no", "yes"], expected="yes" if unsafe else "no",
            provenance=Provenance(source=NAME, source_id=f"{row['id']}:prompt", licence=LICENCE,
                                  label_basis="human" if row["prompt_label_source"] == "human" else "llm",
                                  imported_at=now(), contamination=["qwen3guard-eval", "dynaguard-train"],
                                  exclude_reason="needs_caution" if needs_caution else None),
        ))
        if row["response"] and row["response_label"]:
            r_unsafe = row["response_label"] == "unsafe"
            out.append(Record(
                id=make_id("F1", NAME, f"{row['id']}:response"), feature="F1", subtask="output",
                state=State(role="assistant", text=row["response"], context=[{"role": "user", "text": row["prompt"]}]),
                category=Category(ailuminate=ail if r_unsafe else "benign", bedrock=bedrock_for(ail) if r_unsafe else "NONE", source_label=src_label),
                labels=["no", "yes"], expected="yes" if r_unsafe else "no",
                provenance=Provenance(source=NAME, source_id=f"{row['id']}:response", licence=LICENCE,
                                      label_basis="human" if row["response_label_source"] == "human" else "llm",
                                      imported_at=now(), contamination=["qwen3guard-eval", "dynaguard-train"],
                                      exclude_reason="needs_caution" if needs_caution else None),
            ))
        if limit and len(out) >= limit:
            break
    return out
