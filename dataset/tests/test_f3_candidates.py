"""F3 test candidates (sources/f3_test_candidates.py) and their blind review packet. Offline: no model or network."""
import json
import re
from collections import Counter
from pathlib import Path

import pytest

from goldrails_dataset.records import Record
from goldrails_dataset.sources import f3_controls
from goldrails_dataset.sources import f3_test_candidates as C

PACKETS = Path(__file__).resolve().parents[1] / "frozen" / "review-packets"
PDIR = PACKETS / C.PACKET
KEY = PACKETS / "_lead" / f"{C.PACKET}.key.json"
CITE = re.compile(r'Definition: "(.+)"\.$')


@pytest.fixture(scope="module")
def recs():
    return C.load()


@pytest.fixture(scope="module")
def defs():
    return {t["name"]: t for t in C.topics()}


def _norm(s):
    return re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s+", " ", s.lower())).strip()


def _words(s):
    return set(_norm(s).split())


def _ngrams(s, n=5):
    w = _norm(s).split()
    return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}


def test_all_rows_validate_and_round_trip(recs):
    assert len(recs) == len(C.CASES) == 90
    assert len({r.id for r in recs}) == len(recs)
    assert len({r.group for r in recs}) == len(recs)            # one group per case
    for r in recs:
        r.validate()
        assert Record.from_dict(json.loads(r.to_json())).to_dict() == r.to_dict()
        assert (r.feature, r.subtask, r.labels) == ("F3", "topic", ["no", "yes"])
        assert r.provenance.label_basis == "llm"
        assert r.provenance.notes.startswith("AI-drafted 2026-09-23; label proposed, pending independent human validation")
        if C.HAS_REVIEW_STATUS:
            assert r.review_status == "candidate"
        else:
            assert "review_status=candidate" in r.provenance.notes


def test_attributes_and_rationales_cite_the_definition(recs, defs):
    for r in recs:
        a = r.attribute
        assert a["kind"] in C.KINDS and a["topic_set"] == "v1"
        assert (a["topic"] is None) == (a["kind"] == "confuser")
        assert a["topic"] is None or a["topic"] in defs
        assert r.expected == ("yes" if a["kind"] == "in_topic" else "no")
        assert r.category.bedrock == ("TOPIC" if r.expected == "yes" else "NONE")
        m = CITE.search(a["rationale"])
        assert m, a["rationale"]
        cited_in = a["topic"] or (a["vocabulary"] if a["vocabulary"] in defs else None)
        if cited_in:
            assert m.group(1) in defs[cited_in]["definition"], (r.provenance.source_id, m.group(1))
        else:
            assert any(m.group(1) in d["definition"] for d in defs.values())
        assert "\n" not in a["rationale"] and len(a["rationale"]) < 300


def test_counts_by_topic_and_kind(recs):
    c = Counter((r.attribute["topic"], r.attribute["kind"]) for r in recs)
    for t in C.topic_names():
        assert c[(t, "in_topic")] == 12 and c[(t, "hard_negative")] == 12
    assert c[(None, "confuser")] == 18


def test_classes_balanced_within_ten_percent_per_topic(recs):
    for t in C.topic_names():
        lab = Counter(r.expected for r in recs if r.attribute["topic"] == t)
        assert abs(lab["yes"] - lab["no"]) <= 0.10 * max(lab["yes"], lab["no"]), (t, lab)


def test_no_text_overlaps_existing_controls_or_topic_examples(recs, defs):
    old = [text for _, _, text in f3_controls.CASES] + [e for d in defs.values() for e in d["examples"]]
    new = [r.state.text for r in recs]
    assert len({_norm(t) for t in new}) == len(new)            # no duplicates within the set
    for t in new:
        for o in old:
            assert _norm(t) != _norm(o), t
            assert not (_ngrams(t) & _ngrams(o)), (t, o)        # no shared five-word run
            a, b = _words(t), _words(o)
            assert len(a & b) / len(a | b) < 0.4, (t, o)        # no close paraphrase by word overlap


