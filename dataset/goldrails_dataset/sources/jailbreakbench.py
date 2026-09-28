"""JailbreakBench behaviors: 100 harmful goals and 100 benign lookalikes. MIT.

These are *goals* (plain harmful or benign requests), not jailbreak attempts: no technique is applied to them. So
they test harmful-request classification (F1, subtask harmful_goal), never attack detection. Actual jailbreak
prompts (PAIR, GCG, JBC artifacts per behavior) are a separate source, to be added under F2 with the attack
technique recorded. The benign split reuses the harmful rows' category fields, so we keep only the Goal text and
mark category from the paired index.
"""
from __future__ import annotations

from ..records import Category, Provenance, Record, State, make_id
from ..taxonomy import JBB, bedrock_for
from .base import now

NAME, LICENCE = "jailbreakbench", "mit"
REVISION = "886acc352a31533ffbcf4ef22c744658688086fc"   # pinned Hugging Face dataset revision
URL = "https://huggingface.co/datasets/JailbreakBench/JBB-Behaviors"


def load(limit=None) -> list:
    from datasets import load_dataset
    out = []
    for split, expected in (("harmful", "yes"), ("benign", "no")):
        ds = load_dataset("JailbreakBench/JBB-Behaviors", "behaviors", split=split, revision=REVISION)
        for row in ds:
            ail = JBB.get(row["Category"]) if expected == "yes" else "benign"
            out.append(Record(
                id=make_id("F1", NAME, f"{split}:{row['Index']}"), feature="F1", subtask="harmful_goal",
                state=State(role="user", text=row["Goal"]),
                category=Category(ailuminate=ail, bedrock=bedrock_for(ail) if expected == "yes" else "NONE", source_label=row["Category"]),
                labels=["no", "yes"], expected=expected, group=f"jbb-{row['Index']}",
                provenance=Provenance(source=NAME, source_id=f"{split}:{row['Index']}", licence=LICENCE,
                                      label_basis="human", imported_at=now(),
                                      contamination=["typesafe-cookbook", "harmbench-derived"], notes=row.get("Source")),
            ))
    return out[:limit] if limit else out
