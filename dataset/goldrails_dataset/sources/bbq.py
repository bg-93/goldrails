"""BBQ, the Bias Benchmark for QA (Parrish et al., Findings of ACL 2022), for F7 B3. CC-BY-4.0.

Pinned to one commit of github.com/nyu-mll/BBQ. Eleven category files (nine social dimensions plus two
intersectional ones). Each row is a multiple-choice question over a short context, with three options: two people
and an "unknown" option. ``ambig`` contexts do not contain the answer, so the correct option is "unknown";
``disambig`` contexts add the fact that decides it. ``neg`` questions ask who fits a harmful stereotype, ``nonneg``
the complement. Labels come from the authors' hand-written templates (``label_basis="deterministic"``).

The bias score needs to know which option is the stereotyped target. The authors ship that as ``target_loc`` in
``analysis_scripts/additional_metadata.csv``; ``load`` joins it when available. Rows without it keep
``target_option=None``: unknown, not "no target".

All rows made from one template (same category and ``question_index``, every name and context condition) share a
group, so a template family never straddles tune and test.

Metrics (source-defined, paper section 4): accuracy per context condition, and the bias scores
s_DIS = 2 * (biased answers / non-unknown answers) - 1 and s_AMB = (1 - accuracy) * s_DIS.
"""
from __future__ import annotations

import csv
import io
import json
import urllib.request

from ..records import Category, Provenance, Record, State, make_id
from .base import now

NAME, LICENCE = "bbq", "cc-by-4.0"
COMMIT = "bea11bd97d79217245b5871acd247b9d6eb24598"
URL = f"https://github.com/nyu-mll/BBQ/tree/{COMMIT}"
RAW = "https://raw.githubusercontent.com/nyu-mll/BBQ/{commit}/{path}"
CATEGORIES = ("Age", "Disability_status", "Gender_identity", "Nationality", "Physical_appearance", "Race_ethnicity",
              "Race_x_SES", "Race_x_gender", "Religion", "SES", "Sexual_orientation")
OPTIONS = ("ans0", "ans1", "ans2")
MAPPING_VERSION = "f7-b3-bbq-v0"


def _get(path: str) -> str:
    with urllib.request.urlopen(RAW.format(commit=COMMIT, path=path), timeout=120) as r:
        return r.read().decode("utf-8")


def fetch(category: str) -> list:
    return [json.loads(l) for l in _get(f"data/{category}.jsonl").splitlines() if l.strip()]


def fetch_metadata() -> dict:
    """(category, example_id) -> target_loc (int or None), from the authors' analysis metadata."""
    out = {}
    for row in csv.DictReader(io.StringIO(_get("analysis_scripts/additional_metadata.csv"))):
        loc = (row.get("target_loc") or "").strip()
        out[(row["category"], int(row["example_id"]))] = int(loc) if loc.isdigit() else None
    return out


def prompt(row: dict) -> str:
    opts = "\n".join(f"{letter}. {row[o]}" for letter, o in zip("ABC", OPTIONS))
    return f"{row['context']}\n\nQuestion: {row['question']}\n{opts}"


def to_record(row: dict, target_loc=None) -> Record:
    category, eid = row["category"], int(row["example_id"])
    info = row.get("answer_info") or {}
    groups = {o: (info.get(o) or [None, None])[1] for o in OPTIONS}
    unknown = next((o for o in OPTIONS if groups[o] == "unknown"), None)
    meta = row.get("additional_metadata") or {}
    sid = f"{category}:{eid}"
    return Record(
        id=make_id("F7", NAME, sid), feature="F7", subtask="b3_decision",
        state=State(role="user", text=prompt(row)),
        category=Category(ailuminate=None, bedrock=None,
                          source_label=f"{category}/{row['context_condition']}/{row['question_polarity']}"),
        labels=list(OPTIONS), expected=f"ans{int(row['label'])}", group=f"{NAME}:{category}:{row['question_index']}",
        attribute={"kind": category, "value": ",".join(meta.get("stereotyped_groups") or []) or "unspecified",
                   "subcategory": meta.get("subcategory"), "context_condition": row["context_condition"],
                   "question_polarity": row["question_polarity"], "answer_groups": groups, "unknown_option": unknown,
                   "target_option": f"ans{target_loc}" if target_loc is not None else None,
                   "question_index": str(row["question_index"])},
        provenance=Provenance(
            source=NAME, source_id=sid, licence=LICENCE, label_basis="deterministic", imported_at=now(),
            notes=json.dumps({"commit": COMMIT, "file": f"data/{category}.jsonl", "mapping_version": MAPPING_VERSION,
                              "template_version": meta.get("version"), "template_source": meta.get("source"),
                              "original_label": int(row["label"]), "transforms": [{"op": "format_multiple_choice", "letters": "ABC"}],
                              "review_status": "source_as_is"},
                             sort_keys=True)),
    )


def load(limit=None, categories=CATEGORIES, with_metadata=True) -> list:
    targets = fetch_metadata() if with_metadata else {}
    out = []
    for category in categories:
        for row in fetch(category):
            out.append(to_record(row, targets.get((row["category"], int(row["example_id"])))))
            if limit and len(out) >= limit:
                return out
    return out
