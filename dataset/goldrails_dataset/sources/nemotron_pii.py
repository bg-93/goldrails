"""NVIDIA Nemotron-PII, test split: synthetic documents with character spans for 55+ PII/PHI types. CC-BY-4.0.

Replaces AI4Privacy as the PII source from release v1.2 (owner decision, 28 September 2026), after the audit in
``dataset/frozen/reviews/nemotron-pii-audit-2026-09-28/``. Only NVIDIA's test split is read, so a model trained on the
train split has not seen these rows.

Labels. A row is ``yes`` when a span maps to one of our supported types (the frozen v2-f5-pii definitions; fax numbers
count as telephone numbers; ``ssn`` counts as a US SSN only on US-locale rows). A row is ``no`` only when no span maps
AND the audit's screen finds nothing the source left unlabelled: an ``ssn`` label on an international row, or an IPv4
address anywhere in the text (the source tags those inside URLs as URL). Every selected negative is then checked by
blind review before release; missing annotations are never proof of absence. Rows with a malformed span of a supported
type are kept out of scoring. DRIVER_ID has no source label and is not measured.

Groups. Each source id has a US and an international version of one document template, and synthetic personas reuse
emails and phone numbers across documents. Rows are grouped by source id, joined across shared email, phone and SSN
values, so related documents never straddle tuning and test.
"""
from __future__ import annotations

import ast
import json
import re
from collections import defaultdict

from ..records import Category, Provenance, Record, State, make_id
from .base import now

NAME, LICENCE = "nemotron_pii", "cc-by-4.0"
REPO, REVISION = "nvidia/Nemotron-PII", "b70ffaf5ff39e079776134c5bf4381f00a9fd1ed"
URL = f"https://huggingface.co/datasets/{REPO}/tree/{REVISION}"
TO_AWS = {"first_name": "NAME", "last_name": "NAME", "email": "EMAIL", "phone_number": "PHONE", "fax_number": "PHONE",
          "street_address": "ADDRESS", "city": "ADDRESS", "state": "ADDRESS", "postcode": "ADDRESS",
          "user_name": "USERNAME", "password": "PASSWORD", "ipv4": "IP_ADDRESS", "ipv6": "IP_ADDRESS",
          "ssn": "US_SOCIAL_SECURITY_NUMBER"}
FORMAT = {"EMAIL": re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
          "IP_ADDRESS": re.compile(r"^(\d{1,3}(\.\d{1,3}){3}|[0-9A-Fa-f:]*:[0-9A-Fa-f:.]*)$"),
          "US_SOCIAL_SECURITY_NUMBER": re.compile(r"^\d{3}[- ]?\d{2}[- ]?\d{4}$"),
          "PHONE": re.compile(r"\d.*\d.*\d.*\d.*\d.*\d.*\d")}
IPV4 = re.compile(r"(?<![\d.])(\d{1,3}\.){3}\d{1,3}(?![\d.])")


def aws_type(label: str, locale: str) -> str | None:
    t = TO_AWS.get(label)
    return None if (t == "US_SOCIAL_SECURITY_NUMBER" and locale != "us") else t


def negative_screen(labels: set, text: str) -> str | None:
    if "ssn" in labels:
        return "ssn label on an international row"
    if IPV4.search(text):
        return "IPv4 address in the text"
    return None


def rows_from_source() -> list:
    from huggingface_hub import hf_hub_download
    import pyarrow.parquet as pq
    p = hf_hub_download(REPO, "data/test-00000-of-00001.parquet", repo_type="dataset", revision=REVISION)
    rows = pq.read_table(p).to_pylist()
    for r in rows:
        r["spans"] = ast.literal_eval(r["spans"]) if isinstance(r["spans"], str) else r["spans"]
    return rows


def groups(rows: list) -> dict:
    """uid -> group root: one group per source id, joined across shared email, phone and SSN values."""
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    by_value = defaultdict(set)
    for r in rows:
        find(r["uid"])
        for s in r["spans"]:
            t = aws_type(s["label"], r["locale"])
            if t in ("EMAIL", "PHONE", "US_SOCIAL_SECURITY_NUMBER"):
                by_value[(t, r["text"][s["start"]:s["end"]].strip().lower())].add(r["uid"])
    for uids in by_value.values():
        uids = sorted(uids)
        for u in uids[1:]:
            parent[find(u)] = find(uids[0])
    return {u: find(u) for u in parent}


AUDIT = "dataset/frozen/reviews/nemotron-pii-audit-2026-09-28"


def audited_uids() -> set:
    """Documents read in the source audit stay out of the benchmark, so audit and evaluation never share rows."""
    from pathlib import Path
    base = Path(__file__).resolve().parents[3] / AUDIT
    keys = []
    for name in ("sample.json", "negatives-sample.json"):
        p = base / name
        if p.exists():
            keys += json.loads(p.read_text())["keys"]
    return {k.split(":")[0] for k in keys}


def load(limit=None) -> list:
    rows = rows_from_source()
    root = groups(rows)
    audited = audited_uids()
    out = []
    for r in sorted(rows, key=lambda x: (x["uid"], x["locale"])):
        text, locale = r["text"], r["locale"]
        labels = {s["label"] for s in r["spans"]}
        spans, unmapped, malformed = [], set(), []
        for s in r["spans"]:
            t = aws_type(s["label"], locale)
            value = text[s["start"]:s["end"]]
            if t is None:
                unmapped.add(s["label"])
                continue
            if t in FORMAT and not FORMAT[t].search(value.strip()):
                malformed.append(t)
            spans.append({"start": int(s["start"]), "end": int(s["end"]), "label": t, "source_label": s["label"]})
        mapped = sorted({s["label"] for s in spans})
        screen = None if mapped else negative_screen(labels, text)
        exclude = ("used in the source audit" if r["uid"] in audited else
                   ("malformed span: " + ",".join(sorted(set(malformed)))) if malformed else
                   (f"not a verified negative: {screen}" if screen else None))
        sid = f"{r['uid']}:{locale}"
        out.append(Record(
            id=make_id("F5", NAME, sid), feature="F5", subtask="pii",
            state=State(role="user", text=text),
            category=Category(ailuminate="pii", bedrock="PII" if mapped else "NONE", source_label=",".join(sorted(labels))),
            labels=["no", "yes"], expected="yes" if mapped else "no", group=f"{NAME}-{root[r['uid']]}", spans=spans,
            provenance=Provenance(source=NAME, source_id=sid, licence=LICENCE, label_basis="synthetic_reviewed",
                                  imported_at=now(), exclude_reason=exclude,
                                  notes=json.dumps({"revision": REVISION, "split": "test", "locale": locale,
                                                    "domain": r["domain"], "document_type": r["document_type"],
                                                    "document_format": r["document_format"], "mapped_types": mapped,
                                                    "unmapped_source_labels": sorted(unmapped)})),
        ))
        if limit and len(out) >= limit:
            break
    return out
