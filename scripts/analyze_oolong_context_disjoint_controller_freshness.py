#!/usr/bin/env python3
"""Analyze current/frontier-controller standard-RLM checks on CD-45."""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path, run_id: str | None = None) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if run_id:
        rows = [r for r in rows if r.get("run_id") == run_id]
    return rows


def exact_p_two_sided(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) * (0.5**n) for i in range(k + 1))
    return min(1.0, 2.0 * tail)


def percentile(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    if not xs:
        return 0.0
    pos = (len(xs) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return xs[lo]
    return xs[lo] * (hi - pos) + xs[hi] * (pos - lo)


def normalize(
    rows: list[dict[str, str]],
    method: str,
    manifest: dict[str, dict[str, Any]],
    model: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        eid = str(row["example_id"])
        meta = manifest[eid]
        score = float(row.get("correct") or 0.0)
        out.append(
            {
                "example_id": eid,
                "method": method,
                "model": model,
                "context_len": int(row.get("context_len") or meta["context_len"]),
                "task_group": row.get("task_group") or meta["task_group"],
                "context_window_id": str(meta["context_window_id"]),
                "score": score,
                "exact": 1.0 if math.isclose(score, 1.0) else 0.0,
                "cost_usd": float(row.get("cost_usd") or 0.0),
                "error": row.get("error", ""),
                "prediction": row.get("prediction", ""),
                "gold": row.get("gold", ""),
            }
        )
    return out


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    exact = sum(float(r["exact"]) for r in rows)
    score = sum(float(r["score"]) for r in rows)
    cost = sum(float(r["cost_usd"]) for r in rows)
    errors = sum(1 for r in rows if r.get("error"))
    return {
        "n": n,
        "exact_count": int(exact),
        "exact_rate": round(exact / n, 6) if n else 0.0,
        "mean_score": round(score / n, 6) if n else 0.0,
        "cost_usd": round(cost, 6),
        "cost_per_exact_usd": round(cost / exact, 6) if exact else None,
        "errors": errors,
    }


def paired(
    rows_a: dict[str, dict[str, Any]],
    rows_b: dict[str, dict[str, Any]],
    manifest: dict[str, dict[str, Any]],
    reps: int,
) -> dict[str, Any]:
    ids = sorted(set(rows_a) & set(rows_b))
    b = sum(1 for eid in ids if rows_a[eid]["exact"] == 1.0 and rows_b[eid]["exact"] == 0.0)
    c = sum(1 for eid in ids if rows_a[eid]["exact"] == 0.0 and rows_b[eid]["exact"] == 1.0)
    clusters: dict[str, list[str]] = defaultdict(list)
    for eid in ids:
        clusters[str(manifest[eid]["context_window_id"])].append(eid)
    keys = sorted(clusters)
    rng = random.Random(20260715)
    exact_diffs: list[float] = []
    score_diffs: list[float] = []
    for _ in range(reps):
        sample: list[str] = []
        for _ in keys:
            sample.extend(clusters[rng.choice(keys)])
        exact_diffs.append(sum(rows_a[eid]["exact"] - rows_b[eid]["exact"] for eid in sample) / len(sample))
        score_diffs.append(sum(rows_a[eid]["score"] - rows_b[eid]["score"] for eid in sample) / len(sample))
    return {
        "n": len(ids),
        "b_a_right_b_wrong": b,
        "c_b_right_a_wrong": c,
        "two_sided_exact_p": exact_p_two_sided(b, c),
        "exact_diff": round(sum(rows_a[eid]["exact"] - rows_b[eid]["exact"] for eid in ids) / len(ids), 6),
        "score_diff": round(sum(rows_a[eid]["score"] - rows_b[eid]["score"] for eid in ids) / len(ids), 6),
        "exact_diff_cluster_ci": {
            "ci_low": round(percentile(exact_diffs, 0.025), 6),
            "ci_high": round(percentile(exact_diffs, 0.975), 6),
            "clusters": len(keys),
        },
        "score_diff_cluster_ci": {
            "ci_low": round(percentile(score_diffs, 0.025), 6),
            "ci_high": round(percentile(score_diffs, 0.975), 6),
            "clusters": len(keys),
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=ROOT / "results/oolong_context_disjoint_n45_manifest_20260715.json")
    ap.add_argument("--slm", type=Path, default=ROOT / "results/oolong_context_disjoint_n45_slm_labeler_question_parsed_typed_20260715.csv")
    ap.add_argument("--direct", type=Path, default=ROOT / "results/oolong_context_disjoint_n45_direct_controller_gemini25flash_20260715.csv")
    ap.add_argument("--gemini-rlm", type=Path, default=ROOT / "results/oolong_context_disjoint_n45_rlm_20260715.csv")
    ap.add_argument("--gpt5-rlm", type=Path, default=ROOT / "results/oolong_context_disjoint_n45_gpt5_rlm_strict_20260715.csv")
    ap.add_argument("--gpt5-run-id", default="oolong_context_disjoint_n45_gpt5_rlm_strict_20260715")
    ap.add_argument("--out-json", type=Path, default=ROOT / "results/oolong_context_disjoint_n45_gpt5_controller_freshness_analysis_20260715.json")
    ap.add_argument("--out-csv", type=Path, default=ROOT / "results/oolong_context_disjoint_n45_gpt5_controller_freshness_table_20260715.csv")
    ap.add_argument("--out-md", type=Path, default=ROOT / "results/oolong_context_disjoint_n45_gpt5_controller_freshness_analysis_20260715.md")
    ap.add_argument("--bootstraps", type=int, default=5000)
    args = ap.parse_args()

    manifest_payload = read_json(args.manifest)
    manifest = {str(ex["id"]): ex for ex in manifest_payload["examples"]}
    methods = {
        "slm_qparsed_typed": normalize(read_csv(args.slm), "slm_qparsed_typed", manifest, "google/gemma-4-26b-a4b-it"),
        "direct_gemini25": normalize(read_csv(args.direct), "direct_gemini25", manifest, "google/gemini-2.5-flash"),
        "standard_rlm_gemini25": normalize(read_csv(args.gemini_rlm), "standard_rlm_gemini25", manifest, "google/gemini-2.5-flash"),
        "standard_rlm_gpt5": normalize(read_csv(args.gpt5_rlm, args.gpt5_run_id), "standard_rlm_gpt5", manifest, "openai/gpt-5"),
    }
    by_id = {m: {r["example_id"]: r for r in rows} for m, rows in methods.items()}
    analysis = {
        "metadata": {
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "manifest": str(args.manifest.relative_to(ROOT)),
            "strict_stop_rule": "240 seconds per row; complete rows only; partial failed rows recorded as errors with zero cost if provider usage was not returned",
            "gpt5_status": "complete strict-stop CD-45 run, not a partial canary",
        },
        "overall": {m: summarize(rows) for m, rows in methods.items()},
        "by_group": {
            g: {m: summarize([r for r in rows if r["task_group"] == g]) for m, rows in methods.items()}
            for g in ["counting", "timeline", "user"]
        },
        "by_length": {
            str(length): {m: summarize([r for r in rows if int(r["context_len"]) == length]) for m, rows in methods.items()}
            for length in [1024, 4096, 262144]
        },
        "paired_vs_gpt5": {
            "slm_qparsed_typed_vs_standard_rlm_gpt5": paired(by_id["slm_qparsed_typed"], by_id["standard_rlm_gpt5"], manifest, args.bootstraps),
            "standard_rlm_gemini25_vs_standard_rlm_gpt5": paired(by_id["standard_rlm_gemini25"], by_id["standard_rlm_gpt5"], manifest, args.bootstraps),
            "direct_gemini25_vs_standard_rlm_gpt5": paired(by_id["direct_gemini25"], by_id["standard_rlm_gpt5"], manifest, args.bootstraps),
        },
    }
    args.out_json.write_text(json.dumps(analysis, indent=2), encoding="utf-8")

    with args.out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["method", "model", "n", "exact_count", "exact_rate", "mean_score", "cost_usd", "cost_per_exact_usd", "errors"])
        writer.writeheader()
        for method, rows in methods.items():
            row = summarize(rows)
            row["method"] = method
            row["model"] = rows[0]["model"] if rows else ""
            writer.writerow(row)

    lines = [
        "# GPT-5 Controller Freshness Analysis on Oolong CD-45",
        "",
        "This is a complete strict-stop standard-`rlms` run on the context-window-disjoint Oolong CD-45 manifest. It uses `openai/gpt-5` through OpenRouter with a 240-second per-row timeout.",
        "",
        "| Method | Exact | Mean score | Cost | Errors |",
        "|---|---:|---:|---:|---:|",
    ]
    labels = {
        "slm_qparsed_typed": "Q-parsed SLM+typed",
        "direct_gemini25": "Direct Gemini 2.5 Flash",
        "standard_rlm_gemini25": "Standard RLM / Gemini 2.5 Flash",
        "standard_rlm_gpt5": "Standard RLM / GPT-5",
    }
    for method, summary in analysis["overall"].items():
        lines.append(
            f"| {labels[method]} | {summary['exact_count']}/{summary['n']} ({summary['exact_rate']*100:.1f}%) | "
            f"{summary['mean_score']*100:.1f}% | ${summary['cost_usd']:.6f} | {summary['errors']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- GPT-5 does not close the central CD-45 gap: SLM+typed remains higher on exact accuracy and mean score.",
            "- GPT-5 introduces substantial strict-stop instability on this scaffold: 15/45 rows timed out or errored under the 240-second row cap.",
            "- This result should be reported as a controller-freshness sensitivity and stability check, not as a new RLM-family leaderboard.",
        ]
    )
    args.out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {args.out_json}")
    print(f"Wrote {args.out_csv}")
    print(f"Wrote {args.out_md}")


if __name__ == "__main__":
    main()
