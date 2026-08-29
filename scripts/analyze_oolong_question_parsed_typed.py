#!/usr/bin/env python3
"""Question-parsed typed aggregation for standard-unlabeled Oolong traces.

This is an API-free parity check for the SLM-labeler + typed aggregation
baseline. The original typed aggregation artifact intentionally uses Oolong
task/answer metadata after the SLM labels the rows. This script reuses the
stored SLM row-label predictions but infers the task and answer type from the
natural-language question before calling the typed solver.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from eval_oolong_slice import parse_gold, score_prediction  # noqa: E402
from eval_oolong_standard_slm_labeler_typed import (  # noqa: E402
    labeled_context_from_predictions,
    parse_unlabeled_rows,
)
from probe_typed_oolong_proxy import hydrate_selected_examples, solve_typed  # noqa: E402


FIELDNAMES = [
    "run_id",
    "example_id",
    "context_len",
    "task_group",
    "context_window_id",
    "inferred_task",
    "gold_task",
    "task_match",
    "inferred_answer_type",
    "gold_answer_type",
    "answer_type_match",
    "prediction",
    "gold",
    "correct",
    "cost_usd",
    "row_count",
    "row_label_exact",
    "row_label_accuracy",
    "typed_status",
    "typed_ops",
    "error",
    "question",
]


def load_manifest(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return list(payload["examples"] if isinstance(payload, dict) else payload)


def load_trace(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            out[str(row["example_id"])] = row
    return out


def infer_answer_type(question: str) -> str:
    q = question.lower()
    if "final answer in the form 'user:" in q or "final answer in the form \"user:" in q:
        return "ANSWER_TYPE.USER"
    if "final answer in the form 'date:" in q or "final answer in the form \"date:" in q:
        return "ANSWER_TYPE.DATE"
    if "final answer in the form 'label:" in q or "final answer in the form \"label:" in q:
        return "ANSWER_TYPE.LABEL"
    if "where [x] is the number" in q or "answer: number" in q:
        return "ANSWER_TYPE.NUMERIC"
    if "more common" in q or "less common" in q or "same frequency" in q:
        return "ANSWER_TYPE.COMPARISON"
    if re.search(r"how many .* represented exactly \d+ time", q):
        return "ANSWER_TYPE.NUMERIC"
    raise ValueError("could not infer answer_type")


def infer_task(question: str, answer_type: str) -> str:
    q = question.lower()
    if re.search(r"exactly\s+\d+\s+time", q):
        return "TASK_TYPE.REPRESENTED_N_TIMES"
    if "second most" in q:
        return "TASK_TYPE.SECOND_MOST_FREQ"
    if "least common" in q:
        return "TASK_TYPE.LEAST_FREQ"
    if "how many data points should be classified" in q:
        return "TASK_TYPE.NUMERIC_ONE_CLASS"
    if "for how many months" in q and ("more frequently than" in q or "single most" in q):
        return "TASK_TYPE.RELATIVE_FREQ"
    if "more common" in q or "less common" in q or "same frequency" in q:
        return "TASK_TYPE.RELATIVE_FREQ"
    if re.search(r"which user has more instances with the label", q):
        return "TASK_TYPE.RELATIVE_FREQ"
    if "most common" in q or "most often" in q or "the most instances with the label" in q:
        return "TASK_TYPE.MOST_FREQ"
    if answer_type == "ANSWER_TYPE.USER" and "represented" in q and "most" in q:
        return "TASK_TYPE.MOST_FREQ"
    raise ValueError("could not infer task")


def bootstrap_cluster_diff(rows: list[dict[str, Any]], reps: int = 5000) -> dict[str, float]:
    import random

    clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        clusters[str(row["context_window_id"])].append(row)
    keys = sorted(clusters)
    rng = random.Random(20260713)
    diffs_exact: list[float] = []
    diffs_score: list[float] = []
    for _ in range(reps):
        sample: list[dict[str, Any]] = []
        for key in (rng.choice(keys) for _ in keys):
            sample.extend(clusters[key])
        n = len(sample)
        if not n:
            continue
        diffs_exact.append(
            sum(float(r["qp_exact"]) - float(r["rlm_exact"]) for r in sample) / n
        )
        diffs_score.append(
            sum(float(r["qp_score"]) - float(r["rlm_score"]) for r in sample) / n
        )

    def pack(vals: list[float]) -> dict[str, float]:
        vals = sorted(vals)
        lo = vals[int(0.025 * len(vals))]
        hi = vals[min(len(vals) - 1, int(0.975 * len(vals)))]
        return {"mean": mean(vals), "ci_low": lo, "ci_high": hi}

    return {"exact_diff": pack(diffs_exact), "score_diff": pack(diffs_score), "clusters": len(keys)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--trace", type=Path, required=True)
    ap.add_argument("--rlm-csv", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--summary-out", type=Path, required=True)
    ap.add_argument("--run-id", default="oolong_standard_multilength_n120_slm_labeler_question_parsed_typed_20260713")
    ap.add_argument("--dataset-split", choices=["test", "validation"], default="test")
    ap.add_argument("--rlm-score-column", default="correct")
    args = ap.parse_args()

    manifest = load_manifest(args.manifest)
    trace_by_id = load_trace(args.trace)
    hydrated = hydrate_selected_examples(manifest, split=args.dataset_split)
    rlm_by_id: dict[str, dict[str, str]] = {}
    with args.rlm_csv.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rlm_by_id[str(row["example_id"])] = row

    rows_out: list[dict[str, str]] = []
    paired_rows: list[dict[str, Any]] = []
    for ex in hydrated:
        eid = str(ex["id"])
        trace = trace_by_id[eid]
        error = ""
        prediction = ""
        status = ""
        ops: list[str] = []
        try:
            answer_type = infer_answer_type(ex["question"])
            task = infer_task(ex["question"], answer_type)
            unlabeled_rows = parse_unlabeled_rows(ex["context_window_text"])
            ex2 = dict(ex)
            ex2["answer_type"] = answer_type
            ex2["task"] = task
            ex2["context_window_text_with_labels"] = labeled_context_from_predictions(
                unlabeled_rows,
                list(trace["predicted_labels"]),
                ex["context_window_text"],
            )
            prediction, ops, status = solve_typed(ex2)
            if prediction is None:
                prediction = ""
        except Exception as exc:  # noqa: BLE001
            answer_type = ""
            task = ""
            error = f"{type(exc).__name__}: {exc}"
            prediction = ""
            status = "question_parse_error"
            ops = ["question_parse_error"]

        gold = parse_gold(ex.get("answer", ""), ex.get("answer_type", ""))
        score = score_prediction(str(prediction), gold, ex.get("answer_type", ""))
        row = {
            "run_id": args.run_id,
            "example_id": eid,
            "context_len": str(ex["context_len"]),
            "task_group": str(ex["task_group"]),
            "context_window_id": str(ex["context_window_id"]),
            "inferred_task": task,
            "gold_task": str(ex["task"]),
            "task_match": str(task == str(ex["task"])),
            "inferred_answer_type": answer_type,
            "gold_answer_type": str(ex["answer_type"]),
            "answer_type_match": str(answer_type == str(ex["answer_type"])),
            "prediction": str(prediction),
            "gold": str(gold),
            "correct": str(round(score, 4)),
            "cost_usd": str(trace.get("estimated_cost_usd") or trace.get("cost_usd") or 0.0),
            "row_count": str(trace.get("row_count", "")),
            "row_label_exact": str(trace.get("row_label_exact", "")),
            "row_label_accuracy": str(round(float(trace["row_label_accuracy"]), 6)) if trace.get("row_label_accuracy") is not None else "",
            "typed_status": status,
            "typed_ops": ";".join(ops),
            "error": error,
            "question": ex["question"],
        }
        rows_out.append(row)
        rlm = rlm_by_id[eid]
        paired_rows.append({
            "context_window_id": ex["context_window_id"],
            "qp_exact": 1.0 if math.isclose(score, 1.0) else 0.0,
            "rlm_exact": 1.0 if math.isclose(float(rlm[args.rlm_score_column]), 1.0) else 0.0,
            "qp_score": score,
            "rlm_score": float(rlm[args.rlm_score_column]),
        })

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows_out)

    n = len(rows_out)
    exact = sum(1 for r in rows_out if math.isclose(float(r["correct"]), 1.0))
    score_sum = sum(float(r["correct"]) for r in rows_out)
    cost = sum(float(r["cost_usd"] or 0.0) for r in rows_out)
    errors = sum(1 for r in rows_out if r["error"])
    task_matches = sum(1 for r in rows_out if r["task_match"] == "True")
    answer_matches = sum(1 for r in rows_out if r["answer_type_match"] == "True")
    by_group = defaultdict(list)
    by_length = defaultdict(list)
    for r in rows_out:
        by_group[r["task_group"]].append(float(r["correct"]))
        by_length[r["context_len"]].append(float(r["correct"]))
    rlm_exact = sum(1 for r in paired_rows if r["rlm_exact"])
    b = sum(1 for r in paired_rows if r["qp_exact"] and not r["rlm_exact"])
    c = sum(1 for r in paired_rows if r["rlm_exact"] and not r["qp_exact"])

    summary = {
        "run_id": args.run_id,
        "n": n,
        "exact_count": exact,
        "exact_rate": exact / n,
        "mean_score": score_sum / n,
        "cost_usd": cost,
        "errors": errors,
        "task_parse_accuracy_vs_metadata": task_matches / n,
        "answer_type_parse_accuracy_vs_metadata": answer_matches / n,
        "rlm_exact_count": rlm_exact,
        "paired_exact": {"b_qp_right_rlm_wrong": b, "c_rlm_right_qp_wrong": c},
        "cluster_bootstrap_paired_diff": bootstrap_cluster_diff(paired_rows),
        "by_group": {
            k: {
                "n": len(v),
                "exact_count": sum(1 for x in v if math.isclose(x, 1.0)),
                "mean_score": mean(v),
            }
            for k, v in sorted(by_group.items())
        },
        "by_length": {
            k: {
                "n": len(v),
                "exact_count": sum(1 for x in v if math.isclose(x, 1.0)),
                "mean_score": mean(v),
            }
            for k, v in sorted(by_length.items(), key=lambda kv: int(kv[0]))
        },
        "metadata_contract": "Question parser infers task and answer_type from natural-language question; stored SLM row-label predictions are reused; no new model/API calls.",
        "dataset_split": args.dataset_split,
        "rlm_score_column": args.rlm_score_column,
    }
    args.summary_out.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
