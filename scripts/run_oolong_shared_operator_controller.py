#!/usr/bin/env python3
"""Run an LLM controller over the same typed Oolong operator library.

This is a paid but cheap diagnostic, not a standard-RLM reproduction. It tests a
specific fairness question raised in reviews: if a large controller is given the
same typed operation library used by SLM+typed, can it select the operation
family from the question and close the route-selection concern?

Contract:
* standard Oolong context contract is preserved via stored CD-45 SLM row labels;
* the controller sees the natural-language question and a compact operator
  schema, not benchmark metadata;
* deterministic typed execution then runs over the stored SLM row labels;
* every prompt, raw response, parsed operator, prediction, score, and cost is
  logged.

This is deliberately labeled "shared-operator controller". Do not call it
standard `rlms`, official SRLM, or lambda-RLM.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from analyze_oolong_question_parsed_typed import load_manifest, load_trace  # noqa: E402
from eval_oolong_slice import estimate_cost, parse_gold, score_prediction  # noqa: E402
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
    "controller_model",
    "selected_task",
    "selected_answer_type",
    "gold_task",
    "gold_answer_type",
    "task_match",
    "answer_type_match",
    "prediction",
    "gold",
    "score",
    "exact",
    "cost_usd",
    "input_tokens",
    "output_tokens",
    "latency_s",
    "typed_status",
    "typed_ops",
    "parse_error",
    "execution_error",
    "question",
]

TASKS = [
    "TASK_TYPE.MOST_FREQ",
    "TASK_TYPE.LEAST_FREQ",
    "TASK_TYPE.NUMERIC_ONE_CLASS",
    "TASK_TYPE.RELATIVE_FREQ",
    "TASK_TYPE.REPRESENTED_N_TIMES",
    "TASK_TYPE.SECOND_MOST_FREQ",
]

ANSWER_TYPES = [
    "ANSWER_TYPE.LABEL",
    "ANSWER_TYPE.USER",
    "ANSWER_TYPE.DATE",
    "ANSWER_TYPE.NUMERIC",
    "ANSWER_TYPE.COMPARISON",
]


def load_optional_env_file() -> None:
    env_file = os.environ.get("RLM_OPENROUTER_ENV_FILE")
    if not env_file:
        return
    env_path = Path(env_file).expanduser()
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip("'\"")


def build_prompt(question: str) -> str:
    task_lines = "\n".join(f"- {task}" for task in TASKS)
    answer_lines = "\n".join(f"- {answer_type}" for answer_type in ANSWER_TYPES)
    return (
        "You are selecting a typed aggregation operator for an Oolong-style "
        "long-context aggregation question. You are not answering the question. "
        "Choose only the operation family and output type needed by the typed "
        "operator library.\n\n"
        "Available task operators:\n"
        f"{task_lines}\n\n"
        "Available answer types:\n"
        f"{answer_lines}\n\n"
        "Definitions:\n"
        "- MOST_FREQ: choose the most common label, user, date, or month.\n"
        "- LEAST_FREQ: choose the least common label, user, date, or month.\n"
        "- NUMERIC_ONE_CLASS: count rows of one named class/filter.\n"
        "- RELATIVE_FREQ: compare two labels/users/classes and output more/less/same.\n"
        "- REPRESENTED_N_TIMES: count how many values appear exactly K times.\n"
        "- SECOND_MOST_FREQ: choose the second most frequent value.\n\n"
        "Return JSON only with exactly these keys:\n"
        '{"task":"TASK_TYPE...","answer_type":"ANSWER_TYPE..."}\n\n'
        f"Question:\n{question}\n"
    )


def call_openrouter(prompt: str, model: str, timeout: float) -> tuple[str, int, int, float]:
    load_optional_env_file()
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENROUTER_API_KEY not set")
    import openai

    client = openai.OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        timeout=timeout,
    )
    t0 = time.time()
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=96,
    )
    latency = time.time() - t0
    text = response.choices[0].message.content or ""
    usage = response.usage
    input_tokens = usage.prompt_tokens if usage else max(1, len(prompt) // 4)
    output_tokens = usage.completion_tokens if usage else max(1, len(text) // 4)
    return text, int(input_tokens), int(output_tokens), latency


def parse_controller_json(raw: str) -> tuple[str, str]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if m:
        text = m.group(0)
    payload = json.loads(text)
    task = str(payload.get("task", "")).strip()
    answer_type = str(payload.get("answer_type", "")).strip()
    if task not in TASKS:
        raise ValueError(f"invalid task: {task!r}")
    if answer_type not in ANSWER_TYPES:
        raise ValueError(f"invalid answer_type: {answer_type!r}")
    return task, answer_type


def execute_typed(ex: dict[str, Any], trace: dict[str, Any], task: str, answer_type: str) -> tuple[str, list[str], str]:
    unlabeled_rows = parse_unlabeled_rows(ex["context_window_text"])
    ex2 = dict(ex)
    ex2["task"] = task
    ex2["answer_type"] = answer_type
    ex2["context_window_text_with_labels"] = labeled_context_from_predictions(
        unlabeled_rows,
        list(trace["predicted_labels"]),
        ex["context_window_text"],
    )
    prediction, ops, status = solve_typed(ex2)
    return "" if prediction is None else str(prediction), ops, status


def summarize(rows: list[dict[str, str]], run_id: str, model: str, trace_path: Path, out_path: Path) -> dict[str, Any]:
    scores = [float(r["score"]) for r in rows]
    exact = sum(1 for r in rows if r["exact"] == "True")
    by_group: dict[str, list[dict[str, str]]] = defaultdict(list)
    by_length: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_group[row["task_group"]].append(row)
        by_length[row["context_len"]].append(row)

    def pack(group_rows: list[dict[str, str]]) -> dict[str, Any]:
        vals = [float(r["score"]) for r in group_rows]
        return {
            "n": len(group_rows),
            "exact_count": sum(1 for r in group_rows if r["exact"] == "True"),
            "exact_rate": sum(1 for r in group_rows if r["exact"] == "True") / len(group_rows) if group_rows else 0,
            "mean_score": mean(vals) if vals else 0,
            "cost_usd": sum(float(r["cost_usd"] or 0) for r in group_rows),
            "parse_errors": sum(1 for r in group_rows if r["parse_error"]),
            "execution_errors": sum(1 for r in group_rows if r["execution_error"]),
        }

    def rel(path: Path) -> str:
        path = path if path.is_absolute() else (PROJECT_ROOT / path)
        try:
            return str(path.resolve().relative_to(PROJECT_ROOT))
        except ValueError:
            return str(path)

    return {
        "run_id": run_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "contract": (
            "LLM controller selects task/answer_type from question only; existing typed "
            "Oolong operator library executes over stored CD-45 Gemma row-label predictions. "
            "This is a shared-operator controller diagnostic, not standard rlms or official SRLM/lambda-RLM."
        ),
        "n": len(rows),
        "exact_count": exact,
        "exact_rate": exact / len(rows) if rows else 0,
        "score_sum": sum(scores),
        "mean_score": mean(scores) if scores else 0,
        "cost_usd": sum(float(r["cost_usd"] or 0) for r in rows),
        "task_match_count": sum(1 for r in rows if r["task_match"] == "True"),
        "answer_type_match_count": sum(1 for r in rows if r["answer_type_match"] == "True"),
        "parse_errors": sum(1 for r in rows if r["parse_error"]),
        "execution_errors": sum(1 for r in rows if r["execution_error"]),
        "by_group": {k: pack(v) for k, v in sorted(by_group.items())},
        "by_length": {k: pack(v) for k, v in sorted(by_length.items(), key=lambda kv: int(kv[0]))},
        "selected_task_counts": dict(Counter(r["selected_task"] for r in rows)),
        "selected_answer_type_counts": dict(Counter(r["selected_answer_type"] for r in rows)),
        "source_csv": rel(out_path),
        "trace_jsonl": rel(trace_path),
    }


def write_markdown(summary: dict[str, Any], md_path: Path) -> None:
    lines = [
        "# Oolong CD-45 Shared-Operator Controller Diagnostic",
        "",
        f"Run id: `{summary['run_id']}`",
        f"Model: `{summary['model']}`",
        "",
        summary["contract"],
        "",
        "## Headline",
        "",
        f"- Exact: {summary['exact_count']}/{summary['n']} ({100*summary['exact_rate']:.1f}%).",
        f"- Mean score: {100*summary['mean_score']:.1f}%.",
        f"- Controller API cost: `${summary['cost_usd']:.6f}`.",
        f"- Task matches metadata: {summary['task_match_count']}/{summary['n']}.",
        f"- Answer-type matches metadata: {summary['answer_type_match_count']}/{summary['n']}.",
        f"- Parse errors: {summary['parse_errors']}; execution errors: {summary['execution_errors']}.",
        "",
        "## By Group",
        "",
        "| Group | Exact | Mean score | Cost | Parse err. | Exec. err. |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for group, row in summary["by_group"].items():
        lines.append(
            f"| {group} | {row['exact_count']}/{row['n']} | {100*row['mean_score']:.1f}% | "
            f"${row['cost_usd']:.6f} | {row['parse_errors']} | {row['execution_errors']} |"
        )
    lines.extend(
        [
            "",
            "## Paper Use",
            "",
            "Use this as a fairness/control diagnostic only. It shows what happens when a large controller receives the same typed operator menu as the SLM+typed route and chooses the route from the natural-language question. It does not reproduce standard `rlms`, does not provide generated Python traces, and does not close the official SRLM/lambda-RLM comparator gap.",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=PROJECT_ROOT / "results/oolong_context_disjoint_n45_manifest_20260715.json")
    ap.add_argument("--trace", type=Path, default=PROJECT_ROOT / "results/oolong_context_disjoint_n45_slm_labeler_typed_20260715_trace.jsonl")
    ap.add_argument("--out", type=Path, default=PROJECT_ROOT / "results/oolong_context_disjoint_cd45_shared_operator_controller_20260716.csv")
    ap.add_argument("--summary-out", type=Path, default=PROJECT_ROOT / "results/oolong_context_disjoint_cd45_shared_operator_controller_20260716_summary.json")
    ap.add_argument("--trace-out", type=Path, default=PROJECT_ROOT / "results/oolong_context_disjoint_cd45_shared_operator_controller_20260716_trace.jsonl")
    ap.add_argument("--md-out", type=Path, default=PROJECT_ROOT / "results/oolong_context_disjoint_cd45_shared_operator_controller_20260716.md")
    ap.add_argument("--run-id", default="oolong_context_disjoint_cd45_shared_operator_controller_20260716")
    ap.add_argument("--model", default="google/gemini-2.5-flash")
    ap.add_argument("--limit", type=int, default=0, help="Optional first-N smoke limit.")
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    manifest = load_manifest(args.manifest)
    if args.limit:
        manifest = manifest[: args.limit]
    examples = hydrate_selected_examples(manifest)
    trace_by_id = load_trace(args.trace)

    done: set[str] = set()
    if args.out.exists() and not args.overwrite:
        with args.out.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("run_id") == args.run_id:
                    done.add(row["example_id"])

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.trace_out.parent.mkdir(parents=True, exist_ok=True)
    new_file = args.overwrite or not args.out.exists()
    mode = "w" if args.overwrite else "a"
    trace_mode = "w" if args.overwrite else "a"

    with args.out.open(mode, newline="", encoding="utf-8") as f_csv, args.trace_out.open(trace_mode, encoding="utf-8") as f_trace:
        writer = csv.DictWriter(f_csv, fieldnames=FIELDNAMES)
        if new_file:
            writer.writeheader()

        for i, ex in enumerate(examples, start=1):
            eid = str(ex["id"])
            if eid in done:
                print(f"[{i}/{len(examples)}] {eid}: skip existing")
                continue
            prompt = build_prompt(ex["question"])
            raw = ""
            input_tokens = 0
            output_tokens = 0
            latency = 0.0
            cost = 0.0
            parse_error = ""
            execution_error = ""
            task = ""
            answer_type = ""
            prediction = ""
            ops: list[str] = []
            status = ""
            try:
                raw, input_tokens, output_tokens, latency = call_openrouter(prompt, args.model, args.timeout)
                cost = estimate_cost(args.model, input_tokens, output_tokens)
                task, answer_type = parse_controller_json(raw)
            except Exception as exc:  # noqa: BLE001
                parse_error = f"{type(exc).__name__}: {exc}"
            if not parse_error:
                try:
                    prediction, ops, status = execute_typed(ex, trace_by_id[eid], task, answer_type)
                except Exception as exc:  # noqa: BLE001
                    execution_error = f"{type(exc).__name__}: {exc}"
                    prediction = ""
                    status = "execution_error"
                    ops = ["execution_error"]
            gold = parse_gold(ex.get("answer", ""), ex.get("answer_type", ""))
            score = score_prediction(prediction, gold, ex.get("answer_type", ""))
            row = {
                "run_id": args.run_id,
                "example_id": eid,
                "context_len": str(ex["context_len"]),
                "task_group": str(ex["task_group"]),
                "context_window_id": str(ex["context_window_id"]),
                "controller_model": args.model,
                "selected_task": task,
                "selected_answer_type": answer_type,
                "gold_task": str(ex["task"]),
                "gold_answer_type": str(ex["answer_type"]),
                "task_match": str(task == str(ex["task"])),
                "answer_type_match": str(answer_type == str(ex["answer_type"])),
                "prediction": prediction,
                "gold": str(gold),
                "score": str(round(score, 6)),
                "exact": str(score == 1.0),
                "cost_usd": str(round(cost, 9)),
                "input_tokens": str(input_tokens),
                "output_tokens": str(output_tokens),
                "latency_s": str(round(latency, 3)),
                "typed_status": status,
                "typed_ops": ";".join(ops),
                "parse_error": parse_error,
                "execution_error": execution_error,
                "question": ex["question"],
            }
            writer.writerow(row)
            f_csv.flush()
            f_trace.write(
                json.dumps(
                    {
                        "run_id": args.run_id,
                        "example_id": eid,
                        "controller_model": args.model,
                        "prompt": prompt,
                        "raw_response": raw,
                        "parsed_task": task,
                        "parsed_answer_type": answer_type,
                        "prediction": prediction,
                        "gold": str(gold),
                        "score": score,
                        "cost_usd": cost,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "latency_s": latency,
                        "parse_error": parse_error,
                        "execution_error": execution_error,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            f_trace.flush()
            print(f"[{i}/{len(examples)}] {eid}: score={score:.3f} task={task} answer={answer_type} cost=${cost:.6f}")

    rows: list[dict[str, str]] = []
    with args.out.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("run_id") == args.run_id:
                rows.append(row)
    summary = summarize(rows, args.run_id, args.model, args.trace_out, args.out)
    args.summary_out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(summary, args.md_out)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
