"""RAGTruth (Particle Media, MIT): sources, model-generated replies, and human-annotated hallucination spans.

Pinned to one commit. Each row is one reply (role assistant) with the source document and the task prompt as the
query. Expected "yes" for ``unsupported`` when the reply has any annotated span (label types Evident Conflict,
Subtle Conflict, Evident Baseless Info, Subtle Baseless Info), "no" otherwise; spans are kept with the label type.
Relevance is not annotated in RAGTruth, so ``irrelevant`` has no label here. Replies that share a source share a
group so a split never separates them. Only the source's test split is used, Summary and QA tasks first; Data2txt
sources are JSON objects and are serialised.
"""
from __future__ import annotations

import json
import urllib.request

from ..records import Category, Provenance, Record, State, make_id
from .base import now

NAME, LICENCE = "ragtruth", "mit"
COMMIT = "c103204b9ce28d6bbad859304bf30de72b8ed8fe"
RAW = "https://raw.githubusercontent.com/ParticleMedia/RAGTruth/{commit}/dataset/{file}"


def fetch(file: str) -> list:
    with urllib.request.urlopen(RAW.format(commit=COMMIT, file=file), timeout=120) as r:
        return [json.loads(l) for l in r.read().decode("utf-8").splitlines() if l.strip()]


def load(limit=None, tasks=("Summary", "QA", "Data2txt"), split="test") -> list:
    sources = {s["source_id"]: s for s in fetch("source_info.jsonl")}
    out = []
    for r in fetch("response.jsonl"):
        s = sources.get(r["source_id"])
        if not s or r.get("split") != split or s["task_type"] not in tasks:
            continue
        info = s["source_info"]
        source_text = info if isinstance(info, str) else json.dumps(info, ensure_ascii=False)
        # The query must be the short task the reply answers, not RAGTruth's full prompt (which embeds the source and
        # exceeds Bedrock's one-text-unit query limit). QA has a question; the other tasks get a fixed instruction.
        if isinstance(info, dict) and info.get("question"):
            query = str(info["question"])
        elif s["task_type"] == "Summary":
            query = "Summarise the source text."
        else:
            query = "Write a description of the structured data in the source."
        spans = [{"start": int(l["start"]), "end": int(l["end"]), "label": l.get("label_type", "hallucination"), "source_label": l.get("label_type")} for l in r.get("labels", [])]
        spans = [sp for sp in spans if 0 <= sp["start"] < sp["end"] <= len(r["response"])]
        out.append(Record(
            id=make_id("F6", NAME, str(r["id"])), feature="F6", subtask="grounding",
            state=State(role="assistant", text=r["response"], source=source_text, query=str(query)),
            category=Category(ailuminate="benign", bedrock="NONE", source_label=",".join(sorted({sp["label"] for sp in spans})) or "grounded"),
            labels=["no", "yes"], expected="yes" if spans else "no", group=f"{NAME}-{r['source_id']}", spans=spans,
            provenance=Provenance(source=NAME, source_id=str(r["id"]), licence=LICENCE, label_basis="human", imported_at=now(),
                                  notes=json.dumps({"commit": COMMIT, "source_id": r["source_id"], "task_type": s["task_type"], "model": r.get("model"), "quality": r.get("quality")})),
        ))
        if limit and len(out) >= limit:
            break
    return out
