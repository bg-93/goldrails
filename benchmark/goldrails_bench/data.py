"""Rows for a run, from wherever the dataset lives today, without baking a path into a notebook.

    rows = load_rows("F1", "tune")                      # GOLDRAILS_DATA decides: local samples or Hugging Face
    rows = load_rows("F1", "test", source="hf:raxITLabs/goldrails")
    rows = load_rows("F1", "tune", source="dataset/samples/sample-1k")

``source`` (or the GOLDRAILS_DATA environment variable) is either a directory holding ``{feature}.{split}.jsonl``
files, or ``hf:<repo>`` for a Hugging Face dataset whose config is the feature and whose split is the split. Both
return the same ``Record`` objects, so nothing downstream changes when the dataset moves to the Hub.
"""
from __future__ import annotations

import os
from pathlib import Path

from goldrails_dataset.records import Record, dataset_hash, read_jsonl

REPO = Path(__file__).resolve().parents[2]
DEFAULT = "dataset/samples/pilot"


def load_rows(feature: str = "F1", split: str = "tune", source: str | None = None) -> list[Record]:
    """Rows, each tagged with ``dataset`` = {source, feature, split, sha256}: the identity of the file (or Hub
    revision) it came from. The runner writes it into every ledger record so rows from two versions of a sample
    are never pooled by the scorer."""
    source = source or os.environ.get("GOLDRAILS_DATA") or DEFAULT
    if source.startswith("hf:"):
        from datasets import load_dataset
        ds = load_dataset(source[3:], name=feature, split=split)
        rows = [Record.from_dict(dict(r)) for r in ds]
        tag = {"source": source, "feature": feature, "split": split, "sha256": dataset_hash(rows)}
    else:
        path = Path(source)
        if not path.is_absolute():
            path = REPO / path
        rows = read_jsonl(path / f"{feature}.{split}.jsonl")
        tag = {"source": str(path.relative_to(REPO)) if path.is_relative_to(REPO) else str(path), "feature": feature,
               "split": split, "sha256": dataset_hash(rows)}
    for r in rows:
        r.dataset = tag
    return rows
