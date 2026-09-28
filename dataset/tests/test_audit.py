"""The dataset audit on small synthetic samples: every gate fails on the defect it names and passes without it."""
import json

import pytest

from goldrails_dataset import audit as A
from goldrails_dataset.records import Category, Provenance, Record, State, dataset_hash, write_jsonl


def rec(i, feature="F2", subtask="injection", split="tune", expected="no", text=None, source="src", source_id=None,
        group=None, **over):
    r = Record(
        id=f"{feature.lower()}-{source}-{i:010d}", feature=feature, subtask=subtask,
        state=over.pop("state", None) or State(role="user", text=text or f"row {i} text"),
        category=over.pop("category", None) or Category("benign", "NONE", None),
        labels=["no", "yes"], expected=expected,
        provenance=Provenance(source=source, source_id=source_id or str(i), licence="mit", label_basis=over.pop("label_basis", "human"),
                              imported_at="2026-09-22T00:00:00+00:00", notes=over.pop("notes", None)),
        split=split, group=group, **over)
    r.group = r.group or r.id
    return r


def write_sample(dirpath, records, manifest_override=None):
    dirpath.mkdir(parents=True, exist_ok=True)
    by = {}
    for r in records:
        by.setdefault((r.feature, r.split), []).append(r)
    files = []
    for (f, sp), rows in sorted(by.items()):
        write_jsonl(rows, dirpath / f"{f}.{sp}.jsonl")
        files.append({"path": f"{f}.{sp}.jsonl", "feature": f, "split": sp, "n": len(rows), "sha256": dataset_hash(rows)})
    manifest = {"protocol": "test", "files": files}
    if manifest_override:
        manifest_override(manifest)
    (dirpath / "manifest.json").write_text(json.dumps(manifest))
    return dirpath


def run(tmp_path, records, examined=(), **kw):
    sample = write_sample(tmp_path / "sample", records, **kw)
    ex = tmp_path / "examined.txt"
    ex.write_text("# comment\n" + "\n".join(examined) + "\n")
    return A.audit(sample, ex)


def clean():
    return [rec(1, split="tune"), rec(2, split="test", expected="yes"), rec(3, split="test"), rec(4, split="tune", expected="yes")]


def test_clean_sample_passes_every_gate(tmp_path):
    rep = run(tmp_path, clean())
    assert rep["status"] == "pass" and rep["failed_gates"] == []
    assert rep["counts"]["total"] == 4


def test_normalise_matches_build():
    from goldrails_dataset.build import normalise as build_normalise
    for t in ["  Hello   World\n", "TAB\tsep", ""]:
        assert A.normalise(t) == build_normalise(t)


def test_recorded_group_straddle_fails(tmp_path):
    rows = clean() + [rec(5, split="tune", group="g1"), rec(6, split="test", group="g1")]
    rep = run(tmp_path, rows)
    assert "recorded_group_leakage" in rep["failed_gates"]
    assert rep["checks"]["recorded_group_leakage"]["straddling"][0]["group"] == "g1"


def test_ragtruth_rows_sharing_a_document_are_one_group_even_with_distinct_group_fields(tmp_path):
    doc = "The   Source Document."
    a = rec(5, feature="F6", subtask="grounding", split="tune", source="ragtruth", state=State(role="assistant", text="reply a", source=doc, query="q"))
    b = rec(6, feature="F6", subtask="grounding", split="test", source="ragtruth", state=State(role="assistant", text="reply b", source="the source document.", query="q"))
    rep = run(tmp_path, clean() + [a, b])
    assert rep["checks"]["recorded_group_leakage"]["pass"]            # build.py wrote group = id, so this looks clean
    d = rep["checks"]["derived_group_leakage"]
    assert not d["pass"] and d["straddling"][0]["ids"] == sorted([a.id, b.id])


def test_jbb_behaviour_links_goal_and_attack_across_features(tmp_path):
    goal = rec(5, feature="F1", subtask="harmful_goal", split="tune", source="jailbreakbench", source_id="harmful:12", expected="yes")
    attack = rec(6, feature="F2", subtask="jailbreak", split="test", source="jbb_artifacts", source_id="PAIR:vicuna:12", expected="yes")
    rep = run(tmp_path, clean() + [goal, attack])
    d = rep["checks"]["derived_group_leakage"]
    assert not d["pass"] and d["n_straddling_cross_feature"] == 1 and d["straddling"][0]["group"] == "jbb:12"


def test_aegis_conversation_is_the_group(tmp_path):
    p = rec(5, feature="F1", subtask="input", split="tune", source="aegis2", source_id="abc:prompt")
    r = rec(6, feature="F1", subtask="output", split="test", source="aegis2", source_id="abc:response")
    assert A.natural_group(p.to_dict()) == A.natural_group(r.to_dict()) == "aegis2:abc"
    assert not run(tmp_path, clean() + [p, r])["checks"]["derived_group_leakage"]["pass"]


