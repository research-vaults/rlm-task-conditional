#!/usr/bin/env python3
"""Extract a compact CD-45 same-operator RLM program-trace exhibit.

This is a no-call analysis over completed standard-rlms same-operator runs. It
summarizes representative generated programs from the convenience-tool and
atomic-tool variants without quoting long input contexts.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"

RUNS = {
    "same_ops_convenience": RESULTS / "oolong_cd45_rlm_same_ops_20260716_trace.jsonl",
    "same_ops_atomic": RESULTS / "oolong_cd45_rlm_atomic_ops_20260717_trace.jsonl",
}

OUT_JSON = RESULTS / "oolong_cd45_same_operator_program_trace_exhibit_20260718.json"
OUT_MD = RESULTS / "oolong_cd45_same_operator_program_trace_exhibit_20260718.md"

CASE_SPECS = [
    ("210020017", "timeline success using deterministic date counting"),
    ("410040043", "timeline success using parsed-row filtering"),
    ("312030020", "user aggregate success with direct whole-context failure elsewhere"),
    ("710070026", "least-label edge where same-operator variants can choose the wrong label"),
    ("712070012", "label-comparison malformed final answer"),
    ("612060011", "numeric counting malformed/non-answer finalization"),
    ("910090047", "blank final answer after tool use"),
    ("918090044", "long-context timeout/error row"),
    ("418040032", "self-reported tool-use confusion on a long user row"),
    ("418040058", "malformed final answer on a long user row"),
]


def read_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                rows[str(row["example_id"])] = row
    return rows


def first_nonempty(items: list[str]) -> str:
    for item in items:
        if item:
            return item
    return ""


def clean(value: Any, limit: int = 500) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\r\n", "\n").strip()
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def code_block_summaries(row: dict[str, Any], limit: int = 3) -> list[dict[str, str]]:
    trajectory = row.get("trajectory") or {}
    iterations = trajectory.get("iterations") or []
    blocks: list[dict[str, str]] = []
    for iteration in iterations:
        for block in iteration.get("code_blocks") or []:
            blocks.append(
                {
                    "iteration": str(iteration.get("iteration", "")),
                    "code": clean(block.get("code"), 900),
                    "stdout": clean(block.get("stdout"), 500),
                    "stderr": clean(block.get("stderr"), 300),
                    "error": clean(block.get("error"), 300),
                    "final_answer": clean(block.get("final_answer"), 200),
                }
            )
    if len(blocks) <= limit:
        return blocks
    return [blocks[0], blocks[len(blocks) // 2], blocks[-1]]


def response_summaries(row: dict[str, Any]) -> dict[str, str]:
    trajectory = row.get("trajectory") or {}
    iterations = trajectory.get("iterations") or []
    responses = [clean(it.get("response"), 600) for it in iterations]
    finals = [clean(it.get("final_answer"), 200) for it in iterations]
    return {
        "first_response": first_nonempty(responses),
        "last_response": first_nonempty(list(reversed(responses))),
        "last_iteration_final_answer": first_nonempty(list(reversed(finals))),
    }


def classify_failure(row: dict[str, Any]) -> str:
    if row.get("exact"):
        return "exact"
    error = clean(row.get("error"), 300).lower()
    pred = clean(row.get("prediction"), 400).lower()
    raw = clean(row.get("raw_response"), 500).lower()
    joined = " ".join([error, pred, raw])
    if "timeout" in joined:
        return "timeout_or_row_cap"
    if not pred:
        return "blank_or_missing_final"
    if "unable to determine" in joined or "tool" in joined and "unclear" in joined:
        return "tool_use_confusion"
    if "{" in pred or "answer" in pred and len(pred) > 80:
        return "malformed_final_answer"
    if "unknown" in pred or pred.endswith('"') or "number'." in pred:
        return "malformed_final_answer"
    return "wrong_value_or_wrong_route"


def summarize_row(row: dict[str, Any] | None) -> dict[str, Any]:
    if row is None:
        return {"available": False}
    return {
        "available": True,
        "task_group": row.get("task_group"),
        "context_len": row.get("context_len"),
        "task": row.get("task"),
        "answer_type": row.get("answer_type"),
        "question": clean(row.get("question"), 500),
        "gold": clean(row.get("gold"), 200),
        "prediction": clean(row.get("prediction"), 400),
        "score": row.get("score"),
        "exact": bool(row.get("exact")),
        "failure_class": classify_failure(row),
        "cost_usd": row.get("total_cost_usd"),
        "elapsed_seconds": row.get("elapsed_seconds"),
        "iteration_count": row.get("iteration_count"),
        "code_block_count": row.get("code_block_count"),
        "tool_call_count": row.get("tool_call_count"),
        "tool_names": row.get("tool_names"),
        "error": clean(row.get("error"), 500),
        "raw_response": clean(row.get("raw_response"), 600),
        "response_summaries": response_summaries(row),
        "selected_code_blocks": code_block_summaries(row),
    }


def main() -> None:
    tables = {name: read_jsonl(path) for name, path in RUNS.items()}

    aggregate: dict[str, Any] = {}
    for name, rows in tables.items():
        failure_counts = Counter(classify_failure(row) for row in rows.values())
        aggregate[name] = {
            "source": str(RUNS[name].relative_to(ROOT)),
            "n": len(rows),
            "exact_count": sum(bool(row.get("exact")) for row in rows.values()),
            "mean_score": sum(float(row.get("score") or 0.0) for row in rows.values()) / len(rows),
            "total_cost_usd": sum(float(row.get("total_cost_usd") or 0.0) for row in rows.values()),
            "total_tool_calls": sum(int(row.get("tool_call_count") or 0) for row in rows.values()),
            "total_code_blocks": sum(int(row.get("code_block_count") or 0) for row in rows.values()),
            "failure_counts": dict(sorted(failure_counts.items())),
        }

    cases = []
    for example_id, reason in CASE_SPECS:
        cases.append(
            {
                "example_id": example_id,
                "selection_reason": reason,
                "same_ops_convenience": summarize_row(tables["same_ops_convenience"].get(example_id)),
                "same_ops_atomic": summarize_row(tables["same_ops_atomic"].get(example_id)),
            }
        )

    payload = {
        "metadata": {
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "purpose": "No-call mechanism exhibit over completed CD-45 standard-rlms same-operator trajectories.",
            "source_files": {name: str(path.relative_to(ROOT)) for name, path in RUNS.items()},
            "case_count": len(cases),
            "model_calls_made_by_this_script": 0,
            "interpretation_boundary": "Qualitative generated-program inspection only; aggregate accuracy/cost claims remain the completed CD-45 convenience and atomic rows.",
        },
        "aggregate": aggregate,
        "cases": cases,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    lines = [
        "# CD-45 Same-Operator Standard-RLM Program Trace Exhibit",
        "",
        "No model calls were made. This artifact extracts representative generated-program behavior from completed CD-45 same-operator standard-`rlms` trajectories.",
        "",
        "## Aggregate Trace Coverage",
        "",
        "| Variant | Rows | Exact | Mean score | Cost | Tool calls | Code blocks | Failure classes |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for name, stats in aggregate.items():
        failures = ", ".join(f"{k}:{v}" for k, v in stats["failure_counts"].items())
        lines.append(
            f"| `{name}` | {stats['n']} | {stats['exact_count']}/{stats['n']} | "
            f"{stats['mean_score']*100:.1f}% | ${stats['total_cost_usd']:.6f} | "
            f"{stats['total_tool_calls']} | {stats['total_code_blocks']} | {failures} |"
        )

    lines.extend(
        [
            "",
            "## Representative Cases",
            "",
            "| Example | Reason | Convenience pred | Convenience class | Atomic pred | Atomic class |",
            "|---|---|---|---|---|---|",
        ]
    )
    for case in cases:
        conv = case["same_ops_convenience"]
        atomic = case["same_ops_atomic"]
        lines.append(
            f"| `{case['example_id']}` | {case['selection_reason']} | "
            f"{clean(conv.get('prediction') if conv.get('available') else '', 80)} | "
            f"{conv.get('failure_class', 'missing')} | "
            f"{clean(atomic.get('prediction') if atomic.get('available') else '', 80)} | "
            f"{atomic.get('failure_class', 'missing')} |"
        )

    for case in cases:
        lines.extend(["", f"### Example `{case['example_id']}`", "", case["selection_reason"], ""])
        for variant in ["same_ops_convenience", "same_ops_atomic"]:
            row = case[variant]
            if not row.get("available"):
                continue
            lines.extend(
                [
                    f"#### `{variant}`",
                    "",
                    f"- Group/length: `{row['task_group']}` / `{row['context_len']}`.",
                    f"- Gold/prediction/score: `{row['gold']}` / `{row['prediction']}` / `{row['score']}`.",
                    f"- Failure class: `{row['failure_class']}`; cost `${float(row.get('cost_usd') or 0.0):.6f}`; iterations `{row['iteration_count']}`; code blocks `{row['code_block_count']}`; tool calls `{row['tool_call_count']}`.",
                    f"- Tools: `{clean(row.get('tool_names'), 220)}`.",
                    f"- Raw final response: `{clean(row.get('raw_response'), 220)}`.",
                    "",
                ]
            )
            for idx, block in enumerate(row["selected_code_blocks"], start=1):
                lines.extend(
                    [
                        f"Selected code block {idx} (iteration {block['iteration']}):",
                        "",
                        "```python",
                        block["code"],
                        "```",
                    ]
                )
                if block["stdout"]:
                    lines.extend(["", "Output preview:", "", "```text", block["stdout"], "```"])
                if block["error"] or block["stderr"]:
                    lines.extend(["", "Error/stderr preview:", "", "```text", block["error"] or block["stderr"], "```"])
                lines.append("")

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(payload["aggregate"], indent=2, sort_keys=True))
    print(f"Wrote {OUT_JSON.relative_to(ROOT)}")
    print(f"Wrote {OUT_MD.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
