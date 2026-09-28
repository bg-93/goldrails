"""MLCommons AILuminate v1.0 demo prompt set (en_US), 1,200 human-written prompts
across the 12 hazards. CC-BY-4.0. All rows are hazardous by construction; the
benign side of F1 input comes from other sources.
"""
from __future__ import annotations

import io
import urllib.request

import pandas as pd

from ..records import Category, Provenance, Record, State, make_id
from ..taxonomy import AILUMINATE, bedrock_for
from .base import now

NAME, LICENCE = "ailuminate_demo", "cc-by-4.0"
COMMIT = "769cc2be9d20c8d4fb26ce53b68865ed41dfb8e2"   # pinned mlcommons/ailuminate commit
URL = f"https://raw.githubusercontent.com/mlcommons/ailuminate/{COMMIT}/airr_official_1.0_demo_en_us_prompt_set_release.csv"


def load(limit=None) -> list:
    df = pd.read_csv(io.BytesIO(urllib.request.urlopen(URL).read()))
    out = []
    for _, row in df.iterrows():
        ail = AILUMINATE.get(row["hazard"])
        out.append(Record(
            id=make_id("F1", NAME, row["release_prompt_id"]), feature="F1", subtask="input",
            state=State(role="user", text=row["prompt_text"]),
            category=Category(ailuminate=ail, bedrock=bedrock_for(ail), source_label=row["hazard"]),
            labels=["no", "yes"], expected="yes",
            provenance=Provenance(source=NAME, source_id=row["release_prompt_id"], licence=LICENCE,
                                  label_basis="human", imported_at=now(),
                                  notes=f"persona={row['persona']}"),
        ))
        if limit and len(out) >= limit:
            break
    return out
