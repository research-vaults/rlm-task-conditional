#!/usr/bin/env python3
"""Build the deterministic compact endpoint for the shard-1 fixed-N=45 run."""

from __future__ import annotations

import gzip
import hashlib
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from analyze_browsecomp_plus_qwen36 import (  # noqa: E402
    METHODS,
    count_trace,
    deterministic_score,
    iter_jsonl,
    wilson,
)

RESULT_DIR = ROOT / "results/browsecomp_plus_shard1_fixed_n45"
MANIFEST = RESULT_DIR / "manifest_n45_restricted.json"
FIRST_SUMMARY = RESULT_DIR / "bcp_shard1_fixed_n45_qwen36_20260723_summary.json"
FIRST_RAW = RESULT_DIR / "bcp_shard1_fixed_n45_qwen36_20260723_restricted.jsonl.gz"
RESUME_SUMMARY = RESULT_DIR / "bcp_shard1_fixed_n45_qwen36_20260723_resume1_summary.json"
RESUME_RAW = RESULT_DIR / "bcp_shard1_fixed_n45_qwen36_20260723_resume1_restricted.jsonl.gz"
OUT_COMPACT = RESULT_DIR / "bcp_shard1_fixed_n45_deterministic_compact_restricted.json"
OUT_AGGREGATE = RESULT_DIR / "bcp_shard1_fixed_n45_deterministic_aggregate.json"
OUT_INTEGRITY = RESULT_DIR / "bcp_shard1_fixed_n45_compact_integrity_report.json"
N = 45
FIRST_LOCKED_CELLS = 107
RESUMED_CELLS = N * len(METHODS) - FIRST_LOCKED_CELLS


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def usage_counts(result: dict) -> dict[str, int]:
    """Normalize official-RLM and explicit-call usage into one route ledger."""
    summary = result.get("usage_summary") or {}
    model_summaries = summary.get("model_usage_summaries") or {}
    if model_summaries:
        return {
            "calls": sum(int(row.get("total_calls") or 0) for row in model_summaries.values()),
            "input_tokens": sum(int(row.get("total_input_tokens") or 0) for row in model_summaries.values()),
            "output_tokens": sum(int(row.get("total_output_tokens") or 0) for row in model_summaries.values()),
        }
    calls = result.get("calls") or []
    return {
        "calls": len(calls),
        "input_tokens": sum(int((row.get("usage") or {}).get("prompt_tokens") or 0) for row in calls),
        "output_tokens": sum(int((row.get("usage") or {}).get("completion_tokens") or 0) for row in calls),
    }


