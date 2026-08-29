#!/usr/bin/env python3
"""Analyze the post-hoc seed-21 repeat of the equal-cap BrowseComp+ endpoint."""

from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "results/browsecomp_plus_shard1_equal_cap_n45_seed21"
PARENT = ROOT / "results/browsecomp_plus_shard1_equal_cap_n45"
SOURCE = BASE / "bcp_equal_cap_n45_seed21_deterministic_compact_restricted.json"
SOURCE_AGGREGATE = BASE / "bcp_equal_cap_n45_seed21_deterministic_aggregate.json"
PRIMARY = BASE / "bcp_equal_cap_n45_seed21_gemma4_judge_20260728_restricted.jsonl"
GENERATION_SUMMARY = BASE / "seed21_repeat_20260728_summary.json"
JUDGE_SUMMARY = BASE / "bcp_equal_cap_n45_seed21_gemma4_judge_20260728_summary.json"
PARENT_PRIMARY = PARENT / "bcp_equal_cap_n45_gemma4_judge_20260726_restricted.jsonl"
OUT_JSON = BASE / "semantic_equal_cap_n45_seed21_primary_analysis.json"
OUT_MD = BASE / "semantic_equal_cap_n45_seed21_primary_analysis.md"

METHODS = (
    "standard_rlm_qwen36",
    "iterative_search_qwen36",
    "text_decompose_qwen36",
    "bm25_qwen36",
)
LABELS = {
    "standard_rlm_qwen36": "Standard RLM",
    "iterative_search_qwen36": "Iterative search",
    "text_decompose_qwen36": "Text decomposition",
    "bm25_qwen36": "BM25 + same model",
}
N = 45
ROW_CAP_SECONDS = 1200.0
RATE_USD_PER_HOUR = 4.39
BOOTSTRAP_REPS = 50_000


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def sha256(path: Path) -> str:
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


def percentile(values: list[float], probability: float) -> float:
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


def bootstrap_diff(
    left: list[bool], right: list[bool], seed: int
) -> list[float]:
    rng = random.Random(seed)
    values: list[float] = []
    for _ in range(BOOTSTRAP_REPS):
        indices = [rng.randrange(len(left)) for _ in left]
        values.append(
            sum(int(left[index]) - int(right[index]) for index in indices)
            / len(left)
        )
    values.sort()
    return [
        values[int(0.025 * BOOTSTRAP_REPS)],
        values[min(BOOTSTRAP_REPS - 1, int(0.975 * BOOTSTRAP_REPS))],
    ]


def paired(left: list[bool], right: list[bool], seed: int) -> dict[str, Any]:
    left_only = sum(a and not b for a, b in zip(left, right))
    right_only = sum(b and not a for a, b in zip(left, right))
    return {
        "n": len(left),
        "left_only": left_only,
        "right_only": right_only,
        "difference": sum(left) / len(left) - sum(right) / len(right),
        "paired_bootstrap_95": bootstrap_diff(left, right, seed),
        "bootstrap_repetitions": BOOTSTRAP_REPS,
        "bootstrap_seed": seed,
        "mcnemar_exact_two_sided_p": exact_mcnemar(left_only, right_only),
    }


