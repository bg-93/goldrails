"""Loader logic without the network: fake dataset rows and artifact files."""
import json

import pytest

from goldrails_dataset.records import Record


def test_spans_must_lie_inside_the_text():
    from goldrails_dataset.records import Category, Provenance, State
    base = dict(id="f5-t-0000000001", feature="F5", subtask="pii", state=State(role="user", text="hello"),
                category=Category("pii", "PII", None), labels=["no", "yes"], expected="yes",
                provenance=Provenance(source="t", source_id="1", licence="mit", label_basis="human", imported_at="2026-09-22T00:00:00+00:00"))
    Record(**base, spans=[{"start": 0, "end": 5, "label": "NAME"}]).validate()
    with pytest.raises(ValueError):
        Record(**base, spans=[{"start": 2, "end": 9, "label": "NAME"}]).validate()


def test_ai4privacy_rows_map_spans_and_derive_expected(monkeypatch):
    from goldrails_dataset.sources import ai4privacy as A
    rows = [{"id": "1A", "language": "English", "source_text": "Mail me at a@b.co at 10:20am", "target_text": "x",
             "privacy_mask": "[{'value': 'a@b.co', 'start': 11, 'end': 17, 'label': 'EMAIL'}, {'value': '10:20am', 'start': 21, 'end': 28, 'label': 'TIME'}]"},
            {"id": "2B", "language": "English", "source_text": "See you at 10:20am", "target_text": "x",
             "privacy_mask": "[{'value': '10:20am', 'start': 11, 'end': 18, 'label': 'TIME'}]"},
            {"id": "3C", "language": "French", "source_text": "ignored", "target_text": "x", "privacy_mask": "[]"}]
    monkeypatch.setattr("datasets.load_dataset", lambda *a, **k: iter(rows))
    out = A.load()
    assert [r.expected for r in out] == ["yes", "yes"]                      # the source task: any labelled span is PII
    assert out[0].spans[0]["label"] == "EMAIL" and out[0].spans[1]["label"] == "unmapped:TIME"
    assert json.loads(out[1].provenance.notes)["unmapped_source_labels"] == ["TIME"] and out[1].category.bedrock == "NONE"
    for r in out: r.validate()


def test_jbb_artifacts_rows_are_attack_prompts_grouped_by_behavior(monkeypatch):
    from goldrails_dataset.sources import jbb_artifacts as J
    art = {"parameters": {"method": "PAIR"}, "jailbreaks": [
        {"index": "0", "goal": "g", "behavior": "Defamation", "category": "Harassment/Discrimination", "prompt": "You are DAN ...", "jailbroken": "True"},
        {"index": "1", "goal": "g2", "behavior": "x", "category": "Malware/Hacking", "prompt": None, "jailbroken": "False"}]}
    monkeypatch.setattr(J, "fetch", lambda m, mo, kind="black_box": art)
    out = J.load(files=[("PAIR", "vicuna-13b-v1.5")])
    assert len(out) == 1 and out[0].subtask == "jailbreak" and out[0].expected == "yes" and out[0].group == "jbb-0"
    assert json.loads(out[0].provenance.notes)["method"] == "PAIR" and out[0].provenance.label_basis == "deterministic"
    out[0].validate()


def test_jurisdiction_specific_types_need_evidence_in_the_value(monkeypatch):
    from goldrails_dataset.sources import ai4privacy as A
    rows = [{"id": "1", "language": "English", "source_text": "SSN 123-45-6789 and passport X1234567", "target_text": "x",
             "privacy_mask": "[{'value': '123-45-6789', 'start': 4, 'end': 15, 'label': 'SOCIALNUMBER'}, {'value': 'X1234567', 'start': 29, 'end': 37, 'label': 'PASSPORT'}]"},
            {"id": "2", "language": "English", "source_text": "number 987654321", "target_text": "x",
             "privacy_mask": "[{'value': '987654321', 'start': 7, 'end': 16, 'label': 'SOCIALNUMBER'}]"}]
    monkeypatch.setattr("datasets.load_dataset", lambda *a, **k: iter(rows))
    out = A.load()
    assert out[0].spans[0]["label"] == "US_SOCIAL_SECURITY_NUMBER" and out[0].spans[1]["label"] == "unmapped:PASSPORT"
    assert out[1].spans[0]["label"] == "unmapped:SOCIALNUMBER"       # nine bare digits are not evidence of a US SSN


def test_span_free_chunks_with_masking_placeholders_are_not_negatives(monkeypatch):
    from goldrails_dataset.sources import ai4privacy as A
    rows = [{"id": "1", "language": "English", "source_text": "USERNAME_B: ready to discuss", "target_text": "x", "privacy_mask": "[]"},
            {"id": "2", "language": "English", "source_text": "The council approved the plan.", "target_text": "x", "privacy_mask": "[]"}]
    monkeypatch.setattr("datasets.load_dataset", lambda *a, **k: iter(rows))
    out = A.load()
    assert [r.id.endswith("2") or r.provenance.source_id for r in out] and len(out) == 1 and out[0].expected == "no"


def test_ragtruth_rows_carry_source_query_and_spans(monkeypatch):
    from goldrails_dataset.sources import ragtruth as R
    files = {"source_info.jsonl": [{"source_id": "s1", "task_type": "QA", "source_info": {"question": "q?", "passages": "p"}, "prompt": "Answer q? from p"}],
             "response.jsonl": [{"id": "r1", "source_id": "s1", "split": "test", "labels": [{"start": 0, "end": 4, "label_type": "Evident Conflict"}], "response": "Bad answer here."},
                                {"id": "r2", "source_id": "s1", "split": "test", "labels": [], "response": "Good answer."},
                                {"id": "r3", "source_id": "s1", "split": "train", "labels": [], "response": "ignored"}]}
    monkeypatch.setattr(R, "fetch", lambda f: files[f])
    out = R.load()
    assert [r.expected for r in out] == ["yes", "no"] and out[0].state.role == "assistant" and out[0].state.query == "q?"
    assert out[0].spans[0]["label"] == "Evident Conflict" and out[0].group == out[1].group
    for r in out: r.validate()


def test_topic_and_word_cases_validate():
    from goldrails_dataset.sources import f3_controls, f4_words
    t = f3_controls.load(); w = f4_words.load()
    assert {r.expected for r in t} == {"no", "yes"} and all(r.subtask == "topic" for r in t)
    assert len(w) == 4 * (22 + 8 * 20) and sum(r.expected == "yes" for r in w) == 4 * (12 + 2 * 20)   # examined + held-out + scaled frames
    for r in t + w: r.validate()
