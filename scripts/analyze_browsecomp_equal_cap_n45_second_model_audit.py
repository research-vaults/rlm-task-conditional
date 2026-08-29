#!/usr/bin/env python3
"""Analyze the GPT-5.6 Sol audit of the equal-cap shard-1 N45 outputs."""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "results/browsecomp_plus_shard1_equal_cap_n45"
SOURCE = BASE / "bcp_equal_cap_n45_deterministic_compact_restricted.json"
PRIMARY = BASE / "bcp_equal_cap_n45_gemma4_judge_20260726_restricted.jsonl"
SECOND = BASE / "bcp_equal_cap_n45_gpt56_sol_blind_audit_20260726_restricted.jsonl"
SECOND_SUMMARY = BASE / "bcp_equal_cap_n45_gpt56_sol_blind_audit_20260726_summary.json"
OUT_JSON = BASE / "bcp_equal_cap_n45_second_model_blind_audit_aggregate_20260726.json"
OUT_MD = BASE / "bcp_equal_cap_n45_second_model_blind_audit_aggregate_20260726.md"
DISAGREEMENTS = BASE / "bcp_equal_cap_n45_second_model_disagreements_restricted_20260726.jsonl"
METHODS = (
    "standard_rlm_qwen36",
    "iterative_search_qwen36",
    "text_decompose_qwen36",
    "bm25_qwen36",
)
LABELS = {
    "standard_rlm_qwen36": "Standard RLM",
    "iterative_search_qwen36": "Iterative search agent",
    "text_decompose_qwen36": "Text decomposition + same model",
    "bm25_qwen36": "BM25 + same model",
}
N = 45


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def exact_mcnemar(left_only: int, right_only: int) -> float:
    n = left_only + right_only
    if not n:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(min(left_only, right_only) + 1)) / (2**n)
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
    left_only = sum(a and not b for a, b in zip(left_values, right_values))
    right_only = sum(b and not a for a, b in zip(left_values, right_values))
    return {
        "left": left,
        "right": right,
        "n": N,
        "left_only": left_only,
        "right_only": right_only,
        "difference": sum(left_values) / N - sum(right_values) / N,
        "paired_bootstrap_95": bootstrap_diff(left_values, right_values, seed),
        "mcnemar_exact_two_sided_p": exact_mcnemar(left_only, right_only),
    }


