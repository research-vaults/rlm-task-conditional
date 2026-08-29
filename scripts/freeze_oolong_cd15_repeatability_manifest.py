#!/usr/bin/env python3
"""Freeze a stratified CD-15 subset for future repeatability runs.

The script makes no model calls. It selects a fixed 15-row subset from the
context-window-disjoint Oolong CD-45 manifest, balanced across task groups and
context lengths, then attaches the already logged CD-45 outcomes. The purpose is
to make any later three-rollout repeatability run predeclared instead of
cherry-picked.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"

SOURCE_MANIFEST = RESULTS / "oolong_context_disjoint_n45_manifest_20260715.json"
SLM_CSV = RESULTS / "oolong_context_disjoint_n45_slm_labeler_question_parsed_typed_20260715.csv"
DIRECT_CSV = RESULTS / "oolong_context_disjoint_n45_direct_controller_gemini25flash_20260715.csv"
RLM_CSV = RESULTS / "oolong_context_disjoint_n45_rlm_20260715.csv"
GPT5_CSV = RESULTS / "oolong_context_disjoint_n45_gpt5_rlm_strict_20260715.csv"

OUT_JSON = RESULTS / "oolong_context_disjoint_cd15_repeatability_manifest_20260715.json"
OUT_MD = RESULTS / "oolong_context_disjoint_cd15_repeatability_manifest_20260715.md"

# Row sums = five examples per task group; column sums = five examples per
# length. Every CD-45 group/length cell contains five candidates, so this
# deterministic matrix keeps the future repeatability run balanced.
CELL_COUNTS = {
    ("counting", 1024): 2,
    ("counting", 4096): 2,
    ("counting", 262144): 1,
    ("timeline", 1024): 2,
    ("timeline", 4096): 1,
    ("timeline", 262144): 2,
    ("user", 1024): 1,
    ("user", 4096): 2,
    ("user", 262144): 2,
}


def read_csv_by_id(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return {row["example_id"]: row for row in csv.DictReader(f)}


def compact_method(row: dict[str, str]) -> dict[str, Any]:
    return {
        "prediction": row.get("prediction", ""),
        "gold": row.get("gold", ""),
        "correct": float(row.get("correct") or 0.0),
        "cost_usd": float(row.get("cost_usd") or 0.0),
        "error": row.get("error", ""),
    }


def main() -> None:
    manifest = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    examples = manifest["examples"]
    by_cell: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for ex in examples:
        key = (str(ex["task_group"]), int(ex["context_len"]))
        by_cell.setdefault(key, []).append(ex)
    for key in by_cell:
        by_cell[key].sort(key=lambda ex: (str(ex.get("context_window_id", "")), str(ex["id"])))

    selected: list[dict[str, Any]] = []
    for key, n in CELL_COUNTS.items():
        candidates = by_cell.get(key, [])
        if len(candidates) < n:
            raise RuntimeError(f"Not enough candidates for {key}: need {n}, found {len(candidates)}")
        selected.extend(candidates[:n])
    selected.sort(key=lambda ex: (str(ex["task_group"]), int(ex["context_len"]), str(ex["context_window_id"]), str(ex["id"])))

    slm = read_csv_by_id(SLM_CSV)
    direct = read_csv_by_id(DIRECT_CSV)
    rlm = read_csv_by_id(RLM_CSV)
    gpt5 = read_csv_by_id(GPT5_CSV)

    enriched = []
    for ex in selected:
        eid = str(ex["id"])
        enriched.append(
            {
                **ex,
                "logged_outcomes": {
                    "slm_qparsed_typed": compact_method(slm[eid]),
                    "direct_gemini25_flash": compact_method(direct[eid]),
                    "standard_rlm_gemini25_flash": compact_method(rlm[eid]),
                    "standard_rlm_gpt5": compact_method(gpt5[eid]),
                },
            }
        )

    group_counts = Counter(str(ex["task_group"]) for ex in enriched)
    length_counts = Counter(str(ex["context_len"]) for ex in enriched)
    context_counts = Counter(str(ex["context_window_id"]) for ex in enriched)
    exact_counts: dict[str, int] = {}
    cost_totals: dict[str, float] = {}
    error_counts: dict[str, int] = {}
    for method in ["slm_qparsed_typed", "direct_gemini25_flash", "standard_rlm_gemini25_flash", "standard_rlm_gpt5"]:
        exact_counts[method] = sum(1 for ex in enriched if ex["logged_outcomes"][method]["correct"] >= 1.0)
        cost_totals[method] = round(sum(ex["logged_outcomes"][method]["cost_usd"] for ex in enriched), 6)
        error_counts[method] = sum(1 for ex in enriched if ex["logged_outcomes"][method]["error"])

    payload = {
        "metadata": {
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "purpose": "Predeclared balanced CD-15 subset for future independent repeatability rollouts. No model calls were made by this script.",
            "source_manifest": str(SOURCE_MANIFEST.relative_to(ROOT)),
            "selection_rule": "Deterministic first-by-(context_window_id,id) within a 3x3 group/length allocation matrix with row and column sums of five.",
            "cell_counts": {f"{g}:{l}": n for (g, l), n in CELL_COUNTS.items()},
            "future_run_note": "Run three independent standard-RLM repeats only when provider credit is available; charge all completed and failed rows under the same stop rule.",
        },
        "summary": {
            "n": len(enriched),
            "groups": dict(sorted(group_counts.items())),
            "lengths": dict(sorted(length_counts.items(), key=lambda kv: int(kv[0]))),
            "unique_context_window_ids": len(context_counts),
            "max_questions_per_context_window_id": max(context_counts.values()),
            "logged_exact_counts_on_parent_cd45_outputs": exact_counts,
            "logged_cost_totals_usd_on_parent_cd45_outputs": cost_totals,
            "logged_error_counts_on_parent_cd45_outputs": error_counts,
        },
        "examples": enriched,
        "commands": {
            "repeat_standard_rlm_template": (
                "python3 scripts/eval_oolong_frozen_manifest_methods.py "
                "--manifest results/oolong_context_disjoint_cd15_repeatability_manifest_20260715.json "
                "--context-variant standard --methods rlm --rlm-backend openrouter "
                "--rlm-model google/gemini-2.5-flash --timeout-seconds 360 "
                "--out results/oolong_context_disjoint_cd15_rlm_repeat{K}_YYYYMMDD.csv "
                "--summary-out results/oolong_context_disjoint_cd15_rlm_repeat{K}_YYYYMMDD_summary.json "
                "--run-id oolong_context_disjoint_cd15_rlm_repeat{K}_YYYYMMDD"
            ),
            "repeat_direct_template": (
                "python3 scripts/run_oolong_rollout_replay_from_traces.py "
                "--manifest results/oolong_context_disjoint_cd15_repeatability_manifest_20260715.json "
                "--method direct_controller --timeout-seconds 360"
            ),
        },
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# Oolong CD-15 Repeatability Manifest",
        "",
        "No model calls were made. This artifact freezes a balanced 15-row subset from CD-45 so later repeatability runs are predeclared.",
        "",
        "## Summary",
        "",
        f"- N: {len(enriched)}",
        f"- Groups: {dict(sorted(group_counts.items()))}",
        f"- Lengths: {dict(sorted(length_counts.items(), key=lambda kv: int(kv[0])))}",
        f"- Unique context windows: {len(context_counts)}",
        f"- Max questions per context window: {max(context_counts.values())}",
        f"- Parent CD-45 exact counts: {exact_counts}",
        f"- Parent CD-45 captured costs: {cost_totals}",
        f"- Parent CD-45 error counts: {error_counts}",
        "",
        "## Future Stop Rule",
        "",
        "Run three independent standard-RLM repeats only after provider credits are available. Charge all completed and failed rows, keep the same 360-second row cap, and report exact agreement, errors/timeouts, cost, and latency. Do not replace this subset after seeing outcomes.",
        "",
        "## Selected IDs",
        "",
        "| example_id | group | context_len | context_window_id | SLM | RLM/Gemini | RLM/GPT-5 | direct |",
        "|---|---|---:|---|---:|---:|---:|---:|",
    ]
    for ex in enriched:
        outcomes = ex["logged_outcomes"]
        lines.append(
            f"| {ex['id']} | {ex['task_group']} | {ex['context_len']} | {ex['context_window_id']} | "
            f"{outcomes['slm_qparsed_typed']['correct']:.0f} | {outcomes['standard_rlm_gemini25_flash']['correct']:.0f} | "
            f"{outcomes['standard_rlm_gpt5']['correct']:.0f} | {outcomes['direct_gemini25_flash']['correct']:.0f} |"
        )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    print(f"Wrote {OUT_JSON.relative_to(ROOT)}")
    print(f"Wrote {OUT_MD.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
