"""OR-Bench hard-1k: benign prompts that look unsafe, for over-refusal. CC-BY-4.0.
Labels are by construction (the set is curated to be benign), recorded as automated: membership in the curated set,
not a human judgment per row.
"""
from __future__ import annotations

from ..records import Category, Provenance, Record, State, make_id
from .base import now

NAME, LICENCE = "orbench", "cc-by-4.0"
REVISION = "e36d8b80e81837c8a8f264bbb2a49f1b32c7e272"   # pinned Hugging Face dataset revision
URL = "https://huggingface.co/datasets/bench-llm/or-bench"


def load(limit=None) -> list:
    from datasets import load_dataset
    ds = load_dataset("bench-llm/or-bench", "or-bench-hard-1k", split="train", revision=REVISION)
    out = []
    for i, row in enumerate(ds):
        out.append(Record(
            id=make_id("F1", NAME, str(i)), feature="F1", subtask="over_refusal",
            state=State(role="user", text=row["prompt"]),
            category=Category(ailuminate="benign", bedrock="NONE", source_label=row["category"]),
            labels=["no", "yes"], expected="no",
            provenance=Provenance(source=NAME, source_id=str(i), licence=LICENCE, label_basis="automated", imported_at=now()),
        ))
        if limit and len(out) >= limit:
            break
    return out
