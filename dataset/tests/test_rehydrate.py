"""A rebuilt row is kept only when it matches its published canonical hash."""
import hashlib
import json

from goldrails_dataset.rehydrate import row_hash


def test_row_hash_ignores_published_only_and_volatile_fields():
    row = {"id": "x", "state": {"text": "hello"}, "provenance": {"source": "s", "imported_at": "t1"}}
    want = hashlib.sha256(json.dumps({"id": "x", "state": {"text": "hello"}, "provenance": {"source": "s"}},
                                     sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    published = {**row, "redistribution": "ids_only", "acquisition": {}, "canonical_row_hash": want,
                 "provenance": {"source": "s", "imported_at": "t2"}}
    assert row_hash(published) == want
    assert row_hash({**published, "state": {"text": "other"}}) != want
