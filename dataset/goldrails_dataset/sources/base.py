"""Shared helpers for source loaders. Each loader exposes:

    NAME, LICENCE, URL
    load(limit: int | None = None) -> list[Record]

Loaders never touch the network unless called. They never write the expected
label into the state. They set label_basis honestly.
"""
from __future__ import annotations

from datetime import datetime, timezone


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
