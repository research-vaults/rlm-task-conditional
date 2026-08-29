#!/usr/bin/env python3
"""Create compact method-trace examples for the CD-45 Oolong slice.

This is a no-call analysis over existing CD-45 outputs and traces. It avoids
quoting long contexts; the JSON/Markdown artifacts summarize method behavior,
prediction/cost/error, SLM worker statistics, and whether raw traces are
available for each route.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"

CASE_SPECS = [
    {
        "case_id": "slm_and_direct_fix_standard_rlm",
        "example_id": "912090010",
        "reason": "SLM+typed, direct Gemini, and GPT-5 RLM all answer the comparison correctly; standard RLM/Gemini collapses to a tie.",
    },
    {
        "case_id": "slm_and_direct_fix_standard_and_gpt5_rlm",
        "example_id": "412040009",
        "reason": "SLM+typed and direct Gemini answer a least-label question correctly; standard RLM/Gemini chooses the wrong label and GPT-5 RLM times out.",
    },
    {
        "case_id": "structured_routes_fix_direct",
        "example_id": "312030020",
        "reason": "Both RLM controllers and SLM+typed recover the most frequent user; direct whole-context Gemini selects a different user.",
    },
    {
        "case_id": "rlm_and_direct_fix_slm",
        "example_id": "710070026",
        "reason": "The SLM row labels are locally exact, but a tie/normalization edge in typed aggregation returns the wrong least label; standard RLM and direct Gemini answer correctly.",
    },
    {
        "case_id": "long_context_gpt5_scaffold_timeout",
        "example_id": "218020026",
        "reason": "At 262k context, SLM+typed, standard RLM/Gemini, and direct Gemini agree; GPT-5 standard RLM times out under the strict row cap.",
    },
]

METHOD_FILES = {
    "slm_qparsed_typed": RESULTS / "oolong_context_disjoint_n45_slm_labeler_question_parsed_typed_20260715.csv",
    "standard_rlm_gemini25_flash": RESULTS / "oolong_context_disjoint_n45_rlm_20260715.csv",
    "standard_rlm_gpt5": RESULTS / "oolong_context_disjoint_n45_gpt5_rlm_strict_20260715.csv",
    "direct_gemini25_flash": RESULTS / "oolong_context_disjoint_n45_direct_controller_gemini25flash_20260715.csv",
}

TRACE_FILES = {
    "slm_qparsed_typed": RESULTS / "oolong_context_disjoint_n45_slm_labeler_typed_20260715_trace.jsonl",
    "direct_gemini25_flash": RESULTS / "oolong_context_disjoint_n45_direct_controller_gemini25flash_20260715_trace.jsonl",
}

OUT_JSON = RESULTS / "oolong_context_disjoint_cd45_trace_examples_20260715.json"
OUT_MD = RESULTS / "oolong_context_disjoint_cd45_trace_examples_20260715.md"


def read_csv_by_id(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return {row["example_id"]: row for row in csv.DictReader(f)}


def read_trace_by_id(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                out[str(row["example_id"])] = row
    return out


def method_row(row: dict[str, str]) -> dict[str, Any]:
    return {
        "prediction": row.get("prediction", ""),
        "gold": row.get("gold", ""),
        "correct": float(row.get("correct") or 0.0),
        "cost_usd": float(row.get("cost_usd") or 0.0),
        "error": row.get("error", ""),
    }


def slm_trace_summary(trace: dict[str, Any] | None) -> dict[str, Any]:
    if not trace:
        return {"trace_available": False}
    blocks = trace.get("blocks") or []
    return {
        "trace_available": True,
        "model": trace.get("model"),
        "row_count": trace.get("row_count"),
        "block_count": trace.get("block_count"),
        "typed_ops": trace.get("typed_ops"),
        "typed_status": trace.get("typed_status"),
        "row_label_accuracy": trace.get("row_label_accuracy"),
        "allowed_labels": trace.get("allowed_labels"),
        "input_tokens": trace.get("input_tokens"),
        "output_tokens": trace.get("output_tokens"),
        "estimated_cost_usd": trace.get("estimated_cost_usd"),
        "first_block_rows": [blocks[0].get("start_row"), blocks[0].get("end_row")] if blocks else None,
        "raw_response_preview": str(trace.get("raw_response", ""))[:240],
    }


def direct_trace_summary(trace: dict[str, Any] | None) -> dict[str, Any]:
    if not trace:
        return {"trace_available": False}
    return {
        "trace_available": True,
        "model": trace.get("model"),
        "input_tokens": trace.get("input_tokens"),
        "output_tokens": trace.get("output_tokens"),
        "latency_s": trace.get("latency_s"),
        "raw_response_preview": str(trace.get("raw_response", ""))[:240],
    }


def main() -> None:
    method_tables = {name: read_csv_by_id(path) for name, path in METHOD_FILES.items()}
    trace_tables = {name: read_trace_by_id(path) for name, path in TRACE_FILES.items()}

    cases = []
    for spec in CASE_SPECS:
        eid = spec["example_id"]
        base_row = method_tables["standard_rlm_gemini25_flash"][eid]
        methods = {name: method_row(table[eid]) for name, table in method_tables.items()}
        cases.append(
            {
                **spec,
                "task_group": base_row["task_group"],
                "context_len": int(base_row["context_len"]),
                "task": base_row["task"],
                "answer_type": base_row["answer_type"],
                "question": base_row["question"],
                "gold": base_row["gold"],
                "methods": methods,
                "trace_summaries": {
                    "slm_qparsed_typed": slm_trace_summary(trace_tables["slm_qparsed_typed"].get(eid)),
                    "direct_gemini25_flash": direct_trace_summary(trace_tables["direct_gemini25_flash"].get(eid)),
                    "standard_rlm_gemini25_flash": {
                        "trace_available": False,
                        "reason": "The CD-45 standard-RLM CSV stores prediction, cost, and error only; generated program text was not retained for this run.",
                    },
                    "standard_rlm_gpt5": {
                        "trace_available": False,
                        "reason": "The strict-stop GPT-5 RLM sensitivity stores prediction, cost, and error only; generated program text was not retained for this run.",
                    },
                },
            }
        )

    outcome_pattern_counts: dict[str, int] = {}
    all_ids = sorted(method_tables["standard_rlm_gemini25_flash"])
    for eid in all_ids:
        pattern = tuple(
            int(method_tables[m][eid].get("correct", "0") in {"1", "1.0"})
            for m in ["standard_rlm_gemini25_flash", "standard_rlm_gpt5", "slm_qparsed_typed", "direct_gemini25_flash"]
        )
        key = "rlm_gemini,gpt5_rlm,slm,direct=" + "".join(str(v) for v in pattern)
        outcome_pattern_counts[key] = outcome_pattern_counts.get(key, 0) + 1

    payload = {
        "metadata": {
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "purpose": "No-call representative trace examples over paired CD-45 outputs.",
            "source_files": {k: str(v.relative_to(ROOT)) for k, v in METHOD_FILES.items()},
            "trace_files": {k: str(v.relative_to(ROOT)) for k, v in TRACE_FILES.items()},
            "method_order_for_patterns": ["standard_rlm_gemini25_flash", "standard_rlm_gpt5", "slm_qparsed_typed", "direct_gemini25_flash"],
            "rlm_trace_limitation": "CD-45 standard-RLM generated program text is not available in the stored artifacts; only predictions, costs, and errors are retained.",
        },
        "summary": {
            "case_count": len(cases),
            "outcome_pattern_counts": dict(sorted(outcome_pattern_counts.items())),
        },
        "cases": cases,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# Oolong CD-45 Trace Examples",
        "",
        "No model calls were made. This artifact summarizes paired CD-45 outputs and available traces. Standard-RLM generated program text is not available for CD-45; the stored RLM artifacts contain prediction, cost, and error rows.",
        "",
        "## Outcome Pattern Counts",
        "",
        "Pattern order: standard RLM/Gemini, standard RLM/GPT-5, SLM+typed, direct Gemini.",
        "",
    ]
    for key, value in sorted(outcome_pattern_counts.items()):
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Representative Cases",
            "",
            "| case | example | group | len | gold | RLM/Gemini | RLM/GPT-5 | SLM+typed | direct |",
            "|---|---|---|---:|---|---|---|---|---|",
        ]
    )
    for case in cases:
        methods = case["methods"]
        lines.append(
            f"| {case['case_id']} | {case['example_id']} | {case['task_group']} | {case['context_len']} | {case['gold']} | "
            f"{methods['standard_rlm_gemini25_flash']['prediction']} ({methods['standard_rlm_gemini25_flash']['correct']:.0f}) | "
            f"{methods['standard_rlm_gpt5']['prediction'] or 'ERR'} ({methods['standard_rlm_gpt5']['correct']:.0f}) | "
            f"{methods['slm_qparsed_typed']['prediction']} ({methods['slm_qparsed_typed']['correct']:.0f}) | "
            f"{methods['direct_gemini25_flash']['prediction']} ({methods['direct_gemini25_flash']['correct']:.0f}) |"
        )
    for case in cases:
        slm = case["trace_summaries"]["slm_qparsed_typed"]
        direct = case["trace_summaries"]["direct_gemini25_flash"]
        lines.extend(
            [
                "",
                f"### {case['case_id']} (`{case['example_id']}`)",
                "",
                case["reason"],
                "",
                f"- Question: {case['question']}",
                f"- SLM worker: rows={slm.get('row_count')}, blocks={slm.get('block_count')}, typed_ops={slm.get('typed_ops')}, typed_status={slm.get('typed_status')}, row_label_accuracy={slm.get('row_label_accuracy')}",
                f"- Direct controller trace: input_tokens={direct.get('input_tokens')}, output_tokens={direct.get('output_tokens')}, latency_s={direct.get('latency_s')}",
            ]
        )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    print(f"Wrote {OUT_JSON.relative_to(ROOT)}")
    print(f"Wrote {OUT_MD.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
