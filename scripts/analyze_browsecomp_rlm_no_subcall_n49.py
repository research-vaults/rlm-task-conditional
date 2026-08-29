#!/usr/bin/env python3
"""Analyze the matched-row BrowseComp RLM no-subcall component ablation."""

from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "results/browsecomp_plus_positive_regime_replication/no_subcall_ablation"
COMPACT = DIR / "bcp_n49_rlm_no_subcall_compact_restricted.json"
JUDGE = DIR / "bcp_n49_rlm_no_subcall_gemma4_openrouter_pair_judge_20260722_restricted.jsonl"
GEN_SUMMARY = DIR / "bcp_n49_rlm_no_subcall_qwen36_20260722_summary.json"
JUDGE_SUMMARY = DIR / "bcp_n49_rlm_no_subcall_gemma4_openrouter_pair_judge_20260722_summary.json"
STANDARD_COMPACT = ROOT / "results/browsecomp_plus_positive_regime_replication/bcp_repl_n49_deterministic_compact_restricted.json"
PROTOCOL = ROOT / "protocols/BROWSECOMP_PLUS_N49_RLM_NO_SUBCALL_ABLATION_20260722.md"
OUT = DIR / "bcp_n49_rlm_no_subcall_primary_analysis.json"
REPORT = DIR / "bcp_n49_rlm_no_subcall_primary_analysis.md"
NO_SUB = "rlm_no_subcall_qwen36"
STANDARD = "standard_rlm_qwen36"
N = 49
RATE = 4.39


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def wilson(k: int, n: int, z: float = 1.959963984540054) -> list[float]:
    p = k / n
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [center - half, center + half]


def exact_mcnemar(b: int, c: int) -> float:
    total = b + c
    if not total:
        return 1.0
    tail = sum(math.comb(total, index) for index in range(min(b, c) + 1)) / (2**total)
    return min(1.0, 2 * tail)


def bootstrap_diff(left: list[bool], right: list[bool], seed: int, reps: int = 50_000) -> list[float]:
    rng = random.Random(seed)
    values = []
    for _ in range(reps):
        sample = [rng.randrange(len(left)) for _ in left]
        values.append(sum(int(left[i]) - int(right[i]) for i in sample) / len(left))
    values.sort()
    return [values[int(0.025 * reps)], values[min(reps - 1, int(0.975 * reps))]]


def load_judgments(path: Path, method: str) -> dict[int, bool]:
    out: dict[int, bool] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row["method"] != method:
            continue
        rank = int(row["rank"])
        if rank in out:
            raise RuntimeError(f"duplicate judgment at rank {rank}")
        out[rank] = bool(row["judge"].get("parsed") and row["judge"].get("correct"))
    return out


