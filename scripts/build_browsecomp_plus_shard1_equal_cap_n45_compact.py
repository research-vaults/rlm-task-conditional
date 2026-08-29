#!/usr/bin/env python3
"""Close and compact the prospective BrowseComp+ equal-cap N=45 endpoint."""

from __future__ import annotations

import gzip
import hashlib
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from analyze_browsecomp_plus_qwen36 import count_trace, deterministic_score, wilson  # noqa: E402

RESULT_DIR = ROOT / "results/browsecomp_plus_shard1_equal_cap_n45"
MANIFEST = RESULT_DIR / "manifest_n45_restricted.json"
PROTOCOL = ROOT / "protocols/BROWSECOMP_PLUS_SHARD1_EQUAL_CAP_N45_20260726.md"
EPISODES = (
    (
        RESULT_DIR / "bcp_equal_cap_qwen36_r1_qualification_20260726_summary.json",
        RESULT_DIR / "bcp_equal_cap_qwen36_r1_qualification_20260726_restricted.jsonl.gz",
    ),
    (
        RESULT_DIR / "bcp_equal_cap_qwen36_r2_45_20260726_summary.json",
        RESULT_DIR / "bcp_equal_cap_qwen36_r2_45_20260726_restricted.jsonl.gz",
    ),
    (
        RESULT_DIR / "bcp_equal_cap_qwen36_r20_45_recovery1_20260726_summary.json",
        RESULT_DIR / "bcp_equal_cap_qwen36_r20_45_recovery1_20260726_restricted.jsonl.gz",
    ),
)
OUT_COMPACT = RESULT_DIR / "bcp_equal_cap_n45_deterministic_compact_restricted.json"
OUT_AGGREGATE = RESULT_DIR / "bcp_equal_cap_n45_deterministic_aggregate.json"
OUT_INTEGRITY = RESULT_DIR / "bcp_equal_cap_n45_compact_integrity_report.json"
METHODS = (
    "standard_rlm_qwen36",
    "iterative_search_qwen36",
    "text_decompose_qwen36",
    "bm25_qwen36",
)
N = 45


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def linear_percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


def usage_counts(result: dict) -> dict[str, int]:
    summaries = (result.get("usage_summary") or {}).get("model_usage_summaries") or {}
    if summaries:
        return {
            "calls": sum(int(row.get("total_calls") or 0) for row in summaries.values()),
            "input_tokens": sum(int(row.get("total_input_tokens") or 0) for row in summaries.values()),
            "output_tokens": sum(int(row.get("total_output_tokens") or 0) for row in summaries.values()),
        }
    calls = result.get("calls") or []
    return {
        "calls": len(calls),
        "input_tokens": sum(int((row.get("usage") or {}).get("prompt_tokens") or 0) for row in calls),
        "output_tokens": sum(int((row.get("usage") or {}).get("completion_tokens") or 0) for row in calls),
    }


