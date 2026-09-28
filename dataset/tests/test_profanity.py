"""The profanity candidates: frozen selection, reserves held back, blind packet, a written replenishment rule."""
import json

from goldrails_dataset.sources import civil_comments_profanity as CP


def test_frozen_selection_loads_the_reviewed_set_and_holds_reserves_back():
    lines = [json.loads(l) for l in CP.FROZEN.read_text(encoding="utf-8").splitlines() if l.strip()]
    meta, cands = lines[0]["_meta"], lines[1:]
    assert meta["revision"] == CP.REVISION and meta["lexicon"]["commit"] == CP.LEXICON["commit"]
    assert "never change" in meta["replenishment"]
    recs = CP.load()
    assert len(recs) == sum(1 for c in cands if not c.get("reserve")) == 280
    assert {r.subtask for r in recs} == {"profanity", "profanity_obfuscated"}
    assert all(r.review_status == "candidate" and r.provenance.label_basis == "automated" for r in recs)


def test_packet_is_blind():
    p = CP.render_packet()
    import re
    for text in (p["packet.md"], p["labels.template.jsonl"]):
        for leak in (r"\bbucket\b", r"\bdraft", r"\bobscene=", r"\bpresent_\w", r"\babsent_\w", r"\breserve\b"):
            assert not re.search(leak, text), leak
    assert CP.DEFINITION in p["packet.md"]
