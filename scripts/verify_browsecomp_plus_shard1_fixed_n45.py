#!/usr/bin/env python3
"""Independently verify the fixed-N45 generation, judging and analysis surfaces."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "results/browsecomp_plus_shard1_fixed_n45"
METHODS = ("standard_rlm_qwen36", "text_decompose_qwen36", "bm25_qwen36")
N = 45


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def exact_mcnemar(left_only: int, right_only: int) -> float:
    discordant = left_only + right_only
    if not discordant:
        return 1.0
    tail = sum(math.comb(discordant, k) for k in range(min(left_only, right_only) + 1))
    return min(1.0, 2 * tail / (2**discordant))


def pair(labels: dict[tuple[int, str], bool], left: str, right: str) -> dict[str, Any]:
    left_only = sum(labels[(rank, left)] and not labels[(rank, right)] for rank in range(1, N + 1))
    right_only = sum(labels[(rank, right)] and not labels[(rank, left)] for rank in range(1, N + 1))
    return {
        "left_only": left_only,
        "right_only": right_only,
        "difference": (
            sum(labels[(rank, left)] for rank in range(1, N + 1))
            - sum(labels[(rank, right)] for rank in range(1, N + 1))
        )
        / N,
        "mcnemar_exact_two_sided_p": exact_mcnemar(left_only, right_only),
    }


def assert_close(actual: float, expected: float, label: str, tolerance: float = 1e-12) -> None:
    if abs(actual - expected) > tolerance:
        raise AssertionError(f"{label}: {actual} != {expected}")


def private_inputs_available(paths: list[Path]) -> bool:
    missing = [path for path in paths if not path.exists()]
    if not missing:
        return True
    print(
        "SKIP: full fixed-N45 endpoint verification requires restricted row-level "
        "inputs that are intentionally excluded from the anonymous release."
    )
    for path in missing:
        print(f"  withheld input: {path.relative_to(ROOT)}")
    print("Run `python3 verify_release.py` for the public release-safe verification.")
    return False


def main() -> None:
    manifest_path = DIR / "manifest_n45_restricted.json"
    compact_path = DIR / "bcp_shard1_fixed_n45_deterministic_compact_restricted.json"
    compact_integrity_path = DIR / "bcp_shard1_fixed_n45_compact_integrity_report.json"
    first_summary_path = DIR / "bcp_shard1_fixed_n45_qwen36_20260723_summary.json"
    resume_summary_path = DIR / "bcp_shard1_fixed_n45_qwen36_20260723_resume1_summary.json"
    primary_judge_path = DIR / "bcp_shard1_fixed_n45_gemma4_judge_20260723_restricted.jsonl"
    primary_summary_path = DIR / "bcp_shard1_fixed_n45_gemma4_judge_20260723_summary.json"
    primary_analysis_path = DIR / "semantic_replication_shard1_fixed_n45_primary_analysis.json"
    second_judge_path = DIR / "bcp_shard1_fixed_n45_gpt56_sol_blind_audit_20260723_restricted.jsonl"
    second_summary_path = DIR / "bcp_shard1_fixed_n45_gpt56_sol_blind_audit_20260723_summary.json"
    second_analysis_path = DIR / "bcp_shard1_fixed_n45_second_model_blind_audit_aggregate_20260723.json"
    output_path = DIR / "fixed_n45_independent_verification_20260723.json"

    if not private_inputs_available(
        [manifest_path, compact_path, primary_judge_path, second_judge_path]
    ):
        return

    manifest = load(manifest_path)
    compact = load(compact_path)
    integrity = load(compact_integrity_path)
    first_summary = load(first_summary_path)
    resume_summary = load(resume_summary_path)
    primary_rows = load_jsonl(primary_judge_path)
    primary_summary = load(primary_summary_path)
    primary_analysis = load(primary_analysis_path)
    second_rows = load_jsonl(second_judge_path)
    second_summary = load(second_summary_path)
    second_analysis = load(second_analysis_path)

    expected = {(rank, method) for rank in range(1, N + 1) for method in METHODS}
    manifest_ids = {int(row["rank"]): str(row["query_id"]) for row in manifest["rows"]}
    source = {(int(row["rank"]), str(row["method"])): row for row in compact}
    assert set(manifest_ids) == set(range(1, N + 1))
    assert len(compact) == len(source) == len(expected) == 135
    assert set(source) == expected
    assert all(str(row["query_id"]) == manifest_ids[int(row["rank"])] for row in compact)
    episode_counts = {
        str(episode): sum(int(row["execution_episode"]) == episode for row in compact)
        for episode in (1, 2)
    }
    assert episode_counts == {"1": 107, "2": 28}
    assert first_summary["completed"] + first_summary["errors"] == 107
    assert first_summary["run_incomplete"] is True
    assert resume_summary["completed"] + resume_summary["errors"] == 28
    assert resume_summary["run_incomplete"] is False
    assert not resume_summary["remaining_project_pods"]
    assert (resume_summary["cleanup"] or {}).get("http_status") in {204, 404}
    assert integrity["status"] == "PASS" and integrity["observed_cells"] == 135
    assert integrity["compact_sha256"] == sha256(compact_path)

    successful = {key for key, row in source.items() if row["ok"] and str(row["prediction"]).strip()}
    assert len(successful) == 129
    primary_success = {
        (int(row["rank"]), str(row["method"])): bool(row["judge"]["correct"])
        for row in primary_rows
    }
    second_success = {
        (int(row["rank"]), str(row["method"])): bool(row["correct"])
        for row in second_rows
    }
    assert set(primary_success) == successful and len(primary_rows) == len(primary_success)
    assert set(second_success) == successful and len(second_rows) == len(second_success)
    assert primary_summary["completed"] == 129 and primary_summary["errors"] == 0
    assert not primary_summary["remaining_project_pods"]
    assert second_summary["completed_cases"] == 129 and second_summary["failed_cases"] == 0

    primary = {key: primary_success.get(key, False) for key in expected}
    second = {key: second_success.get(key, False) for key in expected}
    primary_counts = {method: sum(primary[(rank, method)] for rank in range(1, N + 1)) for method in METHODS}
    second_counts = {method: sum(second[(rank, method)] for rank in range(1, N + 1)) for method in METHODS}
    assert primary_counts == {
        "standard_rlm_qwen36": 33,
        "text_decompose_qwen36": 29,
        "bm25_qwen36": 21,
    }
    assert second_counts == {
        "standard_rlm_qwen36": 33,
        "text_decompose_qwen36": 28,
        "bm25_qwen36": 21,
    }

    primary_pairs = {
        "rlm_vs_text": pair(primary, METHODS[0], METHODS[1]),
        "rlm_vs_bm25": pair(primary, METHODS[0], METHODS[2]),
        "text_vs_bm25": pair(primary, METHODS[1], METHODS[2]),
    }
    assert primary_pairs["rlm_vs_text"]["left_only"] == 9
    assert primary_pairs["rlm_vs_text"]["right_only"] == 5
    assert primary_pairs["rlm_vs_bm25"]["left_only"] == 15
    assert primary_pairs["rlm_vs_bm25"]["right_only"] == 3
    for key, value in primary_counts.items():
        assert primary_analysis["methods"][key]["semantic_correct"] == value
    assert_close(
        primary_analysis["paired"]["standard_rlm_qwen36__vs__text_decompose_qwen36"][
            "mcnemar_exact_two_sided_p"
        ],
        primary_pairs["rlm_vs_text"]["mcnemar_exact_two_sided_p"],
        "primary RLM-vs-text p",
    )
    assert_close(
        primary_analysis["paired"]["standard_rlm_qwen36__vs__bm25_qwen36"][
            "mcnemar_exact_two_sided_p"
        ],
        primary_pairs["rlm_vs_bm25"]["mcnemar_exact_two_sided_p"],
        "primary RLM-vs-BM25 p",
    )

    agreement = sum(primary[key] == second[key] for key in successful)
    assert agreement == 128
    assert second_analysis["successful_output_agreement"]["count"] == agreement
    assert second_analysis["successful_output_agreement"]["n"] == 129
    assert_close(
        second_analysis["successful_output_agreement"]["cohen_kappa"],
        0.9831878013814674,
        "judge kappa",
    )
    assert_close(
        primary_analysis["cost"]["generation_creation_to_cleanup_listed_rate_usd"],
        resume_summary["listed_rate_cost_estimate_usd"],
        "generation lifecycle cost",
    )
    assert_close(
        primary_analysis["cost"]["judge_creation_to_cleanup_listed_rate_usd"],
        primary_summary["listed_rate_cost_estimate_usd"],
        "judge lifecycle cost",
    )
    assert_close(
        second_analysis["cost"]["reported_per_call_sum_usd"],
        second_summary["reported_usage_cost_usd"],
        "second-judge returned cost",
    )

    forbidden = {"question", "answer", "prediction", "candidate_response", "reference_answer"}
    for release_safe in (primary_analysis, second_analysis):
        if forbidden & set(release_safe):
            raise AssertionError("release-safe analysis exposes restricted row text")

    report = {
        "status": "PASS",
        "study_id": "browsecomp_plus_shard1_fixed_n45_v1",
        "endpoint": "prospectively frozen disjoint official shard-1 fixed N=45",
        "manifest_rows": 45,
        "attempted_cells": 135,
        "execution_episode_cells": episode_counts,
        "successful_generations": 129,
        "generation_failures_scored_incorrect": 6,
        "primary_semantic_correct": primary_counts,
        "second_model_semantic_correct": second_counts,
        "primary_pairs": primary_pairs,
        "successful_output_agreement": {
            "count": agreement,
            "n": 129,
            "cohen_kappa": second_analysis["successful_output_agreement"]["cohen_kappa"],
        },
        "cost": {
            "generation_runpod_usd": resume_summary["listed_rate_cost_estimate_usd"],
            "primary_judge_runpod_usd": primary_summary["listed_rate_cost_estimate_usd"],
            "second_model_reported_openrouter_usd": second_summary["reported_usage_cost_usd"],
            "second_model_provider_delta_usd": second_summary.get("provider_total_usage_delta_usd"),
        },
        "source_hashes": {
            "manifest": sha256(manifest_path),
            "compact": sha256(compact_path),
            "compact_integrity": sha256(compact_integrity_path),
            "generation_episode_summary": sha256(first_summary_path),
            "generation_recovery_summary": sha256(resume_summary_path),
            "primary_judge": sha256(primary_judge_path),
            "primary_judge_summary": sha256(primary_summary_path),
            "primary_analysis": sha256(primary_analysis_path),
            "second_judge": sha256(second_judge_path),
            "second_judge_summary": sha256(second_summary_path),
            "second_analysis": sha256(second_analysis_path),
        },
    }
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
