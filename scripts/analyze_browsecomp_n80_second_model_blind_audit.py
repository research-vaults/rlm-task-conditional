#!/usr/bin/env python3
"""Reconcile the blinded N=80 semantic audit without releasing restricted text."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "results" / "browsecomp_plus_positive_regime"
LEDGER = BASE / "bcp_n80_privacy_safe_cell_ledger_20260720.jsonl"
MAPPING = BASE / "bcp_n80_second_model_blind_map_20260720_restricted.json"
ADJUDICATION = BASE / "bcp_n80_second_model_blind_adjudication_20260720_restricted.jsonl"
OUT_JSON = BASE / "bcp_n80_second_model_blind_audit_aggregate_20260720.json"
OUT_MD = BASE / "bcp_n80_second_model_blind_audit_aggregate_20260720.md"

METHODS = ["standard_rlm_qwen36", "text_decompose_qwen36", "bm25_qwen36"]


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact_mcnemar(left_only: int, right_only: int) -> float:
    n = left_only + right_only
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(0, min(left_only, right_only) + 1)) / (2**n)
    return min(1.0, 2.0 * tail)


def paired(labels: dict[tuple[int, str], bool], left: str, right: str) -> dict:
    left_only = right_only = both = neither = 0
    for rank in range(1, 81):
        a, b = labels[(rank, left)], labels[(rank, right)]
        if a and b:
            both += 1
        elif a:
            left_only += 1
        elif b:
            right_only += 1
        else:
            neither += 1
    return {
        "left": left,
        "right": right,
        "left_only": left_only,
        "right_only": right_only,
        "both_correct": both,
        "neither_correct": neither,
        "accuracy_difference_points": 100.0 * (left_only - right_only) / 80,
        "two_sided_exact_mcnemar_p": exact_mcnemar(left_only, right_only),
    }


def main() -> None:
    ledger = read_jsonl(LEDGER)
    mapping = json.loads(MAPPING.read_text(encoding="utf-8"))["cases"]
    adjudication_rows = read_jsonl(ADJUDICATION)
    adjudication = {row["case_id"]: row for row in adjudication_rows}

    assert len(ledger) == 240
    assert len(mapping) == 46
    assert len(adjudication_rows) == 46
    assert len(adjudication) == 46
    assert set(mapping) == set(adjudication)
    for row in adjudication_rows:
        assert isinstance(row.get("correct"), bool)
        assert row.get("confidence") in {"low", "medium", "high"}
        assert row.get("rationale_code")
        assert row.get("rationale")

    primary = {(int(row["rank"]), row["method"]): bool(row["semantic_correct"]) for row in ledger}
    sensitivity = dict(primary)
    selection_counts: Counter[str] = Counter()
    agreement_by_stratum: dict[str, Counter[str]] = defaultdict(Counter)
    method_audit: dict[str, Counter[str]] = defaultdict(Counter)
    confidence = Counter()

    for case_id, meta in mapping.items():
        second = bool(adjudication[case_id]["correct"])
        first = bool(meta["primary_semantic_correct"])
        key = (int(meta["rank"]), meta["method"])
        sensitivity[key] = second
        confidence[adjudication[case_id]["confidence"]] += 1
        method_audit[meta["method"]]["audited"] += 1
        method_audit[meta["method"]]["agreement"] += int(first == second)
        method_audit[meta["method"]]["primary_correct"] += int(first)
        method_audit[meta["method"]]["second_model_correct"] += int(second)
        for stratum in meta["selection_strata"]:
            selection_counts[stratum] += 1
            agreement_by_stratum[stratum]["audited"] += 1
            agreement_by_stratum[stratum]["agreement"] += int(first == second)

    primary_totals = {method: sum(primary[(rank, method)] for rank in range(1, 81)) for method in METHODS}
    sensitivity_totals = {method: sum(sensitivity[(rank, method)] for rank in range(1, 81)) for method in METHODS}
    all_agreement = sum(
        bool(meta["primary_semantic_correct"]) == bool(adjudication[case_id]["correct"])
        for case_id, meta in mapping.items()
    )

    pairs = {
        "rlm_vs_text": paired(sensitivity, METHODS[0], METHODS[1]),
        "rlm_vs_bm25": paired(sensitivity, METHODS[0], METHODS[2]),
        "text_vs_bm25": paired(sensitivity, METHODS[1], METHODS[2]),
    }
    ordered = sorted((row["two_sided_exact_mcnemar_p"], name) for name, row in pairs.items())
    running = 0.0
    holm = {}
    m = len(ordered)
    for index, (p_value, name) in enumerate(ordered):
        running = max(running, min(1.0, (m - index) * p_value))
        holm[name] = running
    for name, adjusted in holm.items():
        pairs[name]["holm_adjusted_p_three_route_pairs"] = adjusted

    output = {
        "study_id": "browsecomp_plus_qwen36_n80_resumed_primary",
        "audit_contract": {
            "adjudicator": "GPT-5.6 Sol, high reasoning",
            "independent_second_model": True,
            "method_blinded": True,
            "primary_label_blinded": True,
            "human_validation": False,
            "selection": "all 25 semantic-vs-containment disagreements, all 3 malformed primary-judge outputs, and a deterministic 18-case stratified agreement sample",
            "sensitivity_rule": "replace primary semantic labels only for the 46 preselected audited cells; retain primary labels for the other 194 cells",
            "release_contract": "aggregate counts and hashes only; no restricted questions, answers, predictions, case IDs, or rationales",
        },
        "n_cells": 240,
        "n_audited": 46,
        "primary_second_model_agreement": {"count": all_agreement, "n": 46, "rate": all_agreement / 46},
        "selection_counts": dict(sorted(selection_counts.items())),
        "agreement_by_selection_stratum": {
            name: {**dict(counts), "rate": counts["agreement"] / counts["audited"]}
            for name, counts in sorted(agreement_by_stratum.items())
        },
        "audit_by_method": {
            method: {**dict(counts), "agreement_rate": counts["agreement"] / counts["audited"]}
            for method, counts in sorted(method_audit.items())
        },
        "confidence_counts": dict(sorted(confidence.items())),
        "primary_semantic_correct": primary_totals,
        "second_model_sensitivity_semantic_correct": sensitivity_totals,
        "second_model_sensitivity_pairwise": pairs,
        "source_hashes": {
            "privacy_safe_ledger_sha256": sha256(LEDGER),
            "restricted_mapping_sha256": sha256(MAPPING),
            "restricted_adjudication_sha256": sha256(ADJUDICATION),
        },
    }
    OUT_JSON.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# BrowseComp-Plus N=80 Independent Second-Model Blind Audit",
        "",
        "This release-safe aggregate summarizes a GPT-5.6 Sol high-reasoning adjudication. The adjudicator saw only question, reference answer, candidate response, and opaque case ID; method and primary labels were hidden. This is independent second-model validation, not human validation.",
        "",
        f"- Audited: 46/240 cells.",
        f"- Agreement with the primary Gemma 4 judge: {all_agreement}/46 ({100 * all_agreement / 46:.1f}%).",
        f"- Primary totals (RLM/text/BM25): {primary_totals[METHODS[0]]}/{primary_totals[METHODS[1]]}/{primary_totals[METHODS[2]]}.",
        f"- Sensitivity totals (RLM/text/BM25): {sensitivity_totals[METHODS[0]]}/{sensitivity_totals[METHODS[1]]}/{sensitivity_totals[METHODS[2]]}.",
        "",
        "## Sensitivity Pairwise Results",
        "",
        "| Pair | Difference (points) | b/c | Exact p | Holm p (3 pairs) |",
        "|---|---:|---:|---:|---:|",
    ]
    for name in ["rlm_vs_text", "rlm_vs_bm25", "text_vs_bm25"]:
        row = pairs[name]
        lines.append(
            f"| {name.replace('_', ' ')} | {row['accuracy_difference_points']:.1f} | "
            f"{row['left_only']}/{row['right_only']} | {row['two_sided_exact_mcnemar_p']:.4f} | "
            f"{row['holm_adjusted_p_three_route_pairs']:.4f} |"
        )
    lines += [
        "",
        "The sensitivity analysis changes only the preselected audited cells. Because the audit deliberately oversamples disagreements and malformed outputs, its raw agreement rate is diagnostic rather than a population estimate.",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