def iter_episode(path: Path, allow_truncated_eof: bool = False):
    """Read immutable JSONL records, tolerating only the known episode-1 EOF."""
    try:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)
    except EOFError:
        if not allow_truncated_eof:
            raise


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest_by_rank = {int(row["rank"]): str(row["query_id"]) for row in manifest["rows"]}
    if set(manifest_by_rank) != set(range(1, N + 1)):
        raise ValueError(f"manifest must contain ranks 1-{N} exactly")

    first_summary = json.loads(FIRST_SUMMARY.read_text(encoding="utf-8"))
    resume_summary = json.loads(RESUME_SUMMARY.read_text(encoding="utf-8"))
    if first_summary.get("completed", 0) + first_summary.get("errors", 0) != FIRST_LOCKED_CELLS:
        raise ValueError("interrupted episode does not contain exactly 107 locked cells")
    if not first_summary.get("run_incomplete"):
        raise ValueError("interrupted episode is not marked incomplete")
    if resume_summary.get("first_locked_cells") != FIRST_LOCKED_CELLS:
        raise ValueError("resume summary does not bind the 107-cell interruption boundary")
    if resume_summary.get("expected_resumed_cells") != RESUMED_CELLS:
        raise ValueError("resume summary does not bind the 28-cell recovery endpoint")
    if resume_summary.get("completed", 0) + resume_summary.get("errors", 0) != RESUMED_CELLS:
        raise ValueError("recovery episode does not contain exactly 28 attempted cells")
    if resume_summary.get("run_incomplete"):
        raise ValueError("recovery summary still marks the combined endpoint incomplete")
    if resume_summary.get("fatal_error"):
        raise ValueError(f"recovery ended with a fatal error: {resume_summary['fatal_error']}")
    if resume_summary.get("remaining_project_pods"):
        raise ValueError("generation pod remains active after recovery")
    cleanup_status = (resume_summary.get("cleanup") or {}).get("http_status")
    if cleanup_status not in {204, 404}:
        raise ValueError(f"generation pod cleanup is not closed: {cleanup_status}")

    raw_hashes = {
        FIRST_RAW: sha256_file(FIRST_RAW),
        RESUME_RAW: sha256_file(RESUME_RAW),
    }
    if raw_hashes[FIRST_RAW] != resume_summary.get("first_raw_sha256"):
        raise ValueError("interrupted raw hash does not match the pre-resume lock")
    if raw_hashes[RESUME_RAW] != resume_summary.get("output_sha256"):
        raise ValueError("recovery raw hash does not match the closed recovery summary")

    compact: list[dict] = []
    seen: set[tuple[int, str]] = set()
    episode_counts: dict[str, int] = {}
    for episode, raw, allow_eof in (
        (1, FIRST_RAW, True),
        (2, RESUME_RAW, False),
    ):
        episode_count = 0
        for row in iter_episode(raw, allow_truncated_eof=allow_eof):
            rank = int(row["rank"])
            method = str(row["method"])
            key = (rank, method)
            if rank not in manifest_by_rank or method not in METHODS:
                raise ValueError(f"unexpected endpoint cell {key}")
            if key in seen:
                raise ValueError(f"duplicate endpoint cell {key}")
            if str(row["query_id"]) != manifest_by_rank[rank]:
                raise ValueError(f"query mismatch at rank {rank}")
            seen.add(key)
            episode_count += 1
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
                    "source_file": str(raw.relative_to(ROOT)),
                    "source_sha256": raw_hashes[raw],
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
                }
            )
        episode_counts[str(episode)] = episode_count
    if episode_counts != {"1": FIRST_LOCKED_CELLS, "2": RESUMED_CELLS}:
        raise ValueError(f"episode reconstruction mismatch: {episode_counts}")

    expected = {(rank, method) for rank in range(1, N + 1) for method in METHODS}
    if seen != expected:
        raise ValueError(f"coverage mismatch: missing={sorted(expected-seen)} extra={sorted(seen-expected)}")
    compact.sort(key=lambda row: (row["rank"], METHODS.index(row["method"])))
    OUT_COMPACT.write_text(json.dumps(compact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    OUT_COMPACT.chmod(0o600)

    by_rank: dict[int, dict[str, dict]] = defaultdict(dict)
    for row in compact:
        by_rank[row["rank"]][row["method"]] = row
    aggregate: dict = {
        "study_id": "browsecomp_plus_shard1_fixed_n45_v1",
        "endpoint": "prospectively frozen, disjoint official shard-1 fixed N=45",
        "execution_episodes": episode_counts,
        "infrastructure_amendment": (
            "protocols/BROWSECOMP_PLUS_SHARD1_FIXED_N45_INFRASTRUCTURE_AMENDMENT_1_20260723.md"
        ),
        "n_unique_ranks": N,
        "cells": len(compact),
        "methods": {},
        "paired": {},
    }
    for method in METHODS:
        rows = [row for row in compact if row["method"] == method]
        complete = sum(int(row["ok"] and bool(row["prediction"].strip())) for row in rows)
        strict = sum(int(row["strict_exact"]) for row in rows)
        contains = sum(int(row["normalized_contains"]) for row in rows)
        aggregate["methods"][method] = {
            "attempted": N,
            "completed": complete,
            "strict_exact_count": strict,
            "strict_exact_rate": strict / N,
            "strict_exact_wilson_95": wilson(strict, N),
            "normalized_contains_count": contains,
            "normalized_contains_rate": contains / N,
            "normalized_contains_wilson_95": wilson(contains, N),
            "wall_seconds_total": sum(row["wall_seconds"] for row in rows),
            "wall_seconds_median": statistics.median(row["wall_seconds"] for row in rows),
            "wall_seconds_max": max(row["wall_seconds"] for row in rows),
            "rlm_iterations_total": sum(row["iterations"] for row in rows),
            "rlm_code_blocks_total": sum(row["code_blocks"] for row in rows),
            "model_calls_total": sum(row["model_calls"] for row in rows),
            "input_tokens_total": sum(row["input_tokens"] for row in rows),
            "output_tokens_total": sum(row["output_tokens"] for row in rows),
        }
    for left in METHODS:
        for right in METHODS[METHODS.index(left) + 1 :]:
            pairs = [(rows[left], rows[right]) for rows in by_rank.values()]
            aggregate["paired"][f"{left}__vs__{right}"] = {
                "n": N,
                "strict_left_only": sum(int(a["strict_exact"] and not b["strict_exact"]) for a, b in pairs),
                "strict_right_only": sum(int(b["strict_exact"] and not a["strict_exact"]) for a, b in pairs),
                "contains_left_only": sum(int(a["normalized_contains"] and not b["normalized_contains"]) for a, b in pairs),
                "contains_right_only": sum(int(b["normalized_contains"] and not a["normalized_contains"]) for a, b in pairs),
            }
    OUT_AGGREGATE.write_text(json.dumps(aggregate, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    integrity = {
        "status": "PASS",
        "study_id": aggregate["study_id"],
        "manifest_sha256": sha256_file(MANIFEST),
        "generation_episode_summary_sha256": sha256_file(FIRST_SUMMARY),
        "recovery_episode_summary_sha256": sha256_file(RESUME_SUMMARY),
        "raw_output_sha256_by_episode": {
            "1": raw_hashes[FIRST_RAW],
            "2": raw_hashes[RESUME_RAW],
        },
        "observed_cells_by_episode": episode_counts,
        "compact_sha256": sha256_file(OUT_COMPACT),
        "aggregate_sha256": sha256_file(OUT_AGGREGATE),
        "expected_cells": N * len(METHODS),
        "observed_cells": len(compact),
        "complete_fixed_endpoint": True,
    }
    OUT_INTEGRITY.write_text(json.dumps(integrity, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(integrity, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
