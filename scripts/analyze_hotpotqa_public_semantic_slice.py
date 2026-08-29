#!/usr/bin/env python3
"""Analyze the public HotpotQA semantic evidence-selection diagnostic.

This analysis is not a full HotpotQA leaderboard and not an official RLM-family
comparison. It is a supplement-level public-provenance boundary diagnostic.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def exact_mcnemar_p(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    prob = sum(math.comb(n, i) * (0.5 ** n) for i in range(k + 1))
    return min(1.0, 2.0 * prob)


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    if n == 0:
        return {
            "n": 0,
            "support_exact": 0,
            "support_exact_rate": 0.0,
            "answer_correct": 0,
            "answer_accuracy": 0.0,
            "mean_evidence_f1": 0.0,
            "mean_evidence_precision": 0.0,
            "mean_evidence_recall": 0.0,
            "cost_usd": 0.0,
            "errors": 0,
        }
    return {
        "n": n,
        "support_exact": sum(1 for row in rows if row["support_exact"]),
        "support_exact_rate": sum(1 for row in rows if row["support_exact"]) / n,
        "answer_correct": sum(1 for row in rows if row["answer_correct"]),
        "answer_accuracy": sum(1 for row in rows if row["answer_correct"]) / n,
        "mean_evidence_f1": sum(float(row["evidence_f1"]) for row in rows) / n,
        "mean_evidence_precision": sum(float(row["evidence_precision"]) for row in rows) / n,
        "mean_evidence_recall": sum(float(row["evidence_recall"]) for row in rows) / n,
        "mean_selected_context_recall": sum(float(row["selected_context_recall"]) for row in rows) / n,
        "cost_usd": sum(float(row["cost_usd"]) for row in rows),
        "errors": sum(1 for row in rows if row.get("error")),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--results",
        type=Path,
        default=ROOT / "results/hotpotqa_public_semantic_n24_20260713_results.jsonl",
    )
    parser.add_argument(
        "--summary-out",
        type=Path,
        default=ROOT / "results/hotpotqa_public_semantic_n24_20260713_analysis.json",
    )
    args = parser.parse_args()

    if not args.results.exists():
        print("LOCAL_ONLY: required upstream rows are intentionally withheld from the anonymous release.")
        display = args.results.relative_to(ROOT) if args.results.is_relative_to(ROOT) else args.results
        print(f"  withheld input: {display}")
        print("Run `python3 verify_release.py` for public aggregate verification.")
        return 2
    rows = [json.loads(line) for line in args.results.read_text(encoding="utf-8").splitlines() if line.strip()]
    by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_level: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    by_type: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        by_method[row["method"]].append(row)
        by_level[str(row.get("hotpot_level"))][row["method"]].append(row)
        by_type[str(row.get("hotpot_type"))][row["method"]].append(row)

    base_method = "slm_tfidf_reranker"
    base = {row["example_id"]: row for row in by_method[base_method]}
    pairwise: dict[str, dict[str, Any]] = {}
    for method, items in sorted(by_method.items()):
        if method == base_method:
            continue
        b = c = both_right = both_wrong = 0
        f1_deltas: list[float] = []
        for row in items:
            b_row = base[row["example_id"]]
            base_right = bool(b_row["support_exact"])
            other_right = bool(row["support_exact"])
            f1_deltas.append(float(b_row["evidence_f1"]) - float(row["evidence_f1"]))
            if base_right and other_right:
                both_right += 1
            elif (not base_right) and (not other_right):
                both_wrong += 1
            elif base_right and not other_right:
                b += 1
            else:
                c += 1
        pairwise[f"{base_method}_vs_{method}"] = {
            "base": base_method,
            "other": method,
            "b_base_right_other_wrong": b,
            "c_other_right_base_wrong": c,
            "both_right": both_right,
            "both_wrong": both_wrong,
            "two_sided_exact_p": exact_mcnemar_p(b, c),
            "mean_evidence_f1_delta_base_minus_other": sum(f1_deltas) / len(f1_deltas),
        }

    retrieval_miss: dict[str, dict[str, Any]] = {}
    for method, items in sorted(by_method.items()):
        misses = Counter()
        for row in items:
            if float(row["selected_context_recall"]) < 1.0:
                misses["candidate_recall_lt_1"] += 1
            if float(row["evidence_precision"]) < 1.0:
                misses["extra_non_gold_evidence"] += 1
            if float(row["evidence_recall"]) < 1.0:
                misses["missed_gold_evidence"] += 1
        retrieval_miss[method] = dict(misses)

    result_path = args.results.resolve()
    analysis = {
        "source_results": str(result_path.relative_to(ROOT) if result_path.is_relative_to(ROOT) else result_path),
        "overall": {method: aggregate(items) for method, items in sorted(by_method.items())},
        "by_level": {
            level: {method: aggregate(items) for method, items in sorted(methods.items())}
            for level, methods in sorted(by_level.items())
        },
        "by_type": {
            typ: {method: aggregate(items) for method, items in sorted(methods.items())}
            for typ, methods in sorted(by_type.items())
        },
        "pairwise_support_exact_against_slm_tfidf_reranker": pairwise,
        "failure_counters": retrieval_miss,
        "interpretation": {
            "main_signal": (
                "This is a public natural-evidence diagnostic: HotpotQA support-fact selection. "
                "It should be used to test whether the semantic-boundary result survives outside "
                "project-generated paraphrase tasks."
            ),
            "claim_boundary": (
                "Not a full HotpotQA leaderboard and not an official RLM-family comparison. "
                "Use only as public-provenance evidence that lexical preprocessing alone is an "
                "insufficient default for semantic evidence selection."
            ),
        },
    }
    args.summary_out.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(analysis["overall"], indent=2))
    print(f"Wrote {args.summary_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
