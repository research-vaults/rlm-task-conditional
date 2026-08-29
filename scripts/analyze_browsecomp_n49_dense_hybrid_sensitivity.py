#!/usr/bin/env python3
"""Prepare, validate, and analyze the post-hoc BrowseComp N=49 dense sensitivity."""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any

from run_browsecomp_plus_qwen36_replication_runpod import MANIFEST_PATH


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "results/browsecomp_plus_positive_regime_replication"
DIR = BASE / "dense_hybrid_sensitivity"
RUN_ID = "bcp_n49_dense_hybrid_sensitivity_20260721"
RAW = DIR / f"{RUN_ID}_restricted.jsonl.gz"
PLANS = DIR / f"{RUN_ID}_retrieval_plans_restricted.jsonl.gz"
GEN_SUMMARY = DIR / f"{RUN_ID}_summary.json"
COMPACT = DIR / f"{RUN_ID}_compact_restricted.json"
JUDGES = DIR / "bcp_n49_dense_hybrid_gemma4_judge_20260721_restricted.jsonl"
JUDGE_SUMMARY = DIR / "bcp_n49_dense_hybrid_gemma4_judge_20260721_summary.json"
COST_RECONCILIATION = DIR / "embedding_cost_reconciliation_20260721.json"
EXECUTION_LOCK = DIR / "execution_lock_20260721.json"
SCHEDULER_INTERRUPTION = DIR / "scheduler_interruption_20260721.json"
ORIGINAL_COMPACT = BASE / "bcp_repl_n49_deterministic_compact_restricted.json"
ORIGINAL_JUDGES = BASE / "bcp_repl_gemma4_judge_n49_20260720_restricted.jsonl"
ORIGINAL_ANALYSIS = BASE / "semantic_replication_n49_primary_analysis.json"
OUT = DIR / "semantic_dense_hybrid_sensitivity_n49_analysis.json"
REPORT = DIR / "semantic_dense_hybrid_sensitivity_n49_analysis.md"
METHODS = ("dense_hybrid_qwen3emb8b_qwen36", "bm25_replay_qwen36")
ORIGINAL_METHODS = ("standard_rlm_qwen36", "bm25_qwen36", "text_decompose_qwen36")
LABELS = {
    "dense_hybrid_qwen3emb8b_qwen36": "BM25-64 + Qwen3-Embedding-8B rerank",
    "bm25_replay_qwen36": "BM25 replay",
    "standard_rlm_qwen36": "Standard RLM (original N=49)",
    "bm25_qwen36": "BM25 (original N=49)",
    "text_decompose_qwen36": "Text decomposition (original N=49)",
}
N = 49


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_gzip_jsonl(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def wilson(k: int, n: int, z: float = 1.959963984540054) -> list[float]:
    p = k / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return [center - half, center + half]


def exact_mcnemar(b: int, c: int) -> float:
    n = b + c
    if not n:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(min(b, c) + 1)) / (2**n)
    return min(1.0, 2 * tail)


def bootstrap_difference(left: list[bool], right: list[bool], seed: int, reps: int = 50_000) -> list[float]:
    rng = random.Random(seed)
    n = len(left)
    values = []
    for _ in range(reps):
        sample = [rng.randrange(n) for _ in range(n)]
        values.append(sum(int(left[i]) - int(right[i]) for i in sample) / n)
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
        "paired_bootstrap_95": bootstrap_difference(left, right, seed),
        "mcnemar_exact_two_sided_p": exact_mcnemar(left_only, right_only),
    }


def judge_map(path: Path, expected: set[tuple[int, str]]) -> tuple[dict[tuple[int, str], bool], int]:
    values: dict[tuple[int, str], bool] = {}
    parsed = 0
    for row in read_jsonl(path):
        key = (int(row["rank"]), str(row["method"]))
        if key not in expected or key in values:
            raise ValueError(f"duplicate or unexpected judge cell: {key}")
        parsed += int(bool(row["judge"].get("parsed")))
        values[key] = bool(row["judge"].get("correct"))
    return values, parsed