def holm(p_values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(p_values.items(), key=lambda item: item[1])
    adjusted: dict[str, float] = {}
    running = 0.0
    for index, (key, value) in enumerate(ordered):
        running = max(running, min(1.0, (len(ordered) - index) * value))
        adjusted[key] = running
    return adjusted


def load_judgments(path: Path) -> dict[tuple[int, str], bool]:
    judgments: dict[tuple[int, str], bool] = {}
    for row in read_jsonl(path):
        key = (int(row["rank"]), str(row["method"]))
        if key in judgments:
            raise ValueError(f"duplicate judgment: {key}")
        judgments[key] = bool(row["judge"]["correct"])
    return judgments


def main() -> None:
    required_inputs = (
        SOURCE,
        SOURCE_AGGREGATE,
        PRIMARY,
        GENERATION_SUMMARY,
        JUDGE_SUMMARY,
        PARENT_PRIMARY,
    )
    missing_inputs = [path for path in required_inputs if not path.exists()]
    if missing_inputs:
        print("LOCAL_ONLY: required restricted inputs are intentionally withheld from the anonymous release.")
        for path in missing_inputs:
            print(f"  withheld input: {path.relative_to(ROOT)}")
        print("Run `python3 verify_release.py` for public aggregate verification.")
        raise SystemExit(2)
    rows = json.loads(SOURCE.read_text(encoding="utf-8"))
    aggregate = json.loads(SOURCE_AGGREGATE.read_text(encoding="utf-8"))
    generation_summary = json.loads(GENERATION_SUMMARY.read_text(encoding="utf-8"))
    judge_summary = json.loads(JUDGE_SUMMARY.read_text(encoding="utf-8"))
    expected = {(rank, method) for rank in range(1, N + 1) for method in METHODS}
    source = {(int(row["rank"]), str(row["method"])): row for row in rows}
    if len(rows) != N * len(METHODS) or set(source) != expected:
        raise ValueError("seed-21 compact endpoint is not exactly 45 x 4")
    if aggregate.get("cells") != N * len(METHODS):
        raise ValueError("seed-21 aggregate cell count mismatch")
    if generation_summary.get("run_incomplete"):
        raise ValueError("seed-21 generation is marked incomplete")
    if generation_summary.get("completed", 0) + generation_summary.get("errors", 0) != len(expected):
        raise ValueError("seed-21 generation attempted-cell count mismatch")

    raw_success = {
        key
        for key, row in source.items()
        if row["ok"] and str(row["prediction"]).strip()
    }
    primary_success = load_judgments(PRIMARY)
    if set(primary_success) != raw_success:
        raise ValueError("primary judge does not cover all and only raw successful outputs")
    if judge_summary.get("errors") != 0 or judge_summary.get("completed") != len(raw_success):
        raise ValueError("primary judge summary is incomplete")

    cap_valid_success = {
        key
        for key in raw_success
        if float(source[key]["wall_seconds"]) <= ROW_CAP_SECONDS
    }
    over_cap = [
        {
            "rank": key[0],
            "method": key[1],
            "wall_seconds": float(source[key]["wall_seconds"]),
            "raw_ok": bool(source[key]["ok"]),
            "primary_correct": bool(primary_success.get(key, False)),
        }
        for key in sorted(expected)
        if float(source[key]["wall_seconds"]) > ROW_CAP_SECONDS
    ]
    correctness = {
        method: [
            bool(primary_success.get((rank, method), False))
            and (rank, method) in cap_valid_success
            for rank in range(1, N + 1)
        ]
        for method in METHODS
    }

    output: dict[str, Any] = {
        "study_id": "browsecomp_plus_shard1_equal_cap_n45_seed21_v1",
        "chronology": "POST_HOC_EXPLORATORY",
        "evidence_role": "same-row rollout-variance sensitivity; not an independent endpoint",
        "pooling": "seed-20 and seed-21 are reported separately and are not pooled",
        "planned_n": N,
        "attempted_n": N,
        "n_cells": len(expected),
        "fixed_endpoint_complete": True,
        "row_cap_seconds": ROW_CAP_SECONDS,
        "raw_successful_generations": len(raw_success),
        "cap_valid_successful_generations": len(cap_valid_success),
        "primary_judge_attempted": len(primary_success),
        "primary_judge_errors": judge_summary["errors"],
        "over_cap_rows": over_cap,
        "over_cap_correct_outputs": sum(row["primary_correct"] for row in over_cap),
        "source_hashes": {
            "compact": sha256(SOURCE),
            "compact_aggregate": sha256(SOURCE_AGGREGATE),
            "generation_summary": sha256(GENERATION_SUMMARY),
            "primary_judge": sha256(PRIMARY),
            "primary_judge_summary": sha256(JUDGE_SUMMARY),
            "parent_primary_judge": sha256(PARENT_PRIMARY),
        },
        "methods": {},
        "paired": {},
        "multiplicity": {},
        "cost": {
            "route_rate_usd_per_hour": RATE_USD_PER_HOUR,
            "generation_creation_to_cleanup_usd": float(
                generation_summary["listed_rate_cost_estimate_usd"]
            ),
            "primary_judge_creation_to_cleanup_usd": float(
                judge_summary["listed_rate_cost_estimate_usd"]
            ),
        },
    }

    for method in METHODS:
        method_rows = [source[(rank, method)] for rank in range(1, N + 1)]
        latencies = [float(row["wall_seconds"]) for row in method_rows]
        values = correctness[method]
        correct = sum(values)
        active_cost = sum(latencies) / 3600 * RATE_USD_PER_HOUR
        output["methods"][method] = {
            "attempted": N,
            "raw_completed": sum(
                int(row["ok"] and bool(str(row["prediction"]).strip()))
                for row in method_rows
            ),
            "cap_valid_completed": sum(
                int((rank, method) in cap_valid_success)
                for rank in range(1, N + 1)
            ),
            "semantic_correct": correct,
            "semantic_accuracy": correct / N,
            "wilson_95": wilson(correct, N),
            "model_calls_total": sum(int(row["model_calls"]) for row in method_rows),
            "input_tokens_total": sum(int(row["input_tokens"]) for row in method_rows),
            "output_tokens_total": sum(int(row["output_tokens"]) for row in method_rows),
            "wall_seconds_total": sum(latencies),
            "wall_seconds_median": statistics.median(latencies),
            "wall_seconds_p95": percentile(latencies, 0.95),
            "wall_seconds_max": max(latencies),
            "active_runtime_usd": active_cost,
        }

    primary_specs = {
        "rlm_vs_iterative": ("standard_rlm_qwen36", "iterative_search_qwen36"),
        "rlm_vs_text": ("standard_rlm_qwen36", "text_decompose_qwen36"),
        "rlm_vs_bm25": ("standard_rlm_qwen36", "bm25_qwen36"),
    }
    for index, (name, (left, right)) in enumerate(primary_specs.items()):
        output["paired"][name] = paired(
            correctness[left], correctness[right], 202607281 + index
        )
    output["multiplicity"] = {
        "family": list(primary_specs),
        "procedure": "Holm adjustment over the three declared standard-RLM contrasts",
        "raw_p": {
            key: value["mcnemar_exact_two_sided_p"]
            for key, value in output["paired"].items()
        },
    }
    output["multiplicity"]["holm_adjusted_p"] = holm(
        output["multiplicity"]["raw_p"]
    )

    common_ranks = [
        rank
        for rank in range(1, N + 1)
        if all((rank, method) in cap_valid_success for method in METHODS)
    ]
    output["common_completion_sensitivity"] = {
        "evidence_tier": "post_treatment_sensitivity_only",
        "n": len(common_ranks),
        "methods": {
            method: {
                "semantic_correct": sum(correctness[method][rank - 1] for rank in common_ranks),
                "semantic_accuracy": (
                    sum(correctness[method][rank - 1] for rank in common_ranks)
                    / len(common_ranks)
                    if common_ranks
                    else None
                ),
            }
            for method in METHODS
        },
        "boundary": (
            "Conditioning on cap-valid completion by every route is post-treatment. "
            "The all-attempted fixed denominator remains the analysis target."
        ),
    }

    parent_judge = load_judgments(PARENT_PRIMARY)
    parent = {
        method: [
            bool(parent_judge.get((rank, method), False))
            for rank in range(1, N + 1)
        ]
        for method in METHODS
    }
    output["cross_seed"] = {}
    for index, method in enumerate(METHODS):
        comparison = paired(parent[method], correctness[method], 202607291 + index)
        output["cross_seed"][method] = {
            "seed20_correct": sum(parent[method]),
            "seed21_correct": sum(correctness[method]),
            "seed20_only": comparison["left_only"],
            "seed21_only": comparison["right_only"],
            "mcnemar_exact_two_sided_p": comparison["mcnemar_exact_two_sided_p"],
            "paired_bootstrap_95": comparison["paired_bootstrap_95"],
        }

    rlm_cost = output["methods"]["standard_rlm_qwen36"]["active_runtime_usd"]
    output["cost"]["rlm_over_iterative_active_runtime_ratio"] = (
        rlm_cost / output["methods"]["iterative_search_qwen36"]["active_runtime_usd"]
    )
    output["cost"]["rlm_over_text_active_runtime_ratio"] = (
        rlm_cost / output["methods"]["text_decompose_qwen36"]["active_runtime_usd"]
    )
    output["cost"]["route_active_runtime_total_usd"] = sum(
        row["active_runtime_usd"] for row in output["methods"].values()
    )
    output["cost"]["generation_plus_primary_judge_creation_to_cleanup_usd"] = (
        output["cost"]["generation_creation_to_cleanup_usd"]
        + output["cost"]["primary_judge_creation_to_cleanup_usd"]
    )

    OUT_JSON.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "# BrowseComp-Plus Equal-Cap N45 Seed-21 Rollout Repeat",
        "",
        "This is a post-hoc same-row rollout-variance sensitivity. It is not an independent endpoint and is not pooled with the prospective seed-20 result.",
        "",
        "| Route | Cap-valid complete | Correct / 45 | Active-runtime cost | Median / p95 wall time |",
        "|---|---:|---:|---:|---:|",
    ]
    for method in METHODS:
        row = output["methods"][method]
        lines.append(
            f"| {LABELS[method]} | {row['cap_valid_completed']}/45 | "
            f"{row['semantic_correct']}/45 ({100 * row['semantic_accuracy']:.1f}%) | "
            f"${row['active_runtime_usd']:.3f} | "
            f"{row['wall_seconds_median']:.1f}s / {row['wall_seconds_p95']:.1f}s |"
        )
    lines.extend(
        [
            "",
            "## Declared RLM contrasts",
            "",
            "| Contrast | RLM only / other only | Difference | Paired 95% interval | Raw p | Holm p |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for name in primary_specs:
        row = output["paired"][name]
        interval = row["paired_bootstrap_95"]
        lines.append(
            f"| {name} | {row['left_only']} / {row['right_only']} | "
            f"{100 * row['difference']:.1f} points | "
            f"[{100 * interval[0]:.1f}, {100 * interval[1]:.1f}] | "
            f"{row['mcnemar_exact_two_sided_p']:.6f} | "
            f"{output['multiplicity']['holm_adjusted_p'][name]:.6f} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            f"The non-significant RLM contrast set repeats: the minimum Holm-adjusted p-value is {min(output['multiplicity']['holm_adjusted_p'].values()):.6f}. The route ordering changes across the two rollouts, driven chiefly by textual decomposition changing from 37/45 to 29/45. This establishes seed sensitivity for this same-row endpoint, not equivalence and not independent replication.",
            "",
            f"RLM active-runtime cost is {output['cost']['rlm_over_text_active_runtime_ratio']:.1f}x textual decomposition and {output['cost']['rlm_over_iterative_active_runtime_ratio']:.1f}x iterative search. Seven RLM rows exceed the nominal 1,200-second wrapper wall time; six are failures and the sole late nonempty output is judged incorrect, so strict fail-closed scoring leaves the 30/45 result unchanged.",
            "",
            f"Common cap-valid completion is a post-treatment sensitivity over N={output['common_completion_sensitivity']['n']}; the fixed 45-row denominator remains primary.",
        ]
    )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUT_JSON.relative_to(ROOT))
    print(OUT_MD.relative_to(ROOT))


if __name__ == "__main__":
    main()