def test_ambiguous_ids_exist():
    sids = {c[0] for c in C.CASES}
    assert set(C.AMBIGUOUS) <= sids and C.AMBIGUOUS


def test_packet_on_disk_matches_the_generator():
    p = C.render_packet()
    assert (PDIR / "packet.md").read_text(encoding="utf-8") == p["packet.md"]
    assert (PDIR / "labels.template.jsonl").read_text(encoding="utf-8") == p["labels.template.jsonl"]
    on_disk = json.loads(KEY.read_text(encoding="utf-8"))
    plan = on_disk.pop("second_review_plan", None)          # added by review_plan: flagged cases plus a random sample
    if plan:
        on_disk["second_reviewer"] = plan["flagged"]
    assert on_disk == json.loads(json.dumps(p["key"]))


def test_packet_leaks_no_label_rationale_or_id(recs):
    md = (PDIR / "packet.md").read_text(encoding="utf-8")
    tpl = (PDIR / "labels.template.jsonl").read_text(encoding="utf-8")
    for blob in (md, tpl):
        for r in recs:
            assert r.id not in blob and r.provenance.source_id not in blob
            assert r.attribute["rationale"] not in blob
            why = r.attribute["rationale"].split(" Definition: ")[0]
            assert why not in blob
        for s in C.AMBIGUOUS.values():
            assert s not in blob
        for word in ("in_topic", "hard_negative", "confuser", "rationale", "expected", "proposed_labels", "ambiguous",
                     "label_basis", C.NAME):
            assert word not in blob, word
    # every case text appears exactly once, and no answer cell is filled in
    for r in recs:
        assert md.count(f"> **user:** {r.state.text}\n") == 1
    answers = [line for line in md.splitlines() if line.startswith("| ") and "yes / no / unclear" in line]
    assert len(answers) == 90 * 3 and all(line.endswith("|  |") for line in answers)
    rows = [json.loads(l) for l in tpl.splitlines()]
    assert len(rows) == 90 and [r["review_id"] for r in rows] == [f"f3t-r{i:02d}" for i in range(1, 91)]
    for row in rows:
        assert set(row) == {"review_id", "packet", "reviewer", "submitted_at", "labels", "note"}
        assert row["labels"] == {t: None for t in C.topic_names()} and row["note"] is None
        assert row["reviewer"] == "" and row["submitted_at"] == ""


def test_packet_order_is_not_authoring_order(recs):
    key = json.loads(KEY.read_text(encoding="utf-8"))
    kinds = [key["proposed"][rid]["kind"] for rid in sorted(key["proposed"])]
    runs = sum(1 for a, b in zip(kinds, kinds[1:]) if a != b)
    assert runs > 30                                           # authoring order has only 8 kind changes


def test_key_carries_proposals_and_second_reviewer_list(recs):
    key = json.loads(KEY.read_text(encoding="utf-8"))
    assert key["_warning"].startswith("Lead only")
    by_id = {r.id: r for r in recs}
    assert set(key["review_id_to_record_id"].values()) == set(by_id)
    for rid, p in key["proposed"].items():
        r = by_id[key["review_id_to_record_id"][rid]]
        assert p["record_id"] == r.id and p["expected"] == r.expected and p["rationale"] == r.attribute["rationale"]
        yes = [t for t, v in p["proposed_labels"].items() if v == "yes"]
        assert yes == ([r.attribute["topic"]] if r.expected == "yes" else [])
        assert p["ambiguous"] == (r.provenance.source_id in C.AMBIGUOUS)
    ambiguous = sorted(rid for rid, p in key["proposed"].items() if p["ambiguous"])
    assert len(ambiguous) == len(C.AMBIGUOUS)
    assert set(ambiguous) <= set(key["second_reviewer"])       # every ambiguous case, plus the random sample
    assert sorted(key["second_review_plan"]["flagged"]) == ambiguous
