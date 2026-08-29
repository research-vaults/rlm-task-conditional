#!/usr/bin/env python3
"""Audit recorded attempted costs for official-RLM runs.

This script is intentionally conservative. It reports only costs that are
present in local model-call logs. Failed RLM attempts with empty usage summaries
are counted, but their possible provider-side billed partial calls are not
imputed.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "_reproduced" / "attempted_cost_audit_latest.json",
    )
    args = parser.parse_args()
    calls_by_run: dict[str, list[dict]] = defaultdict(list)
    raw_errors: dict[tuple[str, str], str | None] = {}

    for path in RESULTS.glob("model_calls*.jsonl"):
        for row in read_jsonl(path):
            if row.get("purpose") == "official_rlm_completion" or row.get("method") == "official_rlm_depth1":
                row["_source_file"] = str(path.relative_to(ROOT))
                calls_by_run[row.get("run_id", "UNKNOWN")].append(row)

    for path in RESULTS.glob("raw_results*.jsonl"):
        for row in read_jsonl(path):
            if row.get("method") == "official_rlm_depth1":
                key = (row.get("run_id", "UNKNOWN"), row.get("example_id", "UNKNOWN"))
                raw_errors[key] = row.get("final_error")

    if not calls_by_run:
        raise SystemExit(
            "No results/model_calls*.jsonl inputs containing official-RLM "
            "completion rows were found. The review archive excludes those "
            "source logs; no zero audit was written."
        )

    runs: list[dict] = []
    totals = {
        "runs": 0,
        "attempt_rows": 0,
        "completed_rows": 0,
        "error_rows": 0,
        "zero_usage_error_rows": 0,
        "recorded_attempted_cost_usd": 0.0,
        "recorded_completed_cost_usd": 0.0,
        "recorded_error_cost_usd": 0.0,
    }

    for run_id, rows in sorted(calls_by_run.items()):
        rows = sorted(rows, key=lambda r: (r.get("timestamp", ""), r.get("example_id", "")))
        n = len(rows)
        completed = [r for r in rows if not r.get("error")]
        errors = [r for r in rows if r.get("error")]
        zero_usage_errors = [
            r for r in errors
            if not r.get("prompt_tokens") and not r.get("completion_tokens") and not r.get("usage_by_model")
        ]
        recorded_attempted_cost = sum(float(r.get("estimated_cost_usd") or 0.0) for r in rows)
        recorded_completed_cost = sum(float(r.get("estimated_cost_usd") or 0.0) for r in completed)
        recorded_error_cost = sum(float(r.get("estimated_cost_usd") or 0.0) for r in errors)
        prompt_tokens = sum(int(r.get("prompt_tokens") or 0) for r in rows)
        completion_tokens = sum(int(r.get("completion_tokens") or 0) for r in rows)
        examples = sorted({r.get("example_id", "UNKNOWN") for r in rows})
        error_examples = []
        for r in errors:
            key = (run_id, r.get("example_id", "UNKNOWN"))
            error_examples.append({
                "example_id": r.get("example_id"),
                "error": r.get("error"),
                "raw_final_error": raw_errors.get(key),
                "recorded_cost_usd": round(float(r.get("estimated_cost_usd") or 0.0), 8),
                "prompt_tokens": int(r.get("prompt_tokens") or 0),
                "completion_tokens": int(r.get("completion_tokens") or 0),
            })

        run_summary = {
            "run_id": run_id,
            "model": rows[0].get("model") if rows else None,
            "source_files": sorted({r.get("_source_file") for r in rows}),
            "n_attempt_rows": n,
            "n_unique_examples": len(examples),
            "n_completed_rows": len(completed),
            "n_error_rows": len(errors),
            "n_zero_usage_error_rows": len(zero_usage_errors),
            "recorded_attempted_cost_usd": round(recorded_attempted_cost, 8),
            "recorded_completed_cost_usd": round(recorded_completed_cost, 8),
            "recorded_error_cost_usd": round(recorded_error_cost, 8),
            "recorded_attempted_cost_per_row_usd": round(recorded_attempted_cost / n, 8) if n else 0.0,
            "recorded_completed_cost_per_completed_row_usd": round(recorded_completed_cost / len(completed), 8) if completed else 0.0,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "error_examples": error_examples,
            "interpretation": (
                "Complete attempted-cost lower bound: all failed rows have recorded usage/cost."
                if errors and not zero_usage_errors else
                "Incomplete attempted-cost lower bound: at least one failed row has zero recorded usage/cost."
                if zero_usage_errors else
                "No failed RLM completion rows recorded in this run."
            ),
        }
        runs.append(run_summary)

        totals["runs"] += 1
        totals["attempt_rows"] += n
        totals["completed_rows"] += len(completed)
        totals["error_rows"] += len(errors)
        totals["zero_usage_error_rows"] += len(zero_usage_errors)
        totals["recorded_attempted_cost_usd"] += recorded_attempted_cost
        totals["recorded_completed_cost_usd"] += recorded_completed_cost
        totals["recorded_error_cost_usd"] += recorded_error_cost

    for key in ["recorded_attempted_cost_usd", "recorded_completed_cost_usd", "recorded_error_cost_usd"]:
        totals[key] = round(totals[key], 8)

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Official-RLM completion rows in local results/model_calls*.jsonl.",
        "cost_interpretation": (
            "Costs are recorded-provider or token-estimated costs in local logs. "
            "This audit does not impute provider billing for failed attempts whose usage summaries are empty."
        ),
        "totals": totals,
        "runs": runs,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}")
    print(json.dumps(totals, indent=2))


if __name__ == "__main__":
    main()
