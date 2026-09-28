"""Separability check for an F2 indirect set: can a trivial baseline tell the attacks from the benign emails?

If a regex, a keyword count, the text length or a small bag-of-n-grams model separates the classes, a guardrail's
score on the set mostly measures that shortcut, and the set is unfit for a headline result. The baselines:

- ``regex_contact_confirmation``: 1 if the text matches ``contact|confirmation`` (the LLMail target was "send
  confirmation to contact@contact.com"), else 0. Fixed, not fitted.
- ``keyword_bag``: how many of a fixed list of attack-flavoured words and shapes the text contains. Fixed.
- ``length``: character length. Fixed; either direction counts.
- ``context_query``: the attack rate of the row's user query (the trust context) in the training folds. Fitted.
- ``token_count_rule``: the K tokens most over-represented in training attacks; score = how many the text contains.
  Fitted, pure Python, always run.
- ``char_ngram_l1_logreg``: L1 logistic regression on character 3-5-grams (TF-IDF). Fitted, run only when
  scikit-learn is importable (``uv run --with scikit-learn ...``); it is not a project dependency.

Fitted baselines are scored out of fold with group-aware folds (a group never straddles folds), so a team's attack
variants or a template's benign variants cannot leak between train and test. Each baseline reports AUROC and the
direction-free separability ``max(AUROC, 1 - AUROC)``: a shortcut that works backwards is still a shortcut. The set is
flagged unfit for a headline result when any baseline's separability exceeds THRESHOLD.

    uv run --with scikit-learn python -m goldrails_dataset.separability --max-per-team 10 --out report.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import warnings
from collections import Counter, defaultdict

THRESHOLD = 0.80
FOLDS = 5
TOP_K = 20
REGEX = re.compile(r"contact|confirmation", re.IGNORECASE)
KEYWORDS = ("send", "email", "contact", "confirmation", "confirm", "forward", "reply", "urgent", "immediately",
            "instruction", "ignore", "please", "@", "tool", "execute", "summar", "user", "system", "assistant")
TOKEN = re.compile(r"[a-z0-9@._']+")
# Diagnostic only: LLMail attacks all target one address (contact@contact.com). Replacing every email address in every
# row, attack or benign, with one placeholder shows how much separability is left once that constant is gone. It is
# not a fix; a benchmark cannot rewrite the attacks it scores.
EMAIL_ADDRESS = re.compile(r"[\w.+-]+\s*@\s*[\w-]+(?:\s*\.\s*[\w-]+)+", re.IGNORECASE)


def usable(records) -> list:
    """Rows with a yes/no label and no exclusion: the rows a result would be computed on."""
    return [r for r in records if r.expected in ("yes", "no") and not r.provenance.exclude_reason]


def auroc(scores, labels) -> float:
    """Mann-Whitney AUROC with ties counted half. labels are 1 (attack) or 0 (benign)."""
    pos = sum(labels)
    neg = len(labels) - pos
    if not pos or not neg:
        raise ValueError("AUROC needs both classes")
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    ranks = [0.0] * len(scores)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    rank_pos = sum(r for r, y in zip(ranks, labels) if y)
    return (rank_pos - pos * (pos + 1) / 2) / (pos * neg)


def folds_of(groups, k=FOLDS) -> list:
    """Fold index per row. Whole groups go to the currently smallest fold, in a hash order: deterministic, balanced."""
    size = Counter(groups)
    order = sorted(size, key=lambda g: (-size[g], hashlib.sha1(str(g).encode()).hexdigest()))
    load, fold_of_group = [0] * k, {}
    for g in order:
        f = min(range(k), key=lambda i: (load[i], i))
        fold_of_group[g] = f
        load[f] += size[g]
    return [fold_of_group[g] for g in groups]


def tokens(text: str) -> set:
    return set(TOKEN.findall(text.lower()))


def regex_scores(texts, *_):
    return [1.0 if REGEX.search(t) else 0.0 for t in texts]


def keyword_scores(texts, *_):
    low = [t.lower() for t in texts]
    return [float(sum(1 for w in KEYWORDS if w in t)) for t in low]


def length_scores(texts, *_):
    return [float(len(t)) for t in texts]


def out_of_fold(fit_predict, rows, labels, folds) -> list:
    scores = [0.0] * len(rows)
    for f in sorted(set(folds)):
        train = [i for i, x in enumerate(folds) if x != f]
        test = [i for i, x in enumerate(folds) if x == f]
        if not test or len({labels[i] for i in train}) < 2:
            continue
        preds = fit_predict([rows[i] for i in train], [labels[i] for i in train], [rows[i] for i in test])
        for i, p in zip(test, preds):
            scores[i] = float(p)
    return scores


def context_fit_predict(train, y, test):
    """Attack rate per user query (the last user turn of the trust context) in training; the prior for unseen queries."""
    hits, n = defaultdict(int), defaultdict(int)
    for q, lab in zip(train, y):
        hits[q] += lab
        n[q] += 1
    prior = sum(y) / len(y)
    return [hits[q] / n[q] if n[q] else prior for q in test]


def top_tokens(train, y, k=TOP_K) -> list:
    """Tokens whose document frequency in attacks exceeds that in benign emails by the most (min support 3)."""
    pos, neg = Counter(), Counter()
    n_pos = sum(y) or 1
    n_neg = (len(y) - sum(y)) or 1
    for t, lab in zip(train, y):
        (pos if lab else neg).update(tokens(t))
    gap = {w: pos[w] / n_pos - neg[w] / n_neg for w in pos if pos[w] + neg[w] >= 3}
    return [w for w, _ in sorted(gap.items(), key=lambda kv: (-kv[1], kv[0]))[:k]]


def token_rule_fit_predict(train, y, test):
    chosen = set(top_tokens(train, y))
    return [len(tokens(t) & chosen) for t in test]


def sklearn_available() -> bool:
    try:
        import sklearn  # noqa: F401
        return True
    except ImportError:
        return False


def _logreg():
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    return make_pipeline(TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, sublinear_tf=True, max_features=50000),
                         LogisticRegression(penalty="l1", solver="liblinear", C=1.0, class_weight="balanced", max_iter=1000))


def _fit(texts, y):
    with warnings.catch_warnings():   # scikit-learn 1.8 deprecates ``penalty`` for ``l1_ratio``; older versions need it
        warnings.simplefilter("ignore", category=FutureWarning)
        warnings.simplefilter("ignore", category=UserWarning)
        return _logreg().fit(texts, y)


def logreg_fit_predict(train, y, test):
    return _fit(train, y).predict_proba(test)[:, 1]


def logreg_top_features(texts, labels, n=12) -> dict:
    """The n-grams with the largest positive and negative weights on a fit to all rows: what the shortcut reads."""
    model = _fit(texts, labels)
    vec, clf = model.steps[0][1], model.steps[1][1]
    names, coef = vec.get_feature_names_out(), clf.coef_[0]
    order = sorted(range(len(coef)), key=lambda i: coef[i])
    return {"attack": [[names[i], round(float(coef[i]), 3)] for i in reversed(order[-n:]) if coef[i] > 0],
            "benign": [[names[i], round(float(coef[i]), 3)] for i in order[:n] if coef[i] < 0],
            "nonzero_weights": int(sum(1 for c in coef if c != 0))}


def user_query(record) -> str:
    users = [t.get("text", "") for t in record.state.context if t.get("role") == "user"]
    return users[-1] if users else ""


def check(records, threshold=THRESHOLD, use_sklearn=None, mask=None) -> dict:
    """Separability report for one F2 indirect set (any records; unusable rows are dropped first). ``mask``, a compiled
    regex, replaces its matches with "[address]" in every text first (a diagnostic, see EMAIL_ADDRESS)."""
    rows = usable(records)
    labels = [1 if r.expected == "yes" else 0 for r in rows]
    if len(set(labels)) < 2:
        raise ValueError("the set needs attacks and benign rows")
    texts = [r.state.text if mask is None else mask.sub("[address]", r.state.text) for r in rows]
    groups = [r.group or r.id for r in rows]
    folds = folds_of(groups)
    use_sklearn = sklearn_available() if use_sklearn is None else use_sklearn
    base = {
        "regex_contact_confirmation": (regex_scores(texts), False),
        "keyword_bag": (keyword_scores(texts), False),
        "length": (length_scores(texts), False),
        "context_query": (out_of_fold(context_fit_predict, [user_query(r) for r in rows], labels, folds), True),
        "token_count_rule": (out_of_fold(token_rule_fit_predict, texts, labels, folds), True),
    }
    if use_sklearn:
        base["char_ngram_l1_logreg"] = (out_of_fold(logreg_fit_predict, texts, labels, folds), True)
    out = {}
    for name, (scores, fitted) in base.items():
        a = auroc(scores, labels)
        out[name] = {"auroc": round(a, 4), "separability": round(max(a, 1 - a), 4), "fitted": fitted,
                     "direction": "higher_is_attack" if a >= 0.5 else "lower_is_attack"}
    worst = max(out, key=lambda k: out[k]["separability"])
    pos = [t for t, y in zip(texts, labels) if y]
    neg = [t for t, y in zip(texts, labels) if not y]
    report = {
        "n_attack": len(pos), "n_benign": len(neg), "n_groups": len(set(groups)), "folds": FOLDS,
        "benign_sources": dict(Counter(r.provenance.source for r, y in zip(rows, labels) if not y)),
        "regex_hit_rate": {"attack": round(sum(bool(REGEX.search(t)) for t in pos) / len(pos), 4),
                           "benign": round(sum(bool(REGEX.search(t)) for t in neg) / len(neg), 4)},
        "median_length": {"attack": sorted(map(len, pos))[len(pos) // 2], "benign": sorted(map(len, neg))[len(neg) // 2]},
        "baselines": out, "sklearn": use_sklearn, "threshold": threshold,
        "max_separability": out[worst]["separability"], "worst_baseline": worst,
        "fit_for_headline": all(v["separability"] <= threshold for v in out.values()),
        "token_rule_top_tokens": top_tokens(texts, labels),
    }
    if use_sklearn:
        report["logreg_top_features"] = logreg_top_features(texts, labels)
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--max-per-team", type=int, default=10, help="LLMail attacks kept per team (the loader's own cap)")
    ap.add_argument("--phases", default="phase2")
    ap.add_argument("--out", help="write the JSON report here as well as to stdout")
    args = ap.parse_args(argv)
    from .sources import f2_indirect_controls, llmail_inject
    attacks = [r for r in usable(llmail_inject.load_attacks(phases=tuple(args.phases.split(",")), max_per_team=args.max_per_team))
               if r.expected == "yes"]
    source_benign = llmail_inject.load_benign()
    controls = f2_indirect_controls.load()
    report = {
        "llmail_revision": llmail_inject.REVISION, "max_per_team": args.max_per_team, "phases": args.phases,
        "sets": {
            "llmail_attacks_vs_source_benign": check(attacks + source_benign),
            "llmail_attacks_vs_hard_controls": check(attacks + controls),
            "llmail_attacks_vs_source_benign_plus_hard_controls": check(attacks + source_benign + controls),
        },
        "diagnostics": {   # not a candidate set: what is left once every email address (so the fixed target) is masked
            "source_benign_plus_hard_controls_addresses_masked": check(attacks + source_benign + controls, mask=EMAIL_ADDRESS),
        },
    }
    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    return 0 if all(s["fit_for_headline"] for s in report["sets"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
