"""Release immutability and PII parent grouping (data-quality review, 24 September 2026)."""
import json

import pytest

from goldrails_dataset import release
from goldrails_dataset.build import pii_parent_group


def test_pii_parent_group_joins_suffixed_fragments():
    assert pii_parent_group("50846A") == pii_parent_group("50846B") == pii_parent_group("50846E") == "ai4privacy-50846"
    assert pii_parent_group("51890A") != pii_parent_group("53180A")
    assert pii_parent_group("weird-id") == "ai4privacy-weird-id"


def test_existing_version_with_different_data_writes_nothing(tmp_path, monkeypatch):
    out = tmp_path / "release" / "vX"
    out.mkdir(parents=True)
    manifest = {"version": "vX", "release_sha256": "0" * 64, "build_files": [], "hf_files": []}
    (out / "manifest.json").write_text(json.dumps(manifest))
    before = sorted(p.name for p in out.iterdir())
    monkeypatch.setattr(release, "ROOT", tmp_path)
    monkeypatch.setattr(release, "VERSIONS", {"vX": {"per_cell": 1, "seed": 1}})
    monkeypatch.setattr(release, "build", lambda *a, **k: [])
    with pytest.raises(SystemExit, match="nothing written"):
        release.main(["--version", "vX"])
    assert sorted(p.name for p in out.iterdir()) == before
    assert json.loads((out / "manifest.json").read_text()) == manifest
    assert not [p for p in (tmp_path / "release").iterdir() if p.name.startswith(".")]   # no temporary directory left
