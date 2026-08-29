#!/usr/bin/env python3
"""Analyze the stopped official RLM-Qwen CD-45 completion attempt.

The remaining 30 rows were frozen before any calls. The run expanded after a
three-row preflight, then stopped after two consecutive serving errors as
predeclared. This script preserves the returned prefix as deployability and
stability evidence; it deliberately does not estimate a CD-45 accuracy row.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW = PROJECT_ROOT / "results" / "official_rlm_qwen30b_cd30_completion_20260719.jsonl"
DEFAULT_MANIFEST = (
    PROJECT_ROOT / "results" / "oolong_context_disjoint_cd30_official_qwen_remaining_manifest_20260719.json"
)
DEFAULT_REUSE = PROJECT_ROOT / "results" / "oolong_context_disjoint_cd15_repeatability_manifest_20260715.json"
DEFAULT_RUN_SUMMARY = (
    PROJECT_ROOT / "results" / "official_rlm_qwen30b_cd30_completion_20260719_summary.json"
)

POD_RATE_USD_PER_HOUR = 2.99
LOCAL_REPL_PATH = re.compile("/var/" + r"folders/[^\s'\"<>]+/context_0\.txt")
CONTEXT_LIMIT_FRAGMENT = (
    "maximum context length is 16384 tokens. However, you requested 4096 output tokens "
    "and your prompt contains at least 12289 input tokens"
)


def sanitize(value: Any) -> Any:
    if isinstance(value, str):
        return LOCAL_REPL_PATH.sub("<RLM_CONTEXT_FILE>", value)
    return value


def compact_code_block(block: dict[str, Any]) -> dict[str, Any]:
    result = str(block.get("result", ""))
    return {
        "code": sanitize(block.get("code", "")),
        "result_preview": sanitize(result[:2000]),
        "result_characters": len(result),
        "execution_time": block.get("execution_time"),
    }


def compact_row(row: dict[str, Any]) -> dict[str, Any]:
    iterations = []
    for item in (row.get("trajectory") or {}).get("iterations", []):
        iterations.append(
            {
                "iteration": item.get("iteration"),
                "response": sanitize(item.get("response", "")),
                "final_answer": sanitize(item.get("final_answer")),
                "iteration_time": item.get("iteration_time"),
                "code_blocks": [compact_code_block(block) for block in item.get("code_blocks", [])],
            }
        )
    keys = (
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
    compact = {key: sanitize(row.get(key)) for key in keys}
    compact["iterations"] = iterations
    return compact


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", default=str(DEFAULT_RAW.relative_to(PROJECT_ROOT)))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST.relative_to(PROJECT_ROOT)))
    parser.add_argument("--reuse", default=str(DEFAULT_REUSE.relative_to(PROJECT_ROOT)))
    parser.add_argument("--run-summary", default=str(DEFAULT_RUN_SUMMARY.relative_to(PROJECT_ROOT)))
    parser.add_argument(
        "--prefix", default="results/official_rlm_qwen30b_cd30_completion_20260719_stoprule"
    )
    args = parser.parse_args()

    raw_path = PROJECT_ROOT / args.raw
    manifest_path = PROJECT_ROOT / args.manifest
    reuse_path = PROJECT_ROOT / args.reuse
    run_summary_path = PROJECT_ROOT / args.run_summary
    prefix = PROJECT_ROOT / args.prefix

    rows = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    reuse = json.loads(reuse_path.read_text(encoding="utf-8"))
    run_summary = json.loads(run_summary_path.read_text(encoding="utf-8"))

    manifest_ids = [str(row["id"]) for row in manifest["examples"]]
    reuse_ids = {str(row["id"]) for row in reuse["examples"]}
    row_ids = [str(row["example_id"]) for row in rows]
    errors = [row for row in rows if row.get("error")]
    completed = [row for row in rows if not row.get("error")]

    assert len(manifest_ids) == 30
    assert len(set(manifest_ids)) == 30
    assert not (set(manifest_ids) & reuse_ids)
    assert len(rows) == 8 and len(set(row_ids)) == 8
    preflight_ids = {str(value) for value in run_summary["preflight_ids"]}
    expected_order = [row_id for row_id in manifest_ids if row_id not in preflight_ids]
    assert set(row_ids[:3]) == preflight_ids
    assert row_ids[3:] == expected_order[:5]
    assert len(completed) == 6 and len(errors) == 2
    assert all(CONTEXT_LIMIT_FRAGMENT in row["error"] for row in errors)
    assert all(int(row["context_len"]) >= 8510 for row in errors)
    assert run_summary["stability_stop"] == "stop: 2 consecutive row errors"
    assert run_summary["summary"] == {
        "n": 8,
        "completed": 6,
        "errors": 2,
        "exact_count": 2,
        "score_sum": 3.125,
        "mean_score": 0.390625,
        "elapsed_s": 546.1071295000011,
        "iterations": 57,
        "code_blocks": 55,
    }
    assert run_summary["preflight_summary"]["n"] == 3
    assert run_summary["preflight_summary"]["completed"] == 3
    assert run_summary["preflight_summary"]["errors"] == 0
    assert run_summary["preflight_summary"]["exact_count"] == 2
    assert run_summary["cleanup"] == [{"resource": "pods", "id": "a7c94t7te1le6j", "status": 204}]
    assert run_summary["watchdog_cancelled"] is True

    created = datetime.fromisoformat(run_summary["events"][0]["at"])
    finished = datetime.fromisoformat(run_summary["finished_utc"])
    provider_runtime_s = (finished - created).total_seconds()
    provider_rate_estimate_usd = provider_runtime_s / 3600.0 * POD_RATE_USD_PER_HOUR

    model_calls = input_tokens = output_tokens = 0
    for row in rows:
        for usage in (row.get("usage_summary") or {}).get("model_usage_summaries", {}).values():
            model_calls += int(usage.get("total_calls", 0))
            input_tokens += int(usage.get("total_input_tokens", 0))
            output_tokens += int(usage.get("total_output_tokens", 0))

    by_group: dict[str, dict[str, Any]] = {}
    for group in sorted({str(row["task_group"]) for row in rows}):
        group_rows = [row for row in rows if row["task_group"] == group]
        by_group[group] = {
            "attempted": len(group_rows),
            "completed": sum(not row.get("error") for row in group_rows),
            "errors": sum(bool(row.get("error")) for row in group_rows),
            "exact_count": sum(bool(row.get("exact")) for row in group_rows),
        }

    analysis = {
        "created_utc": datetime.now().astimezone().isoformat(),
        "evidence_role": (
            "prospectively frozen official-policy completion attempt stopped under its predeclared stability "
            "rule; deployability evidence only, not a CD-45 accuracy estimate"
        ),
        "nonclaims": [
            "No pooled CD-45 official-policy accuracy or mean-score row is estimated.",
            "The returned prefix is not treated as random or representative after the stability stop.",
            "The protocol was not resumed with a larger context limit or smaller output cap after outcomes were seen.",
            "This is not an SRLM, lambda-RLM, or RAH reproduction.",
        ],
        "contract": {
            "remaining_manifest": str(manifest_path.relative_to(PROJECT_ROOT)),
            "prior_cd15_manifest": str(reuse_path.relative_to(PROJECT_ROOT)),
            "remaining_n": 30,
            "overlap_with_prior_cd15": 0,
            "selection_rule": manifest["metadata"]["selection_rule"],
            "outcome_blind": manifest["metadata"]["outcome_blind"],
            "official_rlm_commit": run_summary["official_rlm_commit"],
            "base_model": run_summary["base_model"],
            "adapter_model": run_summary["adapter_model"],
            "settings": run_summary["model_card_settings"],
            "preflight_n": 3,
            "max_total_errors": 3,
            "max_consecutive_errors": 2,
        },
        "returned_prefix": {
            **run_summary["summary"],
            "exact_rate_over_returned_prefix_descriptive_only": 2 / 8,
            "mean_score_over_returned_prefix_descriptive_only": 3.125 / 8,
            "median_completed_row_s": statistics.median(float(row["elapsed_s"]) for row in completed),
            "row_ids": row_ids,
            "by_group": by_group,
        },
        "preflight": run_summary["preflight_summary"],
        "stop": {
            "trigger": run_summary["stability_stop"],
            "error_count": len(errors),
            "error_example_ids": [str(row["example_id"]) for row in errors],
            "error_type": "official serving context limit exceeded by at least one token",
            "max_model_len": 16384,
            "minimum_input_tokens": 12289,
            "requested_output_tokens": 4096,
            "minimum_total_tokens": 16385,
        },
        "usage": {
            "model_calls": model_calls,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "iterations": sum(int(row["iteration_count"]) for row in rows),
            "code_blocks": sum(int(row["code_block_count"]) for row in rows),
        },
        "cost": {
            "listed_rate_usd_per_hour": POD_RATE_USD_PER_HOUR,
            "provider_runtime_seconds_created_to_cleanup": provider_runtime_s,
            "provider_rate_estimate_usd": provider_rate_estimate_usd,
            "billing_history_query_result": [],
            "billing_history_note": "RunPod billing endpoint had not populated this pod at analysis time.",
            "openrouter_spend_usd": 0.0,
        },
        "cleanup": run_summary["cleanup"],
        "watchdog_cancelled": run_summary["watchdog_cancelled"],
        "raw_artifact": str(raw_path.relative_to(PROJECT_ROOT)),
    }

    json_path = prefix.with_name(prefix.name + "_analysis.json")
    md_path = prefix.with_name(prefix.name + "_analysis.md")
    compact_path = prefix.with_name(prefix.name + "_compact_trace.jsonl")
    json_path.write_text(json.dumps(analysis, indent=2), encoding="utf-8")
    compact_path.write_text(
        "".join(json.dumps(compact_row(row), ensure_ascii=True) + "\n" for row in rows),
        encoding="utf-8",
    )

    md = f"""# Official RLM-Qwen CD-45 Completion Stop-Rule Audit

