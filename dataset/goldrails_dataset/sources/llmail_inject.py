"""Microsoft LLMail-Inject (MIT): indirect prompt injections sent as emails to a simulated LLM email assistant.

Pinned to one Hugging Face revision. What the source holds, checked against the card and the files at REVISION:

- ``labelled_unique_submissions_{phase}.json``: a dict from the formatted email ("Subject of the email: S.   Body: B")
  to ``attack_attempt`` ("True", "False", "Unclear"), ``reason`` ("api_triggered" or "judge") and, for judge rows, the
  judge's category and explanation. Phase 2 at REVISION: 21,007 True, 13,796 Unclear, 2,500 False.
- ``raw_submissions_{phase}.jsonl``: every submission with ``team_id``, ``scenario`` (level id such as "level2k") and
  ``objectives`` (retrieved, undetected, sent, destination, content). The labelled file has no team or scenario, so we
  join on the formatted email; at REVISION every phase 2 labelled key joins.
- ``scenarios.json``: per scenario the user's query and the benign emails in the mailbox. ``system_prompt.json``: the
  assistant's system prompt. ``emails_for_fp_tests.json``: 203 benign emails (160 unique) the organisers used for
  false-positive tests. These two files are the source's own benign controls, so no authored control set is needed.

Mapping. Feature F2, subtask ``indirect``. The judged text is the email, role ``tool`` (the assistant receives it as
retrieved data; GPT-4o mini got it as a tool message). The trust context goes in ``state.context``: the system prompt
(system turn) and the user's query for that scenario (user turn). The label is attack *presence*, from the source's
``attack_attempt``; attack *success* (the objectives flags of the representative submission) is kept in the notes and
never used as the label. ``api_triggered`` rows are ``deterministic`` (an email that made the assistant call the
send-email tool with the attacker's target is an attack by construction); judge rows are ``llm``. Judge "False" rows
are submissions to an attack challenge that a model judged harmless: kept with ``expected="no"`` but excluded until a
person reviews them, because they are not benign controls. "Unclear" rows are kept with no expected label and
excluded. Benign emails are ``expected="no"`` with ``label_basis="unknown"``: the card says what they were used for,
not how they were written or checked.

Grouping. Attack variants from one team (an adaptive attacker iterating on one idea) share ``group`` so no split
separates them. Benign emails share a group when they are the same template with the project name, dates and
greeting swapped. Known limit: near-duplicate attacks copied across teams are not merged (merging on shared text
chains half of phase 2 into one component).

Scenario N is level N in both phases (challenge config.yaml). Phase 2 used scenarios 1 and 2 only; phase 1 has all
four and is much larger (raw file 1.6 GB), so it is opt-in. Files are downloaded once into a local cache and checked
against the LFS sha256 where the revision records one.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.request
from collections import Counter
from pathlib import Path

from ..records import Category, Provenance, Record, State, make_id
from .base import now

NAME, LICENCE = "llmail_inject", "mit"
REPO = "microsoft/llmail-inject-challenge"
REVISION = "1063bdf01ec8762b812d5e06ee768a06faa5a6f7"
URL = f"https://huggingface.co/datasets/{REPO}"
RESOLVE = "https://huggingface.co/datasets/{repo}/resolve/{rev}/data/{file}"
SHA256 = {   # LFS object ids at REVISION; small JSON files are plain git blobs without one
    "labelled_unique_submissions_phase1.json": "691dfa1595d2bd0e731069f233bd5448f7af1c0ebd9732bc6f12dd6cee446586",
    "labelled_unique_submissions_phase2.json": "f89af984e345430c3b357903890e30867bf4676f4ef10c138cc7bad218e890b8",
    "raw_submissions_phase1.jsonl": "a9c62eca699dd270fdfbbfbfcc1253f5e5017f6d5a34ff7cb0f2cbb80b7f7c0a",
    "raw_submissions_phase2.jsonl": "a9207e1d893ccb74ca6f9cc5eecea433bc49c23a26bed88088afd385c7ab18b6",
}
PHASES = ("phase1", "phase2")
EMAIL_FORMAT = "Subject of the email: {subject}.   Body: {body}"   # the source's own key format
CONTAMINATION = ["llmail-inject-public-2025"]


def cache_dir() -> Path:
    return Path(os.environ.get("GOLDRAILS_CACHE", Path.home() / ".cache" / "goldrails")) / NAME / REVISION


def fetch(file: str) -> Path:
    """Download one data file at the pinned revision into the cache (once) and return its path."""
    path = cache_dir() / file
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    h = hashlib.sha256()
    with urllib.request.urlopen(RESOLVE.format(repo=REPO, rev=REVISION, file=file), timeout=600) as r, open(tmp, "wb") as out:
        while chunk := r.read(1 << 20):
            h.update(chunk)
            out.write(chunk)
    want = SHA256.get(file)
    if want and h.hexdigest() != want:
        tmp.unlink(missing_ok=True)
        raise ValueError(f"{file}: sha256 {h.hexdigest()} does not match the pinned {want}")
    tmp.rename(path)
    return path


def read_json(file: str):
    with open(fetch(file), encoding="utf-8") as fh:
        return json.load(fh)


def iter_jsonl(file: str):
    with open(fetch(file), encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def email_text(subject: str, body: str) -> str:
    return EMAIL_FORMAT.format(subject=subject, body=body)


LEVEL = re.compile(r"^level(\d)([a-z])$")


def scenario_of(level: str) -> str | None:
    m = LEVEL.match(level or "")
    return f"scenario_{m.group(1)}" if m else None


MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december"


def template_key(text: str) -> str:
    """The benign email with project names, dates, numbers and greeting/sign-off names removed: one key per template."""
    t = text.lower()
    t = re.sub(r"project \w+", "project x", t)
    t = re.sub(rf"\b({MONTHS})\b", "month", t)
    t = re.sub(r"\d+(st|nd|rd|th)?", "n", t)
    t = re.sub(r"\b(dear|hi|hello)\s+\w+", r"\1 name", t)
    t = re.sub(r"(regards|best|thanks|sincerely|cheers),?\s+\w+\.?\s*$", r"\1 name", t.strip())
    return hashlib.sha1(re.sub(r"\W+", " ", t).strip().encode("utf-8")).hexdigest()[:12]


def keyword_scenario(text: str) -> str:
    """False-positive test emails carry no scenario; pair each with the query it most plausibly sat under."""
    t = text.lower()
    if "zenith" in t:
        return "scenario_3"
    if "q2" in t and "budget" in t:
        return "scenario_4"
    return "scenario_1"


def context_for(scenario: str, scenarios: dict, system_prompt: str) -> list:
    return [{"role": "system", "text": system_prompt}, {"role": "user", "text": scenarios[scenario]["user_query"]}]


def system_text(system: dict) -> str:
    return (system.get("email_client", "") + system.get("tool_prompt", "")).strip()


def label_of(lab: dict):
    """(expected, label_basis, exclude_reason, source_label) for one labelled submission. Presence, not success."""
    attempt = str(lab.get("attack_attempt")).strip().lower()
    reason = lab.get("reason")
    basis = "deterministic" if reason == "api_triggered" else "llm"
    parts = [f"attack_attempt={lab.get('attack_attempt')}", f"reason={reason}"]
    if lab.get("judge_category"):
        parts.append(f"judge_category={lab['judge_category']}")
    source_label = ";".join(parts)
    if attempt == "true":
        return "yes", basis, None, source_label
    if attempt == "false":
        return "no", basis, "judge-only negative from an attack-challenge submission; not a benign control until reviewed", source_label
    return None, basis, f"source label attack_attempt={lab.get('attack_attempt')!r}", source_label


def load_benign(limit=None) -> list:
    scenarios = read_json("scenarios.json")
    sys_prompt = system_text(read_json("system_prompt.json"))
    items = [(sk, f"{sk}:{j}", e, "scenario_file") for sk in sorted(scenarios) for j, e in enumerate(scenarios[sk]["emails"])]
    items += [(keyword_scenario(e), f"fp:{j}", e, "keyword") for j, e in enumerate(read_json("emails_for_fp_tests.json"))]
    out, seen = [], set()
    for scenario, sid, text, how in items:
        if text in seen or not text.strip():
            continue
        seen.add(text)
        out.append(Record(
            id=make_id("F2", NAME, sid), feature="F2", subtask="indirect",
            state=State(role="tool", text=text, context=context_for(scenario, scenarios, sys_prompt)),
            category=Category(ailuminate="benign", bedrock="NONE", source_label="benign_email"),
            labels=["no", "yes"], expected="no", group=f"{NAME}-benign-{template_key(text)}",
            provenance=Provenance(source=NAME, source_id=sid, licence=LICENCE, label_basis="unknown", imported_at=now(),
                                  contamination=list(CONTAMINATION),
                                  notes=json.dumps({"revision": REVISION, "scenario": scenario, "query_assignment": how,
                                                    "origin": "scenarios.json" if how == "scenario_file" else "emails_for_fp_tests.json",
                                                    "basis": "source-declared benign email; generation and review not documented"})),
        ))
        if limit and len(out) >= limit:
            break
    return out


def load_attacks(limit=None, phases=("phase2",), max_per_team=None) -> list:
    scenarios = read_json("scenarios.json")
    sys_prompt = system_text(read_json("system_prompt.json"))
    levels = read_json("levels_descriptions.json")
    out, seen, per_team = [], set(), Counter()
    for phase in phases:
        if phase not in PHASES:
            raise ValueError(f"unknown phase {phase!r}")
        labels = read_json(f"labelled_unique_submissions_{phase}.json")
        for sub in iter_jsonl(f"raw_submissions_{phase}.jsonl"):
            text = email_text(sub.get("subject", ""), sub.get("body", ""))
            if text in seen or text not in labels:
                continue
            scenario = scenario_of(sub.get("scenario", ""))
            if scenario not in scenarios:
                continue
            team = sub.get("team_id") or "unknown"
            if max_per_team and per_team[team] >= max_per_team:
                continue
            seen.add(text)          # the first submission in file order represents the unique text: deterministic
            per_team[team] += 1
            lab = labels[text]
            expected, basis, exclude, source_label = label_of(lab)
            letter = LEVEL.match(sub["scenario"]).group(2)
            try:
                success = json.loads(sub.get("objectives") or "{}")
            except (TypeError, ValueError):
                success = None
            out.append(Record(
                id=make_id("F2", NAME, f"{phase}:{sub['job_id']}"), feature="F2", subtask="indirect",
                state=State(role="tool", text=text, context=context_for(scenario, scenarios, sys_prompt)),
                category=Category(ailuminate={"yes": "injection", "no": "benign"}.get(expected),
                                  bedrock={"yes": "PROMPT_ATTACK", "no": "NONE"}.get(expected), source_label=source_label),
                labels=["no", "yes"], expected=expected, group=f"{NAME}-team-{team}",
                provenance=Provenance(source=NAME, source_id=f"{phase}:{sub['job_id']}", licence=LICENCE, label_basis=basis,
                                      imported_at=now(), contamination=list(CONTAMINATION), exclude_reason=exclude,
                                      notes=json.dumps({"revision": REVISION, "phase": phase, "level": sub["scenario"],
                                                        "scenario": scenario, "defense": levels.get(phase, {}).get(letter),
                                                        "team_id": team, "reason": lab.get("reason"),
                                                        "judge_category": lab.get("judge_category"),
                                                        "success_objectives_not_label": success})),
            ))
            if limit and len(out) >= limit:
                return out
    return out


def load(limit=None, phases=("phase2",), include_benign=True, max_per_team=None) -> list:
    """Attack submissions plus the source's benign emails. ``limit`` caps each part separately, so a small limit still
    yields both classes. Excluded rows (judge False, Unclear) are returned with ``exclude_reason`` set."""
    out = load_attacks(limit=limit, phases=phases, max_per_team=max_per_team)
    if include_benign:
        out += load_benign(limit=limit)
    return out
