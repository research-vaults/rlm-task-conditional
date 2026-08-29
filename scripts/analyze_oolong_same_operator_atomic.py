#!/usr/bin/env python3
"""Analyze the atomic same-operator standard-RLM diagnostic on Oolong CD-45."""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


FILES = {
    "slm_qparsed_typed": RESULTS / "oolong_context_disjoint_n45_slm_labeler_question_parsed_typed_20260715.csv",
    "standard_rlm": RESULTS / "oolong_context_disjoint_n45_rlm_20260715.csv",
    "direct_gemini25": RESULTS / "oolong_context_disjoint_n45_direct_controller_gemini25flash_20260715.csv",
    "gpt5_standard_rlm": RESULTS / "oolong_context_disjoint_n45_gpt5_rlm_strict_20260715.csv",
    "same_ops_convenience": RESULTS / "oolong_cd45_rlm_same_ops_20260716.csv",
    "same_ops_atomic": RESULTS / "oolong_cd45_rlm_atomic_ops_20260717.csv",
    "shared_operator_controller": RESULTS / "oolong_context_disjoint_cd45_shared_operator_controller_20260716.csv",
}

SUMMARY_FILES = {
    "slm_qparsed_typed": RESULTS / "oolong_context_disjoint_n45_slm_labeler_question_parsed_typed_20260715_summary.json",
    "standard_rlm": RESULTS / "oolong_context_disjoint_n45_rlm_20260715_summary.json",
    "direct_gemini25": RESULTS / "oolong_context_disjoint_n45_direct_controller_gemini25flash_20260715_summary.json",
    "gpt5_standard_rlm": RESULTS / "oolong_context_disjoint_n45_gpt5_rlm_strict_20260715_summary.json",
    "same_ops_convenience": RESULTS / "oolong_cd45_rlm_same_ops_20260716_summary.json",
    "same_ops_atomic": RESULTS / "oolong_cd45_rlm_atomic_ops_20260717_summary.json",
    "shared_operator_controller": RESULTS / "oolong_context_disjoint_cd45_shared_operator_controller_20260716_summary.json",
}


def read_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8") as handle:
        return {row["example_id"]: row for row in csv.DictReader(handle)}


def is_exact(row: dict[str, str]) -> bool:
    if row.get("correct") not in (None, ""):
        return row["correct"].lower() in {"true", "1", "1.0"}
    if row.get("exact") not in (None, ""):
        return row["exact"].lower() in {"true", "1", "1.0"}
    return float(row.get("score") or 0.0) == 1.0


def score(row: dict[str, str]) -> float:
    if row.get("score") not in (None, ""):
        return float(row["score"])
    return 1.0 if is_exact(row) else 0.0


def paired(rows: dict[str, dict[str, dict[str, str]]], a: str, b: str, ids: list[str]) -> dict[str, int]:
    out = {"both": 0, f"{a}_only": 0, f"{b}_only": 0, "neither": 0}
    for example_id in ids:
        ac = is_exact(rows[a][example_id])
        bc = is_exact(rows[b][example_id])
        if ac and bc:
            out["both"] += 1
        elif ac and not bc:
            out[f"{a}_only"] += 1
        elif bc and not ac:
            out[f"{b}_only"] += 1
        else:
            out["neither"] += 1
    return out


def normalized_summary(name: str, summary: dict) -> dict[str, float | int]:
    if name in {"standard_rlm", "gpt5_standard_rlm"}:
        summary = summary["overall"]["rlm"]
    elif name == "direct_gemini25":
        summary = summary["overall"]
    return {
        "n": int(summary["n"]),
        "exact_count": int(summary["exact_count"]),
        "exact_rate": float(summary["exact_rate"]),
        "mean_score": float(summary["mean_score"]),
    }


