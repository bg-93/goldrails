"""Code baseline for the word-filters suite: the matching rule in words.json, as a system. Deterministic, free, the
reference that every other system is compared against on this suite."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from .question_sets import SEP
from .systemone import SystemOneCall, unrepresentable

SUPPORTED_STATE = ("role", "text")   # the rule reads the text being judged; prior turns would change the task
# Adapter identity, part of the config hash: bump when the matching rule or ``text_of`` changes.
ADAPTER = {"name": "regex-words", "version": "1"}

WORDS = Path(__file__).resolve().parents[2] / "benchmark" / "suites" / "word_filters" / "words.json"


def text_of(state) -> str:
    """The text the rule is applied to: exactly the text every other system is asked about."""
    return state if isinstance(state, str) else str(state.get("text", ""))


class RegexWordClient:
    system = "regex-baseline"
    model = "regex/words.json"
    adapter = ADAPTER

    def __init__(self, words: list[str] | None = None):
        self.words = words or json.loads(WORDS.read_text(encoding="utf-8"))["words"]
        self.patterns = {w: re.compile(r"(?<![A-Za-z0-9])" + r"\s+".join(map(re.escape, w.split())) + r"(?![A-Za-z0-9])", re.IGNORECASE) for w in self.words}
        self.identity = {"rule": "exact phrase, case-insensitive, whole words", "words": self.words}

    def ask(self, state, questions: dict) -> SystemOneCall:
        t0 = time.perf_counter()
        missing = unrepresentable(state, SUPPORTED_STATE)
        if missing:
            return SystemOneCall(system=self.system, ok=False, model=self.model,
                                 error=f"UnrepresentableState: the word rule does not define matching over {', '.join(missing)}",
                                 raw={"unanswered": list(questions), "unrepresentable": missing})
        text = text_of(state)
        hits = {"".join(c if c.isalnum() else "_" for c in w.lower()).strip("_"): (1.0 if p.search(text) else 0.0) for w, p in self.patterns.items()}
        hits["any_word"] = max(hits.values(), default=0.0)
        answers, unanswered = {}, []
        for key in questions:
            name = key.split(SEP, 1)[-1]
            if name in hits:
                answers[key] = {"type": "noul", "noul": hits[name], "basis": "regex_exact"}
            else:
                unanswered.append(key)
        return SystemOneCall(system=self.system, ok=True, model=self.model, answers=answers, usage={"input_tokens": None},
                             latency_s=time.perf_counter() - t0, raw={"unanswered": unanswered})
