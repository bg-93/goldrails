"""Frozen robustness diagnostics for Gold Rails.

This module deliberately sits outside the headline leaderboard.  It derives matched input variants, builds exact
question/serialization variants, and compares their ledgers with a canonical ledger.  Every variant carries the
specification hash and a review status.  Only mechanical or human-reviewed variants enter aggregate robustness
summaries; variants marked ``requires_review`` remain visible as provisional diagnostics.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import statistics
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from goldrails_dataset.records import Record, dataset_hash, read_jsonl, write_jsonl

from . import question_sets
from .score import load_ledger, score_of


SPEC_SCHEMA = "goldrails-robustness/1"
AGGREGATE_EQUIVALENCE = {"mechanical", "reviewed"}


def _canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def specification_hash(spec: dict) -> str:
    return hashlib.sha256(_canonical_json(spec).encode("utf-8")).hexdigest()


def load_spec(path) -> dict:
    spec = json.loads(Path(path).read_text(encoding="utf-8"))
    if spec.get("schema") != SPEC_SCHEMA:
        raise ValueError(f"robustness spec schema must be {SPEC_SCHEMA!r}")
    if spec.get("diagnostic_only") is not True:
        raise ValueError("robustness specification must set diagnostic_only=true")
    ids = []
    for section in ("question_variants", "input_variants"):
        values = spec.get(section) or []
        if not isinstance(values, list):
            raise ValueError(f"{section} must be a list")
        for value in values:
            if not value.get("id") or not value.get("operation"):
                raise ValueError(f"every {section} entry needs id and operation")
            if value.get("semantic_equivalence") not in ("mechanical", "reviewed", "requires_review"):
                raise ValueError(f"{value.get('id')}: invalid semantic_equivalence")
            ids.append(value["id"])
    if len(ids) != len(set(ids)):
        raise ValueError("robustness variant ids must be unique across the specification")
    return spec


def _applies(variant: dict, *, feature: str | None = None, question_set: str | None = None) -> bool:
    features = variant.get("features")
    qsets = variant.get("question_sets")
    excluded_features = variant.get("exclude_features") or []
    excluded_qsets = variant.get("exclude_question_sets") or []
    return ((not features or feature in features) and (not qsets or question_set in qsets)
            and feature not in excluded_features and question_set not in excluded_qsets)


def _variant_meta(variant: dict, spec_sha: str, **extra) -> dict:
    return {
        "variant_id": variant["id"],
        "transformation": variant["operation"],
        "transformation_version": str(variant.get("version", "1")),
        "semantic_equivalence": variant["semantic_equivalence"],
        "diagnostic_only": True,
        "spec_sha256": spec_sha,
        "description": variant.get("description"),
        **extra,
    }


def question_variants(base_qsets: dict[str, dict], spec: dict) -> dict[str, dict]:
    """Return exact diagnostic question sets derived from ``base_qsets``.

    Names use ``-rob-`` rather than the merge separator ``__``.  The metadata and any serialization change are part
    of ``runner.config_hash``, so order-only changes can never reuse a canonical ledger row.
    """
    spec_sha = specification_hash(spec)
    out = {}
    for base_name, base in base_qsets.items():
        for variant in spec.get("question_variants") or []:
            if not _applies(variant, question_set=base_name):
                continue
            qset = copy.deepcopy(base)
            operation = variant["operation"]
            changed = False
            if operation == "reverse_criteria":
                for q in qset["questions"].values():
                    criteria = q.get("criteria")
                    if isinstance(criteria, dict) and len(criteria) > 1:
                        q["criteria"] = dict(reversed(list(criteria.items())))
                        changed = True
            elif operation == "reverse_question_order":
                qset["questions"] = dict(reversed(list(qset["questions"].items())))
                if qset.get("decision"):
                    qset["decision"] = list(reversed(qset["decision"]))
                changed = len(qset["questions"]) > 1
            elif operation == "paraphrase_prefix":
                old, new = variant["old"], variant["new"]
                for q in qset["questions"].values():
                    text = q.get("instructions", "")
                    replaced = text.replace(old, new, 1)
                    if replaced != text:
                        q["instructions"] = replaced
                        changed = True
            elif operation == "input_serialization":
                qset["input_serialization"] = copy.deepcopy(variant["serialization"])
                changed = True
            else:
                raise ValueError(f"{variant['id']}: unknown question operation {operation!r}")
            if not changed:
                continue
            name = f"{base_name}-rob-{variant['id']}"
            qset["robustness"] = _variant_meta(
                variant, spec_sha, base_question_set=base_name, layer="question_or_adapter"
            )
            qset["name"] = name
            out[name] = qset
    return out


def write_question_variants(base_qsets: dict[str, dict], spec: dict, out_dir) -> dict:
    variants = question_variants(base_qsets, spec)
    destination = Path(out_dir)
    destination.mkdir(parents=True, exist_ok=True)
    for name, qset in variants.items():
        (destination / f"{name}.json").write_text(
            json.dumps(qset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    manifest = {
        "schema": SPEC_SCHEMA,
        "diagnostic_only": True,
        "spec_sha256": specification_hash(spec),
        "question_sets": [
            {"name": name, "base_question_set": qset["robustness"]["base_question_set"],
             "variant_id": qset["robustness"]["variant_id"],
             "semantic_equivalence": qset["robustness"]["semantic_equivalence"]}
            for name, qset in sorted(variants.items())
        ],
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _normalise_spans(record: Record, form: str) -> None:
    if record.spans is None:
        return
    old = record.state.text
    for span in record.spans:
        span["start"] = len(unicodedata.normalize(form, old[:span["start"]]))
        span["end"] = len(unicodedata.normalize(form, old[:span["end"]]))


def _normalise_state(record: Record, form: str) -> bool:
    before = _canonical_json(record.state.__dict__)
    _normalise_spans(record, form)
    record.state.text = unicodedata.normalize(form, record.state.text)
    record.state.source = unicodedata.normalize(form, record.state.source) if record.state.source else None
    record.state.query = unicodedata.normalize(form, record.state.query) if record.state.query else None
    for turn in record.state.context:
        turn["text"] = unicodedata.normalize(form, turn["text"])
    return before != _canonical_json(record.state.__dict__)


def _apply_input_variant(record: Record, variant: dict) -> bool:
    operation = variant["operation"]
    if operation == "unicode_normalize":
        return _normalise_state(record, variant["form"])
    if operation == "punctuation_wrapper":
        prefix, suffix = variant.get("prefix", "“"), variant.get("suffix", "”")
        record.state.text = prefix + record.state.text + suffix
        for span in record.spans or []:
            span["start"] += len(prefix)
            span["end"] += len(prefix)
        return bool(prefix or suffix)
    if operation == "irrelevant_context":
        record.state.context.append(copy.deepcopy(variant["turn"]))
        return True
    if operation == "replace_text":
        if record.spans:
            return False  # label-bearing offsets require a reviewed, task-specific remapper
        text = record.state.text
        for replacement in variant.get("replacements") or []:
            text = text.replace(replacement["from"], replacement["to"])
        changed = text != record.state.text
        record.state.text = text
        return changed
    raise ValueError(f"{variant['id']}: unknown input operation {operation!r}")


@dataclass
class DerivedBatch:
    records: list[Record]
    manifest: dict


def derive_input_records(records: Iterable[Record], spec: dict) -> DerivedBatch:
    """Build a separate, matched diagnostic dataset; canonical records are never mutated."""
    base = list(records)
    spec_sha = specification_hash(spec)
    derived = []
    counts = {}
    for variant in spec.get("input_variants") or []:
        eligible = changed = skipped_no_change = 0
        for original in base:
            if not _applies(variant, feature=original.feature):
                continue
            eligible += 1
            row = Record.from_dict(original.to_dict())
            if not _apply_input_variant(row, variant):
                skipped_no_change += 1
                continue
            changed += 1
            row.id = f"{original.id}::rob::{variant['id']}"
            row.group = original.group or original.id
            row.robustness = _variant_meta(
                variant, spec_sha, base_id=original.id, layer="input", diagnostic_only=True,
                label_preservation_basis=variant.get("label_preservation_basis", "not stated"),
            )
            row.validate()
            derived.append(row)
        counts[variant["id"]] = {
            "eligible_rows": eligible, "derived_rows": changed, "skipped_no_change": skipped_no_change,
            "semantic_equivalence": variant["semantic_equivalence"],
        }
    derived_sha = dataset_hash(derived) if derived else hashlib.sha256(b"").hexdigest()
    for row in derived:
        row.dataset = {
            "source": "goldrails-derived-robustness", "feature": row.feature, "split": row.split,
            "sha256": derived_sha, "diagnostic_only": True, "spec_sha256": spec_sha,
        }
    manifest = {
        "schema": SPEC_SCHEMA,
        "diagnostic_only": True,
        "spec_sha256": spec_sha,
        "base_dataset_sha256": dataset_hash(base),
        "derived_dataset_sha256": derived_sha,
        "canonical_dataset_unchanged": True,
        "rows": len(derived),
        "variants": counts,
    }
    return DerivedBatch(derived, manifest)


def materialize_input_records(records: Iterable[Record], spec: dict, out_path, manifest_path=None) -> dict:
    batch = derive_input_records(records, spec)
    destination = Path(out_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(batch.records, destination)
    mp = Path(manifest_path) if manifest_path else destination.with_suffix(".manifest.json")
    mp.write_text(json.dumps(batch.manifest, indent=2) + "\n", encoding="utf-8")
    return batch.manifest


def load_materialized_inputs(path, manifest_path) -> list[Record]:
    """Load a derived JSONL and attach the dataset identity required by the normal freeze/runner path."""
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if manifest.get("schema") != SPEC_SCHEMA or manifest.get("diagnostic_only") is not True:
        raise ValueError("not a Gold Rails robustness manifest")
    rows = read_jsonl(path)
    actual = dataset_hash(rows) if rows else hashlib.sha256(b"").hexdigest()
    if actual != manifest.get("derived_dataset_sha256"):
        raise ValueError("derived robustness JSONL does not match its manifest sha256")
    for row in rows:
        row.dataset = {
            "source": "goldrails-derived-robustness", "feature": row.feature, "split": row.split,
            "sha256": actual, "diagnostic_only": True, "spec_sha256": manifest["spec_sha256"],
        }
    return rows


def _read_ledger(paths) -> list[dict]:
    records = []
    for path in paths:
        records.extend(load_ledger(path))
    return records


def thresholds_from_manifest(path) -> dict[tuple[str, str, str], float]:
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    out = {}
    for arm in manifest.get("arms") or []:
        for subtask, threshold in (arm.get("thresholds") or {}).items():
            if threshold.get("threshold") is not None:
                out[(arm["system"], arm["question_set"], subtask)] = float(threshold["threshold"])
    return out


def _safe_mean(values):
    return statistics.fmean(values) if values else None


def build_report(canonical_records: list[dict], variant_records: list[dict], thresholds=None) -> dict:
    """Create paired robustness results without altering or pooling into the primary leaderboard."""
    thresholds = thresholds or {}
    canonical = {}
    ambiguous = set()
    for record in canonical_records:
        if record.get("robustness"):
            continue
        key = (record["system"], record["question_set"], record["id"])
        if key in canonical:
            ambiguous.add(key)
        canonical[key] = record

    pairs = []
    unmatched = []
    for variant in variant_records:
        robustness = variant.get("robustness")
        if not robustness:
            continue
        base_qs = robustness["base_question_set"]
        key = (variant["system"], base_qs, robustness["base_id"])
        if key in ambiguous or key not in canonical:
            unmatched.append({"system": variant["system"], "variant_id": robustness["variant_id"],
                              "base_question_set": base_qs, "base_id": robustness["base_id"],
                              "reason": "ambiguous canonical arm" if key in ambiguous else "canonical row not found"})
            continue
        base = canonical[key]
        base_score = score_of(base) if base.get("ok") else None
        variant_score = score_of(variant) if variant.get("ok") else None
        threshold = thresholds.get((base["system"], base_qs, base.get("subtask")))
        base_prediction = base_score >= threshold if base_score is not None and threshold is not None else None
        variant_prediction = variant_score >= threshold if variant_score is not None and threshold is not None else None
        expected = base.get("expected") == "yes"
        pairs.append({
            "system": base["system"], "base_question_set": base_qs,
            "variant_id": robustness["variant_id"], "semantic_equivalence": robustness["semantic_equivalence"],
            "eligible_for_aggregate": robustness["semantic_equivalence"] in AGGREGATE_EQUIVALENCE,
            "base_id": base["id"], "variant_row_id": variant["id"], "subtask": base.get("subtask"),
            "expected": base.get("expected"), "threshold": threshold,
            "canonical_score": base_score, "variant_score": variant_score,
            "score_delta": variant_score - base_score if base_score is not None and variant_score is not None else None,
            "canonical_prediction": base_prediction, "variant_prediction": variant_prediction,
            "decision_flip": base_prediction != variant_prediction if base_prediction is not None and variant_prediction is not None else None,
            "canonical_correct": base_prediction == expected if base_prediction is not None else None,
            "variant_correct": variant_prediction == expected if variant_prediction is not None else None,
        })

    grouped = defaultdict(list)
    for pair in pairs:
        grouped[(pair["system"], pair["base_question_set"], pair["variant_id"],
                 pair["semantic_equivalence"])].append(pair)
    variants = []
    for (system, base_qs, variant_id, equivalence), rows in sorted(grouped.items()):
        deltas = [r["score_delta"] for r in rows if r["score_delta"] is not None]
        decisions = [r for r in rows if r["decision_flip"] is not None]
        canonically_correct = [r for r in decisions if r["canonical_correct"]]
        canonically_wrong = [r for r in decisions if not r["canonical_correct"]]
        variants.append({
            "system": system, "base_question_set": base_qs, "variant_id": variant_id,
            "semantic_equivalence": equivalence, "eligible_for_aggregate": equivalence in AGGREGATE_EQUIVALENCE,
            "matched_pairs": len(rows), "scored_pairs": len(deltas),
            "mean_score_delta": _safe_mean(deltas),
            "mean_absolute_score_delta": _safe_mean([abs(x) for x in deltas]),
            "max_absolute_score_delta": max((abs(x) for x in deltas), default=None),
            "decision_pairs": len(decisions),
            "decision_flip_rate": _safe_mean([r["decision_flip"] for r in decisions]),
            "canonical_accuracy": _safe_mean([r["canonical_correct"] for r in decisions]),
            "variant_accuracy": _safe_mean([r["variant_correct"] for r in decisions]),
            "canonical_correct_pairs": len(canonically_correct),
            "correct_to_wrong_rate": _safe_mean([not r["variant_correct"] for r in canonically_correct]),
            "canonical_wrong_pairs": len(canonically_wrong),
            "wrong_to_correct_rate": _safe_mean([r["variant_correct"] for r in canonically_wrong]),
        })

    implementations = []
    by_impl = defaultdict(list)
    for row in variants:
        if row["eligible_for_aggregate"]:
            by_impl[(row["system"], row["base_question_set"])].append(row)
    for (system, base_qs), rows in sorted(by_impl.items()):
        with_accuracy = [r for r in rows if r["variant_accuracy"] is not None]
        worst = min(with_accuracy, key=lambda r: r["variant_accuracy"]) if with_accuracy else None
        implementations.append({
            "system": system, "base_question_set": base_qs, "eligible_variants": len(rows),
            "mean_canonical_accuracy": _safe_mean([r["canonical_accuracy"] for r in with_accuracy]),
            "mean_variant_accuracy": _safe_mean([r["variant_accuracy"] for r in with_accuracy]),
            "worst_variant_id": worst["variant_id"] if worst else None,
            "worst_variant_accuracy": worst["variant_accuracy"] if worst else None,
            "mean_decision_flip_rate": _safe_mean([
                r["decision_flip_rate"] for r in rows if r["decision_flip_rate"] is not None
            ]),
            "max_mean_absolute_score_delta": max(
                (r["mean_absolute_score_delta"] for r in rows if r["mean_absolute_score_delta"] is not None),
                default=None,
            ),
        })

    return {
        "schema": "goldrails-robustness-report/1", "diagnostic_only": True,
        "headline_scores_affected": False,
        "interpretation": (
            "Matched robustness diagnostics only. Mechanical and reviewed variants enter aggregate summaries; "
            "requires_review variants remain visible but provisional."
        ),
        "threshold_status": "frozen thresholds supplied" if thresholds else "not supplied; decision metrics omitted",
        "matched_pairs": len(pairs), "unmatched": unmatched,
        "implementations": implementations, "variants": variants, "pairs": pairs,
    }


def _fmt(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def write_report(report: dict, out_dir) -> None:
    destination = Path(out_dir)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "robustness.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    pair_fields = list(report["pairs"][0]) if report["pairs"] else ["system", "base_question_set", "variant_id"]
    with (destination / "robustness-pairs.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=pair_fields)
        writer.writeheader()
        writer.writerows(report["pairs"])
    lines = [
        "# Gold Rails robustness diagnostics", "",
        "> Diagnostic only. These results do not enter the primary suite scores or overall leaderboard.", "",
        f"Thresholds: **{report['threshold_status']}**. Matched pairs: **{report['matched_pairs']}**; "
        f"unmatched variants: **{len(report['unmatched'])}**.", "",
        "## Aggregate-eligible variants", "",
        "Only variants marked `mechanical` or `reviewed` appear here.", "",
        "| System | Base question set | Variants | Mean canonical accuracy | Mean variant accuracy | Worst variant | Worst accuracy | Mean flip rate | Max mean abs score delta |",
        "|---|---|---:|---:|---:|---|---:|---:|---:|",
    ]
    for row in report["implementations"]:
        lines.append("| " + " | ".join([
            row["system"], row["base_question_set"], str(row["eligible_variants"]),
            _fmt(row["mean_canonical_accuracy"]), _fmt(row["mean_variant_accuracy"]), _fmt(row["worst_variant_id"]),
            _fmt(row["worst_variant_accuracy"]), _fmt(row["mean_decision_flip_rate"]),
            _fmt(row["max_mean_absolute_score_delta"]),
        ]) + " |")
    lines += ["", "## Every variant", "",
              "`requires_review` rows are shown for inspection but excluded from the aggregate above.", "",
              "| System | Base question set | Variant | Equivalence | Pairs | Variant accuracy | Flip rate | Mean abs score delta |",
              "|---|---|---|---|---:|---:|---:|---:|"]
    for row in report["variants"]:
        lines.append("| " + " | ".join([
            row["system"], row["base_question_set"], row["variant_id"], row["semantic_equivalence"],
            str(row["matched_pairs"]), _fmt(row["variant_accuracy"]), _fmt(row["decision_flip_rate"]),
            _fmt(row["mean_absolute_score_delta"]),
        ]) + " |")
    if report["unmatched"]:
        lines += ["", "## Unmatched records", "", f"{len(report['unmatched'])} variant records could not be paired; see `robustness.json`."]
    (destination / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    materialize = sub.add_parser("materialize-inputs")
    materialize.add_argument("--input", required=True)
    materialize.add_argument("--spec", required=True)
    materialize.add_argument("--out", required=True)
    materialize.add_argument("--manifest")
    questions = sub.add_parser("write-question-sets")
    questions.add_argument("--base-version", default="v1")
    questions.add_argument("--question-set", action="append")
    questions.add_argument("--spec", required=True)
    questions.add_argument("--out", required=True)
    report_parser = sub.add_parser("report")
    report_parser.add_argument("--canonical-ledger", action="append", required=True)
    report_parser.add_argument("--variant-ledger", action="append", required=True)
    report_parser.add_argument("--freeze-manifest")
    report_parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.command == "materialize-inputs":
        materialize_input_records(read_jsonl(args.input), load_spec(args.spec), args.out, args.manifest)
    elif args.command == "write-question-sets":
        names = args.question_set or question_sets.available(args.base_version)
        bases = {f"{args.base_version}-{name}": question_sets.load(args.base_version, name) for name in names}
        write_question_variants(bases, load_spec(args.spec), args.out)
    else:
        thresholds = thresholds_from_manifest(args.freeze_manifest) if args.freeze_manifest else {}
        report = build_report(_read_ledger(args.canonical_ledger), _read_ledger(args.variant_ledger), thresholds)
        write_report(report, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
