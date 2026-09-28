import pytest

from goldrails_dataset.records import Category, Provenance, Record, State, dataset_hash, make_id


def rec(**over):
    base = dict(
        id="f1-test-0000000001", feature="F1", subtask="input",
        state=State(role="user", text="hello"), category=Category("benign", "NONE", None),
        labels=["no", "yes"], expected="no",
        provenance=Provenance(source="test", source_id="1", licence="mit", label_basis="human", imported_at="2026-09-22T00:00:00+00:00"),
    )
    base.update(over)
    return Record(**base)


def test_valid_record_roundtrips():
    r = rec(); r.validate()
    assert Record.from_dict(r.to_dict()).to_json() == r.to_json()


def test_expected_must_be_in_labels():
    with pytest.raises(ValueError):
        rec(expected="maybe").validate()


def test_state_cannot_carry_answer():
    r = rec(); r.state.tool_call = {"name": "x", "answer": "yes"}
    with pytest.raises(ValueError):
        r.validate()


def test_distribution_must_match_labels_and_sum():
    with pytest.raises(ValueError):
        rec(expected_distribution={"no": 0.5, "maybe": 0.5}).validate()
    with pytest.raises(ValueError):
        rec(expected_distribution={"no": 0.6, "yes": 0.6}).validate()
    rec(expected_distribution={"no": 0.67, "yes": 0.33}).validate()


def test_f7_needs_attribute():
    with pytest.raises(ValueError):
        rec(feature="F7", subtask="b1_disparate_fpr").validate()
    rec(feature="F7", subtask="b1_disparate_fpr", attribute={"kind": "gender", "value": "female"}).validate()


def test_hash_is_order_independent_and_content_sensitive():
    a, b = rec(), rec(id="f1-test-0000000002")
    assert dataset_hash([a, b]) == dataset_hash([b, a])
    assert dataset_hash([a]) != dataset_hash([rec(expected="yes")])


def test_make_id_is_stable():
    assert make_id("F1", "src", "1") == make_id("F1", "src", "1")
    assert make_id("F1", "src", "1") != make_id("F1", "src", "2")


def test_hash_ignores_import_timestamps():
    a = rec(); b = rec()
    b.provenance.imported_at = "2030-01-01T00:00:00+00:00"
    assert dataset_hash([a]) == dataset_hash([b])


def test_cell_rng_is_independent_per_cell():
    from goldrails_dataset.build import cell_rng
    a = [cell_rng(7, "F1", "input", "yes").random() for _ in range(3)]
    b = [cell_rng(7, "F1", "input", "yes").random() for _ in range(3)]
    c = [cell_rng(7, "F2", "injection", "yes").random() for _ in range(3)]
    assert a == b and a != c