def main() -> None:
    required_inputs = (
        COMPACT,
        JUDGE,
        GEN_SUMMARY,
        JUDGE_SUMMARY,
        STANDARD_COMPACT,
        PROTOCOL,
    )
    missing_inputs = [path for path in required_inputs if not path.exists()]
    if missing_inputs:
        print("LOCAL_ONLY: required restricted inputs are intentionally withheld from the anonymous release.")
        for path in missing_inputs:
            print(f"  withheld input: {path.relative_to(ROOT)}")
        print("Run `python3 verify_release.py` for public aggregate verification.")
        raise SystemExit(2)
    compact = json.loads(COMPACT.read_text(encoding="utf-8"))
    if len(compact) != N or [int(row["rank"]) for row in compact] != list(range(1, N + 1)):
        raise RuntimeError("no-subcall compact coverage mismatch")
    standard_compact = [
        row for row in json.loads(STANDARD_COMPACT.read_text(encoding="utf-8"))
        if row["method"] == STANDARD
    ]
    if len(standard_compact) != N:
        raise RuntimeError("standard RLM compact coverage mismatch")

    no_sub_judge = load_judgments(JUDGE, NO_SUB)
    standard_judge = load_judgments(JUDGE, STANDARD)
    expected_no_sub = {
        int(row["rank"]) for row in compact if row["ok"] and str(row["prediction"]).strip()
    }
    if set(no_sub_judge) != expected_no_sub:
        raise RuntimeError(f"no-subcall judge coverage mismatch: {set(no_sub_judge) ^ expected_no_sub}")

    no_sub = [no_sub_judge.get(rank, False) for rank in range(1, N + 1)]
    standard = [standard_judge.get(rank, False) for rank in range(1, N + 1)]
    no_sub_completed = [rank in expected_no_sub for rank in range(1, N + 1)]
    expected_standard = {
        int(row["rank"]) for row in standard_compact if row["ok"] and str(row["prediction"]).strip()
    }
    standard_completed = [rank in expected_standard for rank in range(1, N + 1)]
    common_completed_ranks = sorted(expected_no_sub & expected_standard)
    b = sum(left and not right for left, right in zip(no_sub, standard))
    c = sum(right and not left for left, right in zip(no_sub, standard))
    attempted_n = 30
    no_sub_attempted = no_sub[:attempted_n]
    standard_attempted = standard[:attempted_n]
    attempted_b = sum(left and not right for left, right in zip(no_sub_attempted, standard_attempted))
    attempted_c = sum(right and not left for left, right in zip(no_sub_attempted, standard_attempted))
    generation = json.loads(GEN_SUMMARY.read_text(encoding="utf-8"))
    judging = json.loads(JUDGE_SUMMARY.read_text(encoding="utf-8"))
    if generation.get("remaining_project_pods") or judging.get("remaining_project_pods"):
        raise RuntimeError("provider resource remains active")

    latencies = [float(row["wall_seconds"]) for row in compact]
    standard_latencies = [float(row["wall_seconds"]) for row in standard_compact]
    k_no_sub, k_standard = sum(no_sub), sum(standard)
    analysis: dict[str, Any] = {
        "study_id": "browsecomp_plus_n49_rlm_no_subcall_ablation_v1",
        "design": "retrospective matched-row matched-cap component ablation",
        "nonclaims": [
            "not official SRLM",
            "not a prospective dataset replication",
            "not exact realized-dollar matching",
            "does not by itself identify recursion-only causality",
        ],
        "n": N,
        "attempted_prefix": {
            "n": attempted_n,
            "no_subcall_correct": sum(no_sub_attempted),
            "standard_correct": sum(standard_attempted),
            "difference": sum(no_sub_attempted) / attempted_n - sum(standard_attempted) / attempted_n,
            "no_subcall_only": attempted_b,
            "standard_only": attempted_c,
            "paired_bootstrap_95": bootstrap_diff(no_sub_attempted, standard_attempted, 20260724),
            "mcnemar_exact_two_sided_p": exact_mcnemar(attempted_b, attempted_c),
            "interpretation": "mechanism sensitivity before the stability stop; descriptive and retrospective",
        },
        "methods": {
            NO_SUB: {
                "semantic_correct": k_no_sub,
                "accuracy": k_no_sub / N,
                "wilson_95": wilson(k_no_sub, N),
                "completed": len(expected_no_sub),
                "accuracy_given_completion": k_no_sub / len(expected_no_sub),
                "wall_seconds_total": sum(latencies),
                "wall_seconds_median": statistics.median(latencies),
                "wall_seconds_max": max(latencies),
                "active_runtime_listed_rate_usd": sum(latencies) / 3600 * RATE,
                "root_iterations": sum(int(row["iterations"]) for row in compact),
                "code_blocks": sum(int(row["code_blocks"]) for row in compact),
                "disabled_subcall_attempts": sum(int(row["disabled_subcall_attempts"]) for row in compact),
            },
            STANDARD: {
                "semantic_correct": k_standard,
                "accuracy": k_standard / N,
                "wilson_95": wilson(k_standard, N),
                "completed": sum(bool(row["ok"] and str(row["prediction"]).strip()) for row in standard_compact),
                "accuracy_given_completion": k_standard / len(expected_standard),
                "wall_seconds_total": sum(standard_latencies),
                "wall_seconds_median": statistics.median(standard_latencies),
                "wall_seconds_max": max(standard_latencies),
                "active_runtime_listed_rate_usd": sum(standard_latencies) / 3600 * RATE,
            },
        },
        "paired": {
            "no_subcall_minus_standard": {
                "difference": k_no_sub / N - k_standard / N,
                "no_subcall_only": b,
                "standard_only": c,
                "paired_bootstrap_95": bootstrap_diff(no_sub, standard, 20260722),
                "mcnemar_exact_two_sided_p": exact_mcnemar(b, c),
            },
            "completion_no_subcall_minus_standard": {
                "difference": sum(no_sub_completed) / N - sum(standard_completed) / N,
                "no_subcall_only": sum(left and not right for left, right in zip(no_sub_completed, standard_completed)),
                "standard_only": sum(right and not left for left, right in zip(no_sub_completed, standard_completed)),
                "paired_bootstrap_95": bootstrap_diff(no_sub_completed, standard_completed, 20260723),
                "mcnemar_exact_two_sided_p": exact_mcnemar(
                    sum(left and not right for left, right in zip(no_sub_completed, standard_completed)),
                    sum(right and not left for left, right in zip(no_sub_completed, standard_completed)),
                ),
            },
            "common_completed_correctness": {
                "n": len(common_completed_ranks),
                "no_subcall_correct": sum(no_sub_judge[rank] for rank in common_completed_ranks),
                "standard_correct": sum(standard_judge[rank] for rank in common_completed_ranks),
                "no_subcall_accuracy": sum(no_sub_judge[rank] for rank in common_completed_ranks) / len(common_completed_ranks),
                "standard_accuracy": sum(standard_judge[rank] for rank in common_completed_ranks) / len(common_completed_ranks),
            },
        },
        "cost": {
            "generation_creation_to_cleanup_listed_rate_usd": generation["listed_rate_cost_estimate_usd"],
            "judge_openrouter_provider_account_delta_usd": judging["provider_account_delta_usd"],
            "openrouter_usd": judging["provider_account_delta_usd"],
        },
        "source_hashes": {
            "protocol": sha256_file(PROTOCOL),
            "compact": sha256_file(COMPACT),
            "judge": sha256_file(JUDGE),
            "generation_summary": sha256_file(GEN_SUMMARY),
            "judge_summary": sha256_file(JUDGE_SUMMARY),
            "standard_compact": sha256_file(STANDARD_COMPACT),
            "paired_arm_judge": sha256_file(JUDGE),
        },
    }
    OUT.write_text(json.dumps(analysis, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    diff = analysis["paired"]["no_subcall_minus_standard"]
    no_row, std_row = analysis["methods"][NO_SUB], analysis["methods"][STANDARD]
    lo, hi = diff["paired_bootstrap_95"]
    REPORT.write_text(
        "\n".join([
            "# BrowseComp-Plus N=49 RLM No-Subcall Ablation",
            "",
            "Retrospective matched-row, matched-cap component ablation. This is not official SRLM or exact realized-dollar matching.",
            "",
            "| Route | Complete | Semantic accuracy | Wilson 95% | Median / max wall | Active-runtime cost |",
            "|---|---:|---:|---:|---:|---:|",
            f"| RLM no subcalls | {no_row['completed']}/49 | {k_no_sub}/49 = {100*k_no_sub/N:.1f}% ({100*no_row['accuracy_given_completion']:.1f}% completed-row) | {100*no_row['wilson_95'][0]:.1f}--{100*no_row['wilson_95'][1]:.1f}% | {no_row['wall_seconds_median']:.1f}s / {no_row['wall_seconds_max']:.1f}s | ${no_row['active_runtime_listed_rate_usd']:.3f} |",
            f"| Standard RLM | {std_row['completed']}/49 | {k_standard}/49 = {100*k_standard/N:.1f}% ({100*std_row['accuracy_given_completion']:.1f}% completed-row) | {100*std_row['wilson_95'][0]:.1f}--{100*std_row['wilson_95'][1]:.1f}% | {std_row['wall_seconds_median']:.1f}s / {std_row['wall_seconds_max']:.1f}s | ${std_row['active_runtime_listed_rate_usd']:.3f} |",
            "",
            f"Predeclared N=49 failure-policy endpoint, no-subcall minus standard: {100*diff['difference']:+.1f} points; paired bootstrap 95% {100*lo:+.1f} to {100*hi:+.1f}; discordances {b}/{c}; exact McNemar p={diff['mcnemar_exact_two_sided_p']:.4f}. This endpoint counts ranks 31--49 incorrect after the stability stop and is a conservative route bound, not a clean mechanism estimate.",
            "",
            f"On the actually attempted N=30 prefix, no-subcall is {analysis['attempted_prefix']['no_subcall_correct']}/30 and standard RLM is {analysis['attempted_prefix']['standard_correct']}/30: {100*analysis['attempted_prefix']['difference']:+.1f} points, paired bootstrap 95% {100*analysis['attempted_prefix']['paired_bootstrap_95'][0]:+.1f} to {100*analysis['attempted_prefix']['paired_bootstrap_95'][1]:+.1f}, discordances {attempted_b}/{attempted_c}, exact McNemar p={analysis['attempted_prefix']['mcnemar_exact_two_sided_p']:.4f}.",
            "",
            f"Among the {len(common_completed_ranks)} rows completed by both routes, no-subcall is {analysis['paired']['common_completed_correctness']['no_subcall_correct']}/{len(common_completed_ranks)} and standard RLM is {analysis['paired']['common_completed_correctness']['standard_correct']}/{len(common_completed_ranks)}. The fixed-denominator difference is therefore primarily a completion/reach effect under the matched cap.",
            "",
            f"The no-subcall arm logged {no_row['disabled_subcall_attempts']} attempted disabled calls across {no_row['root_iterations']} root iterations. Failures remain incorrect.",
        ]) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(analysis, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
