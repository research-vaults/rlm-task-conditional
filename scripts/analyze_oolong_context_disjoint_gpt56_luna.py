#!/usr/bin/env python3
"""Analyze the complete GPT-5.6 Luna standard-RLM CD-45 run.

This is a controller-freshness sensitivity, not a new primary benchmark. It
compares the frozen context-window-disjoint Oolong CD-45 slice across the
existing SLM+typed, direct Gemini, standard Gemini RLM, GPT-5 RLM, and the
new complete GPT-5.6 Luna standard-RLM row.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from math import comb
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_INPUTS = {
    "slm_qparsed_typed": {
        "path": "results/oolong_context_disjoint_n45_slm_labeler_question_parsed_typed_20260715.csv",
        "label": "SLM+typed",
    },
    "direct_gemini25": {
        "path": "results/oolong_context_disjoint_n45_direct_controller_gemini25flash_20260715.csv",
        "label": "Direct Gemini 2.5 Flash",
    },
    "standard_rlm_gemini25": {
        "path": "results/oolong_context_disjoint_n45_rlm_20260715.csv",
        "label": "Standard RLM / Gemini 2.5 Flash",
    },
    "standard_rlm_gpt5": {
        "path": "results/oolong_context_disjoint_n45_gpt5_rlm_strict_20260715.csv",
        "label": "Standard RLM / GPT-5",
        "run_id": "oolong_context_disjoint_n45_gpt5_rlm_strict_20260715",
    },
    "standard_rlm_gpt56_luna": {
        "path": "results/oolong_context_disjoint_n45_gpt56_luna_complete_20260718.csv",
        "label": "Standard RLM / GPT-5.6 Luna",
        "run_id": "oolong_context_disjoint_n45_gpt56_luna_complete_20260718",
    },
}


def read_manifest(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(ex["id"]): ex for ex in data["examples"]}


def read_rows(path: Path, run_id: str | None = None) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if run_id and row.get("run_id") != run_id:
                continue
            ex_id = str(row["example_id"])
            score = float(row.get("correct") or 0.0)
            rows[ex_id] = {
                **row,
                "score": score,
                "exact": score >= 1.0,
                "cost": float(row.get("cost_usd") or 0.0),
                "error": bool(row.get("error")),
            }
    return rows


def exact_binom_two_sided(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    observed = min(b, c)
    p = 2 * sum(comb(n, k) * (0.5**n) for k in range(observed + 1))
    return min(1.0, p)


def summarize(rows: dict[str, dict[str, Any]], ids: list[str], manifest: dict[str, dict[str, Any]]) -> dict[str, Any]:
    by_group: dict[str, list[str]] = defaultdict(list)
    by_length: dict[str, list[str]] = defaultdict(list)
    by_task: dict[str, list[str]] = defaultdict(list)
    by_answer_type: dict[str, list[str]] = defaultdict(list)
    for ex_id in ids:
        meta = manifest[ex_id]
        by_group[str(meta["task_group"])].append(ex_id)
        by_length[str(meta["context_len"])].append(ex_id)
        by_task[str(meta["task"])].append(ex_id)
        by_answer_type[str(meta["answer_type"])].append(ex_id)

    def pack(sub_ids: list[str]) -> dict[str, Any]:
        n = len(sub_ids)
        score_sum = sum(rows[i]["score"] for i in sub_ids)
        exact = sum(1 for i in sub_ids if rows[i]["exact"])
        cost = sum(rows[i]["cost"] for i in sub_ids)
        errors = sum(1 for i in sub_ids if rows[i]["error"])
        return {
            "n": n,
            "score_sum": round(score_sum, 4),
            "mean_score": round(score_sum / n, 6) if n else 0.0,
            "exact_count": exact,
            "exact_rate": round(exact / n, 6) if n else 0.0,
            "cost_usd": round(cost, 6),
            "cost_per_exact_usd": round(cost / exact, 6) if exact else None,
            "errors": errors,
        }

    return {
        **pack(ids),
        "by_group": {k: pack(v) for k, v in sorted(by_group.items())},
        "by_length": {k: pack(v) for k, v in sorted(by_length.items(), key=lambda kv: int(kv[0]))},
        "by_task": {k: pack(v) for k, v in sorted(by_task.items())},
        "by_answer_type": {k: pack(v) for k, v in sorted(by_answer_type.items())},
    }


def paired(
    a: dict[str, dict[str, Any]],
    b: dict[str, dict[str, Any]],
    ids: list[str],
    manifest: dict[str, dict[str, Any]],
    bootstraps: int,
    seed: int,
) -> dict[str, Any]:
    b_a_right = 0
    c_b_right = 0
    exact_diffs: list[float] = []
    score_diffs: list[float] = []
    for ex_id in ids:
        a_exact = a[ex_id]["exact"]
        b_exact = b[ex_id]["exact"]
        if a_exact and not b_exact:
            b_a_right += 1
        elif b_exact and not a_exact:
            c_b_right += 1
        exact_diffs.append(float(a_exact) - float(b_exact))
        score_diffs.append(a[ex_id]["score"] - b[ex_id]["score"])

    clusters: dict[str, list[str]] = defaultdict(list)
    for ex_id in ids:
        clusters[str(manifest[ex_id]["context_window_id"])].append(ex_id)
    cluster_keys = sorted(clusters)
    rng = random.Random(seed)
    boot_exact: list[float] = []
    boot_score: list[float] = []
    for _ in range(bootstraps):
        sampled: list[str] = []
        for _ in cluster_keys:
            sampled.extend(clusters[rng.choice(cluster_keys)])
        n = len(sampled)
        boot_exact.append(sum(float(a[i]["exact"]) - float(b[i]["exact"]) for i in sampled) / n)
        boot_score.append(sum(a[i]["score"] - b[i]["score"] for i in sampled) / n)

    def ci(vals: list[float]) -> dict[str, float]:
        vals = sorted(vals)
        return {
            "mean": round(sum(vals) / len(vals), 6),
            "ci_low": round(vals[int(0.025 * len(vals))], 6),
            "ci_high": round(vals[min(len(vals) - 1, int(0.975 * len(vals)))], 6),
        }

    return {
        "n": len(ids),
        "b_a_right_b_wrong": b_a_right,
        "c_b_right_a_wrong": c_b_right,
        "two_sided_exact_p": exact_binom_two_sided(b_a_right, c_b_right),
        "exact_diff": round(sum(exact_diffs) / len(ids), 6),
        "score_diff": round(sum(score_diffs) / len(ids), 6),
        "exact_diff_cluster_ci": ci(boot_exact),
        "score_diff_cluster_ci": ci(boot_score),
        "clusters": len(cluster_keys),
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    labels = report["metadata"]["labels"]
    lines = [
        "# Oolong CD-45 GPT-5.6 Luna Controller-Freshness Analysis",
        "",
        "This is a complete strict-stop standard-`rlms` run on the frozen context-window-disjoint Oolong CD-45 manifest. It uses `openai/gpt-5.6-luna` through OpenRouter with the same standard/unlabeled input contract and 360-second row cap used for the central controller-freshness family. It is not an official SRLM/lambda-RLM/RAH reproduction.",
        "",
        "## Overall",
        "",
        "| Method | Exact | Mean score | Cost | Errors | Cost/exact |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, stats in report["overall"].items():
        cpe = "NA" if stats["cost_per_exact_usd"] is None else f"${stats['cost_per_exact_usd']:.6f}"
        lines.append(
            f"| {labels[name]} | {stats['exact_count']}/{stats['n']} ({100*stats['exact_rate']:.1f}%) | "
            f"{100*stats['mean_score']:.1f}% | ${stats['cost_usd']:.6f} | {stats['errors']} | {cpe} |"
        )
    lines.extend([
        "",
        "## Paired Exact Comparisons",
        "",
        "| Comparison | Exact diff | b | c | two-sided p | Cluster CI |",
        "|---|---:|---:|---:|---:|---|",
    ])
    for name, stats in report["paired"].items():
        lines.append(
            f"| `{name}` | {100*stats['exact_diff']:.1f} pp | {stats['b_a_right_b_wrong']} | "
            f"{stats['c_b_right_a_wrong']} | {stats['two_sided_exact_p']:.6g} | "
            f"[{100*stats['exact_diff_cluster_ci']['ci_low']:.1f}, {100*stats['exact_diff_cluster_ci']['ci_high']:.1f}] pp |"
        )
    luna = report["overall"]["standard_rlm_gpt56_luna"]
    slm = report["overall"]["slm_qparsed_typed"]
    gemini = report["overall"]["standard_rlm_gemini25"]
    gpt5 = report["overall"]["standard_rlm_gpt5"]
    lines.extend([
        "",
        "## Interpretation",
        "",
        f"- GPT-5.6 Luna standard RLM is complete on CD-45: {luna['exact_count']}/{luna['n']} exact, mean score {100*luna['mean_score']:.1f}%, {luna['errors']} timeout/error rows, and ${luna['cost_usd']:.6f} captured cost.",
        f"- It does not overturn the central SLM+typed result: SLM+typed remains {slm['exact_count']}/{slm['n']} exact at ${slm['cost_usd']:.6f}.",
        f"- It is essentially tied with the older Gemini 2.5 Flash standard-RLM row on exact count ({luna['exact_count']} vs {gemini['exact_count']}) and slightly above GPT-5 strict-stop exact count ({luna['exact_count']} vs {gpt5['exact_count']}).",
        "- The paper-facing value is model-freshness/fairness: a complete current GPT-5.6 controller run no longer leaves the result dependent on stale partial GPT-5.6 credit-aborted prefixes.",
        "- This is still standard `rlms`, not stronger-family SRLM/lambda-RLM/RAH parity; keep the official-family non-claim.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="results/oolong_context_disjoint_n45_manifest_20260715.json")
    parser.add_argument("--out-json", default="results/oolong_context_disjoint_n45_gpt56_luna_controller_freshness_analysis_20260718.json")
    parser.add_argument("--out-table", default="results/oolong_context_disjoint_n45_gpt56_luna_controller_freshness_table_20260718.csv")
    parser.add_argument("--out-md", default="results/oolong_context_disjoint_n45_gpt56_luna_controller_freshness_analysis_20260718.md")
    parser.add_argument("--bootstraps", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=20260718)
    args = parser.parse_args()

    manifest = read_manifest(ROOT / args.manifest)
    methods = {
        name: read_rows(ROOT / spec["path"], spec.get("run_id"))
        for name, spec in DEFAULT_INPUTS.items()
    }
    common_ids = sorted(set(manifest).intersection(*(set(rows) for rows in methods.values())))
    if len(common_ids) != 45:
        raise RuntimeError(f"Expected 45 common examples, found {len(common_ids)}")

    report = {
        "metadata": {
            "created_utc": "2026-07-18T21:35:00Z",
            "manifest": args.manifest,
            "n": len(common_ids),
            "bootstraps": args.bootstraps,
            "seed": args.seed,
            "inputs": {k: v["path"] for k, v in DEFAULT_INPUTS.items()},
            "labels": {k: v["label"] for k, v in DEFAULT_INPUTS.items()},
            "purpose": "complete GPT-5.6 Luna standard-rlms controller-freshness sensitivity on frozen CD-45",
        },
        "overall": {
            name: summarize(rows, common_ids, manifest)
            for name, rows in methods.items()
        },
        "paired": {
            "slm_qparsed_typed_vs_standard_rlm_gpt56_luna": paired(methods["slm_qparsed_typed"], methods["standard_rlm_gpt56_luna"], common_ids, manifest, args.bootstraps, args.seed),
            "standard_rlm_gpt56_luna_vs_standard_rlm_gemini25": paired(methods["standard_rlm_gpt56_luna"], methods["standard_rlm_gemini25"], common_ids, manifest, args.bootstraps, args.seed + 1),
            "standard_rlm_gpt56_luna_vs_standard_rlm_gpt5": paired(methods["standard_rlm_gpt56_luna"], methods["standard_rlm_gpt5"], common_ids, manifest, args.bootstraps, args.seed + 2),
            "standard_rlm_gpt56_luna_vs_direct_gemini25": paired(methods["standard_rlm_gpt56_luna"], methods["direct_gemini25"], common_ids, manifest, args.bootstraps, args.seed + 3),
        },
        "interpretation": {
            "headline": "GPT-5.6 Luna completes CD-45 and does not overturn SLM+typed; it mainly closes the current-controller freshness objection.",
            "claim_boundary": "This is a standard rlms controller-freshness sensitivity, not official SRLM/lambda-RLM/RAH or RLM-Qwen parity.",
        },
    }

    out_json = ROOT / args.out_json
    out_table = ROOT / args.out_table
    out_md = ROOT / args.out_md
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    with out_table.open("w", newline="", encoding="utf-8") as f:
        fieldnames = ["method", "n", "exact", "exact_rate", "mean_score", "cost_usd", "errors", "cost_per_exact_usd"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for name, stats in report["overall"].items():
            writer.writerow({
                "method": name,
                "n": stats["n"],
                "exact": stats["exact_count"],
                "exact_rate": stats["exact_rate"],
                "mean_score": stats["mean_score"],
                "cost_usd": stats["cost_usd"],
                "errors": stats["errors"],
                "cost_per_exact_usd": stats["cost_per_exact_usd"],
            })
    write_markdown(report, out_md)
    print(json.dumps({
        "wrote": [str(out_json.relative_to(ROOT)), str(out_table.relative_to(ROOT)), str(out_md.relative_to(ROOT))],
        "luna": report["overall"]["standard_rlm_gpt56_luna"],
        "slm_vs_luna": report["paired"]["slm_qparsed_typed_vs_standard_rlm_gpt56_luna"],
    }, indent=2))


if __name__ == "__main__":
    main()
