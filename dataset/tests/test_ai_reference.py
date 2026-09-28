"""The provisional single-AI reference: labels are applied as ai_reviewed/llm, never as human review."""
from collections import Counter
from pathlib import Path

from goldrails_dataset import build as B
from goldrails_dataset.sources import bias_pairs_reviewed as BP, civil_comments_profanity as CP, f3_controls, f3_test_candidates

AI = Path(__file__).resolve().parents[1] / "frozen" / "reviews" / "ai-codex-2026-09-24"


def test_ai_reference_reproduces_the_handoff_counts_without_calling_anything_human():
    rows, reserves = B.ai_reference(AI)
    assert len(rows) == 442 and len(reserves) == 25
    recs = f3_controls.load() + f3_test_candidates.load() + CP.load(released=set(reserves))
    n = B.apply_ai_reference(recs, rows, reserves, "owner instruction")
    assert n["moved_to_diagnostic"] == 6 and n["excluded_unresolved"] == 14
    prof = [r for r in recs if r.feature == "F4" and r.review_status == "ai_reviewed"]
    assert Counter(r.expected for r in prof if r.subtask == "profanity") == {"yes": 100, "no": 158}
    assert sum(1 for r in recs if r.feature == "F4" and r.provenance.exclude_reason) == 11
    assert sum(1 for r in recs if r.feature == "F3" and r.provenance.exclude_reason) == 3
    scored = [r for r in recs if r.review_status == "ai_reviewed"]
    assert {r.provenance.label_basis for r in scored} == {"llm"} and not any(r.review_status == "reviewed" for r in recs)
    b2 = BP.load(ai_reference=AI)
    assert len(b2) == 16 and {r.review_status for r in b2} == {"ai_reviewed"} and {r.provenance.label_basis for r in b2} == {"llm"}


def test_human_path_is_untouched_by_the_ai_reference():
    recs = f3_test_candidates.load()
    n = B.apply_reviews(recs, {})
    assert n == {"unreviewed_or_unresolved": 90} and all(r.review_status == "candidate" for r in recs)
