#!/usr/bin/env python3
"""Analyze the score-blind BrowseComp+ untouched-slice replication."""

from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "results/browsecomp_plus_positive_regime_replication"
COMPACT = DIR / "bcp_repl_n49_deterministic_compact_restricted.json"
JUDGES = DIR / "bcp_repl_gemma4_judge_n49_20260720_restricted.jsonl"
GEN_SUMMARY = DIR / "bcp_repl_qwen36_n59_20260720_summary.json"
JUDGE_SUMMARY = DIR / "bcp_repl_gemma4_judge_n49_20260720_summary.json"
ORIGINAL = ROOT / "results/browsecomp_plus_positive_regime/semantic_n80_resumed_primary_analysis.json"
OUT = DIR / "semantic_replication_n49_primary_analysis.json"
REPORT = DIR / "semantic_replication_n49_primary_analysis.md"
METHODS = ("standard_rlm_qwen36", "bm25_qwen36", "text_decompose_qwen36")
LABELS = {
    "standard_rlm_qwen36": "Standard RLM",
    "bm25_qwen36": "BM25 + same model",
    "text_decompose_qwen36": "Text decomposition + same model",
}
N = 49
RATE = 4.39


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def wilson(k: int, n: int, z: float = 1.959963984540054) -> list[float]:
    p = k / n
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [center - half, center + half]


def exact_mcnemar(b: int, c: int) -> float:
    n = b + c
    if not n:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(min(b, c) + 1)) / (2**n)
    return min(1.0, 2 * tail)


def bootstrap_diff(left: list[bool], right: list[bool], seed: int, reps: int = 50_000) -> list[float]:
    rng = random.Random(seed)
    n = len(left)
    values = []
    for _ in range(reps):
        idx = [rng.randrange(n) for _ in range(n)]
        values.append(sum(int(left[i]) - int(right[i]) for i in idx) / n)
    values.sort()
    return [values[int(0.025 * reps)], values[min(reps - 1, int(0.975 * reps))]]


def paired(left: list[bool], right: list[bool], seed: int) -> dict[str, Any]:
    b = sum(x and not y for x, y in zip(left, right))
    c = sum(y and not x for x, y in zip(left, right))
    return {
        "n": len(left),
        "left_only": b,
        "right_only": c,
        "difference": sum(left) / len(left) - sum(right) / len(right),
        "paired_bootstrap_95": bootstrap_diff(left, right, seed),
        "mcnemar_exact_two_sided_p": exact_mcnemar(b, c),
    }


