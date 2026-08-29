#!/usr/bin/env python3
"""Analyze official-code lambda-RLM CD-15 attempts and paired baselines."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = PROJECT_ROOT / "results/oolong_context_disjoint_cd15_repeatability_manifest_20260715.json"
SELF_HOSTED_PROTOCOL = PROJECT_ROOT / "results/lambda_rlm_official_cd15_runpod_full_protocol_20260719.md"
BASE_PROTOCOL = PROJECT_ROOT / "results/lambda_rlm_official_cd15_protocol_20260719.md"
OFFICIAL_QWEN_ANALYSIS = PROJECT_ROOT / "results/official_rlm_qwen30b_cd15_20260719_analysis.json"
OFFICIAL_QWEN_ROWS = PROJECT_ROOT / "results/official_rlm_qwen30b_cd15_20260719_adjudicated.jsonl"
LAMBDA_REPO = PROJECT_ROOT / "external_repos/lambda-RLM"
EXPECTED = {
    "manifest_sha256": "6b16c98cd8a4cbb4261768e0334e5354e47f247d2f9f09788e99ac58bf15ec84",
    "lambda_repo_commit": "3874d393483dc4299101918cf8e9af670194bd88",
    "lambda_source_sha256": "3f0e0521f92e1e124e76aa4f717a7bf29c95386ff42b3faf6057d4fa320f42e6",
    "benchmark_source_sha256": "903d8f42a5d6ab512cdc126db54429aee278021841ef07b9e9732afcb034727a",
    "model": "Qwen/Qwen3-8B",
    "model_revision": "b968826d9c46dd6066d109eabc6255188de91218",
    "vllm_image": "vllm/vllm-openai:v0.21.0",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_rows(path: Path, run_id: str) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [row for row in csv.DictReader(handle) if row["run_id"] == run_id]


def exact_binomial_two_sided(b: int, c: int) -> float:
    n = b + c
    if not n:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(0, min(b, c) + 1)) / (2**n)
    return min(1.0, 2 * tail)


def baseline_rows(manifest: dict[str, Any], key: str) -> dict[str, int]:
    return {
        str(ex["id"]): int(float(ex["logged_outcomes"][key]["correct"]) >= 1.0)
        for ex in manifest["examples"]
    }


def paired(ours: dict[str, int], baseline: dict[str, int]) -> dict[str, Any]:
    ids = sorted(set(ours) & set(baseline))
    b = sum(ours[i] == 1 and baseline[i] == 0 for i in ids)
    c = sum(ours[i] == 0 and baseline[i] == 1 for i in ids)
    return {
        "n": len(ids),
        "ours_exact": sum(ours[i] for i in ids),
        "baseline_exact": sum(baseline[i] for i in ids),
        "b_ours_only": b,
        "c_baseline_only": c,
        "mcnemar_exact_two_sided_p": exact_binomial_two_sided(b, c),
    }


def classify_row(row: dict[str, Any]) -> str:
    combined = (row["error"] + " " + row["raw_response"]).lower()
    if "error code: 402" in combined or "depleted your monthly included credits" in combined:
        return "provider_credit_failure"
    if "error code: 404" in combined:
        return "provider_endpoint_failure"
    if row["error"]:
        return "timeout_or_runtime_failure" if "timeout" in row["error"].lower() else "runtime_failure"
    if float(row["correct"]) >= 1.0:
        return "strict_exact"
    raw = row["raw_response"].lower()
    gold = str(json.loads(row["gold"])).lower()
    if re.search(rf"(?<!\w){re.escape(gold)}(?!\w)", raw):
        return "latent_gold_output_contract_failure"
    return "semantic_or_aggregation_error"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--events", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--md-out", required=True)
    parser.add_argument("--compact-out", default=None)
    parser.add_argument("--balance-pre", default=None)
    parser.add_argument("--balance-post", default=None)
    parser.add_argument("--billing", default=None)
    args = parser.parse_args()

    rows = load_rows(PROJECT_ROOT / args.csv, args.run_id)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    meta = {str(ex["id"]): ex for ex in manifest["examples"]}
    events = json.loads((PROJECT_ROOT / args.events).read_text(encoding="utf-8"))
    row_ids = [row["example_id"] for row in rows]
    intended_ids = [str(ex["id"]) for ex in manifest["examples"]]
    duplicate_ids = sorted(key for key, count in Counter(row_ids).items() if count > 1)
    missing_ids = sorted(set(intended_ids) - set(row_ids))
    unexpected_ids = sorted(set(row_ids) - set(intended_ids))
    source_checks = {
        "manifest_sha256": sha256(MANIFEST),
        "base_protocol_sha256": sha256(BASE_PROTOCOL),
        "runpod_protocol_sha256": sha256(SELF_HOSTED_PROTOCOL),
        "lambda_repo_commit": subprocess.check_output(
            ["git", "-C", str(LAMBDA_REPO), "rev-parse", "HEAD"], text=True
        ).strip(),
        "lambda_source_sha256": sha256(LAMBDA_REPO / "rlm/lambda_rlm.py"),
        "benchmark_source_sha256": sha256(LAMBDA_REPO / "benchmarks/benchmark.py"),
    }
    tracked_status = subprocess.check_output(
        ["git", "-C", str(LAMBDA_REPO), "status", "--porcelain", "--untracked-files=no"],
        text=True,
    ).strip()
    config_checks = {
        "model": events.get("model"),
        "model_revision": events.get("model_revision"),
        "vllm_image": events.get("vllm_image"),
    }
    integrity_errors = []
    for key in (
        "manifest_sha256",
        "lambda_repo_commit",
        "lambda_source_sha256",
        "benchmark_source_sha256",
    ):
        if source_checks[key] != EXPECTED[key]:
            integrity_errors.append(f"{key} mismatch")
    if tracked_status:
        integrity_errors.append("official repository has tracked changes")
    for key in ("model", "model_revision", "vllm_image"):
        if config_checks[key] != EXPECTED[key]:
            integrity_errors.append(f"{key} mismatch")
    if duplicate_ids:
        integrity_errors.append(f"duplicate ids: {duplicate_ids}")
    if missing_ids:
        integrity_errors.append(f"missing ids: {missing_ids}")
    if unexpected_ids:
        integrity_errors.append(f"unexpected ids: {unexpected_ids}")
    valid_rows = [row for row in rows if not classify_row(row).startswith("provider_")]
    ours = {row["example_id"]: int(float(row["correct"]) >= 1.0) for row in valid_rows}

    by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_length: dict[str, list[dict[str, Any]]] = defaultdict(list)
    failure_modes = Counter()
    detected_tasks = Counter()
    latent_correct_ids: list[str] = []
    for row in rows:
        by_group[row["task_group"]].append(row)
        by_length[str(row["context_len"])].append(row)
        mode = classify_row(row)
        failure_modes[mode] += 1
        if mode == "latent_gold_output_contract_failure":
            latent_correct_ids.append(row["example_id"])
        match = re.search(r"task=([a-z_]+)", row.get("plan_trace", ""))
        if match:
            detected_tasks[match.group(1)] += 1

    def summarize(items: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "n": len(items),
            "exact": sum(float(row["correct"]) >= 1.0 for row in items),
            "score_sum": round(sum(float(row["correct"]) for row in items), 4),
            "errors": sum(bool(row["error"]) for row in items),
            "execution_time_s_completed": round(sum(float(row["execution_time"]) for row in items), 3),
        }

    baselines = {
        "slm_qparsed_typed": baseline_rows(manifest, "slm_qparsed_typed"),
        "direct_gemini25_flash": baseline_rows(manifest, "direct_gemini25_flash"),
        "standard_rlm_gemini25_flash": baseline_rows(manifest, "standard_rlm_gemini25_flash"),
        "standard_rlm_gpt5": baseline_rows(manifest, "standard_rlm_gpt5"),
    }
    official_qwen = json.loads(OFFICIAL_QWEN_ANALYSIS.read_text(encoding="utf-8"))
    official_qwen_rows = [
        json.loads(line)
        for line in OFFICIAL_QWEN_ROWS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    official_qwen_exact = {
        str(row["example_id"]): int(bool(row["exact"])) for row in official_qwen_rows
    }
    balance_pre = (
        json.loads((PROJECT_ROOT / args.balance_pre).read_text(encoding="utf-8"))
        if args.balance_pre else None
    )
    balance_post = (
        json.loads((PROJECT_ROOT / args.balance_post).read_text(encoding="utf-8"))
        if args.balance_post else None
    )
    balance_delta = None
    actual_runpod_spend = None
    if balance_pre is not None and balance_post is not None:
        balance_delta = (
            float(balance_pre["clientBalance"]) - float(balance_post["clientBalance"])
        )
        if balance_delta >= 0:
            actual_runpod_spend = balance_delta
    billing = (
        json.loads((PROJECT_ROOT / args.billing).read_text(encoding="utf-8"))
        if args.billing else None
    )
    rankable = len(rows) == 15 and len(valid_rows) == 15 and not integrity_errors
    analysis = {
        "evidence_role": "official lambda-RLM implementation cross-task same-contract evaluation; not original-paper benchmark reproduction",
        "rankable_full_cd15": rankable,
        "run_id": args.run_id,
        "integrity": {
            "passed": not integrity_errors,
            "errors": integrity_errors,
            "intended_n": len(intended_ids),
            "observed_n": len(rows),
            "missing_ids": missing_ids,
            "duplicate_ids": duplicate_ids,
            "unexpected_ids": unexpected_ids,
            "source_checks": source_checks,
            "expected": EXPECTED,
            "config_checks": config_checks,
            "official_repo_tracked_status": tracked_status,
            "official_repo_clean_at_analysis": not tracked_status,
            "protocol_note": (
                "The raw wrapper event points to the cumulative base protocol; "
                "the provider-specific frozen protocol is separately hashed here."
            ),
        },
        "all_attempted": summarize(rows),
        "valid_model_outputs": summarize(valid_rows),
        "by_group": {key: summarize(value) for key, value in sorted(by_group.items())},
        "by_length": {key: summarize(value) for key, value in sorted(by_length.items(), key=lambda x: int(x[0]))},
        "valid_by_group": {
            key: summarize([row for row in value if row in valid_rows])
            for key, value in sorted(by_group.items())
        },
        "valid_by_length": {
            key: summarize([row for row in value if row in valid_rows])
            for key, value in sorted(by_length.items(), key=lambda x: int(x[0]))
        },
        "failure_modes": dict(failure_modes),
        "latent_correct_ids": latent_correct_ids,
        "detected_task_counts": dict(detected_tasks),
        "paired": {key: paired(ours, value) for key, value in baselines.items()},
        "paired_official_trained_qwen30b": paired(ours, official_qwen_exact),
        "official_trained_qwen30b_reference": official_qwen["official_rlm_qwen30b"],
        "cost": {
            "openrouter_usd": float(events.get("openrouter_spend_usd", 0.0)),
            "runpod_listed_hourly_usd": float(events.get("listed_hourly_usd", 0.0)),
            "runpod_listed_runtime_cost_usd": float(events.get("listed_runtime_cost_usd", 0.0)),
            "runtime_s": float(events.get("runtime_s", 0.0)),
            "runpod_actual_balance_delta_usd": actual_runpod_spend,
            "runpod_raw_balance_delta_usd": balance_delta,
            "runpod_billing_export": billing,
            "cost_scope": (
                "Creation-to-cleanup listed-rate estimate plus account-balance delta when available; "
                "token costs are unavailable under self-hosted official streaming transport."
            ),
        },
        "canary_gate": events.get("canary_gate"),
        "scale_decision": events.get("scale_decision"),
        "row_diagnostics": [
            {
                "example_id": row["example_id"],
                "group": row["task_group"],
                "length": int(row["context_len"]),
                "gold": json.loads(row["gold"]),
                "prediction": row["prediction"],
                "strict_exact": float(row["correct"]) >= 1.0,
                "failure_mode": classify_row(row),
                "detected_task": (
                    re.search(r"task=([a-z_]+)", row.get("plan_trace", "")).group(1)
                    if re.search(r"task=([a-z_]+)", row.get("plan_trace", ""))
                    else None
                ),
                "call_count": int(row["call_count"] or 0),
                "execution_time_s": float(row["execution_time"] or 0),
                "error": row["error"],
            }
            for row in rows
        ],
    }
    out_path = PROJECT_ROOT / args.out
    out_path.write_text(json.dumps(analysis, indent=2, ensure_ascii=True), encoding="utf-8")

    lines = [
        "# Official lambda-RLM CD-15 cross-task analysis",
        "",
        f"- Evidence role: {analysis['evidence_role']}",
        f"- Rankable full CD-15 row: **{analysis['rankable_full_cd15']}**",
        f"- Integrity gate: **{analysis['integrity']['passed']}**; errors: `{analysis['integrity']['errors']}`",
        f"- Rows attempted: {analysis['all_attempted']['n']}; valid model outputs: {analysis['valid_model_outputs']['n']}; valid strict exact: {analysis['valid_model_outputs']['exact']}",
        f"- Failure modes: `{json.dumps(analysis['failure_modes'], sort_keys=True)}`",
        f"- Listed RunPod runtime cost: `${analysis['cost']['runpod_listed_runtime_cost_usd']:.6f}`; OpenRouter: `$0.00`",
        "",
        "## Paired same-row results",
        "",
        "| Comparator | N | lambda exact | comparator exact | b/c | exact McNemar p |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for key, value in analysis["paired"].items():
        lines.append(
            f"| {key} | {value['n']} | {value['ours_exact']} | {value['baseline_exact']} | "
            f"{value['b_ours_only']}/{value['c_baseline_only']} | {value['mcnemar_exact_two_sided_p']:.4f} |"
        )
    value = analysis["paired_official_trained_qwen30b"]
    lines.append(
        f"| official_trained_qwen30b | {value['n']} | {value['ours_exact']} | "
        f"{value['baseline_exact']} | {value['b_ours_only']}/{value['c_baseline_only']} | "
        f"{value['mcnemar_exact_two_sided_p']:.4f} |"
    )
    lines.extend(["", "## Row diagnostics", ""])
    for row in analysis["row_diagnostics"]:
        lines.append(
            f"- `{row['example_id']}` ({row['group']}, {row['length']}): "
            f"{row['failure_mode']}; task={row['detected_task']}; exact={row['strict_exact']}; "
            f"calls={row['call_count']}; time={row['execution_time_s']:.1f}s; error={row['error']!r}."
        )
    (PROJECT_ROOT / args.md_out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    if args.compact_out:
        with (PROJECT_ROOT / args.compact_out).open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps({
                    "run_id": row["run_id"],
                    "example_id": row["example_id"],
                    "task_group": row["task_group"],
                    "context_len": int(row["context_len"]),
                    "question": row["question"],
                    "gold": json.loads(row["gold"]),
                    "prediction": row["prediction"],
                    "raw_response": row["raw_response"],
                    "strict_score": float(row["correct"]),
                    "failure_mode": classify_row(row),
                    "call_count": int(row["call_count"] or 0),
                    "execution_time_s": float(row["execution_time"] or 0),
                    "plan_trace": row.get("plan_trace", ""),
                    "error": row["error"],
                }, ensure_ascii=True) + "\n")
    print(json.dumps(analysis, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