def iter_rows(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest_ids = {int(row["rank"]): str(row["query_id"]) for row in manifest["rows"]}
    if set(manifest_ids) != set(range(1, N + 1)):
        raise ValueError("manifest is not the exact rank 1-45 endpoint")

    compact: list[dict] = []
    seen: set[tuple[int, str]] = set()
    episode_ledger: list[dict] = []
    total_generation_cost = 0.0
    expected_by_episode = {1: 4, 2: 72, 3: 104}
    interrupted_raw_hash = (
        "f2904f602e9467ca402793f8b58df292e96b9113c7f39fe51fa464a146126d10"
    )
    for episode, (summary_path, raw_path) in enumerate(EPISODES, start=1):
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if summary.get("fatal_error"):
            raise ValueError(f"episode {episode} fatal error: {summary['fatal_error']}")
        if episode != 2 and summary.get("run_incomplete"):
            raise ValueError(f"episode {episode} is incomplete")
        if episode != 2 and (summary.get("cleanup") or {}).get("http_status") not in {204, 404}:
            raise ValueError(f"episode {episode} cleanup is not closed")
        raw_hash = sha256_file(raw_path)
        if episode == 2 and raw_hash != interrupted_raw_hash:
            raise ValueError("interrupted episode raw hash does not match the pre-score amendment")
        if episode != 2 and raw_hash != summary.get("output_sha256"):
            raise ValueError(f"episode {episode} raw hash mismatch")
        expected = expected_by_episode[episode]
        if int(summary.get("completed", 0)) + int(summary.get("errors", 0)) != expected:
            raise ValueError(f"episode {episode} does not contain {expected} terminal cells")
        episode_cost = float(summary.get("listed_rate_cost_estimate_usd") or 0.0)
        if episode == 2:
            created = summary["events"][0]["at"]
            last_terminal = summary["events"][-1]["at"]
            from datetime import datetime

            elapsed_lower_bound = (
                datetime.fromisoformat(last_terminal) - datetime.fromisoformat(created)
            ).total_seconds()
            episode_cost = elapsed_lower_bound / 3600 * float(
                (summary.get("pod") or {}).get("cost_per_hr") or 0.0
            )
        total_generation_cost += episode_cost
        count = 0
        for row in iter_rows(raw_path):
            rank, method = int(row["rank"]), str(row["method"])
            key = (rank, method)
            if rank not in manifest_ids or method not in METHODS or key in seen:
                raise ValueError(f"invalid or duplicate endpoint cell: {key}")
            if str(row["query_id"]) != manifest_ids[rank]:
                raise ValueError(f"query mismatch at rank {rank}")
            seen.add(key)
            count += 1
            result = row.get("result") or {}
            prediction = str(result.get("response") or "")
            strict, contains = deterministic_score(str(row["answer"]), prediction)
            iterations, code_blocks = count_trace(result)
            usage = usage_counts(result)
            compact.append(
                {
                    "rank": rank,
                    "query_id": str(row["query_id"]),
                    "method": method,
                    "execution_episode": episode,
                    "source_file": str(raw_path.relative_to(ROOT)),
                    "source_sha256": raw_hash,
                    "ok": bool(result.get("ok")),
                    "error": str(result.get("error") or ""),
                    "question": str(row["query"]),
                    "answer": str(row["answer"]),
                    "prediction": prediction,
                    "strict_exact": strict,
                    "normalized_contains": contains,
                    "wall_seconds": float(row.get("wall_seconds") or 0.0),
                    "iterations": iterations,
                    "code_blocks": code_blocks,
                    "model_calls": usage["calls"],
                    "input_tokens": usage["input_tokens"],
                    "output_tokens": usage["output_tokens"],
                    "context_chars": int(row.get("context_chars_manifest") or 0),
                    "retrieved_doc_ids": list(result.get("retrieved_doc_ids") or []),
                    "iterative_actions": list(result.get("actions") or []),
                }
            )
        episode_ledger.append(
            {
                "episode": episode,
                "summary": str(summary_path.relative_to(ROOT)),
                "summary_sha256": sha256_file(summary_path),
                "raw": str(raw_path.relative_to(ROOT)),
                "raw_sha256": raw_hash,
                "cells": count,
                "listed_rate_cost_estimate_usd": (
                    None if episode == 2 else episode_cost
                ),
                "interrupted_episode_cost_lower_bound_usd": (
                    episode_cost if episode == 2 else None
                ),
                "status": (
                    "local_session_interrupted_after_locked_cells"
                    if episode == 2
                    else "complete"
                ),
            }
        )

    expected_cells = {
        (rank, method) for rank in range(1, N + 1) for method in METHODS
    }
    if seen != expected_cells:
        raise ValueError(
            f"coverage mismatch: missing={sorted(expected_cells - seen)} "
            f"extra={sorted(seen - expected_cells)}"
        )
    compact.sort(key=lambda row: (row["rank"], METHODS.index(row["method"])))
    OUT_COMPACT.write_text(
        json.dumps(compact, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    OUT_COMPACT.chmod(0o600)

    aggregate = {
        "study_id": "browsecomp_plus_shard1_equal_cap_n45_v1",
        "endpoint": "prospectively frozen shard-1 ranks 46-90, fixed N=45",
        "protocol": str(PROTOCOL.relative_to(ROOT)),
        "protocol_sha256": sha256_file(PROTOCOL),
        "manifest_sha256": sha256_file(MANIFEST),
        "n_unique_ranks": N,
        "cells": len(compact),
        "generation_episodes": episode_ledger,
        "generation_cost_usd_with_interrupted_episode_lower_bound": total_generation_cost,
        "methods": {},
    }
    for method in METHODS:
        rows = [row for row in compact if row["method"] == method]
        walls = [row["wall_seconds"] for row in rows]
        strict = sum(int(row["strict_exact"]) for row in rows)
        contains = sum(int(row["normalized_contains"]) for row in rows)
        aggregate["methods"][method] = {
            "attempted": N,
            "completed": sum(
                int(bool(row["ok"] and row["prediction"].strip())) for row in rows
            ),
            "strict_exact_count": strict,
            "strict_exact_rate": strict / N,
            "strict_exact_wilson_95": wilson(strict, N),
            "normalized_contains_count": contains,
            "normalized_contains_rate": contains / N,
            "normalized_contains_wilson_95": wilson(contains, N),
            "wall_seconds_total": sum(walls),
            "wall_seconds_median": statistics.median(walls),
            "wall_seconds_p95_type7": linear_percentile(walls, 0.95),
            "wall_seconds_max": max(walls),
            "model_calls_total": sum(row["model_calls"] for row in rows),
            "input_tokens_total": sum(row["input_tokens"] for row in rows),
            "output_tokens_total": sum(row["output_tokens"] for row in rows),
            "rlm_iterations_total": sum(row["iterations"] for row in rows),
            "rlm_code_blocks_total": sum(row["code_blocks"] for row in rows),
        }
    OUT_AGGREGATE.write_text(
        json.dumps(aggregate, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    integrity = {
        "status": "PASS",
        "study_id": aggregate["study_id"],
        "protocol_sha256": sha256_file(PROTOCOL),
        "manifest_sha256": sha256_file(MANIFEST),
        "episodes": episode_ledger,
        "expected_cells": N * len(METHODS),
        "observed_cells": len(compact),
        "compact_sha256": sha256_file(OUT_COMPACT),
        "aggregate_sha256": sha256_file(OUT_AGGREGATE),
        "complete_fixed_endpoint": True,
    }
    OUT_INTEGRITY.write_text(
        json.dumps(integrity, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(integrity, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