def main() -> None:
    required_inputs = (COMPACT, JUDGES, GEN_SUMMARY, JUDGE_SUMMARY, ORIGINAL)
    missing_inputs = [path for path in required_inputs if not path.exists()]
    if missing_inputs:
        print("LOCAL_ONLY: required restricted inputs are intentionally withheld from the anonymous release.")
        for path in missing_inputs:
            print(f"  withheld input: {path.relative_to(ROOT)}")
        print("Run `python3 verify_release.py` for public aggregate verification.")
        raise SystemExit(2)
    compact = json.loads(COMPACT.read_text(encoding="utf-8"))
    if len(compact) != N * len(METHODS):
        raise ValueError(f"expected {N * len(METHODS)} cells, got {len(compact)}")
    source = {(int(row["rank"]), str(row["method"])): row for row in compact}
    expected = {(rank, method) for rank in range(1, N + 1) for method in METHODS}
    if set(source) != expected:
        raise ValueError("replication coverage mismatch")

    judge: dict[tuple[int, str], bool] = {}
    parsed = 0
    for line in JUDGES.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        key = (int(row["rank"]), str(row["method"]))
        if key in judge or key not in expected:
            raise ValueError(f"duplicate/unexpected judge cell {key}")
        parsed += int(bool(row["judge"].get("parsed")))
        judge[key] = bool(row["judge"].get("correct"))
    successful = {key for key, row in source.items() if row["ok"] and str(row["prediction"]).strip()}
    if set(judge) != successful:
        raise ValueError(f"judge coverage mismatch: missing={successful-set(judge)} extra={set(judge)-successful}")

    generation = json.loads(GEN_SUMMARY.read_text(encoding="utf-8"))
    judging = json.loads(JUDGE_SUMMARY.read_text(encoding="utf-8"))
    if generation["completed"] + generation["errors"] != N * len(METHODS):
        raise ValueError("generation attempted-cell count mismatch")
    if generation.get("fatal_error") != "RuntimeError: stability stop: three consecutive method errors":
        raise ValueError("unexpected generation terminal state")
    if generation.get("remaining_project_pods"):
        raise ValueError("generation pod remains active")
    if judging.get("cleanup", {}).get("http_status") != 204:
        raise ValueError("judge pod cleanup missing")

    out: dict[str, Any] = {
        "study_id": "browsecomp_plus_untouched_replication_n59_v1",
        "analysis_contract": (
            "all 59 untouched rows were frozen; score-blind execution reached the predeclared three-consecutive-error "
            "stability stop at rank 49; ranks 1-49 and every failure are retained, with no score-visible continuation"
        ),
        "planned_n": 59,
        "attempted_n": N,
        "fully_generated_ranks": 48,
        "terminal_rank": 49,
        "post_stop_score_visibility": False,
        "single_execution_episode": True,
        "semantic_judge": "google/gemma-4-26B-A4B-it",
        "judge_revision": "01e5b3ee840d3a9e0b0b493c593e85398a30ef75",
        "judge_attempted": len(judge),
        "judge_parsed": parsed,
        "judge_format_failures_scored_incorrect": len(judge) - parsed,
        "source_hashes": {
            "compact": sha256_file(COMPACT),
            "judge": sha256_file(JUDGES),
            "generation_summary": sha256_file(GEN_SUMMARY),
            "judge_summary": sha256_file(JUDGE_SUMMARY),
        },
        "methods": {},
        "paired": {},
        "cost": {
            "openrouter_usd": 0.0,
            "generation_creation_to_cleanup_listed_rate_usd": float(generation["listed_rate_cost_estimate_usd"]),
            "judge_creation_to_cleanup_listed_rate_usd": float(judging["listed_rate_cost_estimate_usd"]),
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
        k = sum(values)
        latency = [float(row["wall_seconds"]) for row in rows]
        out["methods"][method] = {
            "attempted": N,
            "completed": sum(int(row["ok"] and bool(str(row["prediction"]).strip())) for row in rows),
            "semantic_correct": k,
            "semantic_accuracy": k / N,
            "wilson_95": wilson(k, N),
            "strict_exact": sum(int(row["strict_exact"]) for row in rows),
            "normalized_contains": sum(int(row["normalized_contains"]) for row in rows),
            "wall_seconds_total": sum(latency),
            "wall_seconds_median": statistics.median(latency),
            "wall_seconds_max": max(latency),
            "active_runtime_listed_rate_usd": sum(latency) / 3600 * RATE,
            "rlm_iterations": sum(int(row["iterations"]) for row in rows),
            "rlm_code_blocks": sum(int(row["code_blocks"]) for row in rows),
        }
    out["cost"]["generation_pod_listed_rate_usd_per_hour"] = RATE
    out["cost"]["active_runtime_routes_total_usd"] = sum(
        row["active_runtime_listed_rate_usd"] for row in out["methods"].values()
    )

    for i, left in enumerate(METHODS):
        for j, right in enumerate(METHODS[i + 1 :], i + 1):
            out["paired"][f"{left}__vs__{right}"] = paired(
                correctness[left], correctness[right], 20260721 + i * 10 + j
            )

    original = json.loads(ORIGINAL.read_text(encoding="utf-8"))
    pooled: dict[str, Any] = {
        "n": 80 + N,
        "scope": "secondary synthesis; original N=80 and untouched replication N=49 retain separate provenance",
        "methods": {},
    }
    for method in METHODS:
        old_k = int(original["methods"][method]["semantic_correct"])
        new_k = int(out["methods"][method]["semantic_correct"])
        pooled["methods"][method] = {
            "semantic_correct": old_k + new_k,
            "semantic_accuracy": (old_k + new_k) / (80 + N),
            "wilson_95": wilson(old_k + new_k, 80 + N),
        }
    out["pooled_descriptive_n129"] = pooled

    OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# BrowseComp+ Untouched-Slice Replication (Attempted N=49)", "",
        "All 59 untouched rows were frozen before model output. Score-blind generation reached the predeclared stability stop at rank 49; all attempted rows and failures remain in the denominator. Semantic judging occurred only after generation closed.", "",
        "| Method | Complete | Semantic accuracy (Wilson 95%) | Median / max wall | Active-runtime cost |",
        "|---|---:|---:|---:|---:|",
    ]
    for method in METHODS:
        row = out["methods"][method]
        lo, hi = row["wilson_95"]
        lines.append(
            f"| {LABELS[method]} | {row['completed']}/{N} | {row['semantic_correct']}/{N} = {100*row['semantic_accuracy']:.1f}% ({100*lo:.1f}--{100*hi:.1f}) | "
            f"{row['wall_seconds_median']:.1f}s / {row['wall_seconds_max']:.1f}s | ${row['active_runtime_listed_rate_usd']:.3f} |"
        )
    lines += ["", "## Paired comparisons", "", "| Comparison | Difference | Left/right-only | Bootstrap 95% | McNemar p |", "|---|---:|---:|---:|---:|"]
    for key, row in out["paired"].items():
        left, right = key.split("__vs__")
        lo, hi = row["paired_bootstrap_95"]
        lines.append(
            f"| {LABELS[left]} vs {LABELS[right]} | {100*row['difference']:+.1f} pp | {row['left_only']}/{row['right_only']} | "
            f"{100*lo:+.1f} to {100*hi:+.1f} pp | {row['mcnemar_exact_two_sided_p']:.4f} |"
        )
    lines += ["", "## Cost and synthesis", "",
              f"Generation plus semantic judging cost ${out['cost']['generation_plus_judge_listed_rate_usd']:.3f} at listed rates; OpenRouter cost was $0.00.", "",
              "The separately labeled N=129 synthesis combines the original N=80 and this N=49 attempted endpoint descriptively; it does not erase the original two-episode provenance."]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