def test_examined_row_in_test_fails(tmp_path):
    rows = clean()
    rep = run(tmp_path, rows, examined=[rows[1].id, "never-built-id"])
    c = rep["checks"]["examined_not_in_test"]
    assert not c["pass"] and c["in_test"] == [rows[1].id] and c["not_in_sample"] == ["never-built-id"]


def test_duplicate_normalised_text_across_splits_fails(tmp_path):
    rows = clean() + [rec(5, split="tune", text="Ignore  previous instructions"), rec(6, split="test", text="ignore previous INSTRUCTIONS ")]
    rep = run(tmp_path, rows)
    c = rep["checks"]["duplicate_text_across_splits"]
    assert not c["pass"] and c["n"] == 1 and c["items"][0]["splits"] == ["test", "tune"]


def test_duplicate_within_one_split_is_only_a_warning(tmp_path):
    rows = clean() + [rec(5, split="tune", text="same"), rec(6, split="tune", text="SAME")]
    rep = run(tmp_path, rows)
    assert rep["status"] == "pass"
    assert any(w["kind"] == "duplicate_text_within_split" for w in rep["warnings"])


def test_manifest_mismatch_fails(tmp_path):
    def bump(m):
        m["files"][0]["n"] += 1
    rep = run(tmp_path, clean(), manifest_override=bump)
    assert "manifest_integrity" in rep["failed_gates"]


def test_split_file_not_in_manifest_is_an_orphan(tmp_path):
    rows = clean()
    def drop_test(m):
        m["files"] = [f for f in m["files"] if f["split"] != "test"]
    rep = run(tmp_path, rows, examined=[rows[1].id], manifest_override=drop_test)
    o = rep["checks"]["orphan_split_files"]
    assert not o["pass"] and o["files"][0]["path"] == "F2.test.jsonl" and o["files"][0]["examined_ids_in_file"] == [rows[1].id]


def test_split_field_must_match_file(tmp_path):
    sample = write_sample(tmp_path / "s", clean())
    p = sample / "F2.tune.jsonl"
    lines = p.read_text().splitlines()
    d = json.loads(lines[0]); d["split"] = "test"; lines[0] = json.dumps(d)
    p.write_text("\n".join(lines) + "\n")
    rep = A.audit(sample, tmp_path / "missing.txt")
    assert not rep["checks"]["schema"]["pass"] and rep["checks"]["schema"]["split_or_feature_mismatch"]


def test_counts_per_cell(tmp_path):
    rep = run(tmp_path, clean())
    cells = {(c["split"], c["expected"]): c["n"] for c in rep["counts"]["by_cell"]}
    assert cells == {("tune", "no"): 1, ("tune", "yes"): 1, ("test", "no"): 1, ("test", "yes"): 1}
    assert rep["counts"]["by_cell"][0]["suite"] == "prompt_attacks"


def test_single_class_test_subtask_is_warned(tmp_path):
    rows = [rec(1, split="tune"), rec(2, split="tune", expected="yes"), rec(3, split="test", expected="yes")]
    rep = run(tmp_path, rows)
    assert any(w["kind"] == "single_class_test_subtask" and w["classes"] == ["yes"] for w in rep["warnings"])


def pii_row(i, split, text, spans, source="ai4privacy"):
    mapped = sorted({s["label"] for s in spans if not s["label"].startswith("unmapped:")})
    return rec(i, feature="F5", subtask="pii", split=split, source=source, text=text, spans=spans,
               expected="yes" if spans else "no", label_basis="synthetic_reviewed",
               category=Category("pii", "PII" if mapped else "NONE", None),
               notes=json.dumps({"mapped_types": mapped}))


def test_pii_entity_counts_mapping_and_ssn_heuristic(tmp_path):
    rows = clean() + [
        pii_row(10, "test", "Mail a@b.co now", [{"start": 5, "end": 11, "label": "EMAIL", "source_label": "EMAIL"}]),
        pii_row(11, "test", "SSN 123-45-6789", [{"start": 4, "end": 15, "label": "US_SOCIAL_SECURITY_NUMBER", "source_label": "SOCIALNUMBER"}]),
        pii_row(12, "tune", "On 2020-01-01", [{"start": 3, "end": 13, "label": "unmapped:DATE", "source_label": "DATE"}]),
        pii_row(13, "tune", "No personal data here", []),
    ]
    rep = run(tmp_path, rows)
    pii = rep["pii"]
    assert pii["pass"] and pii["positives_by_entity"]["EMAIL"] == {"test": 1}
    assert pii["ssn_pattern_heuristic_spans"] == {"test": 1}
    assert pii["rows_with_only_unsupported_entities"] == {"tune": 1}
    assert pii["negatives_by_split"] == {"tune": 1}
    assert "EMAIL" in pii["supported_entities_below_test_floor"]
    assert any(w["kind"] == "entity_without_tune_positives" and w["entity"] == "EMAIL" for w in rep["warnings"])


