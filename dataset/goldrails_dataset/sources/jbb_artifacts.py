"""JailbreakBench attack artifacts: jailbreak prompts produced by published attacks (PAIR, GCG, JBC) against each of
the 100 JBB behaviors. MIT. Pinned to one commit of github.com/JailbreakBench/artifacts.

Each row's text is the attack prompt as submitted to the target model, so it carries a technique (persona, hypothetical
frame, adversarial suffix). That is what makes it an F2 jailbreak positive; the underlying goal is the same behavior
that feeds F1 harmful_goal from the JBB-Behaviors set, and the two share a group id so a split never separates them
by accident when both features are built together. ``jailbroken`` (did the target comply) is kept as a note; it is
not the label. label_basis is deterministic: the prompt is an attack by construction.
"""
from __future__ import annotations

import json
import urllib.request

from ..records import Category, Provenance, Record, State, make_id
from ..taxonomy import JBB, bedrock_for
from .base import now

NAME, LICENCE = "jbb_artifacts", "mit"
COMMIT = "909e68c01d94222b8ad2e397a017e2e12e2adb73"
# (method, attack type directory, target model). JBC is a manual attack, so it lives under manual/, not black_box/.
FILES = [("PAIR", "black_box", "vicuna-13b-v1.5"), ("PAIR", "black_box", "llama-2-7b-chat-hf"),
         ("GCG", "white_box", "vicuna-13b-v1.5"), ("JBC", "manual", "gpt-3.5-turbo-1106")]
RAW = "https://raw.githubusercontent.com/JailbreakBench/artifacts/{commit}/attack-artifacts/{method}/{kind}/{model}.json"


def fetch(method: str, model: str, kind: str = "black_box") -> dict:
    with urllib.request.urlopen(RAW.format(commit=COMMIT, method=method, kind=kind, model=model), timeout=60) as r:
        return json.load(r)


def load(limit=None, files=FILES) -> list:
    out, seen = [], set()
    for entry in files:
        method, kind, model = entry if len(entry) == 3 else (entry[0], "black_box", entry[1])
        d = fetch(method, model, kind)   # a missing file is an error: a silent skip would change the dataset
        for j in d["jailbreaks"]:
            prompt = j.get("prompt")
            if not prompt or prompt in seen:
                continue
            seen.add(prompt)
            ail = JBB.get(j.get("category"), "nonviolent_crimes")
            out.append(Record(
                id=make_id("F2", NAME, f"{method}:{model}:{j['index']}"), feature="F2", subtask="jailbreak",
                state=State(role="user", text=prompt),
                category=Category(ailuminate="injection", bedrock="PROMPT_ATTACK", source_label=f"{method}:{j.get('category')}"),
                labels=["no", "yes"], expected="yes", group=f"jbb-{j['index']}",
                provenance=Provenance(source=NAME, source_id=f"{method}:{model}:{j['index']}", licence=LICENCE,
                                      label_basis="deterministic", imported_at=now(), contamination=["jailbreakbench"],
                                      notes=json.dumps({"method": method, "target_model": model, "goal_category": j.get("category"),
                                                        "goal_ailuminate": ail, "jailbroken": j.get("jailbroken"), "commit": COMMIT})),
            ))
            if limit and len(out) >= limit:
                return out
    return out
