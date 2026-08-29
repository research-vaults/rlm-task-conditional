#!/usr/bin/env python3
"""Run a traced direct-controller baseline on a frozen Oolong manifest.

This baseline sends the standard, unlabeled Oolong context and question directly
to the same model used as the standard-RLM controller. It does not execute code
or recurse. The script logs every prompt, raw response, token usage, prediction,
score, latency, and cost so the run can be audited later.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from eval_oolong_frozen_manifest_methods import selected_manifest_examples  # noqa: E402
from eval_oolong_slice import (  # noqa: E402
    estimate_cost,
    extract_answer_from_slm_output,
    parse_gold,
    rough_token_count,
    score_prediction,
)
from probe_typed_oolong_proxy import hydrate_selected_examples  # noqa: E402


FIELDNAMES = [
    "run_id",
    "example_id",
    "context_len",
    "task_group",
    "task",
    "answer_type",
    "context_variant",
    "method",
    "model",
    "prediction",
    "gold",
    "correct",
    "cost_usd",
    "input_tokens",
    "output_tokens",
    "latency_s",
    "error",
    "question",
]


def get_openrouter_client(timeout: float):
    import openai

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENROUTER_API_KEY not set")
    return openai.OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        timeout=timeout,
    )


def build_prompt(example: dict[str, Any]) -> str:
    ctx = example.get("context_window_text", "")
    question = example.get("question", "")
    return (
        "You are a precise data analyst. Read the dataset and answer the "
        "question exactly as requested. Use only the dataset. Do not write code, "
        "do not explain, and do not include extra text. Return only the final "
        "answer string.\n\n"
        f"Dataset:\n{ctx}\n\nQuestion:\n{question}\n\nFinal answer:"
    )


def existing_ids(out_path: Path, run_id: str) -> set[str]:
    if not out_path.exists():
        return set()
    done: set[str] = set()
    with out_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("run_id") == run_id and row.get("method") == "direct_controller":
                done.add(str(row["example_id"]))
    return done


def call_direct(
    client,
    prompt: str,
    model: str,
    max_tokens: int,
    temperature: float,
) -> tuple[str, int, int, float]:
    start = time.time()
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    latency = time.time() - start
    text = response.choices[0].message.content or ""
    usage = response.usage
    input_tokens = usage.prompt_tokens if usage else rough_token_count(prompt)
    output_tokens = usage.completion_tokens if usage else rough_token_count(text)
    return text, input_tokens, output_tokens, latency


def summarize(out_path: Path, run_id: str) -> dict[str, Any]:
    rows: list[dict[str, str]] = []
    with out_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("run_id") == run_id:
                rows.append(row)

    by_group: dict[str, list[dict[str, str]]] = defaultdict(list)
    by_length: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_group[row["task_group"]].append(row)
        by_length[str(row["context_len"])].append(row)

    def pack(items: list[dict[str, str]]) -> dict[str, Any]:
        n = len(items)
        scores = [float(r["correct"]) for r in items]
        exact = sum(1 for s in scores if s >= 1.0)
        return {
            "n": n,
            "score_sum": round(sum(scores), 4),
            "mean_score": round(sum(scores) / n, 6) if n else 0.0,
            "exact_count": exact,
            "exact_rate": round(exact / n, 6) if n else 0.0,
            "cost_usd": round(sum(float(r["cost_usd"] or 0.0) for r in items), 6),
            "input_tokens": sum(int(float(r["input_tokens"] or 0)) for r in items),
            "output_tokens": sum(int(float(r["output_tokens"] or 0)) for r in items),
            "errors": sum(1 for r in items if r["error"]),
            "latency_s": round(sum(float(r["latency_s"] or 0.0) for r in items), 3),
        }

    return {
        "metadata": {
            "run_id": run_id,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "source_csv": str(out_path.relative_to(PROJECT_ROOT)),
            "method": "direct_controller",
        },
        "overall": pack(rows),
        "by_group": {g: pack(items) for g, items in sorted(by_group.items())},
        "by_length": {k: pack(items) for k, items in sorted(by_length.items(), key=lambda kv: int(kv[0]))},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--summary-out", required=True)
    parser.add_argument("--trace-out", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--model", default="google/gemini-2.5-flash")
    parser.add_argument("--dataset-split", choices=["test", "validation"], default="test",
                        help="Explicit Oolong split used to hydrate the frozen manifest.")
    parser.add_argument("--per-group-limit", type=int, default=None)
    parser.add_argument("--request-timeout", type=float, default=180.0)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    out_path = PROJECT_ROOT / args.out
    summary_path = PROJECT_ROOT / args.summary_out
    trace_path = PROJECT_ROOT / args.trace_out
    manifest_path = PROJECT_ROOT / args.manifest

    selected = selected_manifest_examples(manifest_path, args.per_group_limit)
    examples = hydrate_selected_examples(selected, split=args.dataset_split)
    client = get_openrouter_client(timeout=args.request_timeout)

    done = set() if args.overwrite else existing_ids(out_path, args.run_id)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    new_csv = not out_path.exists() or args.overwrite
    csv_mode = "w" if args.overwrite else "a"
    trace_mode = "w" if args.overwrite else "a"

    with out_path.open(csv_mode, newline="", encoding="utf-8") as f_csv, trace_path.open(trace_mode, encoding="utf-8") as f_trace:
        writer = csv.DictWriter(f_csv, fieldnames=FIELDNAMES)
        if new_csv:
            writer.writeheader()

        for i, ex in enumerate(examples, start=1):
            ex_id = str(ex["id"])
            if ex_id in done:
                print(f"[{i}/{len(examples)}] id={ex_id}: skip existing")
                continue

            gold = parse_gold(ex.get("answer", ""), ex.get("answer_type", ""))
            prompt = build_prompt(ex)
            prediction = ""
            raw_response = ""
            input_tokens = 0
            output_tokens = 0
            latency = 0.0
            cost = 0.0
            error = ""
            score = 0.0

            print(f"[{i}/{len(examples)}] id={ex_id} group={ex['task_group']} len={ex['context_len']}")
            try:
                raw_response, input_tokens, output_tokens, latency = call_direct(
                    client,
                    prompt,
                    args.model,
                    max_tokens=args.max_tokens,
                    temperature=args.temperature,
                )
                cost = estimate_cost(args.model, input_tokens, output_tokens)
                prediction = extract_answer_from_slm_output(raw_response, ex.get("answer_type", ""))
                score = score_prediction(prediction, gold, ex.get("answer_type", ""))
                print(f"  - pred={prediction!r} gold={str(gold)!r} score={score:.3f} cost=${cost:.5f}")
            except Exception as exc:  # noqa: BLE001 - preserve row and continue
                error = f"{type(exc).__name__}: {exc}"
                print(f"  ! error={error}")

            writer.writerow({
                "run_id": args.run_id,
                "example_id": ex_id,
                "context_len": ex["context_len"],
                "task_group": ex["task_group"],
                "task": ex["task"],
                "answer_type": ex["answer_type"],
                "context_variant": "standard",
                "method": "direct_controller",
                "model": args.model,
                "prediction": prediction,
                "gold": str(gold),
                "correct": round(score, 4),
                "cost_usd": round(cost, 8),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "latency_s": round(latency, 3),
                "error": error,
                "question": ex["question"],
            })
            f_csv.flush()

            # Keep future trace files one physical line per record even when
            # source datasets contain Unicode line-separator characters.
            f_trace.write(json.dumps({
                "run_id": args.run_id,
                "example_id": ex_id,
                "context_len": ex["context_len"],
                "task_group": ex["task_group"],
                "task": ex["task"],
                "answer_type": ex["answer_type"],
                "context_variant": "standard",
                "method": "direct_controller",
                "model": args.model,
                "question": ex["question"],
                "prompt": prompt,
                "raw_response": raw_response,
                "prediction": prediction,
                "gold": str(gold),
                "correct": round(score, 4),
                "cost_usd": round(cost, 8),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "latency_s": round(latency, 3),
                "error": error,
            }, ensure_ascii=True) + "\n")
            f_trace.flush()

    summary = summarize(out_path, args.run_id)
    summary["metadata"].update({
        "manifest": args.manifest,
        "trace": args.trace_out,
        "model": args.model,
        "context_variant": "standard",
        "dataset_split": args.dataset_split,
        "prompt_contract": "standard context_window_text plus natural-language question; no code execution, no recursion, final answer only",
    })
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
