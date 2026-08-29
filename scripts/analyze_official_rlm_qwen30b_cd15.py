#!/usr/bin/env python3
"""Analyze the official RLM-Qwen3-30B-A3B frozen CD-15 run.

Fourteen rows were returned before the fifteenth exceeded the predeclared
1,500-second row cap. The raw JSONL is retained verbatim. This script creates a
derived adjudicated table, paired tests, a compact trace exhibit, and a report.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW = PROJECT_ROOT / "results" / "official_rlm_qwen30b_cd15_20260719.jsonl"
DEFAULT_MANIFEST = PROJECT_ROOT / "results" / "oolong_context_disjoint_cd15_repeatability_manifest_20260715.json"

POD_RENTED_UTC = datetime.fromisoformat("2026-07-18T23:37:12+00:00")
ROW_CAP_SECONDS = 1500.0
POD_RATE_USD_PER_HOUR = 2.99
RUNPOD_BILLING_ROWS = [
    {"date": "2026-07-18", "amount_usd": 1.0079400367103517, "time_billed_ms": 1202425},
    {"date": "2026-07-19", "amount_usd": 11.501909890561365, "time_billed_ms": 13748119},
]

LOCAL_REPL_PATH = re.compile("/var/" + r"folders/[^\s'\"<>]+/context_0\.txt")


def sanitize_trace_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    return LOCAL_REPL_PATH.sub("<RLM_CONTEXT_FILE>", value)


def exact_binomial_two_sided(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(0, min(b, c) + 1)) / (2**n)
    return min(1.0, 2.0 * tail)


def paired(first: dict[str, bool], second: dict[str, bool]) -> dict[str, Any]:
    ids = sorted(set(first) & set(second))
    b = sum(first[i] and not second[i] for i in ids)
    c = sum(second[i] and not first[i] for i in ids)
    return {
        "n": len(ids),
        "first_only": b,
        "second_only": c,
        "two_sided_exact_p": exact_binomial_two_sided(b, c),
    }


def compact_code_block(block: dict[str, Any]) -> dict[str, Any]:
    result = str(block.get("result", ""))
    return {
        "code": sanitize_trace_text(block.get("code", "")),
        "result_preview": sanitize_trace_text(result[:2000]),
        "result_characters": len(result),
        "execution_time": block.get("execution_time"),
    }


def compact_row(row: dict[str, Any]) -> dict[str, Any]:
    iterations = []
    for item in (row.get("trajectory") or {}).get("iterations", []):
        iterations.append(
            {
                "iteration": item.get("iteration"),
                "response": sanitize_trace_text(item.get("response", "")),
                "final_answer": sanitize_trace_text(item.get("final_answer")),
                "iteration_time": item.get("iteration_time"),
                "code_blocks": [compact_code_block(block) for block in item.get("code_blocks", [])],
            }
        )
    compact = {
        key: row.get(key)
        for key in (
            "run_id",
            "phase",
            "created_utc",
            "example_id",
            "task_group",
            "task",
            "answer_type",
            "context_len",
            "question",
            "gold",
            "prediction",
            "score",
            "exact",
            "elapsed_s",
            "error",
            "response",
            "usage_summary",
            "iteration_count",
            "code_block_count",
        )
    } | {"iterations": iterations}
    for key, value in list(compact.items()):
        compact[key] = sanitize_trace_text(value)
    return compact


def method_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "n": len(rows),
        "completed": sum(not row.get("error") for row in rows),
        "errors": sum(bool(row.get("error")) for row in rows),
        "exact_count": sum(bool(row.get("exact")) for row in rows),
        "exact_rate": sum(bool(row.get("exact")) for row in rows) / len(rows),
        "score_sum": sum(float(row.get("score", 0.0)) for row in rows),
        "mean_score": sum(float(row.get("score", 0.0)) for row in rows) / len(rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", default=str(DEFAULT_RAW.relative_to(PROJECT_ROOT)))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST.relative_to(PROJECT_ROOT)))
    parser.add_argument("--prefix", default="results/official_rlm_qwen30b_cd15_20260719")
    args = parser.parse_args()

    raw_path = PROJECT_ROOT / args.raw
    manifest_path = PROJECT_ROOT / args.manifest
    prefix = PROJECT_ROOT / args.prefix
    missing_inputs = [path for path in (raw_path, manifest_path) if not path.exists()]
    if missing_inputs:
        print("LOCAL_ONLY: required restricted inputs are intentionally withheld from the anonymous release.")
        for path in missing_inputs:
            print(f"  withheld input: {path.relative_to(PROJECT_ROOT)}")
        print("Run `python3 verify_release.py` for public aggregate verification.")
        raise SystemExit(2)
    raw_rows = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_rows = {str(row["id"]): row for row in manifest["examples"]}
    raw_by_id = {str(row["example_id"]): row for row in raw_rows}
    missing = sorted(set(manifest_rows) - set(raw_by_id))
    if len(raw_rows) != 14 or len(missing) != 1:
        raise ValueError(f"Expected 14 raw rows and one missing row; got {len(raw_rows)} and {missing}")

    last_completed_at = datetime.fromisoformat(raw_rows[-1]["created_utc"])
    timeout_row_meta = manifest_rows[missing[0]]
    timeout_row = {
        "run_id": raw_rows[0]["run_id"],
        "phase": "scale",
        "created_utc": (last_completed_at + timedelta(seconds=ROW_CAP_SECONDS)).isoformat(),
        "example_id": missing[0],
        "task_group": timeout_row_meta["task_group"],
        "task": timeout_row_meta["task"],
        "answer_type": timeout_row_meta["answer_type"],
        "context_len": timeout_row_meta["context_len"],
        "question": timeout_row_meta["question"],
        "gold": str(timeout_row_meta["logged_outcomes"]["slm_qparsed_typed"]["gold"]),
        "prediction": "",
        "score": 0.0,
        "exact": False,
        "elapsed_s": ROW_CAP_SECONDS,
        "error": "Timeout: exceeded predeclared 1500-second outer row cap; no response returned",
        "response": "",
        "usage_summary": None,
        "trajectory": None,
        "iteration_count": 0,
        "code_block_count": 0,
        "derived_timeout_adjudication": True,
    }
    adjudicated = raw_rows + [timeout_row]
    adjudicated_by_id = {str(row["example_id"]): row for row in adjudicated}

    baselines: dict[str, dict[str, bool]] = defaultdict(dict)
    baseline_scores: dict[str, list[float]] = defaultdict(list)
    for example_id, row in manifest_rows.items():
        for name, outcome in row["logged_outcomes"].items():
            score = float(outcome["correct"])
            baselines[name][example_id] = score >= 1.0
            baseline_scores[name].append(score)
    official_exact = {example_id: bool(row["exact"]) for example_id, row in adjudicated_by_id.items()}

    completed_latencies = [float(row["elapsed_s"]) for row in raw_rows]
    total_calls = 0
    total_input_tokens = 0
    total_output_tokens = 0
    for row in raw_rows:
        models = (row.get("usage_summary") or {}).get("model_usage_summaries", {})
        for usage in models.values():
            total_calls += int(usage.get("total_calls", 0))
            total_input_tokens += int(usage.get("total_input_tokens", 0))
            total_output_tokens += int(usage.get("total_output_tokens", 0))

    protocol_end = last_completed_at + timedelta(seconds=ROW_CAP_SECONDS)
    protocol_elapsed_s = (protocol_end - POD_RENTED_UTC).total_seconds()
    protocol_compute_usd = protocol_elapsed_s / 3600.0 * POD_RATE_USD_PER_HOUR
    actual_billed_usd = sum(row["amount_usd"] for row in RUNPOD_BILLING_ROWS)
    actual_billed_ms = sum(row["time_billed_ms"] for row in RUNPOD_BILLING_ROWS)

    by_group = {}
    for group in sorted({row["task_group"] for row in adjudicated}):
        by_group[group] = method_pack([row for row in adjudicated if row["task_group"] == group])

    comparisons = {
        "official_vs_slm_qparsed_typed": paired(official_exact, baselines["slm_qparsed_typed"]),
        "official_vs_direct_gemini25_flash": paired(official_exact, baselines["direct_gemini25_flash"]),
        "official_vs_standard_rlm_gemini25_flash": paired(
            official_exact, baselines["standard_rlm_gemini25_flash"]
        ),
        "official_vs_standard_rlm_gpt5": paired(official_exact, baselines["standard_rlm_gpt5"]),
    }
    summary = {
        "created_utc": datetime.now().astimezone().isoformat(),
        "evidence_role": "official trained RLM-policy same-contract diagnostic; not SRLM/lambda-RLM/RAH parity",
        "contract": {
            "manifest": str(manifest_path.relative_to(PROJECT_ROOT)),
            "input": "standard/unlabeled context_window_text",
            "root_prompt": "official Oolong instruction plus natural-language question",
            "scorer": "same local Oolong scorer as CD-15 baselines",
            "base_model": "Qwen/Qwen3-30B-A3B-Instruct-2507",
            "adapter": "mit-oasys/rlm-qwen3-30b-a3b-v0.1",
            "official_rlm_commit": "72d6940142ddfb84ee6be573dc999a37e633e671",
            "max_iterations": 20,
            "max_depth": 1,
            "enable_thinking": False,
            "max_completion_tokens": 4096,
            "sub_max_tokens": 4096,
            "row_cap_seconds": ROW_CAP_SECONDS,
        },
        "official_rlm_qwen30b": method_pack(adjudicated),
        "by_group": by_group,
        "baselines": {
            name: {
                "n": len(values),
                "exact_count": sum(baselines[name].values()),
                "exact_rate": sum(baselines[name].values()) / len(values),
                "mean_score": sum(values) / len(values),
            }
            for name, values in baseline_scores.items()
        },
        "paired_exact_tests": comparisons,
        "latency_and_trace": {
            "completed_rows": len(raw_rows),
            "timeout_rows": 1,
            "median_completed_row_s": statistics.median(completed_latencies),
            "max_completed_row_s": max(completed_latencies),
            "total_iterations_completed_rows": sum(int(row["iteration_count"]) for row in raw_rows),
            "total_code_blocks_completed_rows": sum(int(row["code_block_count"]) for row in raw_rows),
            "total_model_calls_completed_rows": total_calls,
            "total_input_tokens_completed_rows": total_input_tokens,
            "total_output_tokens_completed_rows": total_output_tokens,
        },
        "cost": {
            "gpu": "one 80GB-class RunPod GPU",
            "listed_rate_usd_per_hour": POD_RATE_USD_PER_HOUR,
            "protocol_accounted_compute_seconds_including_cold_start_and_timeout_cap": protocol_elapsed_s,
            "protocol_accounted_compute_usd": protocol_compute_usd,
            "actual_runpod_billed_ms": actual_billed_ms,
            "actual_runpod_spend_usd": actual_billed_usd,
            "overrun_usd": actual_billed_usd - protocol_compute_usd,
            "overrun_reason": (
                "The final request outlived the intended local alarm and the detached pod remained active after "
                "the local process died. Actual spend is reported for transparency; protocol-accounted compute "
                "is the deployment-comparison quantity."
            ),
            "openrouter_spend_usd": 0.0,
        },
        "raw_artifact": str(raw_path.relative_to(PROJECT_ROOT)),
        "raw_rows": len(raw_rows),
        "adjudicated_timeout_example_id": missing[0],
    }

    json_path = prefix.with_name(prefix.name + "_analysis.json")
    compact_path = prefix.with_name(prefix.name + "_compact_trace.jsonl")
    md_path = prefix.with_name(prefix.name + "_analysis.md")
    adjudicated_path = prefix.with_name(prefix.name + "_adjudicated.jsonl")
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    compact_path.write_text(
        "".join(json.dumps(compact_row(row), ensure_ascii=True) + "\n" for row in raw_rows),
        encoding="utf-8",
    )
    adjudicated_path.write_text(
        "".join(json.dumps(compact_row(row), ensure_ascii=True) + "\n" for row in adjudicated),
        encoding="utf-8",
    )

    official = summary["official_rlm_qwen30b"]
    direct = summary["baselines"]["direct_gemini25_flash"]
    slm = summary["baselines"]["slm_qparsed_typed"]
    md = f"""# Official RLM-Qwen3-30B-A3B CD-15 Same-Contract Diagnostic

