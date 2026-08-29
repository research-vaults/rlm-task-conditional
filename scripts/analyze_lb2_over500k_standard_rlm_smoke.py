#!/usr/bin/env python3
"""Analyze the LB2 >500k same-row standard-RLM smoke."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
METHODS = [
    "standard_rlm",
    "bm25_gemma_vote",
    "bm25_gemini_vote",
    "bm25_gemma_rerank_gemini_vote",
]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def analyze(rlm_path: Path, retrieval_path: Path) -> dict[str, Any]:
    rlm_rows = load_jsonl(rlm_path)
    retrieval_rows = {row["_id"]: row for row in load_jsonl(retrieval_path)}
    paired = []
    for rlm in rlm_rows:
        rid = rlm["_id"]
        ret = retrieval_rows[rid]
        item = {
            "_id": rid,
            "domain": rlm["domain"],
            "context_chars": rlm["context_chars"],
            "gold": rlm["gold"],
            "methods": {
                "standard_rlm": {
                    "prediction": rlm["prediction"],
                    "correct": bool(rlm["correct"]),
                    "cost_usd": float(rlm.get("cost_usd") or 0.0),
                    "elapsed_seconds": float(rlm.get("elapsed_seconds") or 0.0),
                    "error": rlm.get("error") or "",
                }
            },
        }
        for method in METHODS[1:]:
            m = ret["methods"][method]
            item["methods"][method] = {
                "prediction": m.get("prediction"),
                "correct": bool(m.get("correct")),
                "cost_usd": float(m.get("cost_usd") or 0.0) + float(m.get("rerank_cost_usd") or 0.0),
                "elapsed_seconds": None,
                "error": "; ".join(m.get("errors", []) + m.get("rerank_errors", [])),
            }
        paired.append(item)

    summary = {}
    for method in METHODS:
        rows = [p["methods"][method] for p in paired]
        n = len(rows)
        correct = sum(1 for r in rows if r["correct"])
        cost = sum(float(r["cost_usd"] or 0.0) for r in rows)
        errors = sum(1 for r in rows if r["error"])
        summary[method] = {
            "n": n,
            "correct": correct,
            "accuracy": correct / n if n else 0.0,
            "total_cost_usd": round(cost, 6),
            "cost_per_example_usd": round(cost / n, 6) if n else 0.0,
            "errors": errors,
        }

    rlm_cost = summary["standard_rlm"]["total_cost_usd"]
    best_retrieval = max(METHODS[1:], key=lambda m: (summary[m]["correct"], -summary[m]["total_cost_usd"]))
    return {
        "run_type": "lb2_over500k_standard_rlm_smoke_analysis",
        "n": len(paired),
        "source_rlm_results": str(rlm_path.relative_to(ROOT)),
        "source_retrieval_results": str(retrieval_path.relative_to(ROOT)),
        "methods": summary,
        "paired_rows": paired,
        "decision": {
            "scale_standard_rlm_to_n30_now": False,
            "reason": (
                "The bounded same-row smoke solved 1/6 with one 480s timeout. "
                f"The best retrieval route on the same six rows is {best_retrieval} with "
                f"{summary[best_retrieval]['correct']}/6 at ${summary[best_retrieval]['total_cost_usd']:.6f}, "
                f"versus standard RLM 1/6 at ${rlm_cost:.6f}. This does not justify a blind N=30 standard-RLM scale-up before submission."
            ),
            "paper_role": (
                "Supplement-level feasibility/stop-rule evidence for the over-window positive-regime section; "
                "not a full LongBench-v2 ranking and not an SRLM/lambda-RLM reproduction."
            ),
        },
    }


def write_table(analysis: dict[str, Any], out_csv: Path) -> None:
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["method", "n", "correct", "accuracy", "total_cost_usd", "cost_per_example_usd", "errors"])
        for method, stats in analysis["methods"].items():
            w.writerow([
                method,
                stats["n"],
                stats["correct"],
                f"{stats['accuracy']:.6f}",
                f"{stats['total_cost_usd']:.6f}",
                f"{stats['cost_per_example_usd']:.6f}",
                stats["errors"],
            ])


def write_md(analysis: dict[str, Any], out_md: Path) -> None:
    labels = {
        "standard_rlm": "Standard RLM",
        "bm25_gemma_vote": "BM25+Gemma vote",
        "bm25_gemini_vote": "BM25+Gemini vote",
        "bm25_gemma_rerank_gemini_vote": "BM25+Gemma rerank+Gemini",
    }
    lines = [
        "# LB2 >500k Standard-RLM Same-Row Smoke Analysis",
        "",
        "This analysis compares the bounded standard-`rlms` smoke against the existing retrieval/rerank outputs on the exact same six rows from the balanced LongBench-v2 `>500k` manifest.",
        "",
        "## Summary",
        "",
        "| Method | N | Correct | Accuracy | Total cost | Cost/example | Errors |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for method, stats in analysis["methods"].items():
        lines.append(
            f"| {labels[method]} | {stats['n']} | {stats['correct']} | "
            f"{stats['accuracy']*100:.1f}% | `${stats['total_cost_usd']:.6f}` | "
            f"`${stats['cost_per_example_usd']:.6f}` | {stats['errors']} |"
        )
    lines.extend([
        "",
        "## Paired Rows",
        "",
        "| Domain | Gold | RLM | BM25+Gemma | BM25+Gemini | Rerank+Gemini |",
        "|---|---:|---|---|---|---|",
    ])
    for row in analysis["paired_rows"]:
        def cell(method: str) -> str:
            m = row["methods"][method]
            mark = "OK" if m["correct"] else "MISS"
            err = " timeout" if m["error"] else ""
            return f"{m['prediction']} ({mark}{err})"
        lines.append(
            f"| {row['domain']} | {row['gold']} | {cell('standard_rlm')} | "
            f"{cell('bm25_gemma_vote')} | {cell('bm25_gemini_vote')} | "
            f"{cell('bm25_gemma_rerank_gemini_vote')} |"
        )
    lines.extend([
        "",
        "## Decision",
        "",
        f"- Scale standard RLM to N=30 now: `{analysis['decision']['scale_standard_rlm_to_n30_now']}`.",
        f"- Reason: {analysis['decision']['reason']}",
        f"- Paper role: {analysis['decision']['paper_role']}",
        "",
    ])
    out_md.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rlm", type=Path, default=ROOT / "results/lb2_over500k_standard_rlm_smoke_n6_20260714.jsonl")
    parser.add_argument("--retrieval", type=Path, default=ROOT / "results/lb2_over500k_retrieval_rerank_n30_retuned_20260714.jsonl")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("_reproduced/lb2_over500k_standard_rlm_smoke"),
        help="Generated-output directory; immutable released evidence is never overwritten.",
    )
    parser.add_argument("--out", type=Path)
    parser.add_argument("--table", type=Path)
    parser.add_argument("--md", type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.out = args.out or args.output_dir / "analysis.json"
    args.table = args.table or args.output_dir / "method_table.csv"
    args.md = args.md or args.output_dir / "analysis.md"
    for path in (args.out, args.table, args.md):
        path.parent.mkdir(parents=True, exist_ok=True)
    analysis = analyze(args.rlm, args.retrieval)
    args.out.write_text(json.dumps(analysis, indent=2, ensure_ascii=True), encoding="utf-8")
    write_table(analysis, args.table)
    write_md(analysis, args.md)
    print(json.dumps(analysis["methods"], indent=2))
    print(f"Analysis: {args.out}")
    print(f"Table: {args.table}")
    print(f"Markdown: {args.md}")


if __name__ == "__main__":
    main()