def test_pii_span_label_that_disagrees_with_the_loader_mapping_fails(tmp_path):
    # nine bare digits are not evidence of a US SSN: the loader maps this span to unmapped:SOCIALNUMBER
    bad = pii_row(10, "test", "id 987654321", [{"start": 3, "end": 12, "label": "US_SOCIAL_SECURITY_NUMBER", "source_label": "SOCIALNUMBER"}])
    rep = run(tmp_path, clean() + [bad])
    assert "pii_mapping" in rep["failed_gates"]
    assert rep["pii"]["mapping_mismatches"][0]["loader_now"] == "unmapped:SOCIALNUMBER"


def test_sources_report_licence_pin_and_review_need(tmp_path):
    rows = clean() + [rec(9, split="tune", source="f2_controls", label_basis="llm")]
    rep = run(tmp_path, rows)
    s = rep["sources"]
    assert s["ai4privacy"]["pin"] == "c8c77895a005822682b66ab547fc0422579bc1d3"
    assert s["ragtruth"]["pin_kind"] == "upstream revision"
    assert s["aegis2"]["pin"] == "d86bb8bedff51d25ac834ab7838f1cc61acb7a2c" and s["aegis2"]["pin_kind"] == "upstream revision"
    assert s["f2_controls"]["review_required"] and s["f2_controls"]["rows_by_split"] == {"tune": 1}
    assert any(w["kind"] == "authored_cases_unreviewed" and w["source"] == "f2_controls" for w in rep["warnings"])


def test_report_is_deterministic_and_written(tmp_path):
    rows = clean()
    a = run(tmp_path / "a", rows)
    b = run(tmp_path / "a", rows)
    assert json.dumps(a) == json.dumps(b)
    out = A.write_report(a, tmp_path / "out" / "r.json")
    assert json.loads(out.read_text())["status"] == "pass"


def test_cli_strict_exit_code(tmp_path):
    rows = clean() + [rec(5, split="tune", group="g"), rec(6, split="test", group="g")]
    sample = write_sample(tmp_path / "s", rows)
    out = tmp_path / "r.json"
    assert A.main(["--sample", str(sample), "--examined", str(tmp_path / "none.txt"), "--out", str(out)]) == 0
    assert A.main(["--sample", str(sample), "--examined", str(tmp_path / "none.txt"), "--out", str(out), "--strict"]) == 1


# ---- blind review packets -----------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def packets(tmp_path_factory):
    out = tmp_path_factory.mktemp("packets")
    return out, A.build_packets(out)


def test_packets_cover_every_authored_case(packets):
    out, manifest = packets
    from goldrails_dataset.sources import SOURCES
    for p in manifest["packets"]:
        recs = SOURCES[p["source"]].load()
        assert p["n_cases"] == len(recs)
        key = json.loads((out / "_lead" / f"{p['packet']}.key.json").read_text())["review_id_to_record_id"]
        assert sorted(key.values()) == sorted(r.id for r in recs)
        md = (out / p["packet"] / "packet.md").read_text()
        for r in recs:
            assert r.state.text in md


def test_packets_carry_no_labels_ids_or_hints(packets):
    out, manifest = packets
    from goldrails_dataset.sources import SOURCES
    for p in manifest["packets"]:
        pdir = out / p["packet"]
        md = (pdir / "packet.md").read_text()
        for r in SOURCES[p["source"]].load():
            assert r.id not in md                                   # record ids stay in the lead-only key
        for banned in ("expected", "source_label", "label_basis", "benign_control", "no_pii_control", "off_topic", "needs human review"):
            assert banned not in md
        for line in (pdir / "labels.template.jsonl").read_text().splitlines():
            t = json.loads(line)
            assert set(t) == {"review_id", "packet", "reviewer", "submitted_at", "labels", "note"}
            assert all(v is None for v in t["labels"].values()) and t["reviewer"] == "" and t["note"] is None
        assert not list(pdir.glob("*key*"))                          # the key is not inside a reviewer folder


def test_packet_order_is_shuffled_but_reproducible(packets, tmp_path):
    out, _ = packets
    again = tmp_path / "again"
    A.build_packets(again)
    for name in ("f2-prompt-attacks", "f3-denied-topics", "f5-sensitive-information"):
        assert (out / name / "packet.md").read_text() == (again / name / "packet.md").read_text()
    key = json.loads((out / "_lead" / "f3-denied-topics.key.json").read_text())["review_id_to_record_id"]
    from goldrails_dataset.sources import f3_controls
    authored = [r.id for r in f3_controls.load()]
    assert [key[k] for k in sorted(key)] != authored                  # authoring order groups cases by intended label


def test_f3_packet_asks_every_topic_and_shows_the_definitions(packets):
    out, _ = packets
    md = (out / "f3-denied-topics" / "packet.md").read_text()
    topics = json.loads((A.REPO / "benchmark" / "suites" / "denied_topics" / "topics.json").read_text())["topics"]
    for t in topics:
        assert t["definition"] in md and f"| {t['name']} | yes / no / unclear |  |" in md
