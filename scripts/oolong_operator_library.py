#!/usr/bin/env python3
"""Custom-tool wrappers for the Oolong same-operator RLM diagnostic.

The functions in this module are deliberately thin wrappers around the existing
SLM-labeler + typed aggregation code. They are intended to be injected into the
standard `rlms` local REPL via `custom_tools` so the generated program can choose
whether and how to use the same typed operator library.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from eval_oolong_standard_slm_labeler_typed import (  # noqa: E402
    extract_allowed_labels,
    label_rows_with_slm,
    labeled_context_from_predictions,
    parse_unlabeled_rows,
)
from probe_typed_oolong_proxy import solve_typed  # noqa: E402


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


def _safe_preview(value: Any, limit: int = 300) -> str:
    text = str(value)
    return text if len(text) <= limit else text[:limit] + "...[truncated]"


def _write_trace(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _normalize_task(task: str) -> str:
    task = str(task).strip()
    if not task.startswith("TASK_TYPE.") and task:
        task = "TASK_TYPE." + task
    if task not in TASKS:
        raise ValueError(f"Unknown task {task!r}. Use one of {TASKS}.")
    return task


def _normalize_answer_type(answer_type: str) -> str:
    answer_type = str(answer_type).strip()
    if not answer_type.startswith("ANSWER_TYPE.") and answer_type:
        answer_type = "ANSWER_TYPE." + answer_type
    if answer_type not in ANSWER_TYPES:
        raise ValueError(f"Unknown answer_type {answer_type!r}. Use one of {ANSWER_TYPES}.")
    return answer_type


def make_oolong_operator_tools(
    *,
    run_id: str,
    example_id: str,
    tool_trace_path: str | Path,
    slm_model: str = "google/gemma-4-26b-a4b-it",
    chunk_size: int = 0,
    request_timeout: float = 120.0,
    block_cache_dir: str | Path | None = None,
    slm_cache_run_id: str | None = None,
    block_concurrency: int = 1,
    block_retries: int = 0,
    block_retry_sleep: float = 2.0,
    include_convenience_solver: bool = True,
) -> dict[str, Any]:
    """Return custom tools for one RLM row.

    The returned dictionary uses the `{"tool": callable, "description": ...}`
    form supported by `rlms`, so descriptions are visible to the controller.
    """

    trace_path = Path(tool_trace_path)
    cache_dir = Path(block_cache_dir) if block_cache_dir else None
    labeler_run_id = slm_cache_run_id or run_id

    def log_call(tool: str, started: float, **payload: Any) -> None:
        record = {
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
            "example_id": example_id,
            "tool": tool,
            "latency_s": round(time.time() - started, 6),
            **payload,
        }
        _write_trace(trace_path, record)

    def parse_oolong_rows(context: str) -> list[dict[str, str]]:
        """Parse standard Oolong rows from `context` into date/user/instance dictionaries."""
        started = time.time()
        rows = parse_unlabeled_rows(context)
        log_call("parse_oolong_rows", started, row_count=len(rows), context_chars=len(context))
        return rows

    def label_oolong_rows_with_slm(context: str, question: str) -> dict[str, Any]:
        """Label rows with the same Gemma SLM worker path used by SLM+typed."""
        started = time.time()
        rows = parse_unlabeled_rows(context)
        labels = extract_allowed_labels(context, question)
        if not rows:
            err = "No Oolong rows parsed from context."
            log_call("label_oolong_rows_with_slm", started, error=err, row_count=0)
            raise ValueError(err)
        if not labels:
            err = "Could not infer allowed label set from context/question."
            log_call("label_oolong_rows_with_slm", started, error=err, row_count=len(rows))
            raise ValueError(err)
        predicted, cost, in_tok, out_tok, raw, blocks = label_rows_with_slm(
            rows=rows,
            labels=labels,
            question=question,
            model=slm_model,
            dry_run=False,
            chunk_size=chunk_size,
            request_timeout=request_timeout,
            run_id=labeler_run_id,
            example_id=example_id,
            block_cache_dir=cache_dir,
            overwrite_block_cache=False,
            block_concurrency=block_concurrency,
            block_retries=block_retries,
            block_retry_sleep=block_retry_sleep,
        )
        result = {
            "labels": predicted,
            "allowed_labels": labels,
            "row_count": len(rows),
            "cost_usd": cost,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "block_count": len(blocks),
        }
        log_call(
            "label_oolong_rows_with_slm",
            started,
            row_count=len(rows),
            allowed_labels=labels,
            predicted_labels=predicted,
            cost_usd=cost,
            input_tokens=in_tok,
            output_tokens=out_tok,
            block_count=len(blocks),
            raw_preview=_safe_preview(raw),
        )
        return result

    def solve_labeled_oolong(
        context: str,
        question: str,
        labels: list[str],
        task: str,
        answer_type: str,
    ) -> dict[str, Any]:
        """Run typed aggregation over supplied predicted row labels.

        The caller must choose `task` and `answer_type`. Valid task strings are
        available in `available_oolong_tasks`; valid answer types are in
        `available_oolong_answer_types`.
        """
        started = time.time()
        task_norm = _normalize_task(task)
        answer_norm = _normalize_answer_type(answer_type)
        rows = parse_unlabeled_rows(context)
        if len(rows) != len(labels):
            err = f"Expected {len(rows)} labels for parsed rows, got {len(labels)}."
            log_call(
                "solve_labeled_oolong",
                started,
                error=err,
                row_count=len(rows),
                label_count=len(labels),
                task=task_norm,
                answer_type=answer_norm,
            )
            raise ValueError(err)
        ex = {
            "question": question,
            "task": task_norm,
            "answer_type": answer_norm,
            "context_window_text": context,
            "context_window_text_with_labels": labeled_context_from_predictions(rows, labels, context),
        }
        prediction, ops, status = solve_typed(ex)
        answer = "" if prediction is None else str(prediction)
        log_call(
            "solve_labeled_oolong",
            started,
            row_count=len(rows),
            label_count=len(labels),
            task=task_norm,
            answer_type=answer_norm,
            prediction=answer,
            typed_ops=ops,
            typed_status=status,
        )
        return {
            "answer": answer,
            "prediction": answer,
            "task": task_norm,
            "answer_type": answer_norm,
            "typed_ops": ops,
            "typed_status": status,
            "row_count": len(rows),
        }

    def solve_oolong_with_tools(context: str, question: str, task: str, answer_type: str) -> dict[str, Any]:
        """Label rows with Gemma, then solve using typed aggregation.

        The caller must choose `task` and `answer_type`; the tool does not read
        benchmark metadata. Return `result["answer"]` as the final answer.
        """
        started = time.time()
        task_norm = _normalize_task(task)
        answer_norm = _normalize_answer_type(answer_type)
        label_result = label_oolong_rows_with_slm(context, question)
        solve_result = solve_labeled_oolong(
            context,
            question,
            list(label_result["labels"]),
            task_norm,
            answer_norm,
        )
        total_cost = float(label_result.get("cost_usd") or 0.0)
        result = {
            **solve_result,
            "label_cost_usd": total_cost,
            "label_input_tokens": int(label_result.get("input_tokens") or 0),
            "label_output_tokens": int(label_result.get("output_tokens") or 0),
            "allowed_labels": label_result.get("allowed_labels", []),
        }
        log_call(
            "solve_oolong_with_tools",
            started,
            task=task_norm,
            answer_type=answer_norm,
            prediction=result["answer"],
            label_cost_usd=total_cost,
            typed_status=result.get("typed_status"),
            typed_ops=result.get("typed_ops"),
        )
        return result

    tools = {
        "parse_oolong_rows": {
            "tool": parse_oolong_rows,
            "description": "Parse standard Oolong rows from the REPL `context` string into date/user/instance dictionaries.",
        },
        "label_oolong_rows_with_slm": {
            "tool": label_oolong_rows_with_slm,
            "description": "Use the same Gemma SLM worker path as SLM+typed to classify each parsed row into allowed labels inferred from context/question. Returns labels and cost.",
        },
        "solve_labeled_oolong": {
            "tool": solve_labeled_oolong,
            "description": "Run typed Oolong aggregation over predicted labels. You must supply task and answer_type strings from the available lists.",
        },
        "available_oolong_tasks": {
            "tool": TASKS,
            "description": "Valid task strings for the typed Oolong operator library.",
        },
        "available_oolong_answer_types": {
            "tool": ANSWER_TYPES,
            "description": "Valid answer_type strings for the typed Oolong operator library.",
        },
    }
    if include_convenience_solver:
        tools["solve_oolong_with_tools"] = {
            "tool": solve_oolong_with_tools,
            "description": "Convenience function: label rows with Gemma, then run typed aggregation. You must choose task and answer_type. Return result['answer'].",
        }
    return tools