## Result

| Method | Exact | Mean Oolong score | Cost role |
|---|---:|---:|---|
| Official RLM-Qwen3-30B-A3B | {official['exact_count']}/{official['n']} ({official['exact_rate']:.1%}) | {official['mean_score']:.1%} | ${protocol_compute_usd:.3f} protocol-accounted RunPod compute |
| Standard RLM/Gemini stored CD-15 | {summary['baselines']['standard_rlm_gemini25_flash']['exact_count']}/15 | {summary['baselines']['standard_rlm_gemini25_flash']['mean_score']:.1%} | Stored same-row baseline |
| Direct Gemini stored CD-15 | {direct['exact_count']}/15 | {direct['mean_score']:.1%} | Stored same-row baseline |
| SLM+typed stored CD-15 | {slm['exact_count']}/15 | {slm['mean_score']:.1%} | Stored same-row baseline |

The official policy completed 14/15 rows and generated {summary['latency_and_trace']['total_code_blocks_completed_rows']}
code blocks across {summary['latency_and_trace']['total_iterations_completed_rows']} iterations. The final 262k-token-window
row is scored as a timeout under the predeclared 1,500-second outer cap.

## Paired exact tests

| Comparison (official first) | Official-only | Comparator-only | Two-sided exact p |
|---|---:|---:|---:|
| vs SLM+typed | {comparisons['official_vs_slm_qparsed_typed']['first_only']} | {comparisons['official_vs_slm_qparsed_typed']['second_only']} | {comparisons['official_vs_slm_qparsed_typed']['two_sided_exact_p']:.4f} |
| vs direct Gemini | {comparisons['official_vs_direct_gemini25_flash']['first_only']} | {comparisons['official_vs_direct_gemini25_flash']['second_only']} | {comparisons['official_vs_direct_gemini25_flash']['two_sided_exact_p']:.4f} |
| vs standard RLM/Gemini | {comparisons['official_vs_standard_rlm_gemini25_flash']['first_only']} | {comparisons['official_vs_standard_rlm_gemini25_flash']['second_only']} | {comparisons['official_vs_standard_rlm_gemini25_flash']['two_sided_exact_p']:.4f} |

## Interpretation

This closes the narrowest version of the official-policy omission: the model is an official post-trained
RLM policy and was run through the authors' current canonical harness and published Oolong settings on the
same frozen input/scorer contract. It does not establish parity with SRLM, lambda-RLM, or RAH. On this
diagnostic it improves numerically over direct Gemini but remains below SLM+typed and does not reverse the
task-conditional deployment recommendation.

## Cost and incident boundary

Protocol-accounted compute, including cold start and the final timeout cap, is ${protocol_compute_usd:.3f}.
Actual RunPod billing was ${actual_billed_usd:.3f}; the difference is an infrastructure teardown overrun after
the local process died, not model inference required by the protocol. OpenRouter spend was $0.00.
"""
    md_path.write_text(md, encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Wrote {json_path.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {compact_path.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {adjudicated_path.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {md_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
