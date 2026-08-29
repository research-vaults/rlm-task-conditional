#!/usr/bin/env python3
"""Build and validate the interrupted-then-resumed BrowseComp+ N=80 endpoint."""

from __future__ import annotations

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

RESULT_DIR = ROOT / "results/browsecomp_plus_positive_regime"
MANIFEST = RESULT_DIR / "manifest_n80_restricted.json"
SOURCES = (
    {
        "episode": "parent_stage_a",
        "path": RESULT_DIR / "bcp_qwen36_stageA_v12_20260720_restricted.jsonl.gz",
        "ranks": range(1, 13),
        "sha256": "6cf62a7542b878bb10ff62099b9b616965e96a99a6e16fa1633f2ccc6f1ca563",
    },
    {
        "episode": "parent_stage_b_before_user_stop",
        "path": RESULT_DIR / "bcp_qwen36_stageB_r13_80_20260720_restricted.jsonl.gz",
        "ranks": range(13, 38),
        "sha256": "608abb1a60b6ada9dc5f1b6b98e9e7e013a69ed060f132b08e9799fb96731c96",
    },
    {
        "episode": "resumed_stage_b",
        "path": RESULT_DIR / "bcp_qwen36_resume_r38_80_20260720_restricted.jsonl.gz",
        "ranks": range(38, 81),
        "sha256": "1d7571058f564933189ea371e7058a22b764e26b160b4f9e8570da63fe49fd49",
    },
)
OUT_COMPACT = RESULT_DIR / "bcp_qwen36_n80_deterministic_compact_restricted.json"
OUT_AGGREGATE = RESULT_DIR / "bcp_qwen36_n80_deterministic_aggregate.json"
OUT_INTEGRITY = RESULT_DIR / "bcp_qwen36_n80_integrity_report.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    required_inputs = [MANIFEST, *(source["path"] for source in SOURCES)]
    missing_inputs = [path for path in required_inputs if not path.exists()]
    if missing_inputs:
        print("LOCAL_ONLY: required restricted inputs are intentionally withheld from the anonymous release.")
        for path in missing_inputs:
            print(f"  withheld input: {path.relative_to(ROOT)}")
        print("Run `python3 verify_release.py` for public aggregate verification.")
        raise SystemExit(2)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest_by_rank = {int(row["rank"]): str(row["query_id"]) for row in manifest["rows"]}
    if set(manifest_by_rank) != set(range(1, 81)):
        raise ValueError("manifest must contain ranks 1-80 exactly")

    compact: list[dict] = []
    source_report: list[dict] = []
    seen: set[tuple[int, str]] = set()
    for source in SOURCES:
        actual_hash = sha256_file(source["path"])
        if actual_hash != source["sha256"]:
            raise ValueError(f"source hash mismatch: {source['path']}")
        allowed = set(source["ranks"])
        selected = 0
        for row in iter_jsonl(source["path"]):
            rank = int(row["rank"])
            if rank not in allowed:
                continue
            method = str(row["method"])
            key = (rank, method)
            if method not in METHODS:
                raise ValueError(f"unknown method {method}")
            if key in seen:
                raise ValueError(f"duplicate selected cell {key}")
            if str(row["query_id"]) != manifest_by_rank[rank]:
                raise ValueError(f"query mismatch at rank {rank}")
            seen.add(key)
            result = row.get("result") or {}
            prediction = str(result.get("response") or "")
            strict, contains = deterministic_score(str(row["answer"]), prediction)
            iterations, code_blocks = count_trace(result)
            compact.append(
                {
                    "rank": rank,
                    "query_id": str(row["query_id"]),
                    "method": method,
                    "episode": source["episode"],
                    "source_file": str(source["path"].relative_to(ROOT)),
                    "source_sha256": actual_hash,
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
                    "context_chars": int(row.get("context_chars_manifest") or 0),
                }
            )
            selected += 1
        expected = len(allowed) * len(METHODS)
        if selected != expected:
            raise ValueError(f"{source['episode']} selected {selected}, expected {expected}")
        source_report.append(
            {
                "episode": source["episode"],
                "path": str(source["path"].relative_to(ROOT)),
                "sha256": actual_hash,
                "selected_cells": selected,
                "rank_min": min(allowed),
                "rank_max": max(allowed),
            }
        )

    expected_keys = {(rank, method) for rank in range(1, 81) for method in METHODS}
    if seen != expected_keys:
        raise ValueError(f"coverage mismatch: missing={sorted(expected_keys - seen)} extra={sorted(seen - expected_keys)}")
    compact.sort(key=lambda row: (row["rank"], METHODS.index(row["method"])))
    OUT_COMPACT.write_text(json.dumps(compact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    OUT_COMPACT.chmod(0o600)

    summary: dict = {
        "study_id": "browsecomp_plus_positive_regime_v1_4_resumption",
        "endpoint": "originally frozen N=80 manifest completed across two execution episodes after disclosed user interruption and post-stop score visibility",
        "n_unique_ranks": 80,
        "cells": len(compact),
        "methods": {},
        "paired": {},
    }
    by_rank: dict[int, dict[str, dict]] = defaultdict(dict)
    for row in compact:
        by_rank[row["rank"]][row["method"]] = row
    for method in METHODS:
        rows = [row for row in compact if row["method"] == method]
        complete = sum(int(row["ok"] and bool(row["prediction"].strip())) for row in rows)
        strict = sum(int(row["strict_exact"]) for row in rows)
        contains = sum(int(row["normalized_contains"]) for row in rows)
        summary["methods"][method] = {
            "attempted": len(rows),
            "completed": complete,
            "completion_rate": complete / len(rows),
            "strict_exact_count": strict,
            "strict_exact_rate": strict / len(rows),
            "strict_exact_wilson_95": wilson(strict, len(rows)),
            "normalized_contains_count": contains,
            "normalized_contains_rate": contains / len(rows),
            "normalized_contains_wilson_95": wilson(contains, len(rows)),
            "wall_seconds_total": sum(row["wall_seconds"] for row in rows),
            "wall_seconds_median": statistics.median(row["wall_seconds"] for row in rows),
            "wall_seconds_max": max(row["wall_seconds"] for row in rows),
            "rlm_iterations_total": sum(row["iterations"] for row in rows),
            "rlm_code_blocks_total": sum(row["code_blocks"] for row in rows),
        }
    for i, left in enumerate(METHODS):
        for right in METHODS[i + 1 :]:
            pairs = [(rows[left], rows[right]) for rows in by_rank.values()]
            summary["paired"][f"{left}__vs__{right}"] = {
                "n": len(pairs),
                "strict_left_only": sum(int(a["strict_exact"] and not b["strict_exact"]) for a, b in pairs),
                "strict_right_only": sum(int(b["strict_exact"] and not a["strict_exact"]) for a, b in pairs),
                "contains_left_only": sum(int(a["normalized_contains"] and not b["normalized_contains"]) for a, b in pairs),
                "contains_right_only": sum(int(b["normalized_contains"] and not a["normalized_contains"]) for a, b in pairs),
            }
    OUT_AGGREGATE.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    integrity = {
        "status": "PASS",
        "manifest_sha256": sha256_file(MANIFEST),
        "compact_sha256": sha256_file(OUT_COMPACT),
        "aggregate_sha256": sha256_file(OUT_AGGREGATE),
        "sources": source_report,
        "n_ranks": 80,
        "n_cells": 240,
        "duplicate_selected_cells": 0,
        "missing_selected_cells": 0,
        "post_stop_score_visibility": True,
    }
    OUT_INTEGRITY.write_text(json.dumps(integrity, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"summary": summary, "integrity": integrity}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