## Outcome

The remaining 30 examples were frozen before calls by subtracting the prior CD-15
manifest from the parent context-window-disjoint CD-45 manifest. The three-row
preflight completed without errors (2/3 exact), so the predeclared gate expanded.
The run returned eight rows: six completed and two consecutive serving errors.
The predeclared stability stop then fired. **This is not a completed CD-45 accuracy
row, and the 2/8 descriptive prefix accuracy is not used for method ranking.**

| Quantity | Value |
|---|---:|
| Frozen remaining manifest | 30 rows |
| Overlap with prior CD-15 | 0 rows |
| Returned prefix | 8 rows |
| Completed / errors | 6 / 2 |
| Generated iterations / code blocks | 57 / 55 |
| Stability trigger | 2 consecutive errors |

## Failure mechanism

Both errors came from the official serving configuration: the model advertises a
16,384-token maximum, while each failing internal request contained at least
12,289 input tokens and requested 4,096 output tokens, totaling at least 16,385.
The two failures occurred on examples {', '.join(analysis['stop']['error_example_ids'])}.
Because the model-card settings and stop rule were fixed before the run, we did
not reduce the completion cap, raise the model context limit, reorder rows, or
resume the prefix after observing this failure.

## Cost and cleanup

The pod existed for {provider_runtime_s:.2f} seconds from provider creation to
successful deletion (HTTP 204). At the listed $2.99/hour rate, this is a
provider-rate estimate of ${provider_rate_estimate_usd:.4f}; the billing-history
endpoint had not yet populated an itemized charge. The detached watchdog was
cancelled after normal cleanup. OpenRouter spend was $0.00.

## Interpretation boundary

This result strengthens the audit's deployability evidence: a prospectively
locked official-policy scale attempt encountered a deterministic serving-contract
boundary under published settings. It does not strengthen or weaken the CD-15
accuracy ranking, does not estimate full-CD-45 performance, and does not establish
parity with SRLM, lambda-RLM, or RAH.
"""
    md_path.write_text(md, encoding="utf-8")
    print(json.dumps(analysis, indent=2))
    print(f"Wrote {json_path.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {md_path.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {compact_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
