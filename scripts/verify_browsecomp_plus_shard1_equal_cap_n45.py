#!/usr/bin/env python3
"""Independently verify the prospective equal-cap BrowseComp-Plus endpoint."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "results/browsecomp_plus_shard1_equal_cap_n45"
METHODS = (
    "standard_rlm_qwen36",
    "iterative_search_qwen36",
    "text_decompose_qwen36",
    "bm25_qwen36",
)
N = 45


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
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


def exact_mcnemar(left_only: int, right_only: int) -> float:
    discordant = left_only + right_only
    if not discordant:
        return 1.0
    tail = sum(
        math.comb(discordant, k)
        for k in range(min(left_only, right_only) + 1)
    )
    return min(1.0, 2 * tail / (2**discordant))


def pair(
    labels: dict[tuple[int, str], bool], left: str, right: str
) -> dict[str, Any]:
    left_only = sum(
        labels[(rank, left)] and not labels[(rank, right)]
        for rank in range(1, N + 1)
    )
    right_only = sum(
        labels[(rank, right)] and not labels[(rank, left)]
        for rank in range(1, N + 1)
    )
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


def assert_close(
    actual: float, expected: float, label: str, tolerance: float = 1e-12
) -> None:
    if abs(actual - expected) > tolerance:
        raise AssertionError(f"{label}: {actual} != {expected}")


def private_inputs_available(paths: dict[str, Path]) -> bool:
    required = ("manifest", "compact", "primary_judge", "second_judge")
    missing = [paths[name] for name in required if not paths[name].exists()]
    if not missing:
        return True
    print(
        "SKIP: full equal-cap endpoint verification requires restricted row-level "
        "inputs that are intentionally excluded from the anonymous release."
    )
    for path in missing:
        print(f"  withheld input: {path.relative_to(ROOT)}")
    print("Run `python3 verify_release.py` for the public release-safe verification.")
    return False


def main() -> None:
    paths = {
        "manifest": DIR / "manifest_n45_restricted.json",
        "compact": DIR / "bcp_equal_cap_n45_deterministic_compact_restricted.json",
        "compact_integrity": DIR / "bcp_equal_cap_n45_compact_integrity_report.json",
        "episode_1": DIR / "bcp_equal_cap_qwen36_r1_qualification_20260726_summary.json",
        "episode_2": DIR / "bcp_equal_cap_qwen36_r2_45_20260726_summary.json",
        "episode_3": DIR / "bcp_equal_cap_qwen36_r20_45_recovery1_20260726_summary.json",
        "primary_judge": DIR / "bcp_equal_cap_n45_gemma4_judge_20260726_restricted.jsonl",
        "primary_judge_summary": DIR / "bcp_equal_cap_n45_gemma4_judge_20260726_summary.json",
        "primary_analysis": DIR / "semantic_equal_cap_n45_primary_analysis.json",
        "second_judge": DIR / "bcp_equal_cap_n45_gpt56_sol_blind_audit_20260726_restricted.jsonl",
        "second_judge_summary": DIR / "bcp_equal_cap_n45_gpt56_sol_blind_audit_20260726_summary.json",
        "second_analysis": DIR / "bcp_equal_cap_n45_second_model_blind_audit_aggregate_20260726.json",
    }
    if not private_inputs_available(paths):
        return
    manifest = load(paths["manifest"])
    compact = load(paths["compact"])
    integrity = load(paths["compact_integrity"])
    episode_1 = load(paths["episode_1"])
    episode_2 = load(paths["episode_2"])
    episode_3 = load(paths["episode_3"])
    primary_rows = load_jsonl(paths["primary_judge"])
    primary_summary = load(paths["primary_judge_summary"])
    primary_analysis = load(paths["primary_analysis"])
    second_rows = load_jsonl(paths["second_judge"])
    second_summary = load(paths["second_judge_summary"])
    second_analysis = load(paths["second_analysis"])

    expected = {
        (rank, method) for rank in range(1, N + 1) for method in METHODS
    }
    manifest_ids = {
        int(row["rank"]): str(row["query_id"]) for row in manifest["rows"]
    }
    source = {
        (int(row["rank"]), str(row["method"])): row for row in compact
    }
    assert set(manifest_ids) == set(range(1, N + 1))
    assert len(compact) == len(source) == len(expected) == 180
    assert set(source) == expected
    assert all(
        str(row["query_id"]) == manifest_ids[int(row["rank"])]
        for row in compact
    )

    episode_counts = {
        str(episode): sum(
            int(row["execution_episode"]) == episode for row in compact
        )
        for episode in (1, 2, 3)
    }
    assert episode_counts == {"1": 4, "2": 72, "3": 104}
    assert episode_1["completed"] + episode_1["errors"] == 4
    assert episode_2["completed"] + episode_2["errors"] == 72
    assert episode_3["completed"] + episode_3["errors"] == 104
    assert episode_2["run_incomplete"] is True
    assert episode_3["run_incomplete"] is False
    assert not episode_1["remaining_project_pods"]
    assert not episode_3["remaining_project_pods"]
    assert (episode_3["cleanup"] or {}).get("http_status") in {204, 404}
    assert integrity["status"] == "PASS"
    assert integrity["observed_cells"] == 180
    assert integrity["compact_sha256"] == sha256(paths["compact"])

    successful = {
        key
        for key, row in source.items()
        if row["ok"] and str(row["prediction"]).strip()
    }
    assert len(successful) == 173
    primary_success = {
        (int(row["rank"]), str(row["method"])): bool(row["judge"]["correct"])
        for row in primary_rows
    }
    second_success = {
        (int(row["rank"]), str(row["method"])): bool(row["correct"])
        for row in second_rows
    }
    assert set(primary_success) == successful
    assert set(second_success) == successful
    assert primary_summary["completed"] == 173
    assert primary_summary["errors"] == 0
    assert not primary_summary["remaining_project_pods"]
    assert second_summary["completed_cases"] == 173
    assert second_summary["failed_cases"] == 0

    primary = {key: primary_success.get(key, False) for key in expected}
    second = {key: second_success.get(key, False) for key in expected}
    primary_counts = {
        method: sum(primary[(rank, method)] for rank in range(1, N + 1))
        for method in METHODS
    }
    second_counts = {
        method: sum(second[(rank, method)] for rank in range(1, N + 1))
        for method in METHODS
    }
    assert primary_counts == {
        "standard_rlm_qwen36": 31,
        "iterative_search_qwen36": 33,
        "text_decompose_qwen36": 37,
        "bm25_qwen36": 25,
    }
    assert second_counts == {
        "standard_rlm_qwen36": 31,
        "iterative_search_qwen36": 33,
        "text_decompose_qwen36": 37,
        "bm25_qwen36": 24,
    }

    completion = {
        method: sum(
            bool(source[(rank, method)]["ok"])
            and bool(str(source[(rank, method)]["prediction"]).strip())
            for rank in range(1, N + 1)
        )
        for method in METHODS
    }
    assert completion == {
        "standard_rlm_qwen36": 41,
        "iterative_search_qwen36": 45,
        "text_decompose_qwen36": 45,
        "bm25_qwen36": 42,
    }
    calls = {
        method: sum(int(source[(rank, method)]["model_calls"]) for rank in range(1, N + 1))
        for method in METHODS
    }
    assert calls == {
        "standard_rlm_qwen36": 476,
        "iterative_search_qwen36": 426,
        "text_decompose_qwen36": 311,
        "bm25_qwen36": 42,
    }

    primary_pairs = {
        "rlm_vs_iterative": pair(primary, METHODS[0], METHODS[1]),
        "rlm_vs_text": pair(primary, METHODS[0], METHODS[2]),
        "rlm_vs_bm25": pair(primary, METHODS[0], METHODS[3]),
    }
    assert (
        primary_pairs["rlm_vs_iterative"]["left_only"],
        primary_pairs["rlm_vs_iterative"]["right_only"],
    ) == (6, 8)
    assert (
        primary_pairs["rlm_vs_text"]["left_only"],
        primary_pairs["rlm_vs_text"]["right_only"],
    ) == (5, 11)
    assert (
        primary_pairs["rlm_vs_bm25"]["left_only"],
        primary_pairs["rlm_vs_bm25"]["right_only"],
    ) == (10, 4)

    analysis_pair_keys = {
        "rlm_vs_iterative": "standard_rlm_qwen36__vs__iterative_search_qwen36",
        "rlm_vs_text": "standard_rlm_qwen36__vs__text_decompose_qwen36",
        "rlm_vs_bm25": "standard_rlm_qwen36__vs__bm25_qwen36",
    }
    for method, value in primary_counts.items():
        assert primary_analysis["methods"][method]["semantic_correct"] == value
        assert primary_analysis["methods"][method]["completed"] == completion[method]
        assert primary_analysis["methods"][method]["model_calls_total"] == calls[method]
    for short, full in analysis_pair_keys.items():
        observed = primary_pairs[short]
        recorded = primary_analysis["paired"][full]
        assert recorded["left_only"] == observed["left_only"]
        assert recorded["right_only"] == observed["right_only"]
        assert_close(
            recorded["difference"], observed["difference"], f"{short} difference"
        )
        assert_close(
            recorded["mcnemar_exact_two_sided_p"],
            observed["mcnemar_exact_two_sided_p"],
            f"{short} McNemar p",
        )
        assert primary_analysis["multiplicity"]["holm_adjusted_p"][full] >= 0.05

    common_ranks = [
        rank
        for rank in range(1, N + 1)
        if all((rank, method) in successful for method in METHODS)
    ]
    assert len(common_ranks) == 39
    common_primary = {
        method: sum(primary[(rank, method)] for rank in common_ranks)
        for method in METHODS
    }
    assert common_primary == {
        "standard_rlm_qwen36": 30,
        "iterative_search_qwen36": 28,
        "text_decompose_qwen36": 31,
        "bm25_qwen36": 22,
    }

    agreement = sum(
        primary_success[key] == second_success[key] for key in successful
    )
    assert agreement == 172
    assert second_analysis["successful_output_agreement"]["count"] == agreement
    assert second_analysis["successful_output_agreement"]["n"] == 173
    assert_close(
        second_analysis["successful_output_agreement"]["cohen_kappa"],
        0.985490228969219,
        "judge kappa",
    )

    route_costs = {
        method: primary_analysis["methods"][method][
            "active_runtime_listed_rate_usd"
        ]
        for method in METHODS
    }
    expected_route_costs = {
        "standard_rlm_qwen36": 9.872524015940618,
        "iterative_search_qwen36": 1.7100801279238025,
        "text_decompose_qwen36": 1.4003779344010276,
        "bm25_qwen36": 0.2964021628860759,
    }
    for method, expected_cost in expected_route_costs.items():
        assert_close(route_costs[method], expected_cost, f"{method} route cost")
    assert_close(
        primary_analysis["cost"]["judge_creation_to_cleanup_listed_rate_usd"],
        primary_summary["listed_rate_cost_estimate_usd"],
        "primary judge cost",
    )
    assert_close(
        second_analysis["cost"]["reported_per_call_sum_usd"],
        second_summary["reported_usage_cost_usd"],
        "second judge returned cost",
    )

    forbidden = {
        "question",
        "answer",
        "prediction",
        "candidate_response",
        "reference_answer",
    }
    for release_safe in (primary_analysis, second_analysis):
        if forbidden & set(release_safe):
            raise AssertionError("release-safe analysis exposes restricted row text")

    report = {
        "status": "PASS",
        "study_id": "browsecomp_plus_shard1_equal_cap_n45_v1",
        "endpoint": (
            "prospectively frozen outcome-unseen shard-1 ranks 46-90, "
            "equal decision/time caps, fixed N=45"
        ),
        "manifest_rows": 45,
        "attempted_cells": 180,
        "execution_episode_cells": episode_counts,
        "successful_generations": 173,
        "generation_failures_scored_incorrect": 7,
        "completion": completion,
        "model_calls": calls,
        "primary_semantic_correct": primary_counts,
        "second_model_semantic_correct": second_counts,
        "primary_rlm_pairs": primary_pairs,
        "common_completion": {"n": 39, "primary_semantic_correct": common_primary},
        "successful_output_agreement": {
            "count": agreement,
            "n": 173,
            "cohen_kappa": second_analysis["successful_output_agreement"][
                "cohen_kappa"
            ],
        },
        "cost": {
            "route_active_runtime_usd": route_costs,
            "generation_lower_bound_usd": primary_analysis["cost"][
                "generation_cost_usd_with_interrupted_episode_lower_bound"
            ],
            "primary_judge_runpod_usd": primary_summary[
                "listed_rate_cost_estimate_usd"
            ],
            "second_model_reported_openrouter_usd": second_summary[
                "reported_usage_cost_usd"
            ],
            "second_model_provider_delta_usd": second_summary.get(
                "provider_total_usage_delta_usd"
            ),
        },
        "source_hashes": {name: sha256(path) for name, path in paths.items()},
    }
    output_path = DIR / "equal_cap_n45_independent_verification_20260727.json"
    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