def add_primary_holm(pairs: dict[str, dict[str, Any]]) -> None:
    family = ("rlm_vs_iterative", "rlm_vs_text", "rlm_vs_bm25")
    ordered = sorted((pairs[name]["mcnemar_exact_two_sided_p"], name) for name in family)
    running = 0.0
    for index, (p_value, name) in enumerate(ordered):
        running = max(running, min(1.0, (len(ordered) - index) * p_value))
        pairs[name]["holm_adjusted_p_three_rlm_contrasts"] = running


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
        raise ValueError("source coverage is not exactly 45 x 4")
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
    if set(primary_success) != successful or len(primary_success) != len(primary_rows):
        raise ValueError("primary judge does not cover all and only successful generations")
    if set(second_success) != successful or len(second_success) != len(second_rows):
        raise ValueError("second judge does not cover all and only successful generations")
    if not all(row.get("parsed") is True for row in second_rows):
        raise ValueError("second-judge parse failure")

    second_summary = json.loads(SECOND_SUMMARY.read_text(encoding="utf-8"))
    if second_summary.get("completed_cases") != len(successful) or second_summary.get("failed_cases") != 0:
        raise ValueError("second-judge run is incomplete")
    if second_summary.get("model") != "openai/gpt-5.6-sol":
        raise ValueError("unexpected second-judge model")

    primary = {key: primary_success.get(key, False) for key in expected}
    second = {key: second_success.get(key, False) for key in expected}
    confusion: Counter[tuple[bool, bool]] = Counter()
    method_confusion: dict[str, Counter[tuple[bool, bool]]] = defaultdict(Counter)
    disagreements = []
    primary_by_key = {(int(row["rank"]), str(row["method"])): row for row in primary_rows}
    second_by_key = {(int(row["rank"]), str(row["method"])): row for row in second_rows}
    for key in sorted(successful):
        pair = (primary[key], second[key])
        confusion[pair] += 1
        method_confusion[key[1]][pair] += 1
        if pair[0] != pair[1]:
            src = source[key]
            disagreements.append(
                {
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
                }
            )

    pair_specs = {
        "rlm_vs_iterative": (METHODS[0], METHODS[1]),
        "rlm_vs_text": (METHODS[0], METHODS[2]),
        "rlm_vs_bm25": (METHODS[0], METHODS[3]),
        "iterative_vs_text": (METHODS[1], METHODS[2]),
        "iterative_vs_bm25": (METHODS[1], METHODS[3]),
        "text_vs_bm25": (METHODS[2], METHODS[3]),
    }
    primary_pairs = {
        name: paired(primary, left, right, 202607231 + index)
        for index, (name, (left, right)) in enumerate(pair_specs.items())
    }
    second_pairs = {
        name: paired(second, left, right, 202607241 + index)
        for index, (name, (left, right)) in enumerate(pair_specs.items())
    }
    add_primary_holm(primary_pairs)
    add_primary_holm(second_pairs)

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

    both_no = confusion[(False, False)]
    primary_no_second_yes = confusion[(False, True)]
    primary_yes_second_no = confusion[(True, False)]
    both_yes = confusion[(True, True)]
    agreement = both_no + both_yes
    positive_denominator = 2 * both_yes + primary_no_second_yes + primary_yes_second_no
    negative_denominator = 2 * both_no + primary_no_second_yes + primary_yes_second_no
    output = {
        "study_id": "browsecomp_plus_shard1_equal_cap_n45_v1",
        "audit_contract": {
            "endpoint": "prospectively frozen outcome-unseen shard-1 ranks 46-90, fixed N=45",
            "adjudicator": "GPT-5.6 Sol, high reasoning",
            "independent_second_model": True,
            "human_validation": False,
            "coverage": "all successful generations; generation failures remain incorrect",
            "blinding": "opaque case ID, question, reference answer and one candidate response only",
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
            "positive_agreement": 2 * both_yes / positive_denominator if positive_denominator else 1.0,
            "negative_agreement": 2 * both_no / negative_denominator if negative_denominator else 1.0,
            "cohen_kappa": kappa(confusion),
            "both_incorrect": both_no,
            "primary_incorrect_second_correct": primary_no_second_yes,
            "primary_correct_second_incorrect": primary_yes_second_no,
            "both_correct": both_yes,
        },
        "methods": method_rows,
        "primary_pairwise": primary_pairs,
        "second_model_pairwise": second_pairs,
        "disagreements": {
            "count": len(disagreements),
            "restricted_ledger": str(DISAGREEMENTS.relative_to(ROOT)),
            "restricted_ledger_sha256": None,
        },
        "cost": {
            "reported_per_call_sum_usd": second_summary["reported_usage_cost_usd"],
            "provider_account_usage_delta_usd": second_summary.get("provider_total_usage_delta_usd"),
            "runpod_usd": 0.0,
        },
        "source_hashes": {
            "restricted_source_sha256": sha256(SOURCE),
            "restricted_primary_judge_sha256": sha256(PRIMARY),
            "restricted_second_judge_sha256": sha256(SECOND),
            "restricted_second_judge_summary_sha256": sha256(SECOND_SUMMARY),
        },
    }
    common_ranks = [
        rank
        for rank in range(1, N + 1)
        if all((rank, method) in successful for method in METHODS)
    ]
    output["common_completion_sensitivity"] = {
        "evidence_tier": "post_treatment_sensitivity_only",
        "n": len(common_ranks),
        "primary_correct": {
            method: sum(primary[(rank, method)] for rank in common_ranks)
            for method in METHODS
        },
        "second_model_correct": {
            method: sum(second[(rank, method)] for rank in common_ranks)
            for method in METHODS
        },
        "boundary": (
            "Conditioning on successful completion by every route is post-treatment. "
            "The all-attempted fixed-N endpoint with failures incorrect remains primary."
        ),
    }
    with DISAGREEMENTS.open("x", encoding="utf-8") as handle:
        for row in disagreements:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    DISAGREEMENTS.chmod(0o600)
    output["disagreements"]["restricted_ledger_sha256"] = sha256(DISAGREEMENTS)
    OUT_JSON.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    agreement_row = output["successful_output_agreement"]
    lines = [
        "# BrowseComp-Plus Shard-1 Equal-Cap N45 Second-Model Audit",
        "",
        f"GPT-5.6 Sol (high reasoning) adjudicated all {len(successful)} successful route generations under method and primary-label blinding. Generation failures remain incorrect. This is independent second-model sensitivity, not human validation.",
        "",
        f"- Successful-output agreement: {agreement}/{len(successful)} ({100*agreement_row['rate']:.1f}%), Cohen's kappa {agreement_row['cohen_kappa']:.3f}.",
        f"- Positive/negative agreement: {100*agreement_row['positive_agreement']:.1f}% / {100*agreement_row['negative_agreement']:.1f}%.",
        f"- Judge disagreements: {len(disagreements)}/{len(successful)}.",
        f"- Returned per-call cost sum: ${second_summary['reported_usage_cost_usd']:.6f}; account delta: ${float(second_summary.get('provider_total_usage_delta_usd') or 0):.6f}.",
        "",
        "| Method | Primary correct | Sol correct | Successful-output agreement | Primary no / Sol yes | Primary yes / Sol no |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for method in METHODS:
        row = method_rows[method]
        lines.append(
            f"| {LABELS[method]} | {row['primary_correct']}/{N} | {row['second_model_correct']}/{N} | "
            f"{row['successful_output_agreement_count']}/{row['successful_output_agreement_n']} "
            f"({100*row['successful_output_agreement_rate']:.1f}%) | "
            f"{row['primary_no_second_yes']} | {row['primary_yes_second_no']} |"
        )
    lines += [
        "",
        "## Sol-label paired sensitivity",
        "",
        "| Pair | Difference | Left/right only | Bootstrap 95% | Exact p | Holm p (three RLM contrasts) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name in pair_specs:
        row = second_pairs[name]
        lo, hi = row["paired_bootstrap_95"]
        holm = row.get("holm_adjusted_p_three_rlm_contrasts")
        lines.append(
            f"| {name.replace('_', ' ')} | {100*row['difference']:+.1f} pp | "
            f"{row['left_only']}/{row['right_only']} | {100*lo:+.1f} to {100*hi:+.1f} pp | "
            f"{row['mcnemar_exact_two_sided_p']:.4f} | {holm:.4f} |"
            if holm is not None
            else f"| {name.replace('_', ' ')} | {100*row['difference']:+.1f} pp | "
            f"{row['left_only']}/{row['right_only']} | {100*lo:+.1f} to {100*hi:+.1f} pp | "
            f"{row['mcnemar_exact_two_sided_p']:.4f} | -- |"
        )
    lines += [
        "",
        "Case text, opaque IDs, rationales and the disagreement ledger are restricted. The release surface contains only this aggregate and cryptographic hashes.",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