def main() -> None:
    rows = {name: read_rows(path) for name, path in FILES.items()}
    ids = sorted(set.intersection(*(set(method_rows) for method_rows in rows.values())))
    summaries = {
        name: json.loads(path.read_text(encoding="utf-8"))
        for name, path in SUMMARY_FILES.items()
    }

    overall = {}
    for name, method_rows in rows.items():
        method_ids = [example_id for example_id in ids if example_id in method_rows]
        if name in summaries:
            overall[name] = normalized_summary(name, summaries[name])
        else:
            exact_count = sum(is_exact(method_rows[example_id]) for example_id in method_ids)
            overall[name] = {
                "n": len(method_ids),
                "exact_count": exact_count,
                "exact_rate": exact_count / len(method_ids),
                "mean_score": sum(score(method_rows[example_id]) for example_id in method_ids) / len(method_ids),
            }

    atomic = summaries["same_ops_atomic"]
    convenience = summaries["same_ops_convenience"]
    analysis = {
        "metadata": {
            "created_from": "Existing completed CD-45 rows; no model calls.",
            "n": len(ids),
            "contract": atomic["contract"],
            "atomic_stop_rule": atomic["stop_rule"],
        },
        "overall": overall,
        "summary_costs": {
            "same_ops_atomic": {
                "controller_cost_usd": atomic["controller_cost_usd"],
                "tool_cost_usd": atomic["tool_cost_usd"],
                "total_cost_usd": atomic["total_cost_usd"],
                "errors": atomic["errors"],
                "tool_call_count": atomic["tool_call_count"],
                "tool_names": atomic["tool_names"],
            },
            "same_ops_convenience": {
                "controller_cost_usd": convenience["controller_cost_usd"],
                "tool_cost_usd": convenience["tool_cost_usd"],
                "total_cost_usd": convenience["total_cost_usd"],
                "errors": convenience["errors"],
                "tool_call_count": convenience["tool_call_count"],
                "tool_names": convenience["tool_names"],
            },
        },
        "atomic_by_group": atomic["by_group"],
        "atomic_by_length": atomic["by_length"],
        "paired_exact": {
            "slm_qparsed_typed_vs_same_ops_atomic": paired(rows, "slm_qparsed_typed", "same_ops_atomic", ids),
            "same_ops_convenience_vs_same_ops_atomic": paired(rows, "same_ops_convenience", "same_ops_atomic", ids),
            "standard_rlm_vs_same_ops_atomic": paired(rows, "standard_rlm", "same_ops_atomic", ids),
            "direct_gemini25_vs_same_ops_atomic": paired(rows, "direct_gemini25", "same_ops_atomic", ids),
            "gpt5_standard_rlm_vs_same_ops_atomic": paired(rows, "gpt5_standard_rlm", "same_ops_atomic", ids),
            "shared_operator_controller_vs_same_ops_atomic": paired(rows, "shared_operator_controller", "same_ops_atomic", ids),
        },
        "interpretation": [
            "Atomic-only standard rlms reaches 29/45, below SLM+typed and shared-operator controller at 36/45.",
            "Withholding the convenience solver lowers the same-operator diagnostic from 31/45 to 29/45 and reduces total cost from $1.31445 to $0.958685.",
            "The atomic row is still above the original standard-RLM row and direct Gemini on exact count, so access to typed tools helps, but free-form orchestration remains less reliable than the specialized route.",
            "The result is a bounded diagnostic, not an official SRLM/lambda-RLM result and not a replacement benchmark row.",
        ],
    }

    out_json = RESULTS / "oolong_cd45_same_operator_atomic_analysis_20260717.json"
    out_md = RESULTS / "oolong_cd45_same_operator_atomic_analysis_20260717.md"
    out_json.write_text(json.dumps(analysis, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Oolong CD-45 Same-Operator Atomic Analysis",
        "",
        "No model calls were made by this analysis script. It summarizes completed CD-45 rows.",
        "",
        "## Overall",
        "",
        "| Method | Exact | Mean score |",
        "|---|---:|---:|",
    ]
    for name, stats in overall.items():
        lines.append(f"| `{name}` | {stats['exact_count']}/{stats['n']} ({stats['exact_rate']*100:.1f}%) | {stats['mean_score']*100:.1f}% |")
    lines.extend([
        "",
        "## Atomic Same-Operator Cost and Failure Profile",
        "",
        f"- Exact: {atomic['exact_count']}/{atomic['n']} ({atomic['exact_rate']*100:.1f}%).",
        f"- Mean score: {atomic['mean_score']*100:.1f}%.",
        f"- Cost: ${atomic['total_cost_usd']:.6f} total (${atomic['controller_cost_usd']:.6f} controller, ${atomic['tool_cost_usd']:.6f} tools).",
        f"- Errors/timeouts: {atomic['errors']}.",
        f"- Tool calls: {atomic['tool_call_count']} ({atomic['tool_names']}).",
        "",
        "## Paired Exact Counts",
        "",
        "| Pair | Both | First only | Atomic only | Neither |",
        "|---|---:|---:|---:|---:|",
    ])
    for pair_name, counts in analysis["paired_exact"].items():
        first_only_key = [key for key in counts if key.endswith("_only") and not key.startswith("same_ops_atomic")][0]
        atomic_only = counts.get("same_ops_atomic_only", 0)
        lines.append(f"| `{pair_name}` | {counts['both']} | {counts[first_only_key]} | {atomic_only} | {counts['neither']} |")
    lines.extend([
        "",
        "## Interpretation",
        "",
        *[f"- {item}" for item in analysis["interpretation"]],
        "",
    ])
    out_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_json}")
    print(f"Wrote {out_md}")


if __name__ == "__main__":
    main()
