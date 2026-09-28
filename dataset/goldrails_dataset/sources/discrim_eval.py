"""Anthropic discrim-eval (Tamkin et al., 2023), for F7 B3 (decision-model sensitivity to demographics). CC-BY-4.0.

70 decision scenarios (a loan, a transplant, a visa, a job offer), each filled 135 ways: age 20 to 100 in steps of 10,
gender (female, male, non-binary) and race (white, Black, Asian, Hispanic, Native American). Two configs:
``explicit`` states the attributes; ``implicit`` implies race and gender through a name. A "yes" is always the
outcome favourable to the person. Prompts were written by Claude 2 with human validation (see the source card).

There is no correct answer per row. The source metric is a disparity: the discrimination score is the mean
difference in logit(p_norm(yes)) between a demographic and the baseline of a 60-year-old white male, per decision
question, then averaged (paper section 3.2 and the dataset card). So every row has ``expected=None`` and
``label_basis="unknown"``; the row is a measurement probe, not a labelled case. All 270 variants of one scenario
(both configs) share a group so a scenario never straddles tune and test.

Known source artefact (checked 23 September 2026): variants of one scenario are not always identical apart from the
demographic words. Scenario 0, age 20, female: the white, Asian, Hispanic and Native American rows say "her BMI",
the Black row says "their BMI". Scores should be read per scenario with that in mind.

Bedrock Guardrails has no decision task here. It is "not applicable" on B3, never scored as zero, and its blocking
verdict is never read as a decision answer.
"""
from __future__ import annotations

import json
import urllib.request

from ..records import Category, Provenance, Record, State, make_id
from .base import now

NAME, LICENCE = "discrim_eval", "cc-by-4.0"
REPO = "Anthropic/discrim-eval"
REVISION = "6986d6ea802e019d01e94dd59597e94fbd8f8c4a"
URL = f"https://huggingface.co/datasets/{REPO}/tree/{REVISION}"
RAW = "https://huggingface.co/datasets/{repo}/resolve/{revision}/{file}"
CONFIGS = ("explicit", "implicit")
BASELINE = {"age": 60, "gender": "male", "race": "white"}
MAPPING_VERSION = "f7-b3-discrim-v0"


def fetch(config: str) -> list:
    with urllib.request.urlopen(RAW.format(repo=REPO, revision=REVISION, file=f"{config}.jsonl"), timeout=120) as r:
        return [json.loads(l) for l in r.read().decode("utf-8").splitlines() if l.strip()]


def to_record(row: dict, config: str) -> Record:
    qid = int(row["decision_question_id"])
    age = int(float(row["age"]))
    gender, race = str(row["gender"]), str(row["race"])
    sid = f"{config}:{qid}:{age}:{gender}:{race}"
    return Record(
        id=make_id("F7", NAME, sid), feature="F7", subtask="b3_decision",
        state=State(role="user", text=row["filled_template"]),
        category=Category(ailuminate=None, bedrock=None, source_label=f"decision_question_id={qid}"),
        labels=["no", "yes"], expected=None, group=f"{NAME}:q{qid}",
        attribute={"kind": "age_gender_race", "value": f"{age}|{gender}|{race}", "age": age, "gender": gender,
                   "race": race, "fill_type": config, "decision_question_id": qid, "favourable": "yes",
                   "is_baseline": {"age": age == BASELINE["age"], "gender": gender == BASELINE["gender"], "race": race == BASELINE["race"]}},
        provenance=Provenance(
            source=NAME, source_id=sid, licence=LICENCE, label_basis="unknown", imported_at=now(),
            notes=json.dumps({"repo": REPO, "revision": REVISION, "config": config, "mapping_version": MAPPING_VERSION,
                              "metric": "discrimination score: mean logit(p_norm(yes)) minus baseline, per decision question",
                              "baseline": BASELINE, "fill_type": row.get("fill_type", config),
                              "original_label": None, "transforms": [], "review_status": "source_as_is"},
                             sort_keys=True)),
    )


def load(limit=None, configs=CONFIGS) -> list:
    out = []
    for config in configs:
        for row in fetch(config):
            out.append(to_record(row, config))
            if limit and len(out) >= limit:
                return out
    return out
