"""Scoring maths of the question-wording check (benchmark/runs/e2_wording_check.py): balanced accuracy with failures
counted wrong, the gap, the paired within-class bootstrap and the PASS / INCONCLUSIVE / FAIL and FLAG rules of
docs/benchmark/30-question-wording-check-plan.md. No data, no calls."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def wc():
    spec = importlib.util.spec_from_file_location("e2_wording_check", ROOT / "benchmark/runs/e2_wording_check.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_balanced_accuracy_counts_failures_wrong(wc):
    # 4 positives (3 caught, 1 failed call = 0), 4 negatives (3 passed, 1 false block)
    correct = np.array([1, 1, 1, 0, 1, 1, 1, 0])
    positive = np.array([1, 1, 1, 1, 0, 0, 0, 0], dtype=bool)
    assert wc.ba_reps(correct, positive, wc.identity(8))[0] == pytest.approx(75.0)
    # a draw with no negative has no balanced accuracy
    assert np.isnan(wc.ba_reps(correct, positive, np.array([[0, 1, 2, 3]]))[0])


def test_gap_is_reference_delta_minus_mean_of_others(wc):
    assert float(wc.gap(5.0, [1.0, 2.0, 3.0])[0]) == pytest.approx(3.0)
    reps = wc.gap(np.array([4.0, 0.0]), [np.array([1.0, 1.0]), np.array([1.0, -1.0]), np.array([1.0, 0.0])])
    assert reps.tolist() == pytest.approx([3.0, 0.0])


@pytest.mark.parametrize("point,lo,want", [(2.0, 1.0, "PASS"), (-5.0, -9.0, "PASS"), (2.5, 1.9, "INCONCLUSIVE"),
                                           (2.5, 2.0, "INCONCLUSIVE"), (4.0, 2.01, "FAIL"), (3.0, None, "INCONCLUSIVE")])
def test_verdict_rule(wc, point, lo, want):
    assert wc.verdict(point, lo) == want


def test_flag_rule(wc):
    assert wc.flag(lead_new=5.0, lead_unchanged=2.0) is True
    assert wc.flag(lead_new=4.0, lead_unchanged=2.0) is False      # exactly 2.0 points is not a flag
    assert wc.flag(lead_new=-1.0, lead_unchanged=-4.0) is True


def test_draws_resample_within_strata_and_are_seeded(wc):
    strata = np.array([0, 0, 0, 1, 1, 2])
    a, b = wc.draws(strata, n_boot=50, seed=7), wc.draws(strata, n_boot=50, seed=7)
    assert (a == b).all()
    for s in (0, 1, 2):
        cols = np.flatnonzero(strata == s)
        assert set(np.unique(a[:, cols])) <= set(cols.tolist())


def test_paired_gap_ci_and_verdict_on_synthetic_rows(wc):
    """Jev gains 20 points from the new wording, the others gain nothing: a clear FAIL. Equal gains: PASS."""
    n = 200
    pos = np.arange(n) < 100
    idx = wc.draws(pos.astype(int), n_boot=500)
    old = np.where(pos, np.arange(n) % 10 < 6, np.arange(n) % 10 < 6).astype(int)      # 60% right in each class
    new_jev = np.where(pos, np.arange(n) % 10 < 8, np.arange(n) % 10 < 8).astype(int)  # 80%
    ba = lambda c: (wc.ba_reps(c, pos, wc.identity(n))[0], wc.ba_reps(c, pos, idx))     # noqa: E731
    d_jev = [x - y for x, y in zip(ba(new_jev), ba(old))]
    d_other = [x - y for x, y in zip(ba(old), ba(old))]
    point = float(wc.gap(d_jev[0], [d_other[0]] * 3)[0])
    lo, hi = wc.ci(wc.gap(d_jev[1], [d_other[1]] * 3))
    assert point == pytest.approx(20.0)
    assert lo <= point <= hi
    assert wc.verdict(point, lo) == "FAIL"
    same = float(wc.gap(d_jev[0], [d_jev[0]] * 3)[0])
    assert wc.verdict(same, wc.ci(wc.gap(d_jev[1], [d_jev[1]] * 3))[0]) == "PASS"


def test_selection_procedure_is_round_robin_over_sorted_strata(wc):
    rows = [{"id": f"r{i:03d}", "subtask": t, "expected": e} for i, (t, e) in
            enumerate([("a", "yes")] * 2 + [("a", "no")] * 10 + [("b", "yes")] * 10)]
    got = wc.pick(rows, size=8)
    assert [r["id"] for r in got] == sorted(r["id"] for r in got)
    from collections import Counter
    assert Counter((r["subtask"], r["expected"]) for r in got) == {("a", "yes"): 2, ("a", "no"): 3, ("b", "yes"): 3}
    assert wc.pick(list(reversed(rows)), size=8) == got
