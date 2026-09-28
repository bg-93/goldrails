"""deepset/prompt-injections: 546 short texts labelled injection (1) or not (0).
Apache-2.0. Small and old (2023); kept for the pilot and as anchor rows.
"""
from __future__ import annotations

from ..records import Category, Provenance, Record, State, make_id
from .base import now

NAME, LICENCE = "deepset_injections", "apache-2.0"
REVISION = "4f61ecb038e9c3fb77e21034b22511b523772cdd"   # pinned Hugging Face dataset revision
GERMAN = {"und", "der", "die", "das", "ist", "nicht", "ich", "wie", "was", "mit", "für", "auf", "ein", "eine", "sie", "du",
          "bitte", "vergiss", "alle", "sind", "wir", "zu", "den", "dem", "des", "auch", "über", "welche", "wurde", "kann"}
ENGLISH = {"the", "and", "is", "not", "what", "how", "with", "for", "you", "are", "all", "please", "of", "to", "in", "a"}


def is_german(text: str) -> bool:
    """Heuristic: v1 is English, and the source mixes in German rows. A row is German when German function words
    outnumber English ones and at least two appear. Excluded rows keep their reason; nothing is silently dropped."""
    words = [w.strip(".,!?;:\"'()").lower() for w in text.split()]
    de, en = sum(w in GERMAN for w in words), sum(w in ENGLISH for w in words)
    return de >= 2 and de > en
URL = "https://huggingface.co/datasets/deepset/prompt-injections"


def load(limit=None) -> list:
    from datasets import load_dataset
    ds = load_dataset("deepset/prompt-injections", split="train", revision=REVISION)
    out = []
    for i, row in enumerate(ds):
        inj = str(row["label"]) == "1"
        out.append(Record(
            id=make_id("F2", NAME, str(i)), feature="F2", subtask="injection",
            state=State(role="user", text=row["text"]),
            category=Category(ailuminate="injection" if inj else "benign", bedrock="PROMPT_ATTACK" if inj else "NONE", source_label=str(row["label"])),
            labels=["no", "yes"], expected="yes" if inj else "no",
            provenance=Provenance(source=NAME, source_id=str(i), licence=LICENCE, label_basis="unknown", imported_at=now(),
                                  contamination=["promptguard-era-public"],
                                  exclude_reason="non_english" if is_german(row["text"]) else None),
        ))
        if limit and len(out) >= limit:
            break
    return out
