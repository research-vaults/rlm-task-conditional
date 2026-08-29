#!/usr/bin/env python3
"""Create the restricted Gemma-judge input for the RLM no-subcall ablation."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "results/browsecomp_plus_positive_regime_replication/no_subcall_ablation"
RAW = DIR / "bcp_n49_rlm_no_subcall_qwen36_20260722_restricted.jsonl.gz"
SUMMARY = DIR / "bcp_n49_rlm_no_subcall_qwen36_20260722_summary.json"
OUT = DIR / "bcp_n49_rlm_no_subcall_compact_restricted.json"
METHOD = "rlm_no_subcall_qwen36"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    if summary.get("remaining_project_pods"):
        raise RuntimeError("generation pod remains active")
    by_rank = {}
    with gzip.open(RAW, "rt", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("method") != METHOD:
                raise RuntimeError(f"unexpected method {row.get('method')}")
            rank = int(row["rank"])
            if rank in by_rank:
                raise RuntimeError(f"duplicate rank {rank}")
            result = row.get("result") or {}
            trace = result.get("trace") or {}
            iterations = trace.get("iterations") if isinstance(trace, dict) else []
            by_rank[rank] = {
                "rank": rank,
                "query_id": row.get("query_id"),
                "method": METHOD,
                "ok": bool(result.get("ok")),
                "error": str(result.get("error") or ""),
                "question": row.get("query", ""),
                "answer": row.get("answer", ""),
                "prediction": str(result.get("response") or ""),
                "wall_seconds": float(row.get("wall_seconds") or result.get("latency_seconds") or 0.0),
                "iterations": len(iterations or []),
                "code_blocks": sum(len(item.get("code_blocks") or []) for item in (iterations or [])),
                "disabled_subcall_attempts": len(result.get("disabled_subcall_attempts") or []),
                "context_chars": result.get("context_chars"),
            }

    compact = []
    for rank in range(1, 50):
        row = by_rank.get(rank)
        if row is None:
            compact.append({
                "rank": rank,
                "method": METHOD,
                "ok": False,
                "error": "unattempted_after_stability_stop",
                "question": "",
                "answer": "",
                "prediction": "",
                "wall_seconds": 0.0,
                "iterations": 0,
                "code_blocks": 0,
                "disabled_subcall_attempts": 0,
            })
            continue
        compact.append(row)
    OUT.write_text(json.dumps(compact, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    OUT.chmod(0o600)
    print(json.dumps({
        "raw_sha256": sha256_file(RAW),
        "summary_sha256": sha256_file(SUMMARY),
        "output": str(OUT.relative_to(ROOT)),
        "output_sha256": sha256_file(OUT),
        "attempted": len(by_rank),
        "completed_with_output": sum(bool(row["ok"] and row["prediction"].strip()) for row in compact),
    }, indent=2))


if __name__ == "__main__":
    main()