def main() -> None:
    required_inputs = (
        RAW,
        PLANS,
        GEN_SUMMARY,
        COMPACT,
        JUDGES,
        JUDGE_SUMMARY,
        COST_RECONCILIATION,
        EXECUTION_LOCK,
        SCHEDULER_INTERRUPTION,
        ORIGINAL_COMPACT,
        ORIGINAL_JUDGES,
        ORIGINAL_ANALYSIS,
        MANIFEST_PATH,
    )
    missing_inputs = [path for path in required_inputs if not path.exists()]
    if missing_inputs:
        print("LOCAL_ONLY: required restricted inputs are intentionally withheld from the anonymous release.")
        for path in missing_inputs:
            print(f"  withheld input: {path.relative_to(ROOT)}")
        print("Run `python3 verify_release.py` for public aggregate verification.")
        raise SystemExit(2)
    raw_rows = read_gzip_jsonl(RAW)
    source = {(int(row["rank"]), str(row["method"])): row for row in raw_rows}
    expected = {(rank, method) for rank in range(1, N + 1) for method in METHODS}
    if set(source) != expected:
        missing = sorted(expected - set(source))
        extra = sorted(set(source) - expected)
        raise ValueError(f"generation coverage mismatch: missing={missing[:10]} extra={extra[:10]}")

    plan_rows = read_gzip_jsonl(PLANS)
    plans = {int(row["rank"]): row for row in plan_rows}
    if set(plans) != set(range(1, N + 1)):
        raise ValueError("retrieval-plan coverage mismatch")
    execution_lock = json.loads(EXECUTION_LOCK.read_text(encoding="utf-8"))
    for rank, plan in plans.items():
        if len(plan["candidate_scores"]) != 64:
            raise ValueError(f"rank {rank}: expected 64 BM25 candidates")
        if len(plan["selected_doc_ids"]) > 12:
            raise ValueError(f"rank {rank}: selected-document cap exceeded")
        candidate_ids = {str(row["docid"]) for row in plan["candidate_scores"]}
        if not set(map(str, plan["selected_doc_ids"])).issubset(candidate_ids):
            raise ValueError(f"rank {rank}: selected document outside candidate set")
        if plan["runner_sha256"] != execution_lock["runner_sha256"]:
            raise ValueError(f"rank {rank}: semantic runner hash mismatch")
        if rank <= 4:
            if "planner_orchestrator_sha256" in plan:
                raise ValueError(f"rank {rank}: unexpected scheduler amendment")
        else:
            if plan.get("planner_orchestrator_sha256") != execution_lock["parallel_planner_sha256"]:
                raise ValueError(f"rank {rank}: parallel planner hash mismatch")
            if plan.get("execution_amendment_sha256") != execution_lock["execution_amendment_sha256"]:
                raise ValueError(f"rank {rank}: scheduler amendment hash mismatch")

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest_rows = {int(row["rank"]): row for row in manifest["rows"] if int(row["rank"]) <= N}
    if set(manifest_rows) != set(range(1, N + 1)):
        raise ValueError("manifest coverage mismatch")

    compact: list[dict[str, Any]] = []
    for rank in range(1, N + 1):
        for method in METHODS:
            row = source[(rank, method)]
            result = row["result"]
            prediction = str(result.get("response") or "")
            compact.append({
                "rank": rank,
                "method": method,
                "question": row["query"],
                "answer": row["answer"],
                "prediction": prediction,
                "ok": bool(result.get("ok")),
            })
    COMPACT.write_text(json.dumps(compact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    COMPACT.chmod(0o600)

    generation = json.loads(GEN_SUMMARY.read_text(encoding="utf-8"))
    completed_from_rows = sum(bool(row["result"].get("ok")) and bool(str(row["result"].get("response") or "").strip()) for row in raw_rows)
    errors_from_rows = len(raw_rows) - completed_from_rows
    retrieval: dict[str, Any] = {}
    embedding_requests = [request for plan in plan_rows for request in plan["embedding_requests"]]
    embedding_returned_cost = sum(
        float(request.get("usage", {}).get("cost") or 0) for request in embedding_requests
    )
    embedding_returned_tokens = sum(
        int(request.get("usage", {}).get("total_tokens") or 0) for request in embedding_requests
    )
    for method in METHODS:
        recalls = []
        candidate_recalls = []
        selected_counts = []
        selected_chars = []
        for rank in range(1, N + 1):
            required = set(map(str, manifest_rows[rank]["required_doc_ids"]))
            if method == METHODS[0]:
                selected = set(map(str, plans[rank]["selected_doc_ids"]))
                candidates = set(map(str, (row["docid"] for row in plans[rank]["candidate_scores"])))
                candidate_recalls.append(len(required & candidates) / len(required) if required else 1.0)
            else:
                selected = set(map(str, source[(rank, method)]["result"].get("retrieved_doc_ids", [])))
            recalls.append(len(required & selected) / len(required) if required else 1.0)
            selected_counts.append(len(selected))
            selected_chars.append(int(source[(rank, method)]["result"].get("retrieved_chars") or plans[rank].get("selected_chars") or 0))
        retrieval[method] = {
            "required_document_recall_mean_post_output_diagnostic": statistics.mean(recalls),
            "required_document_full_recall_rows": sum(value == 1.0 for value in recalls),
            "selected_documents_median": statistics.median(selected_counts),
            "selected_chars_median": statistics.median(selected_chars),
        }
        if candidate_recalls:
            retrieval[method]["bm25_top64_required_document_recall_mean_post_output_diagnostic"] = statistics.mean(candidate_recalls)
            retrieval[method]["bm25_top64_required_document_full_recall_rows"] = sum(
                value == 1.0 for value in candidate_recalls
            )
    selection_jaccards = []
    for rank in range(1, N + 1):
        dense_ids = set(map(str, plans[rank]["selected_doc_ids"]))
        bm25_ids = set(map(str, source[(rank, METHODS[1])]["result"].get("retrieved_doc_ids", [])))
        union = dense_ids | bm25_ids
        selection_jaccards.append(len(dense_ids & bm25_ids) / len(union) if union else 1.0)
    retrieval["dense_vs_bm25_selection"] = {
        "rows_with_different_selected_sets": sum(value < 1.0 for value in selection_jaccards),
        "jaccard_mean": statistics.mean(selection_jaccards),
        "jaccard_median": statistics.median(selection_jaccards),
    }

    base: dict[str, Any] = {
        "study_id": "browsecomp_plus_n49_dense_hybrid_sensitivity_v1",
        "evidence_tier": "post_hoc_sensitivity_only",
        "chronology": (
            "Designed after the original N=49 outcomes and scores were visible. Rank 1 was a bounded preflight; "
            "ranks 2-49 were resumed under unchanged protocol and runner hashes. No result is confirmatory."
        ),
        "n": N,
        "methods": list(METHODS),
        "generation_coverage_reconstructed_from_rows": {
            "attempted": len(raw_rows),
            "completed": completed_from_rows,
            "errors": errors_from_rows,
            "summary_episode_completed_counter": generation.get("completed"),
            "summary_episode_error_counter": generation.get("errors"),
            "counter_note": "The resumed summary counter excludes the two rank-1 preflight cells; row-level coverage is authoritative.",
        },
        "retrieval_diagnostic": retrieval,
        "source_hashes": {
            "raw_generation": sha256_file(RAW),
            "retrieval_plans": sha256_file(PLANS),
            "generation_summary": sha256_file(GEN_SUMMARY),
            "compact_judge_input": sha256_file(COMPACT),
            "manifest": sha256_file(MANIFEST_PATH),
            "execution_lock": sha256_file(EXECUTION_LOCK),
            "scheduler_interruption": sha256_file(SCHEDULER_INTERRUPTION),
        },
        "cost": {
            "runpod_generation_listed_rate_usd_resumed_episode": float(generation.get("listed_rate_cost_estimate_usd") or 0),
            "openrouter_embedding_usage_delta_resumed_episode": (
                float(generation.get("openrouter_after", {}).get("total_usage") or 0)
                - float(generation.get("openrouter_before", {}).get("total_usage") or 0)
            ),
            "rank1_preflight_runpod_listed_rate_usd": 0.2895052784883887,
            "rank1_preflight_openrouter_embedding_usage_delta": 0.0017763999999829139,
            "embedding_successful_request_cost_sum_all_plans": embedding_returned_cost,
            "embedding_successful_request_tokens_all_plans": embedding_returned_tokens,
            "embedding_successful_request_count_all_plans": len(embedding_requests),
        },
    }
    base["cost"]["runpod_generation_listed_rate_usd_all_episodes"] = (
        base["cost"]["runpod_generation_listed_rate_usd_resumed_episode"]
        + base["cost"]["rank1_preflight_runpod_listed_rate_usd"]
    )
    base["cost"]["openrouter_usage_delta_generation_driver_episodes_only"] = (
        base["cost"]["openrouter_embedding_usage_delta_resumed_episode"]
        + base["cost"]["rank1_preflight_openrouter_embedding_usage_delta"]
    )
    if COST_RECONCILIATION.exists():
        base["cost"]["openrouter_account_reconciliation"] = json.loads(
            COST_RECONCILIATION.read_text(encoding="utf-8")
        )
        base["source_hashes"]["embedding_cost_reconciliation"] = sha256_file(COST_RECONCILIATION)

    if not JUDGES.exists() or not JUDGE_SUMMARY.exists():
        OUT.write_text(json.dumps(base, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"Prepared {COMPACT}; semantic judge outputs are not present yet.")
        return

    judges, parsed = judge_map(JUDGES, expected)
    successful = {
        key for key, row in source.items()
        if row["result"].get("ok") and str(row["result"].get("response") or "").strip()
    }
    if set(judges) != successful:
        raise ValueError(f"judge coverage mismatch: missing={successful-set(judges)} extra={set(judges)-successful}")

    judge_summary = json.loads(JUDGE_SUMMARY.read_text(encoding="utf-8"))
    if judge_summary.get("cleanup", {}).get("http_status") != 204:
        raise ValueError("judge pod cleanup was not recorded")
    base["semantic_judge"] = {
        "model": "google/gemma-4-26B-A4B-it",
        "revision": "01e5b3ee840d3a9e0b0b493c593e85398a30ef75",
        "attempted": len(judges),
        "parsed": parsed,
        "format_failures_scored_incorrect": len(judges) - parsed,
    }
    base["source_hashes"]["semantic_judge"] = sha256_file(JUDGES)
    base["source_hashes"]["semantic_judge_summary"] = sha256_file(JUDGE_SUMMARY)
    base["cost"]["runpod_judge_listed_rate_usd"] = float(judge_summary.get("listed_rate_cost_estimate_usd") or 0)
    base["cost"]["runpod_generation_plus_judge_all_episodes_usd"] = (
        base["cost"]["runpod_generation_listed_rate_usd_all_episodes"]
        + base["cost"]["runpod_judge_listed_rate_usd"]
    )

    correctness: dict[str, list[bool]] = {}
    base["results"] = {}
    generation_rate = float(generation["pod"]["cost_per_hr"])
    for method in METHODS:
        values = [judges.get((rank, method), False) for rank in range(1, N + 1)]
        correctness[method] = values
        k = sum(values)
        rows = [source[(rank, method)] for rank in range(1, N + 1)]
        latencies = [float(row["wall_seconds"]) for row in rows]
        base["results"][method] = {
            "semantic_correct": k,
            "semantic_accuracy": k / N,
            "wilson_95": wilson(k, N),
            "completed": sum(bool(row["result"].get("ok")) and bool(str(row["result"].get("response") or "").strip()) for row in rows),
            "wall_seconds_median": statistics.median(latencies),
            "wall_seconds_total": sum(latencies),
            "active_runtime_listed_rate_usd": sum(latencies) / 3600 * generation_rate,
        }
    base["results"][METHODS[0]]["active_runtime_plus_embedding_returned_cost_usd"] = (
        base["results"][METHODS[0]]["active_runtime_listed_rate_usd"]
        + embedding_returned_cost
    )

    original_compact = json.loads(ORIGINAL_COMPACT.read_text(encoding="utf-8"))
    original_analysis = json.loads(ORIGINAL_ANALYSIS.read_text(encoding="utf-8"))
    original_expected = {(rank, method) for rank in range(1, N + 1) for method in ORIGINAL_METHODS}
    original_judges, original_parsed = judge_map(ORIGINAL_JUDGES, original_expected)
    original_successful = {
        (int(row["rank"]), str(row["method"]))
        for row in original_compact if row["ok"] and str(row["prediction"]).strip()
    }
    if set(original_judges) != original_successful:
        raise ValueError("original judge coverage mismatch")
    base["original_judge_parsed"] = original_parsed
    for method in ORIGINAL_METHODS:
        values = [original_judges.get((rank, method), False) for rank in range(1, N + 1)]
        correctness[method] = values
        k = sum(values)
        base["results"][method] = {
            "semantic_correct": k,
            "semantic_accuracy": k / N,
            "wilson_95": wilson(k, N),
            "completed": int(original_analysis["methods"][method]["completed"]),
            "wall_seconds_median": float(original_analysis["methods"][method]["wall_seconds_median"]),
            "active_runtime_listed_rate_usd": float(
                original_analysis["methods"][method]["active_runtime_listed_rate_usd"]
            ),
            "provenance": "original untouched N=49 execution; same frozen rows and same Gemma judge revision",
        }
    dense_cost = base["results"][METHODS[0]]["active_runtime_plus_embedding_returned_cost_usd"]
    base["cost"]["standard_rlm_to_dense_hybrid_route_attributed_ratio"] = (
        base["results"]["standard_rlm_qwen36"]["active_runtime_listed_rate_usd"] / dense_cost
    )

    comparisons = [
        (METHODS[0], METHODS[1]),
        (METHODS[0], "standard_rlm_qwen36"),
        (METHODS[0], "bm25_qwen36"),
        (METHODS[0], "text_decompose_qwen36"),
        (METHODS[1], "bm25_qwen36"),
    ]
    base["paired_descriptive"] = {
        f"{left}__vs__{right}": paired(correctness[left], correctness[right], 20260721 + index)
        for index, (left, right) in enumerate(comparisons)
    }
    base["interpretation_guardrail"] = (
        "All comparisons involving the learned retriever are post-hoc sensitivity analyses. They may assess whether a "
        "stronger nonrecursive retrieval alternative changes the observed ranking, but cannot establish a newly confirmed effect."
    )
    OUT.write_text(json.dumps(base, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# BrowseComp N=49 Learned-Retrieval Sensitivity",
        "",
        "**Evidence tier:** post-hoc sensitivity only. The original N=49 outcomes and scores were visible before this protocol was written. Rank 1 was a bounded preflight; ranks 2--49 used the unchanged protocol and runner hashes.",
        "",
        "| Route | Semantic accuracy (Wilson 95%) | Complete | Median wall time | Route-attributed cost |",
        "|---|---:|---:|---:|---:|",
    ]
    for method in (*METHODS, *ORIGINAL_METHODS):
        row = base["results"][method]
        lo, hi = row["wilson_95"]
        complete = row.get("completed", "--")
        latency = f"{row['wall_seconds_median']:.1f}s" if "wall_seconds_median" in row else "--"
        cost = row["active_runtime_listed_rate_usd"]
        if method == METHODS[0]:
            cost = row["active_runtime_plus_embedding_returned_cost_usd"]
        lines.append(
            f"| {LABELS[method]} | {row['semantic_correct']}/{N} = {100*row['semantic_accuracy']:.1f}% "
            f"({100*lo:.1f}--{100*hi:.1f}) | {complete} | {latency} | ${cost:.3f} |"
        )
    lines += [
        "",
        "## Paired descriptive comparisons",
        "",
        "| Comparison | Difference | Left/right only | Bootstrap 95% | McNemar p |",
        "|---|---:|---:|---:|---:|",
    ]
    for key, row in base["paired_descriptive"].items():
        left, right = key.split("__vs__")
        lo, hi = row["paired_bootstrap_95"]
        lines.append(
            f"| {LABELS[left]} vs {LABELS[right]} | {100*row['difference']:+.1f} pp | "
            f"{row['left_only']}/{row['right_only']} | {100*lo:+.1f} to {100*hi:+.1f} pp | "
            f"{row['mcnemar_exact_two_sided_p']:.4f} |"
        )
    lines += [
        "",
        "Required-document recall is an outcome-aware diagnostic computed after the run; it is not a selection criterion or a confirmatory endpoint.",
        "",
        "The learned-retriever row is not promoted into the primary evidence. Its role is to test whether the paper's decision boundary survives a stronger, reproducible, nonrecursive retrieval alternative under the same answer model and context fitter.",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(base, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
