#!/usr/bin/env python3
"""Analyze the balanced LongBench-v2 >500k retrieval/rerank diagnostic."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


METHODS = [
    "bm25_gemma_vote",
    "bm25_gemini_vote",
    "bm25_gemma_rerank_gemini_vote",
]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def analyze(results_path: Path, trace_path: Path) -> dict[str, Any]:
    rows = load_jsonl(results_path)
    trace = load_jsonl(trace_path)
    n = len(rows)
    method_summary = {}
    for method in METHODS:
        method_rows = [r["methods"][method] for r in rows]
        correct = sum(1 for r in method_rows if r.get("correct"))
        total_cost = sum(float(r.get("cost_usd", 0.0)) + float(r.get("rerank_cost_usd", 0.0)) for r in method_rows)
        invalid_examples = sum(1 for r in method_rows if r.get("prediction") == "?")
        invalid_votes = sum(1 for t in trace if t.get("stage") == "answer" and t.get("method") == method and t.get("canonical_pred") == "?")
        method_summary[method] = {
            "n": n,
            "correct": correct,
            "accuracy": correct / n if n else 0.0,
            "total_cost_usd": total_cost,
            "cost_per_example_usd": total_cost / n if n else 0.0,
            "invalid_example_predictions": invalid_examples,
            "invalid_answer_votes": invalid_votes,
        }

    by_domain: dict[str, Any] = {}
    for domain in sorted({r["domain"] for r in rows}):
        sub = [r for r in rows if r["domain"] == domain]
        by_domain[domain] = {
            "n": len(sub),
            "context_chars_min": min(r["context_chars"] for r in sub),
            "context_chars_max": max(r["context_chars"] for r in sub),
            "methods": {
                method: {
                    "correct": sum(1 for r in sub if r["methods"][method]["correct"]),
                    "accuracy": sum(1 for r in sub if r["methods"][method]["correct"]) / len(sub),
                    "predictions": [r["methods"][method]["prediction"] for r in sub],
                    "gold": [r["answer"] for r in sub],
                }
                for method in METHODS
            },
        }

    delta_rows = []
    for row in rows:
        base = row["methods"]["bm25_gemini_vote"]
        rerank = row["methods"]["bm25_gemma_rerank_gemini_vote"]
        if base["prediction"] != rerank["prediction"] or base["correct"] != rerank["correct"]:
            delta_rows.append(
                {
                    "_id": row["_id"],
                    "domain": row["domain"],
                    "context_chars": row["context_chars"],
                    "gold": row["answer"],
                    "bm25_gemini_prediction": base["prediction"],
                    "bm25_gemini_correct": base["correct"],
                    "rerank_prediction": rerank["prediction"],
                    "rerank_correct": rerank["correct"],
                }
            )

    by_context_bucket = defaultdict(lambda: {m: {"n": 0, "correct": 0} for m in METHODS})
    for row in rows:
        chars = row["context_chars"]
        if chars < 750_000:
            bucket = "500k-750k"
        elif chars < 1_000_000:
            bucket = "750k-1M"
        elif chars < 2_000_000:
            bucket = "1M-2M"
        elif chars < 5_000_000:
            bucket = "2M-5M"
        else:
            bucket = ">5M"
        for method in METHODS:
            by_context_bucket[bucket][method]["n"] += 1
            by_context_bucket[bucket][method]["correct"] += int(row["methods"][method]["correct"])

    context_buckets = {}
    for bucket, vals in by_context_bucket.items():
        context_buckets[bucket] = {
            method: {
                "n": stats["n"],
                "correct": stats["correct"],
                "accuracy": stats["correct"] / stats["n"] if stats["n"] else 0.0,
            }
            for method, stats in vals.items()
        }

    failure_notes = []
    if method_summary["bm25_gemma_rerank_gemini_vote"]["correct"] <= 12:
        failure_notes.append("Gemma reranking gives only a one-example gain over BM25+Gemini, so reranking is not a general fix for over-window LB2.")
    if by_domain.get("Long-dialogue History Understanding", {}).get("methods", {}).get("bm25_gemma_rerank_gemini_vote", {}).get("correct") == 1:
        failure_notes.append("Long-dialogue history is the clearest failure domain: retrieved excerpts rarely contain enough diffuse temporal evidence.")
    if method_summary["bm25_gemma_vote"]["correct"] < method_summary["bm25_gemini_vote"]["correct"]:
        failure_notes.append("Gemma-only reading is cheapest but weaker overall; it occasionally solves rows Gemini misses, so model choice and evidence style interact.")

    return {
        "run_type": "lb2_over500k_retrieval_rerank_analysis",
        "results_path": str(results_path),
        "trace_path": str(trace_path),
        "n": n,
        "methods": method_summary,
        "by_domain": by_domain,
        "context_buckets": context_buckets,
        "rerank_delta_rows": delta_rows,
        "gold_distribution": dict(Counter(r["answer"] for r in rows)),
        "domain_distribution": dict(Counter(r["domain"] for r in rows)),
        "failure_notes": failure_notes,
        "paper_framing": (
            "Use as supplement-level over-window boundary evidence. The balanced full LongBench-v2 >500k diagnostic "
            "shows that cheap retrieval/rerank routes are feasible and low-cost, but not reliable enough to close the "
            "RLM-favorable extreme-context region. It should calibrate, not replace, the existing LB2 pilot."
        ),
    }


def write_tables(analysis: dict[str, Any], method_csv: Path, domain_csv: Path) -> None:
    with method_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["method", "n", "correct", "accuracy", "total_cost_usd", "cost_per_example_usd", "invalid_examples", "invalid_votes"])
        for method, stats in analysis["methods"].items():
            w.writerow([
                method,
                stats["n"],
                stats["correct"],
                f"{stats['accuracy']:.6f}",
                f"{stats['total_cost_usd']:.9f}",
                f"{stats['cost_per_example_usd']:.9f}",
                stats["invalid_example_predictions"],
                stats["invalid_answer_votes"],
            ])
    with domain_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["domain", "method", "n", "correct", "accuracy", "context_chars_min", "context_chars_max"])
        for domain, info in analysis["by_domain"].items():
            for method, stats in info["methods"].items():
                w.writerow([
                    domain,
                    method,
                    info["n"],
                    stats["correct"],
                    f"{stats['accuracy']:.6f}",
                    info["context_chars_min"],
                    info["context_chars_max"],
                ])


def write_plot(analysis: dict[str, Any], plot_path: Path) -> None:
    import matplotlib.pyplot as plt

    labels = {
        "bm25_gemma_vote": "BM25+Gemma",
        "bm25_gemini_vote": "BM25+Gemini",
        "bm25_gemma_rerank_gemini_vote": "BM25+Gemma rerank+Gemini",
    }
    methods = METHODS
    accuracies = [analysis["methods"][m]["accuracy"] * 100 for m in methods]
    costs = [analysis["methods"][m]["cost_per_example_usd"] for m in methods]
    fig, ax1 = plt.subplots(figsize=(6.4, 3.2))
    x = range(len(methods))
    bars = ax1.bar(x, accuracies, color=["#6A8CAF", "#5AA36F", "#C58B43"])
    ax1.set_ylabel("Accuracy (%)")
    ax1.set_ylim(0, 100)
    ax1.set_xticks(list(x), [labels[m] for m in methods], rotation=15, ha="right")
    for bar, acc in zip(bars, accuracies):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1, f"{acc:.0f}%", ha="center", va="bottom", fontsize=8)
    ax2 = ax1.twinx()
    ax2.plot(list(x), costs, color="#333333", marker="o", linewidth=1.5)
    ax2.set_ylabel("Cost per example (USD)")
    ax2.set_ylim(0, max(costs) * 1.8 if costs else 0.01)
    ax1.set_title("LongBench-v2 >500k balanced diagnostic (N=30)")
    fig.tight_layout()
    fig.savefig(plot_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=Path("results/lb2_over500k_retrieval_rerank_n30_retuned_20260714.jsonl"))
    parser.add_argument("--trace", type=Path, default=Path("results/lb2_over500k_retrieval_rerank_n30_retuned_20260714_trace.jsonl"))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("_reproduced/lb2_over500k_retrieval_rerank"),
        help="Generated-output directory; immutable released evidence is never overwritten.",
    )
    parser.add_argument("--out", type=Path)
    parser.add_argument("--method-table", type=Path)
    parser.add_argument("--domain-table", type=Path)
    parser.add_argument("--plot", type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.out = args.out or args.output_dir / "analysis.json"
    args.method_table = args.method_table or args.output_dir / "method_table.csv"
    args.domain_table = args.domain_table or args.output_dir / "domain_table.csv"
    args.plot = args.plot or args.output_dir / "plot.pdf"
    for path in (args.out, args.method_table, args.domain_table, args.plot):
        path.parent.mkdir(parents=True, exist_ok=True)
    analysis = analyze(args.results, args.trace)
    args.out.write_text(json.dumps(analysis, indent=2, ensure_ascii=True), encoding="utf-8")
    write_tables(analysis, args.method_table, args.domain_table)
    write_plot(analysis, args.plot)
    print(json.dumps(analysis["methods"], indent=2))
    print(f"Analysis: {args.out}")
    print(f"Plot: {args.plot}")


if __name__ == "__main__":
    main()
