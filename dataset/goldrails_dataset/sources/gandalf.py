"""Lakera gandalf_ignore_instructions: 777 real user attempts to make the model
ignore its instructions and reveal a secret. MIT. All rows are attacks
(prompt leakage subtype); benign counterparts come from other sources.
"""
from __future__ import annotations

from ..records import Category, Provenance, Record, State, make_id
from .base import now

NAME, LICENCE = "gandalf", "mit"
REVISION = "04737b65e90a6794ec227012e4a255a7def6344b"   # pinned Hugging Face dataset revision
URL = "https://huggingface.co/datasets/Lakera/gandalf_ignore_instructions"


def load(limit=None) -> list:
    from datasets import load_dataset
    ds = load_dataset("Lakera/gandalf_ignore_instructions", split="train", revision=REVISION)
    out = []
    for i, row in enumerate(ds):
        out.append(Record(
            id=make_id("F2", NAME, str(i)), feature="F2", subtask="leakage",
            state=State(role="user", text=row["text"]),
            category=Category(ailuminate="injection", bedrock="PROMPT_ATTACK", source_label="ignore_instructions"),
            labels=["no", "yes"], expected="yes",
            provenance=Provenance(source=NAME, source_id=str(i), licence=LICENCE, label_basis="automated", imported_at=now(),
                                  notes=f"similarity={row['similarity']}"),
        ))
        if limit and len(out) >= limit:
            break
    return out
