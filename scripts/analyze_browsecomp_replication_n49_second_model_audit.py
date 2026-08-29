#!/usr/bin/env python3
"""Analyze the exhaustive blinded GPT-5.6 Luna audit of N=49 outputs."""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "results/browsecomp_plus_positive_regime_replication"
SOURCE = BASE / "bcp_repl_n49_deterministic_compact_restricted.json"
PRIMARY = BASE / "bcp_repl_gemma4_judge_n49_20260720_restricted.jsonl"
SECOND = BASE / "bcp_repl_gpt56_luna_blind_audit_n49_restricted.jsonl"
SECOND_SUMMARY = BASE / "bcp_repl_gpt56_luna_blind_audit_n49_summary.json"
OUT_JSON = BASE / "bcp_repl_n49_second_model_blind_audit_aggregate_20260721.json"
OUT_MD = BASE / "bcp_repl_n49_second_model_blind_audit_aggregate_20260721.md"
DISAGREEMENTS = BASE / "bcp_repl_n49_second_model_disagreements_restricted_20260721.jsonl"

METHODS = ("standard_rlm_qwen36", "text_decompose_qwen36", "bm25_qwen36")
LABELS = {
    "standard_rlm_qwen36": "Standard RLM",
    "text_decompose_qwen36": "Text decomposition + same model",
    "bm25_qwen36": "BM25 + same model",
}
N = 49


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact_mcnemar(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(min(b, c) + 1)) / (2**n)
    return min(1.0, 2.0 * tail)


def bootstrap_diff(left: list[bool], right: list[bool], seed: int, reps: int = 50_000) -> list[float]:
    rng = random.Random(seed)
    n = len(left)
    values = []
    for _ in range(reps):
        indices = [rng.randrange(n) for _ in range(n)]
        values.append(sum(int(left[i]) - int(right[i]) for i in indices) / n)
    values.sort()
    return [values[int(0.025 * reps)], values[min(reps - 1, int(0.975 * reps))]]


def paired(labels: dict[tuple[int, str], bool], left: str, right: str, seed: int) -> dict[str, Any]:
    left_values = [labels[(rank, left)] for rank in range(1, N + 1)]
    right_values = [labels[(rank, right)] for rank in range(1, N + 1)]
    b = sum(a and not z for a, z in zip(left_values, right_values))
    c = sum(z and not a for a, z in zip(left_values, right_values))
    return {
        "left": left,
        "right": right,
        "n": N,
        "left_only": b,
        "right_only": c,
        "difference": sum(left_values) / N - sum(right_values) / N,
        "paired_bootstrap_95": bootstrap_diff(left_values, right_values, seed),
        "mcnemar_exact_two_sided_p": exact_mcnemar(b, c),
    }


def add_holm(pairs: dict[str, dict[str, Any]]) -> None:
    ordered = sorted((row["mcnemar_exact_two_sided_p"], name) for name, row in pairs.items())
    running = 0.0
    m = len(ordered)
    for index, (p_value, name) in enumerate(ordered):
        running = max(running, min(1.0, (m - index) * p_value))
        pairs[name]["holm_adjusted_p_three_route_pairs"] = running


def kappa(confusion: Counter[tuple[bool, bool]]) -> float:
    n = sum(confusion.values())
    observed = (confusion[(False, False)] + confusion[(True, True)]) / n
    first_true = (confusion[(True, False)] + confusion[(True, True)]) / n
    second_true = (confusion[(False, True)] + confusion[(True, True)]) / n
    expected = first_true * second_true + (1 - first_true) * (1 - second_true)
    return (observed - expected) / (1 - expected) if expected < 1 else 1.0


