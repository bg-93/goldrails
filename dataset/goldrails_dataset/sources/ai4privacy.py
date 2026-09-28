"""AI4Privacy pii-masking-300k, English rows: synthetic texts with labelled PII spans and a masked target text.

Licence is the dataset's own (custom, "other" on the Hub): usable for evaluation, not redistributed in Gold Rails;
rows carry the source id so anyone can rebuild them from the pinned revision. The task we keep is the source's:
"which spans are personal information, and of which type". Every row therefore has expected "yes" for contains_pii
(the source has no PII-free rows; negatives are authored controls). Each span also carries the AWS entity type it
maps to, or "unmapped:<label>" where the managed guardrail has no such type (date of birth, national ID card, sex,
title); those are coverage differences, recorded in notes as ``unmapped_source_labels`` and never used to make a
row negative. The first version of this loader did exactly that with a guessed vocabulary, which produced fake
negatives; the vocabulary is now the one observed in the data.
"""
from __future__ import annotations

import ast
import json
import re

from ..records import Category, Provenance, Record, State, make_id
from .base import now

NAME, LICENCE = "ai4privacy", "ai4privacy-custom"
REPO, REVISION = "ai4privacy/pii-masking-300k", "c8c77895a005822682b66ab547fc0422579bc1d3"

# Source label (the vocabulary actually present in pii-masking-300k) -> AWS Bedrock sensitive-information entity type.
# None means the managed guardrail has no equivalent type: a coverage difference, disclosed per row, not a negative.
TO_AWS = {
    "EMAIL": "EMAIL", "TEL": "PHONE", "USERNAME": "USERNAME", "PASS": "PASSWORD",
    "GIVENNAME1": "NAME", "GIVENNAME2": "NAME", "LASTNAME1": "NAME", "LASTNAME2": "NAME", "LASTNAME3": "NAME",
    "STREET": "ADDRESS", "BUILDING": "ADDRESS", "CITY": "ADDRESS", "STATE": "ADDRESS", "POSTCODE": "ADDRESS", "SECADDRESS": "ADDRESS",
    "DRIVERLICENSE": "DRIVER_ID", "IP": "IP_ADDRESS",
    # Jurisdiction-specific AWS types get a mapping only with evidence in the span itself (see BY_PATTERN); English
    # text does not establish US jurisdiction, so a bare PASSPORT or SOCIALNUMBER label stays a coverage gap.
    "PASSPORT": None, "SOCIALNUMBER": None,
    "IDCARD": None, "BOD": None, "DATE": None, "TIME": None, "SEX": None, "TITLE": None, "COUNTRY": None, "GEOCOORD": None,
}
# span value pattern -> AWS type: a heuristic. The 123-45-6789 form is evidence of SSN-like formatting, not of US
# jurisdiction; rows mapped this way are kept out of strict entity-level correctness claims (suite README).
BY_PATTERN = {"SOCIALNUMBER": (re.compile(r"^\d{3}-\d{2}-\d{4}$"), "US_SOCIAL_SECURITY_NUMBER")}
# Some span-free chunks still carry masking placeholders from the source's generation (e.g. "USERNAME_B:"). They are not
# PII-free text and detectors rightly fire on them, so they are excluded rather than used as negatives.
PLACEHOLDER = re.compile(r"\b[A-Z]{3,}_[A-Z0-9]{1,3}\b")


def load(limit=None, split="validation") -> list:
    from datasets import load_dataset
    ds = load_dataset(REPO, split=split, revision=REVISION, streaming=True)
    out = []
    for row in ds:
        if row.get("language") != "English":
            continue
        raw = row["privacy_mask"]
        spans_src = ast.literal_eval(raw) if isinstance(raw, str) else raw
        text = row["source_text"]
        if not spans_src and PLACEHOLDER.search(text):
            continue
        spans, unmapped = [], []
        for sp in spans_src:
            lab = str(sp.get("label", "")).upper()
            aws = TO_AWS.get(lab)
            if aws is None and lab in BY_PATTERN and BY_PATTERN[lab][0].match(str(sp.get("value", "")).strip()):
                aws = BY_PATTERN[lab][1]          # the value's format is the evidence for the jurisdiction-specific type
            if aws is None:          # unknown label, or a known one with no managed-guardrail equivalent
                unmapped.append(lab)
            spans.append({"start": int(sp["start"]), "end": int(sp["end"]), "label": aws or f"unmapped:{lab}", "source_label": lab})
        mapped = sorted({s["label"] for s in spans if not s["label"].startswith("unmapped:")})
        out.append(Record(
            id=make_id("F5", NAME, str(row["id"])), feature="F5", subtask="pii",
            state=State(role="user", text=text),
            category=Category(ailuminate="pii", bedrock="PII" if mapped else "NONE",
                              source_label=",".join(sorted({s["source_label"] for s in spans}))),
            labels=["no", "yes"], expected="yes" if spans else "no", group=f"{NAME}-{row['id']}", spans=spans,
            provenance=Provenance(source=NAME, source_id=str(row["id"]), licence=LICENCE, label_basis="synthetic_reviewed",
                                  imported_at=now(), notes=json.dumps({"revision": REVISION, "mapped_types": mapped,
                                                                       "unmapped_source_labels": sorted(set(unmapped)),
                                                                       "target_text_available": bool(row.get("target_text"))})),
        ))
        if limit and len(out) >= limit:
            break
    return out
