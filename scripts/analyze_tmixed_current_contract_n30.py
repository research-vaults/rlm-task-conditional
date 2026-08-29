#!/usr/bin/env python3
"""Analyze the deterministic T-MIXED current-contract N=30 extension."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def as_bool(value: str) -> bool:
    return value.strip().lower() in {"true", "1", "yes"}


def exact_binomial_p_two_sided(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    observed = min(b, c)
    prob = sum(math.comb(n, k) for k in range(observed + 1)) / (2**n)
    return min(1.0, 2 * prob)


def method_summary(rows: list[dict[str, str]], method: str) -> dict[str, Any]:
    correct = [as_bool(r[f"{method}_correct"]) for r in rows]
    preds = [int(float(r[f"{method}_pred"])) for r in rows]
    costs = [float(r.get(f"{method}_cost_usd") or 0.0) for r in rows]
    finalized_key = f"{method}_finalized"
    finalized = [as_bool(r[finalized_key]) for r in rows] if finalized_key in rows[0] else [True] * len(rows)
    errors = [r.get(f"{method}_error", "") for r in rows]
    return {
        "n": len(rows),
        "correct": sum(correct),
        "accuracy": sum(correct) / len(rows),
        "minus1": sum(p == -1 for p in preds),
        "minus1_rate": sum(p == -1 for p in preds) / len(rows),
        "finalized": sum(finalized),
        "finalized_rate": sum(finalized) / len(rows),
        "errors": sum(1 for e in errors if e.strip()),
        "cost_usd": sum(costs),
        "cost_per_example": sum(costs) / len(rows),
        "predictions": preds,
    }


def paired(rows: list[dict[str, str]], a: str, b: str) -> dict[str, Any]:
    a_ok = [as_bool(r[f"{a}_correct"]) for r in rows]
    b_ok = [as_bool(r[f"{b}_correct"]) for r in rows]
    b_a = sum(x and not y for x, y in zip(a_ok, b_ok))
    c_b = sum(y and not x for x, y in zip(a_ok, b_ok))
    return {
        "b_a_right_b_wrong": b_a,
        "c_b_right_a_wrong": c_b,
        "n_discordant": b_a + c_b,
        "two_sided_exact_p": exact_binomial_p_two_sided(b_a, c_b),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=RESULTS / "tmixed_current_contract_n30_20260714.csv")
    parser.add_argument("--manifest", type=Path, default=RESULTS / "tmixed_current_contract_n30_manifest_20260714.json")
    parser.add_argument("--out-json", type=Path, default=RESULTS / "tmixed_current_contract_n30_20260714_analysis.json")
    parser.add_argument("--out-md", type=Path, default=RESULTS / "tmixed_current_contract_n30_20260714_analysis.md")
    args = parser.parse_args()

    rows = list(csv.DictReader(args.csv.open(newline="", encoding="utf-8")))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    methods = [m for m in ["direct_gemini", "rlm_content_json_contract"] if f"{m}_correct" in rows[0]]
    summaries = {m: method_summary(rows, m) for m in methods}
    domain_breakdown: dict[str, Any] = {}
    for domain in sorted({r["domain"] for r in rows}):
        sub = [r for r in rows if r["domain"] == domain]
        domain_breakdown[domain] = {m: method_summary(sub, m) for m in methods}

    analysis: dict[str, Any] = {
        "n": len(rows),
        "manifest": str(args.manifest),
        "manifest_n": manifest["n"],
        "generator": manifest.get("generator", {}),
        "domain_counts": manifest.get("domain_counts", {}),
        "methods": summaries,
        "by_domain": domain_breakdown,
        "paired": {},
        "cost_ratios": {},
        "interpretation": (
            "This deterministic current-contract extension avoids the historical salted-generator "
            "issue and compares direct Gemini with the repaired/content-contract RLM finalizer. "
            "It is a controlled-family mechanism extension, not a public benchmark."
        ),
    }
    if {"direct_gemini", "rlm_content_json_contract"} <= set(methods):
        analysis["paired"]["direct_vs_content_rlm"] = paired(rows, "direct_gemini", "rlm_content_json_contract")
        analysis["cost_ratios"]["content_rlm_vs_direct_total"] = (
            summaries["rlm_content_json_contract"]["cost_usd"] / summaries["direct_gemini"]["cost_usd"]
            if summaries["direct_gemini"]["cost_usd"]
            else None
        )

    args.out_json.write_text(json.dumps(analysis, indent=2), encoding="utf-8")
    lines = [
        "# T-MIXED Current-Contract N=30 Extension",
        "",
        f"- Manifest: `{args.manifest}`.",
        f"- Run CSV: `{args.csv}`.",
        f"- N: {analysis['n']} deterministic examples; domain counts {analysis['domain_counts']}.",
        "- Contract: direct Gemini versus RLM with repaired `answer['content']` JSON finalization.",
        "- Boundary: this uses a stable generator extension, not the historical salted Round 22 generator.",
        "",
        "| Method | Correct/N | Accuracy | Cost USD | Errors | Finalized |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for method, info in summaries.items():
        lines.append(
            f"| {method} | {info['correct']}/{info['n']} | {info['accuracy']:.1%} | "
            f"${info['cost_usd']:.6f} | {info['errors']} | {info['finalized']}/{info['n']} |"
        )
    if analysis["paired"]:
        p = analysis["paired"]["direct_vs_content_rlm"]
        lines.extend(
            [
                "",
                f"Paired direct-vs-content-RLM exact: b={p['b_a_right_b_wrong']}, "
                f"c={p['c_b_right_a_wrong']}, two-sided exact p={p['two_sided_exact_p']:.6g}.",
                f"Cost ratio content-RLM/direct: {analysis['cost_ratios']['content_rlm_vs_direct_total']:.2f}x.",
            ]
        )
    args.out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(analysis, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
