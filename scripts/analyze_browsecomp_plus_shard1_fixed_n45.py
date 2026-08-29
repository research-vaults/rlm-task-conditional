#!/usr/bin/env python3
"""Analyze the prospectively frozen BrowseComp+ shard-1 fixed-N=45 endpoint."""

from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "results/browsecomp_plus_shard1_fixed_n45"
COMPACT = DIR / "bcp_shard1_fixed_n45_deterministic_compact_restricted.json"
JUDGES = DIR / "bcp_shard1_fixed_n45_gemma4_judge_20260723_restricted.jsonl"
GEN_FIRST_SUMMARY = DIR / "bcp_shard1_fixed_n45_qwen36_20260723_summary.json"
GEN_RESUME_SUMMARY = DIR / "bcp_shard1_fixed_n45_qwen36_20260723_resume1_summary.json"
JUDGE_SUMMARY = DIR / "bcp_shard1_fixed_n45_gemma4_judge_20260723_summary.json"
PRIOR = ROOT / "results/browsecomp_plus_positive_regime_replication/semantic_replication_n49_primary_analysis.json"
OUT = DIR / "semantic_replication_shard1_fixed_n45_primary_analysis.json"
REPORT = DIR / "semantic_replication_shard1_fixed_n45_primary_analysis.md"
METHODS = ("standard_rlm_qwen36", "bm25_qwen36", "text_decompose_qwen36")
LABELS = {
    "standard_rlm_qwen36": "Standard RLM",
    "bm25_qwen36": "BM25 + same model",
    "text_decompose_qwen36": "Text decomposition + same model",
}
N = 45
RATE = 4.39


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def wilson(k: int, n: int, z: float = 1.959963984540054) -> list[float]:
    p = k / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return [center - half, center + half]


def linear_percentile(values: list[float], probability: float) -> float:
    """Return the empirical percentile using linear interpolation (type 7)."""
    if not values:
        raise ValueError("percentile requires at least one value")
    if not 0.0 <= probability <= 1.0:
        raise ValueError("percentile probability must be in [0, 1]")
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] + weight * (ordered[upper] - ordered[lower])


def exact_mcnemar(left_only: int, right_only: int) -> float:
    n = left_only + right_only
    if not n:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(min(left_only, right_only) + 1)) / (2**n)
    return min(1.0, 2 * tail)


def bootstrap_diff(left: list[bool], right: list[bool], seed: int, reps: int = 50_000) -> list[float]:
    rng = random.Random(seed)
    n = len(left)
    values = []
    for _ in range(reps):
        indices = [rng.randrange(n) for _ in range(n)]
        values.append(sum(int(left[i]) - int(right[i]) for i in indices) / n)
    values.sort()
    return [values[int(0.025 * reps)], values[min(reps - 1, int(0.975 * reps))]]


def paired(left: list[bool], right: list[bool], seed: int) -> dict[str, Any]:
    left_only = sum(x and not y for x, y in zip(left, right))
    right_only = sum(y and not x for x, y in zip(left, right))
    return {
        "n": len(left),
        "left_only": left_only,
        "right_only": right_only,
        "difference": sum(left) / len(left) - sum(right) / len(right),
        "paired_bootstrap_95": bootstrap_diff(left, right, seed),
        "mcnemar_exact_two_sided_p": exact_mcnemar(left_only, right_only),
    }


