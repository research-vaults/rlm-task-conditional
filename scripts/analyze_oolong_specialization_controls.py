#!/usr/bin/env python3
"""No-call specialization controls for the Oolong CD-45 typed route.

The main SLM+typed route is intentionally deployment-specialized: a small
model labels local rows, then a typed deterministic solver executes the
question's operation family. This script stress-tests that specialization
without making any new model/API calls. It reuses the stored SLM row-label
predictions from CD-45 and compares:

* metadata_oracle: benchmark task/answer_type metadata;
* question_parsed: task/answer_type inferred from the natural-language question;
* wrong_family_rotated: an intentionally wrong operation family; and
* generic_label_route: a naive fixed "most frequent label" route.

The wrong-family rows are not baselines and should not be framed as a fair
method. They are falsification-style controls: if they stayed strong, the paper's
claim that typed-route success depends on correct operation-family specialization
would be weaker.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from analyze_oolong_question_parsed_typed import infer_answer_type, infer_task, load_manifest, load_trace  # noqa: E402
from eval_oolong_slice import parse_gold, score_prediction  # noqa: E402
from eval_oolong_standard_slm_labeler_typed import labeled_context_from_predictions, parse_unlabeled_rows  # noqa: E402
from probe_typed_oolong_proxy import hydrate_selected_examples, solve_typed  # noqa: E402


FIELDNAMES = [
    "run_id",
    "route",
    "example_id",
    "context_len",
    "task_group",
    "context_window_id",
    "task_used",
    "answer_type_used",
    "gold_task",
    "gold_answer_type",
    "prediction",
    "gold",
    "score",
    "exact",
    "typed_status",
    "typed_ops",
    "error",
    "question",
]


def wrong_family_route(task_group: str) -> tuple[str, str]:
    """Rotate to a deliberately wrong high-level operation/output family."""
    if task_group == "counting":
        return "TASK_TYPE.MOST_FREQ", "ANSWER_TYPE.USER"
    if task_group == "user":
        return "TASK_TYPE.MOST_FREQ", "ANSWER_TYPE.DATE"
    if task_group == "timeline":
        return "TASK_TYPE.NUMERIC_ONE_CLASS", "ANSWER_TYPE.NUMERIC"
    return "TASK_TYPE.MOST_FREQ", "ANSWER_TYPE.LABEL"


def route_specs(ex: dict[str, Any]) -> dict[str, tuple[str, str]]:
    inferred_answer_type = infer_answer_type(ex["question"])
    inferred_task = infer_task(ex["question"], inferred_answer_type)
    wrong_task, wrong_answer_type = wrong_family_route(str(ex["task_group"]))
    return {
        "metadata_oracle": (str(ex["task"]), str(ex["answer_type"])),
        "question_parsed": (inferred_task, inferred_answer_type),
        "wrong_family_rotated": (wrong_task, wrong_answer_type),
        "generic_label_route": ("TASK_TYPE.MOST_FREQ", "ANSWER_TYPE.LABEL"),
    }


def score_route(ex: dict[str, Any], trace: dict[str, Any], route: str, task: str, answer_type: str) -> dict[str, str]:
    error = ""
    pred = ""
    status = ""
    ops: list[str] = []
    try:
        unlabeled_rows = parse_unlabeled_rows(ex["context_window_text"])
        ex2 = dict(ex)
        ex2["task"] = task
        ex2["answer_type"] = answer_type
        ex2["context_window_text_with_labels"] = labeled_context_from_predictions(
            unlabeled_rows,
            list(trace["predicted_labels"]),
            ex["context_window_text"],
        )
        pred, ops, status = solve_typed(ex2)
        if pred is None:
            pred = ""
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
        pred = ""
        status = "route_error"
        ops = ["route_error"]

    gold = parse_gold(ex.get("answer", ""), ex.get("answer_type", ""))
    score = score_prediction(str(pred), gold, ex.get("answer_type", ""))
    return {
        "run_id": "oolong_context_disjoint_cd45_specialization_controls_20260716",
        "route": route,
        "example_id": str(ex["id"]),
        "context_len": str(ex["context_len"]),
        "task_group": str(ex["task_group"]),
        "context_window_id": str(ex["context_window_id"]),
        "task_used": task,
        "answer_type_used": answer_type,
        "gold_task": str(ex["task"]),
        "gold_answer_type": str(ex["answer_type"]),
        "prediction": str(pred),
        "gold": str(gold),
        "score": str(round(score, 6)),
        "exact": str(math.isclose(score, 1.0)),
        "typed_status": status,
        "typed_ops": ";".join(ops),
        "error": error,
        "question": ex["question"],
    }


def summarize(rows: list[dict[str, str]]) -> dict[str, Any]:
    by_route: dict[str, list[dict[str, str]]] = defaultdict(list)
    by_route_group: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        by_route[row["route"]].append(row)
        by_route_group[row["route"]][row["task_group"]].append(float(row["score"]))

    routes: dict[str, Any] = {}
    for route, route_rows in sorted(by_route.items()):
        scores = [float(r["score"]) for r in route_rows]
        exact_count = sum(1 for r in route_rows if r["exact"] == "True")
        routes[route] = {
            "n": len(route_rows),
            "exact_count": exact_count,
            "exact_rate": exact_count / len(route_rows),
            "mean_score": mean(scores),
            "errors": sum(1 for r in route_rows if r["error"]),
            "status_counts": dict(Counter(r["typed_status"] for r in route_rows)),
            "by_group": {
                group: {
                    "n": len(vals),
                    "exact_count": sum(
                        1
                        for r in route_rows
                        if r["task_group"] == group and r["exact"] == "True"
                    ),
                    "mean_score": mean(vals),
                }
                for group, vals in sorted(by_route_group[route].items())
            },
        }

    qp = routes["question_parsed"]
    wrong = routes["wrong_family_rotated"]
    generic = routes["generic_label_route"]
    return {
        "run_id": "oolong_context_disjoint_cd45_specialization_controls_20260716",
        "n": qp["n"],
        "contract": (
            "No new model/API calls. Reuses stored Gemma SLM row-label predictions "
            "from CD-45 and changes only the typed operation family before scoring "
            "against the original Oolong gold answer."
        ),
        "interpretation": (
            "wrong_family_rotated and generic_label_route are stress tests, not fair "
            "baselines. They show whether the SLM+typed result depends on correct "
            "operation-family specialization."
        ),
        "routes": routes,
        "specialization_drop_exact_points": round(
            100 * (qp["exact_rate"] - wrong["exact_rate"]), 3
        ),
        "generic_drop_exact_points": round(
            100 * (qp["exact_rate"] - generic["exact_rate"]), 3
        ),
    }


def write_markdown(summary: dict[str, Any], path: Path) -> None:
    routes = summary["routes"]
    lines = [
        "# Oolong CD-45 Specialization Controls",
        "",
        f"Run id: `{summary['run_id']}`",
        "",
        summary["contract"],
        "",
        summary["interpretation"],
        "",
        "| Route | Exact | Exact rate | Mean score | Errors | Interpretation |",
        "|---|---:|---:|---:|---:|---|",
    ]
    descriptions = {
        "metadata_oracle": "Uses benchmark task/answer_type metadata.",
        "question_parsed": "Infers task/answer_type from the question; main CD-45 typed route.",
        "wrong_family_rotated": "Intentionally rotates to a wrong task family; stress test only.",
        "generic_label_route": "Naive fixed most-frequent-label route; stress test only.",
    }
    for route in ["metadata_oracle", "question_parsed", "wrong_family_rotated", "generic_label_route"]:
        r = routes[route]
        lines.append(
            f"| `{route}` | {r['exact_count']}/{r['n']} | {100*r['exact_rate']:.1f}% | "
            f"{100*r['mean_score']:.1f}% | {r['errors']} | {descriptions[route]} |"
        )
    lines.extend(
        [
            "",
            f"Exact-rate drop from question-parsed to wrong-family route: {summary['specialization_drop_exact_points']:.1f} points.",
            f"Exact-rate drop from question-parsed to generic-label route: {summary['generic_drop_exact_points']:.1f} points.",
            "",
            "Paper use: this artifact should be cited as a specialization stress test, not as a competing method. It supports the claim that SLM+typed success depends on correct deployment prior knowledge about the operation family.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=PROJECT_ROOT / "results/oolong_context_disjoint_n45_manifest_20260715.json")
    ap.add_argument("--trace", type=Path, default=PROJECT_ROOT / "results/oolong_context_disjoint_n45_slm_labeler_typed_20260715_trace.jsonl")
    ap.add_argument("--out", type=Path, default=PROJECT_ROOT / "results/oolong_context_disjoint_cd45_specialization_controls_20260716.csv")
    ap.add_argument("--summary-out", type=Path, default=PROJECT_ROOT / "results/oolong_context_disjoint_cd45_specialization_controls_20260716_summary.json")
    ap.add_argument("--md-out", type=Path, default=PROJECT_ROOT / "results/oolong_context_disjoint_cd45_specialization_controls_20260716.md")
    args = ap.parse_args()

    manifest = load_manifest(args.manifest)
    trace_by_id = load_trace(args.trace)
    examples = hydrate_selected_examples(manifest)

    rows: list[dict[str, str]] = []
    for ex in examples:
        trace = trace_by_id[str(ex["id"])]
        for route, (task, answer_type) in route_specs(ex).items():
            rows.append(score_route(ex, trace, route, task, answer_type))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    summary = summarize(rows)
    args.summary_out.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(summary, args.md_out)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