def main() -> None:
    source_rows = json.loads(SOURCE.read_text(encoding="utf-8"))
    source = {(int(row["rank"]), str(row["method"])): row for row in source_rows}
    expected = {(rank, method) for rank in range(1, N + 1) for method in METHODS}
    if len(source_rows) != N * len(METHODS) or set(source) != expected:
        raise ValueError("source coverage is not exactly 49 x 3")
    successful = {key for key, row in source.items() if row["ok"] and str(row["prediction"]).strip()}

    primary_rows = read_jsonl(PRIMARY)
    primary_success = {
        (int(row["rank"]), str(row["method"])): bool(row["judge"]["correct"])
        for row in primary_rows
    }
    second_rows = read_jsonl(SECOND)
    second_success = {
        (int(row["rank"]), str(row["method"])): bool(row["correct"])
        for row in second_rows
    }
    if len(primary_rows) != 137 or len(primary_success) != 137 or set(primary_success) != successful:
        raise ValueError("primary judge does not cover all and only 137 successful generations")
    if len(second_rows) != 137 or len(second_success) != 137 or set(second_success) != successful:
        raise ValueError("second judge does not cover all and only 137 successful generations")
    if not all(row.get("parsed") is True for row in second_rows):
        raise ValueError("second-judge parse failure")

    second_summary = json.loads(SECOND_SUMMARY.read_text(encoding="utf-8"))
    if second_summary.get("completed_cases") != 137 or second_summary.get("failed_cases") != 0:
        raise ValueError("second-judge run is incomplete")
    if second_summary.get("model") != "openai/gpt-5.6-luna":
        raise ValueError("unexpected second-judge model")

    primary = {key: primary_success.get(key, False) for key in expected}
    second = {key: second_success.get(key, False) for key in expected}
    confusion: Counter[tuple[bool, bool]] = Counter()
    method_confusion: dict[str, Counter[tuple[bool, bool]]] = defaultdict(Counter)
    disagreement_rows = []
    second_by_key = {(int(row["rank"]), str(row["method"])): row for row in second_rows}
    primary_by_key = {(int(row["rank"]), str(row["method"])): row for row in primary_rows}
    for key in sorted(successful):
        pair = (primary[key], second[key])
        confusion[pair] += 1
        method_confusion[key[1]][pair] += 1
        if pair[0] != pair[1]:
            src = source[key]
            disagreement_rows.append({
                "rank": key[0],
                "method": key[1],
                "question": src["question"],
                "reference_answer": src["answer"],
                "candidate_response": src["prediction"],
                "primary_correct": pair[0],
                "primary_rationale": primary_by_key[key]["judge"]["response"],
                "second_correct": pair[1],
                "second_rationale": second_by_key[key]["rationale"],
                "case_id": second_by_key[key]["case_id"],
            })

    primary_pairs = {
        "rlm_vs_text": paired(primary, METHODS[0], METHODS[1], 202607211),
        "rlm_vs_bm25": paired(primary, METHODS[0], METHODS[2], 202607212),
        "text_vs_bm25": paired(primary, METHODS[1], METHODS[2], 202607213),
    }
    second_pairs = {
        "rlm_vs_text": paired(second, METHODS[0], METHODS[1], 202607221),
        "rlm_vs_bm25": paired(second, METHODS[0], METHODS[2], 202607222),
        "text_vs_bm25": paired(second, METHODS[1], METHODS[2], 202607223),
    }
    add_holm(primary_pairs)
    add_holm(second_pairs)

    method_rows = {}
    for method in METHODS:
        successful_method = sum(key[1] == method for key in successful)
        agreement = sum(count for pair, count in method_confusion[method].items() if pair[0] == pair[1])
        method_rows[method] = {
            "attempted": N,
            "successful_generations": successful_method,
            "primary_correct": sum(primary[(rank, method)] for rank in range(1, N + 1)),
            "second_model_correct": sum(second[(rank, method)] for rank in range(1, N + 1)),
            "successful_output_agreement_count": agreement,
            "successful_output_agreement_n": successful_method,
            "successful_output_agreement_rate": agreement / successful_method,
            "primary_no_second_yes": method_confusion[method][(False, True)],
            "primary_yes_second_no": method_confusion[method][(True, False)],
        }

    agreement = confusion[(False, False)] + confusion[(True, True)]
    output = {
        "study_id": "browsecomp_plus_untouched_replication_n59_v1",
        "audit_contract": {
            "endpoint": "score-blind stability stop at attempted N=49",
            "adjudicator": "GPT-5.6 Luna, high reasoning",
            "independent_second_model": True,
            "human_validation": False,
            "coverage": "all 137 successful generations; ten generation failures remain incorrect",
            "blinding": "opaque case ID, question, reference answer, and one candidate response only",
            "release_contract": "aggregate counts and hashes only; no restricted case text, IDs, rationales, or route traces",
        },
        "attempted_n": N,
        "n_cells": N * len(METHODS),
        "successful_generations": len(successful),
        "generation_failures_scored_incorrect": len(expected - successful),
        "second_model_parsed": len(second_rows),
        "successful_output_agreement": {
            "count": agreement,
            "n": len(successful),
            "rate": agreement / len(successful),
            "cohen_kappa": kappa(confusion),
            "both_incorrect": confusion[(False, False)],
            "primary_incorrect_second_correct": confusion[(False, True)],
            "primary_correct_second_incorrect": confusion[(True, False)],
            "both_correct": confusion[(True, True)],
        },
        "methods": method_rows,
        "primary_pairwise": primary_pairs,
        "second_model_pairwise": second_pairs,
        "disagreements": {
            "count": len(disagreement_rows),
            "restricted_ledger": str(DISAGREEMENTS.relative_to(ROOT)),
            "restricted_ledger_sha256": None,
        },
        "cost": {
            "reported_per_call_sum_usd": second_summary["reported_usage_cost_usd"],
            "provider_account_usage_delta_usd": second_summary["provider_total_usage_delta_usd"],
            "runpod_usd": 0.0,
        },
        "source_hashes": {
            "restricted_source_sha256": sha256(SOURCE),
            "restricted_primary_judge_sha256": sha256(PRIMARY),
            "restricted_second_judge_sha256": sha256(SECOND),
            "restricted_second_judge_summary_sha256": sha256(SECOND_SUMMARY),
        },
    }

    with DISAGREEMENTS.open("x", encoding="utf-8") as handle:
        for row in disagreement_rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    DISAGREEMENTS.chmod(0o600)
    output["disagreements"]["restricted_ledger_sha256"] = sha256(DISAGREEMENTS)
    OUT_JSON.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# BrowseComp+ N=49 Exhaustive Independent Second-Model Audit",
        "",
        "GPT-5.6 Luna (high reasoning) adjudicated all 137 successful route generations under method and primary-label blinding. The ten generation failures remain incorrect. This is independent second-model sensitivity, not human validation.",
        "",
        f"- Successful-output agreement: {agreement}/137 ({100 * agreement / 137:.1f}%), Cohen's kappa {output['successful_output_agreement']['cohen_kappa']:.3f}.",
        f"- Judge disagreements: {len(disagreement_rows)}/137.",
        f"- Returned per-call cost sum: ${second_summary['reported_usage_cost_usd']:.6f}; concurrent provider-account delta: ${second_summary['provider_total_usage_delta_usd']:.6f}.",
        "",
        "| Method | Primary correct | Luna correct | Successful-output agreement | Primary no / Luna yes | Primary yes / Luna no |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for method in METHODS:
        row = method_rows[method]
        lines.append(
            f"| {LABELS[method]} | {row['primary_correct']}/49 | {row['second_model_correct']}/49 | "
            f"{row['successful_output_agreement_count']}/{row['successful_output_agreement_n']} "
            f"({100 * row['successful_output_agreement_rate']:.1f}%) | {row['primary_no_second_yes']} | {row['primary_yes_second_no']} |"
        )
    lines += [
        "",
        "## Luna-label paired sensitivity",
        "",
        "| Pair | Difference | Left/right only | Bootstrap 95% | Exact p | Holm p |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name in ("rlm_vs_text", "rlm_vs_bm25", "text_vs_bm25"):
        row = second_pairs[name]
        lo, hi = row["paired_bootstrap_95"]
        lines.append(
            f"| {name.replace('_', ' ')} | {100 * row['difference']:+.1f} pp | {row['left_only']}/{row['right_only']} | "
            f"{100 * lo:+.1f} to {100 * hi:+.1f} pp | {row['mcnemar_exact_two_sided_p']:.4f} | "
            f"{row['holm_adjusted_p_three_route_pairs']:.4f} |"
        )
    lines += [
        "",
        "Case text, opaque IDs, rationales, and the disagreement ledger are restricted. The release surface contains only this aggregate and cryptographic hashes.",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
