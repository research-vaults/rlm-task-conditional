#!/usr/bin/env python3
"""Analyze frozen BrowseComp+ Qwen3.6 generation outputs.

The compact per-row export remains restricted because BrowseComp+ requests
that plaintext queries/answers not be published. Aggregate JSON/Markdown can be
used in the paper after semantic judging is complete.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import re
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[1]
METHODS = ("standard_rlm_qwen36", "bm25_qwen36", "text_decompose_qwen36")
ARTICLES = re.compile(r"\b(a|an|the)\b", flags=re.IGNORECASE)
NON_ALNUM = re.compile(r"[^a-z0-9]+")


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    opener = gzip.open(path, "rt", encoding="utf-8") if path.suffix == ".gz" else path.open("r", encoding="utf-8")
    with opener as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def normalize(text: str) -> str:
    text = ARTICLES.sub(" ", text.casefold())
    return " ".join(NON_ALNUM.sub(" ", text).split())


def deterministic_score(answer: str, prediction: str) -> tuple[bool, bool]:
    gold, pred = normalize(answer), normalize(prediction)
    strict = bool(gold and pred == gold)
    contains = bool(gold and (gold in pred or pred in gold) and min(len(gold), len(pred)) >= 2)
    return strict, contains


def wilson(k: int, n: int, z: float = 1.959963984540054) -> list[float]:
    if not n:
        return [0.0, 0.0]
    p = k / n
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [center - half, center + half]


def count_trace(result: dict[str, Any]) -> tuple[int, int]:
    trace = result.get("trace") or {}
    iterations = trace.get("iterations") if isinstance(trace, dict) else []
    if not isinstance(iterations, list):
        return 0, 0
    code = 0
    for item in iterations:
        blocks = item.get("code_blocks") if isinstance(item, dict) else []
        if isinstance(blocks, list):
            code += len(blocks)
    return len(iterations), code


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+")
    parser.add_argument("--out-prefix", default="results/browsecomp_plus_positive_regime/stageA_deterministic")
    args = parser.parse_args()
    paths = [ROOT / item for item in args.inputs]
    compact: list[dict[str, Any]] = []
    for path in paths:
        for row in iter_jsonl(path):
            result = row.get("result") or {}
            prediction = str(result.get("response") or "")
            strict, contains = deterministic_score(str(row["answer"]), prediction)
            iterations, code_blocks = count_trace(result)
            compact.append({
                "rank": int(row["rank"]),
                "query_id": str(row["query_id"]),
                "method": str(row["method"]),
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
            })
    compact.sort(key=lambda r: (r["rank"], METHODS.index(r["method"])))
    prefix = ROOT / args.out_prefix
    prefix.parent.mkdir(parents=True, exist_ok=True)
    restricted = prefix.with_name(prefix.name + "_compact_restricted.json")
    restricted.write_text(json.dumps(compact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    restricted.chmod(0o600)

    summary: dict[str, Any] = {"n_unique_ranks": len({r["rank"] for r in compact}), "methods": {}}
    for method in METHODS:
        rows = [r for r in compact if r["method"] == method]
        completed = [r for r in rows if r["ok"]]
        strict = sum(int(r["strict_exact"]) for r in rows)
        contains = sum(int(r["normalized_contains"]) for r in rows)
        summary["methods"][method] = {
            "attempted": len(rows),
            "completed": len(completed),
            "completion_rate": len(completed) / len(rows) if rows else 0.0,
            "strict_exact_count": strict,
            "strict_exact_rate": strict / len(rows) if rows else 0.0,
            "strict_exact_wilson_95": wilson(strict, len(rows)),
            "normalized_contains_count": contains,
            "normalized_contains_rate": contains / len(rows) if rows else 0.0,
            "normalized_contains_wilson_95": wilson(contains, len(rows)),
            "wall_seconds_total": sum(r["wall_seconds"] for r in rows),
            "wall_seconds_median": statistics.median(r["wall_seconds"] for r in rows) if rows else 0.0,
            "wall_seconds_max": max((r["wall_seconds"] for r in rows), default=0.0),
            "rlm_iterations_total": sum(r["iterations"] for r in rows),
            "rlm_code_blocks_total": sum(r["code_blocks"] for r in rows),
            "error_types": sorted({r["error"] for r in rows if r["error"]}),
        }
    paired: dict[str, Any] = {}
    by_rank: dict[int, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in compact:
        by_rank[row["rank"]][row["method"]] = row
    for left in METHODS:
        for right in METHODS:
            if METHODS.index(left) >= METHODS.index(right):
                continue
            pairs = [(m[left], m[right]) for m in by_rank.values() if left in m and right in m]
            paired[f"{left}__vs__{right}"] = {
                "n": len(pairs),
                "strict_left_only": sum(int(a["strict_exact"] and not b["strict_exact"]) for a, b in pairs),
                "strict_right_only": sum(int(b["strict_exact"] and not a["strict_exact"]) for a, b in pairs),
                "contains_left_only": sum(int(a["normalized_contains"] and not b["normalized_contains"]) for a, b in pairs),
                "contains_right_only": sum(int(b["normalized_contains"] and not a["normalized_contains"]) for a, b in pairs),
            }
    summary["paired"] = paired
    aggregate = prefix.with_name(prefix.name + "_aggregate.json")
    aggregate.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"restricted={restricted.relative_to(ROOT)}")
    print(f"aggregate={aggregate.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