def holm_two(p_values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(p_values.items(), key=lambda item: item[1])
    adjusted: dict[str, float] = {}
    running = 0.0
    m = len(ordered)
    for index, (key, p_value) in enumerate(ordered):
        running = max(running, min(1.0, (m - index) * p_value))
        adjusted[key] = running
    return adjusted


def main() -> None:
    compact = json.loads(COMPACT.read_text(encoding="utf-8"))
    expected = {(rank, method) for rank in range(1, N + 1) for method in METHODS}
    source = {(int(row["rank"]), str(row["method"])): row for row in compact}
    if len(compact) != N * len(METHODS) or set(source) != expected:
        raise ValueError("fixed-N compact endpoint coverage mismatch")

    judge: dict[tuple[int, str], bool] = {}
    parsed = 0
    for line in JUDGES.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        key = (int(row["rank"]), str(row["method"]))
        if key in judge or key not in expected:
            raise ValueError(f"duplicate or unexpected judge cell {key}")
        parsed += int(bool(row["judge"].get("parsed")))
        judge[key] = bool(row["judge"].get("correct"))
    successful = {key for key, row in source.items() if row["ok"] and str(row["prediction"]).strip()}
    if set(judge) != successful:
        raise ValueError(f"judge coverage mismatch: missing={successful-set(judge)} extra={set(judge)-successful}")

    generation_first = json.loads(GEN_FIRST_SUMMARY.read_text(encoding="utf-8"))
    generation = json.loads(GEN_RESUME_SUMMARY.read_text(encoding="utf-8"))
    judging = json.loads(JUDGE_SUMMARY.read_text(encoding="utf-8"))
    if generation_first["completed"] + generation_first["errors"] != 107:
        raise ValueError("interrupted generation episode must lock exactly 107 cells")
    if not generation_first.get("run_incomplete"):
        raise ValueError("interrupted generation episode must remain marked incomplete")
    if generation.get("run_incomplete"):
        raise ValueError("recovery episode is incomplete")
    if generation.get("first_locked_cells") != 107 or generation.get("expected_resumed_cells") != 28:
        raise ValueError("recovery summary does not bind the two-episode endpoint")
    if generation["completed"] + generation["errors"] != 28:
        raise ValueError("recovery attempted-cell count mismatch")
    if generation.get("fatal_error"):
        raise ValueError(f"unexpected generation fatal error: {generation['fatal_error']}")
    if generation.get("remaining_project_pods"):
        raise ValueError("generation pod remains active")
    if judging["completed"] + judging["errors"] != len(successful):
        raise ValueError("judge attempted-cell count mismatch")
    if judging.get("errors"):
        raise ValueError("primary semantic judge contains infrastructure errors")
    if judging.get("cleanup", {}).get("http_status") not in {204, 404}:
        raise ValueError("judge pod cleanup is not recorded")

    out: dict[str, Any] = {
        "study_id": "browsecomp_plus_shard1_fixed_n45_v1",
        "analysis_contract": (
            "prospectively frozen disjoint official shard-1 N=45; all 135 cells attempted before "
            "semantic scoring; failures remain incorrect in the fixed denominator"
        ),
        "latency_contract": (
            "wall time is summarized over all 45 attempted rows per route, including failed attempts; "
            "p95 uses the linear empirical percentile (Hyndman-Fan type 7)"
        ),
        "planned_n": N,
        "attempted_n": N,
        "fixed_endpoint_complete": True,
        "post_stop_score_visibility": False,
        "single_execution_episode": False,
        "execution_episodes": {
            "1": {"attempted_cells": 107, "status": "local_driver_interrupted"},
            "2": {"attempted_cells": 28, "status": "bounded_same-pod_recovery"},
        },
        "infrastructure_amendment": (
            "protocols/BROWSECOMP_PLUS_SHARD1_FIXED_N45_INFRASTRUCTURE_AMENDMENT_1_20260723.md"
        ),
        "semantic_judge": "google/gemma-4-26B-A4B-it",
        "judge_revision": "01e5b3ee840d3a9e0b0b493c593e85398a30ef75",
        "judge_attempted": len(judge),
        "judge_parsed": parsed,
        "judge_format_failures_scored_incorrect": len(judge) - parsed,
        "source_hashes": {
            "compact": sha256_file(COMPACT),
            "judge": sha256_file(JUDGES),
            "generation_episode_summary": sha256_file(GEN_FIRST_SUMMARY),
            "generation_recovery_summary": sha256_file(GEN_RESUME_SUMMARY),
            "judge_summary": sha256_file(JUDGE_SUMMARY),
        },
        "methods": {},
        "paired": {},
        "multiplicity": {},
        "cost": {
            "openrouter_usd": 0.0,
            "generation_creation_to_cleanup_listed_rate_usd": float(generation["listed_rate_cost_estimate_usd"]),
            "judge_creation_to_cleanup_listed_rate_usd": float(judging["listed_rate_cost_estimate_usd"]),
            "generation_pod_listed_rate_usd_per_hour": RATE,
        },
    }
    out["cost"]["generation_plus_judge_listed_rate_usd"] = (
        out["cost"]["generation_creation_to_cleanup_listed_rate_usd"]
        + out["cost"]["judge_creation_to_cleanup_listed_rate_usd"]
    )

    correctness: dict[str, list[bool]] = {}
    for method in METHODS:
        rows = [source[(rank, method)] for rank in range(1, N + 1)]
        values = [judge.get((rank, method), False) for rank in range(1, N + 1)]
        correctness[method] = values
        correct = sum(values)
        latency = [float(row["wall_seconds"]) for row in rows]
        out["methods"][method] = {
            "attempted": N,
            "completed": sum(int(row["ok"] and bool(str(row["prediction"]).strip())) for row in rows),
            "semantic_correct": correct,
            "semantic_accuracy": correct / N,
            "wilson_95": wilson(correct, N),
            "strict_exact": sum(int(row["strict_exact"]) for row in rows),
            "normalized_contains": sum(int(row["normalized_contains"]) for row in rows),
            "wall_seconds_total": sum(latency),
            "wall_seconds_median": statistics.median(latency),
            "wall_seconds_p95": linear_percentile(latency, 0.95),
            "wall_seconds_max": max(latency),
            "active_runtime_listed_rate_usd": sum(latency) / 3600 * RATE,
            "model_calls_total": sum(int(row["model_calls"]) for row in rows),
            "input_tokens_total": sum(int(row["input_tokens"]) for row in rows),
            "output_tokens_total": sum(int(row["output_tokens"]) for row in rows),
            "rlm_iterations": sum(int(row["iterations"]) for row in rows),
            "rlm_code_blocks": sum(int(row["code_blocks"]) for row in rows),
        }
    out["cost"]["active_runtime_routes_total_usd"] = sum(
        row["active_runtime_listed_rate_usd"] for row in out["methods"].values()
    )

    for i, left in enumerate(METHODS):
        for j, right in enumerate(METHODS[i + 1 :], i + 1):
            key = f"{left}__vs__{right}"
            out["paired"][key] = paired(correctness[left], correctness[right], 20260723 + i * 10 + j)
    primary_keys = (
        "standard_rlm_qwen36__vs__bm25_qwen36",
        "standard_rlm_qwen36__vs__text_decompose_qwen36",
    )
    raw_primary = {key: out["paired"][key]["mcnemar_exact_two_sided_p"] for key in primary_keys}
    out["multiplicity"] = {
        "family": list(primary_keys),
        "procedure": "Holm adjustment over the two standard-RLM primary contrasts",
        "raw_p": raw_primary,
        "holm_adjusted_p": holm_two(raw_primary),
    }

    common_ranks = [
        rank
        for rank in range(1, N + 1)
        if all((rank, method) in successful for method in METHODS)
    ]
    common_correctness = {
        method: [judge[(rank, method)] for rank in common_ranks]
        for method in METHODS
    }
    common_sensitivity: dict[str, Any] = {
        "evidence_tier": "post_treatment_sensitivity_only",
        "contract": (
            "intersection of rows with successful nonblank generation from all three routes; "
            "completion is post-treatment, so the fixed-N45 all-attempted failure-as-incorrect "
            "endpoint remains primary"
        ),
        "n": len(common_ranks),
        "methods": {},
        "paired": {},
    }
    for method in METHODS:
        correct = sum(common_correctness[method])
        common_sensitivity["methods"][method] = {
            "semantic_correct": correct,
            "semantic_accuracy": correct / len(common_ranks),
            "wilson_95": wilson(correct, len(common_ranks)),
        }
    for i, left in enumerate(METHODS):
        for j, right in enumerate(METHODS[i + 1 :], i + 1):
            key = f"{left}__vs__{right}"
            common_sensitivity["paired"][key] = paired(
                common_correctness[left],
                common_correctness[right],
                20260726 + i * 10 + j,
            )
    out["common_completion_sensitivity"] = common_sensitivity

    if PRIOR.exists():
        prior = json.loads(PRIOR.read_text(encoding="utf-8"))
        out["prior_shard0_attempted_n49_context_only"] = {
            "scope": "chronological context only; not pooled into the shard-1 primary endpoint",
            "methods": {
                method: {
                    "semantic_correct": prior["methods"][method]["semantic_correct"],
                    "attempted": prior["attempted_n"],
                    "semantic_accuracy": prior["methods"][method]["semantic_accuracy"],
                }
                for method in METHODS
            },
        }

    OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# BrowseComp-Plus Shard-1 Fixed-N45 Replication",
        "",
        "This endpoint was prospectively frozen on a disjoint official query shard. All 45 rows and all three routes were attempted before semantic scoring; generation failures remain incorrect.",
        "",
        "| Method | Complete | Semantic accuracy (Wilson 95%) | Calls | Input/output tokens | Median / p95 / max wall | Active-runtime cost |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for method in METHODS:
        row = out["methods"][method]
        lo, hi = row["wilson_95"]
        lines.append(
            f"| {LABELS[method]} | {row['completed']}/{N} | {row['semantic_correct']}/{N} = "
            f"{100*row['semantic_accuracy']:.1f}% ({100*lo:.1f}--{100*hi:.1f}) | "
            f"{row['model_calls_total']} | {row['input_tokens_total']:,}/{row['output_tokens_total']:,} | "
            f"{row['wall_seconds_median']:.1f}s / {row['wall_seconds_p95']:.1f}s / "
            f"{row['wall_seconds_max']:.1f}s | "
            f"${row['active_runtime_listed_rate_usd']:.3f} |"
        )
    lines += [
        "",
        "## Paired comparisons",
        "",
        "| Comparison | Difference | Left/right-only | Bootstrap 95% | McNemar p | Holm p (primary family) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for key, row in out["paired"].items():
        left, right = key.split("__vs__")
        lo, hi = row["paired_bootstrap_95"]
        holm = out["multiplicity"]["holm_adjusted_p"].get(key)
        lines.append(
            f"| {LABELS[left]} vs {LABELS[right]} | {100*row['difference']:+.1f} pp | "
            f"{row['left_only']}/{row['right_only']} | {100*lo:+.1f} to {100*hi:+.1f} pp | "
            f"{row['mcnemar_exact_two_sided_p']:.4f} | {holm:.4f} |"
            if holm is not None
            else f"| {LABELS[left]} vs {LABELS[right]} | {100*row['difference']:+.1f} pp | "
            f"{row['left_only']}/{row['right_only']} | {100*lo:+.1f} to {100*hi:+.1f} pp | "
            f"{row['mcnemar_exact_two_sided_p']:.4f} | -- |"
        )
    lines += [
        "",
        "## Common-completion sensitivity",
        "",
        "This post-treatment sensitivity retains only rows with successful nonblank generation from "
        "all three routes. It does not replace the fixed-N45 failure-as-incorrect primary endpoint.",
        "",
        "| Method | Semantic accuracy (Wilson 95%) |",
        "|---|---:|",
    ]
    for method in METHODS:
        row = out["common_completion_sensitivity"]["methods"][method]
        lo, hi = row["wilson_95"]
        lines.append(
            f"| {LABELS[method]} | {row['semantic_correct']}/{out['common_completion_sensitivity']['n']} = "
            f"{100*row['semantic_accuracy']:.1f}% ({100*lo:.1f}--{100*hi:.1f}) |"
        )
    lines += [
        "",
        "| Comparison | Difference | Left/right-only | Bootstrap 95% | McNemar p |",
        "|---|---:|---:|---:|---:|",
    ]
    for key, row in out["common_completion_sensitivity"]["paired"].items():
        left, right = key.split("__vs__")
        lo, hi = row["paired_bootstrap_95"]
        lines.append(
            f"| {LABELS[left]} vs {LABELS[right]} | {100*row['difference']:+.1f} pp | "
            f"{row['left_only']}/{row['right_only']} | {100*lo:+.1f} to {100*hi:+.1f} pp | "
            f"{row['mcnemar_exact_two_sided_p']:.4f} |"
        )
    lines += [
        "",
        "## Cost and provenance",
        "",
        "Latency summaries include all 45 attempted rows per route, including failed attempts. "
        "The p95 uses the linear empirical percentile (Hyndman-Fan type 7).",
        "",
        "Generation used two disclosed infrastructure episodes after a local-driver interruption: "
        "the original 107 cells were retained and only 28 missing cells were resumed on the same pod. "
        f"Generation plus semantic judging cost ${out['cost']['generation_plus_judge_listed_rate_usd']:.3f} "
        "at listed rates; OpenRouter cost was $0.00.",
        "",
        "The prior shard-0 attempted-N49 result is retained only as chronological context. It is not pooled into this primary fixed-N45 endpoint.",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
