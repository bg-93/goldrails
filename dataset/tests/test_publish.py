"""Publication staging refuses leaked text, withheld sources and unregistered sources."""
from goldrails_dataset.publish import WITHHOLD, validate


def row(source, mode="text", text=None):
    return {"id": f"x-{source}", "provenance": {"source": source}, "redistribution": mode, "state": {"text": text}}


def test_validate_flags_leaks_withheld_and_unknown(tmp_path):
    reg = [{"source": "ragtruth"}, {"source": "aegis2"}]
    rows = [row("ragtruth", "ids_only", "leaked"), row(next(iter(WITHHOLD))), row("nobody"), row("aegis2", "text", "fine")]
    problems = validate(tmp_path, [], rows, reg)
    assert any("carries text" in p for p in problems)
    assert any("withheld source" in p for p in problems)
    assert any("not in registry" in p for p in problems)
    assert not any("aegis2" in p for p in problems)
