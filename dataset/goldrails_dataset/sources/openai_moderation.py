"""OpenAI's 2022 moderation evaluation set (1,680 prompts, 8 categories). MIT.
Anchor-only: every guard model reports on it. A row is unsafe if any category
column is 1; the first set column decides the AILuminate mapping.
"""
from __future__ import annotations

from ..records import Category, Provenance, Record, State, make_id
from ..taxonomy import OPENAI_MOD, bedrock_for
from .base import now

NAME, LICENCE = "openai_moderation", "mit"
REVISION = "84e5cf3bcd6acb3dfc70b6760451645872218a3e"   # pinned Hugging Face dataset revision
URL = "https://huggingface.co/datasets/mmathys/openai-moderation-api-evaluation"
COLS = ("S", "H", "V", "HR", "SH", "S3", "H2", "V2")


def load(limit=None) -> list:
    from datasets import load_dataset
    ds = load_dataset("mmathys/openai-moderation-api-evaluation", split="train", revision=REVISION)
    out = []
    for i, row in enumerate(ds):
        flagged = [c for c in COLS if str(row[c]) == "1"]
        unknown = [c for c in COLS if row[c] is None or str(row[c]) not in ("0", "1")]
        ail = OPENAI_MOD[flagged[0]] if flagged else "benign"
        out.append(Record(
            id=make_id("F1", NAME, str(i)), feature="F1", subtask="input",
            state=State(role="user", text=row["prompt"]),
            category=Category(ailuminate=ail, bedrock=bedrock_for(ail) if flagged else "NONE", source_label=",".join(flagged) or "none"),
            labels=["no", "yes"], expected="yes" if flagged else "no",
            provenance=Provenance(source=NAME, source_id=str(i), licence=LICENCE, label_basis="human", imported_at=now(),
                                  contamination=["qwen3guard-eval", "gpt-oss-safeguard-eval", "anchor-only"],
                                  # benign only when all eight categories are labelled 0; an unlabelled category is unknown
                                  exclude_reason="unknown_category_label" if (not flagged and unknown) else None),
        ))
        if limit and len(out) >= limit:
            break
    return out
