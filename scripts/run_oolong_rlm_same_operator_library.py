#!/usr/bin/env python3
"""Run standard `rlms` with the same typed Oolong operator library.

This is the faithful same-operator-library diagnostic defined by the evaluation protocol.
It is not the shared-operator controller: standard `rlms` still writes Python in
the local REPL and can decide whether/how to call the injected custom tools.
"""

from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as mp
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

from eval_oolong_slice import (  # noqa: E402
    estimate_cost,
    extract_answer_from_slm_output,
    get_oolong_context,
    parse_gold,
    score_prediction,
)
from oolong_operator_library import make_oolong_operator_tools  # noqa: E402
from probe_typed_oolong_proxy import hydrate_selected_examples  # noqa: E402


FIELDNAMES = [
    "run_id",
    "example_id",
    "task_group",
    "context_len",
    "context_window_id",
    "task",
    "answer_type",
    "prediction",
    "gold",
    "score",
    "exact",
    "controller_cost_usd",
    "tool_cost_usd",
    "total_cost_usd",
    "input_tokens",
    "output_tokens",
    "elapsed_seconds",
    "error",
    "iteration_count",
    "code_block_count",
    "tool_call_count",
    "tool_names",
    "final_answer_seen",
    "slm_typed_prediction",
    "slm_typed_score",
    "standard_rlm_prediction",
    "standard_rlm_score",
    "direct_gemini_prediction",
    "direct_gemini_score",
    "standard_rlm_repeat_exact_count",
    "shared_operator_prediction",
    "shared_operator_score",
    "question",
]


def load_env_file() -> None:
    env_paths = []
    if os.environ.get("RLM_ENV_PATH"):
        env_paths.append(Path(os.environ["RLM_ENV_PATH"]).expanduser())
    env_paths.append(Path.home() / "<local-config>" / ".env")
    for path in env_paths:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def selected_examples(manifest_path: Path, example_ids: list[str] | None, limit: int | None) -> list[dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    examples = list(manifest["examples"])
    if example_ids:
        wanted = set(example_ids)
        examples = [ex for ex in examples if str(ex["id"]) in wanted]
        missing = sorted(wanted - {str(ex["id"]) for ex in examples})
        if missing:
            raise ValueError(f"IDs not found in manifest: {missing}")
    if limit is not None:
        examples = examples[:limit]
    hydrated = hydrate_selected_examples(examples)
    for ex in hydrated:
        ex["_oolong_context_variant"] = "standard"
    return hydrated


def usage_to_cost_and_tokens(usage: Any, model: str) -> tuple[float, int, int]:
    if usage is None:
        return 0.0, 0, 0
    cost = getattr(usage, "total_cost", None)
    in_tok = int(getattr(usage, "total_input_tokens", 0) or 0)
    out_tok = int(getattr(usage, "total_output_tokens", 0) or 0)
    if cost is None:
        cost = estimate_cost(model, in_tok, out_tok)
    return float(cost or 0.0), in_tok, out_tok


def compact_trajectory(metadata: dict[str, Any] | None, max_prompt_chars: int) -> dict[str, Any]:
    if not metadata:
        return {"available": False, "iterations": []}
    compact_iterations = []
    for iteration in metadata.get("iterations", []):
        code_blocks = []
        for block in iteration.get("code_blocks", []):
            result = block.get("result") or {}
            code_blocks.append(
                {
                    "code": block.get("code", ""),
                    "stdout": result.get("stdout", ""),
                    "stderr": result.get("stderr", ""),
                    "error": result.get("error", ""),
                    "final_answer": result.get("final_answer"),
                }
            )
        compact_iterations.append(
            {
                "iteration": iteration.get("iteration"),
                "response": iteration.get("response", ""),
                "code_blocks": code_blocks,
                "final_answer": iteration.get("final_answer"),
                "iteration_time": iteration.get("iteration_time"),
                "prompt_preview": str(iteration.get("prompt", ""))[:max_prompt_chars],
            }
        )
    return {
        "available": True,
        "run_metadata": metadata.get("run_metadata"),
        "iterations": compact_iterations,
    }


def read_tool_trace(path: Path, run_id: str, example_id: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if payload.get("run_id") == run_id and str(payload.get("example_id")) == str(example_id):
            rows.append(payload)
    return rows


def run_one(payload: dict[str, Any]) -> dict[str, Any]:
    from rlm import RLM
    from rlm.logger.rlm_logger import RLMLogger

    load_env_file()
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENROUTER_API_KEY not set")

    ex = payload["example"]
    model = payload["model"]
    tool_trace_path = Path(payload["tool_trace_path"])
    backend_kwargs = {
        "api_key": api_key,
        "model_name": model,
        "sampling_args": {"temperature": 0},
    }
    tools = make_oolong_operator_tools(
        run_id=payload["run_id"],
        example_id=str(ex["id"]),
        tool_trace_path=tool_trace_path,
        slm_model=payload["slm_model"],
        chunk_size=payload["chunk_size"],
        request_timeout=payload["slm_request_timeout"],
        block_cache_dir=payload["block_cache_dir"],
        slm_cache_run_id=payload.get("slm_cache_run_id"),
        block_concurrency=payload["block_concurrency"],
        block_retries=payload["block_retries"],
        block_retry_sleep=payload["block_retry_sleep"],
        include_convenience_solver=payload["tool_mode"] != "atomic",
    )
    logger = RLMLogger()
    rlm = RLM(
        backend="openrouter",
        backend_kwargs=backend_kwargs,
        environment="local",
        max_depth=1,
        max_iterations=payload["max_iterations"],
        max_budget=payload["max_budget"],
        logger=logger,
        verbose=False,
        custom_tools=tools,
    )
    started = time.time()
    result = rlm.completion(get_oolong_context(ex), root_prompt=ex.get("question", ""))
    elapsed = time.time() - started
    prediction = extract_answer_from_slm_output(result.response or "", ex.get("answer_type", ""))
    controller_cost, input_tokens, output_tokens = usage_to_cost_and_tokens(
        getattr(result, "usage_summary", None),
        model,
    )
    trajectory = compact_trajectory(getattr(result, "metadata", None), payload["max_prompt_chars"])
    code_block_count = sum(len(it.get("code_blocks", [])) for it in trajectory.get("iterations", []))
    final_answer_seen = any(
        block.get("final_answer") is not None
        for it in trajectory.get("iterations", [])
        for block in it.get("code_blocks", [])
    )
    return {
        "ok": True,
        "response": result.response or "",
        "prediction": prediction,
        "controller_cost_usd": controller_cost,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "elapsed_seconds": elapsed,
        "trajectory": trajectory,
        "iteration_count": len(trajectory.get("iterations", [])),
        "code_block_count": code_block_count,
        "final_answer_seen": final_answer_seen,
    }


def _worker(queue: mp.Queue, payload: dict[str, Any]) -> None:
    try:
        queue.put(run_one(payload))
    except BaseException as exc:
        queue.put({"ok": False, "error": f"{type(exc).__name__}: {exc}"})


def run_with_timeout(payload: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    ctx = mp.get_context("spawn")
    queue: mp.Queue = ctx.Queue()
    proc = ctx.Process(target=_worker, args=(queue, payload))
    proc.start()
    proc.join(timeout_seconds)
    if proc.is_alive():
        proc.terminate()
        proc.join(10)
        if proc.is_alive():
            proc.kill()
            proc.join()
        return {"ok": False, "error": f"TimeoutError: RLM+ops run timed out after {timeout_seconds}s"}
    if queue.empty():
        return {"ok": False, "error": f"RuntimeError: subprocess exited code {proc.exitcode} without result"}
    return queue.get()


def existing_ids(path: Path, run_id: str) -> set[str]:
    if not path.exists():
        return set()
    with path.open(newline="", encoding="utf-8") as f:
        return {row["example_id"] for row in csv.DictReader(f) if row.get("run_id") == run_id}


def load_shared_operator_rows(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as f:
        return {row["example_id"]: row for row in csv.DictReader(f)}


def pack_scores(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"n": 0, "exact_count": 0, "exact_rate": 0.0, "mean_score": 0.0, "cost_usd": 0.0, "errors": 0}
    return {
        "n": len(rows),
        "exact_count": sum(1 for r in rows if bool(r.get("exact"))),
        "exact_rate": sum(1 for r in rows if bool(r.get("exact"))) / len(rows),
        "mean_score": mean(float(r.get("score") or 0.0) for r in rows),
        "cost_usd": sum(float(r.get("total_cost_usd") or 0.0) for r in rows),
        "controller_cost_usd": sum(float(r.get("controller_cost_usd") or 0.0) for r in rows),
        "tool_cost_usd": sum(float(r.get("tool_cost_usd") or 0.0) for r in rows),
        "errors": sum(1 for r in rows if r.get("error")),
        "tool_call_count": sum(int(r.get("tool_call_count") or 0) for r in rows),
        "code_block_count": sum(int(r.get("code_block_count") or 0) for r in rows),
    }


def summarize(rows: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_length: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_group[str(row["task_group"])].append(row)
        by_length[str(row["context_len"])].append(row)
    exact = sum(1 for r in rows if bool(r.get("exact")))
    tool_names = Counter()
    for row in rows:
        for name in str(row.get("tool_names") or "").split(";"):
            if name:
                tool_names[name] += 1
    split_label = "CD-45" if "n45" in str(args.manifest).lower() else "CD-15"
    return {
        "run_type": (
            "standard_rlms_same_operator_library_atomic_diagnostic"
            if args.tool_mode == "atomic"
            else "standard_rlms_same_operator_library_diagnostic"
        ),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": args.run_id,
        "model": args.rlm_model,
        "slm_model": args.slm_model,
        "tool_mode": args.tool_mode,
        "source_manifest": args.manifest,
        "n": len(rows),
        "exact_count": exact,
        "exact_rate": exact / len(rows) if rows else 0.0,
        "score_sum": round(sum(float(r.get("score") or 0) for r in rows), 4),
        "mean_score": mean(float(r.get("score") or 0.0) for r in rows) if rows else 0.0,
        "controller_cost_usd": round(sum(float(r.get("controller_cost_usd") or 0.0) for r in rows), 6),
        "tool_cost_usd": round(sum(float(r.get("tool_cost_usd") or 0.0) for r in rows), 6),
        "total_cost_usd": round(sum(float(r.get("total_cost_usd") or 0.0) for r in rows), 6),
        "errors": sum(1 for r in rows if r.get("error")),
        "tool_call_count": sum(int(r.get("tool_call_count") or 0) for r in rows),
        "tool_names": dict(tool_names),
        "code_block_count": sum(int(r.get("code_block_count") or 0) for r in rows),
        "by_group": {k: pack_scores(v) for k, v in sorted(by_group.items())},
        "by_length": {k: pack_scores(v) for k, v in sorted(by_length.items(), key=lambda kv: int(kv[0]))},
        "contract": (
            "Standard rlms v0.1.3 with custom_tools exposing the same typed Oolong operator library. "
            "Input is standard context_window_text only; root prompt is the natural-language question. "
            "The generated program must choose task/answer_type itself. "
            + (
                "Atomic mode removes the solve_oolong_with_tools convenience solver, leaving parse, SLM-label, solve_labeled, and schema-list tools only. "
                if args.tool_mode == "atomic"
                else "Convenience mode includes solve_oolong_with_tools in addition to the atomic tools. "
            )
            + "This is not shared-operator routing and not official SRLM/lambda-RLM."
        ),
        "stop_rule": (
            f"{split_label} same-operator-library diagnostic; stop or demote the result if >=50% "
            "timeout/error/tool-unusable rows."
        ),
    }


def first_code_block(row: dict[str, Any], max_chars: int = 1600) -> str:
    traj = row.get("trajectory") or {}
    for iteration in traj.get("iterations", []):
        for block in iteration.get("code_blocks", []):
            code = block.get("code")
            if code:
                code = re.sub(r"\s+$", "", str(code))
                return code if len(code) <= max_chars else code[:max_chars] + "\n# ... [truncated]"
    return ""


def write_markdown(rows: list[dict[str, Any]], summary: dict[str, Any], path: Path) -> None:
    lines = [
        (
            "# Standard `rlms` + Atomic Same Typed Operator Library Diagnostic"
            if summary.get("tool_mode") == "atomic"
            else "# Standard `rlms` + Same Typed Operator Library Diagnostic"
        ),
        "",
        (
            "This is the atomic same-operator-library diagnostic for standard `rlms`. It preserves free-form RLM program generation while injecting parse, SLM-label, typed-solve, and schema-list tools through `custom_tools`, but withholds the `solve_oolong_with_tools` convenience solver."
            if summary.get("tool_mode") == "atomic"
            else "This is the same-operator-library diagnostic for standard `rlms`. It preserves free-form RLM program generation while injecting the typed Oolong operator library through `custom_tools`."
        ),
        "",
        "## Summary",
        "",
        f"- Run ID: `{summary['run_id']}`",
        f"- Tool mode: `{summary.get('tool_mode', 'convenience')}`",
        f"- Rows: {summary['exact_count']}/{summary['n']} exact",
        f"- Mean score: {summary['mean_score']:.4f}",
        f"- Controller cost: `${summary['controller_cost_usd']:.6f}`",
        f"- Tool cost: `${summary['tool_cost_usd']:.6f}`",
        f"- Total cost: `${summary['total_cost_usd']:.6f}`",
        f"- Errors: {summary['errors']}",
        f"- Tool calls: {summary['tool_call_count']}",
        f"- Generated code blocks: {summary['code_block_count']}",
        "",
        "## Contract",
        "",
        summary["contract"],
        "",
        "## Rows",
        "",
        "| example | group | len | gold | pred | score | cost | tools | std RLM | SLM+typed | direct | shared-op | error |",
        "|---|---|---:|---|---|---:|---:|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['example_id']} | {row['task_group']} | {row['context_len']} | {row['gold']} | {row['prediction']} | "
            f"{float(row['score']):.3f} | ${float(row['total_cost_usd']):.6f} | {row.get('tool_names','')} | "
            f"{row.get('standard_rlm_prediction','')} | {row.get('slm_typed_prediction','')} | "
            f"{row.get('direct_gemini_prediction','')} | {row.get('shared_operator_prediction','')} | {row.get('error','')} |"
        )
    lines.extend(["", "## First Generated Code Block Per Completed Row", ""])
    for row in rows:
        code = first_code_block(row)
        if code:
            lines.extend([f"### {row['example_id']}", "", "```python", code, "```", ""])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="results/oolong_context_disjoint_cd15_repeatability_manifest_20260715.json")
    parser.add_argument("--example-ids", default="")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--out", default="results/oolong_cd15_rlm_same_ops_20260716.csv")
    parser.add_argument("--trace-out", default="results/oolong_cd15_rlm_same_ops_20260716_trace.jsonl")
    parser.add_argument("--tool-trace-out", default="results/oolong_cd15_rlm_same_ops_20260716_tool_trace.jsonl")
    parser.add_argument("--summary-out", default="results/oolong_cd15_rlm_same_ops_20260716_summary.json")
    parser.add_argument("--md-out", default="results/oolong_cd15_rlm_same_ops_20260716.md")
    parser.add_argument("--run-log", default="results/oolong_cd15_rlm_same_ops_20260716_run.log")
    parser.add_argument("--run-id", default="oolong_cd15_rlm_same_ops_20260716")
    parser.add_argument("--rlm-model", default="google/gemini-2.5-flash")
    parser.add_argument("--slm-model", default="google/gemma-4-26b-a4b-it")
    parser.add_argument("--timeout-seconds", type=int, default=360)
    parser.add_argument("--max-iterations", type=int, default=15)
    parser.add_argument("--max-budget", type=float, default=0.50)
    parser.add_argument("--chunk-size", type=int, default=80)
    parser.add_argument("--slm-request-timeout", type=float, default=180.0)
    parser.add_argument("--block-cache-dir", default="results/oolong_rlm_same_ops_block_cache_20260716")
    parser.add_argument("--slm-cache-run-id", default="")
    parser.add_argument("--block-concurrency", type=int, default=4)
    parser.add_argument("--block-retries", type=int, default=1)
    parser.add_argument("--block-retry-sleep", type=float, default=2.0)
    parser.add_argument("--max-prompt-chars", type=int, default=1000)
    parser.add_argument("--shared-operator-csv", default="results/oolong_context_disjoint_cd45_shared_operator_controller_20260716.csv")
    parser.add_argument("--tool-mode", choices=["convenience", "atomic"], default="convenience")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    load_env_file()
    ids = [x.strip() for x in args.example_ids.split(",") if x.strip()]
    examples = selected_examples(PROJECT_ROOT / args.manifest, ids or None, args.limit)
    out_path = PROJECT_ROOT / args.out
    trace_path = PROJECT_ROOT / args.trace_out
    tool_trace_path = PROJECT_ROOT / args.tool_trace_out
    summary_path = PROJECT_ROOT / args.summary_out
    md_path = PROJECT_ROOT / args.md_out
    log_path = PROJECT_ROOT / args.run_log
    shared_rows = load_shared_operator_rows(PROJECT_ROOT / args.shared_operator_csv)

    for path in [out_path, trace_path, tool_trace_path, summary_path, md_path, log_path]:
        path.parent.mkdir(parents=True, exist_ok=True)
    if args.overwrite:
        for path in [out_path, trace_path, tool_trace_path, summary_path, md_path, log_path]:
            if path.exists():
                path.unlink()

    done = existing_ids(out_path, args.run_id)
    mode = "a" if out_path.exists() else "w"
    rows: list[dict[str, Any]] = []
    with out_path.open(mode, newline="", encoding="utf-8") as csv_f, trace_path.open(mode, encoding="utf-8") as trace_f, log_path.open("a", encoding="utf-8") as log_f:
        writer = csv.DictWriter(csv_f, fieldnames=FIELDNAMES)
        if mode == "w":
            writer.writeheader()
        for idx, ex in enumerate(examples, start=1):
            eid = str(ex["id"])
            if eid in done:
                continue
            log_line = f"[{idx}/{len(examples)}] RLM+ops id={eid} group={ex['task_group']} len={ex['context_len']}"
            print(log_line)
            log_f.write(log_line + "\n")
            log_f.flush()
            gold = parse_gold(ex.get("answer", ""), ex.get("answer_type", ""))
            payload = {
                "run_id": args.run_id,
                "example": ex,
                "model": args.rlm_model,
                "slm_model": args.slm_model,
                "max_iterations": args.max_iterations,
                "max_budget": args.max_budget,
                "tool_trace_path": str(tool_trace_path),
                "chunk_size": args.chunk_size,
                "slm_request_timeout": args.slm_request_timeout,
                "block_cache_dir": str(PROJECT_ROOT / args.block_cache_dir),
                "slm_cache_run_id": args.slm_cache_run_id or None,
                "block_concurrency": args.block_concurrency,
                "block_retries": args.block_retries,
                "block_retry_sleep": args.block_retry_sleep,
                "max_prompt_chars": args.max_prompt_chars,
                "tool_mode": args.tool_mode,
            }
            result = run_with_timeout(payload, args.timeout_seconds)
            prediction = ""
            score = 0.0
            controller_cost = 0.0
            input_tokens = 0
            output_tokens = 0
            elapsed = 0.0
            error = ""
            if result.get("ok"):
                prediction = str(result.get("prediction") or "")
                score = score_prediction(prediction, gold, ex.get("answer_type", ""))
                controller_cost = float(result.get("controller_cost_usd") or 0.0)
                input_tokens = int(result.get("input_tokens") or 0)
                output_tokens = int(result.get("output_tokens") or 0)
                elapsed = float(result.get("elapsed_seconds") or 0.0)
            else:
                error = str(result.get("error") or "unknown error")
            tool_rows = read_tool_trace(tool_trace_path, args.run_id, eid)
            tool_cost = sum(float(t.get("cost_usd") or 0.0) for t in tool_rows if t.get("tool") == "label_oolong_rows_with_slm")
            tool_names = ";".join(t.get("tool", "") for t in tool_rows if t.get("tool"))
            logged = ex.get("logged_outcomes", {})
            shared = shared_rows.get(eid, {})
            row = {
                "run_id": args.run_id,
                "example_id": eid,
                "task_group": ex.get("task_group", ""),
                "context_len": ex.get("context_len", ""),
                "context_window_id": ex.get("context_window_id", ""),
                "task": ex.get("task", ""),
                "answer_type": ex.get("answer_type", ""),
                "prediction": prediction,
                "gold": str(gold),
                "score": round(score, 4),
                "exact": score >= 1.0,
                "controller_cost_usd": round(controller_cost, 6),
                "tool_cost_usd": round(tool_cost, 6),
                "total_cost_usd": round(controller_cost + tool_cost, 6),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "elapsed_seconds": round(elapsed, 3),
                "error": error,
                "iteration_count": int(result.get("iteration_count") or 0),
                "code_block_count": int(result.get("code_block_count") or 0),
                "tool_call_count": len(tool_rows),
                "tool_names": tool_names,
                "final_answer_seen": bool(result.get("final_answer_seen")),
                "slm_typed_prediction": logged.get("slm_qparsed_typed", {}).get("prediction", ""),
                "slm_typed_score": logged.get("slm_qparsed_typed", {}).get("correct", ""),
                "standard_rlm_prediction": logged.get("standard_rlm_gemini25_flash", {}).get("prediction", ""),
                "standard_rlm_score": logged.get("standard_rlm_gemini25_flash", {}).get("correct", ""),
                "direct_gemini_prediction": logged.get("direct_gemini25_flash", {}).get("prediction", ""),
                "direct_gemini_score": logged.get("direct_gemini25_flash", {}).get("correct", ""),
                "standard_rlm_repeat_exact_count": "",
                "shared_operator_prediction": shared.get("prediction", ""),
                "shared_operator_score": shared.get("score", ""),
                "question": ex.get("question", ""),
                "trajectory_available": bool((result.get("trajectory") or {}).get("available")),
                "trajectory": result.get("trajectory") or {},
                "tool_trace": tool_rows,
                "raw_response": result.get("response", ""),
            }
            writer.writerow({k: row[k] for k in FIELDNAMES})
            csv_f.flush()
            trace_f.write(json.dumps(row, ensure_ascii=False) + "\n")
            trace_f.flush()
            rows.append(row)
            out_line = (
                f"  pred={prediction!r} gold={str(gold)!r} score={score:.3f} "
                f"ctrl=${controller_cost:.4f} tools=${tool_cost:.4f} "
                f"tool_calls={len(tool_rows)} code_blocks={row['code_block_count']} error={error!r}"
            )
            print(out_line)
            log_f.write(out_line + "\n")
            log_f.flush()

    if not rows and trace_path.exists():
        rows = [
            json.loads(line)
            for line in trace_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and json.loads(line).get("run_id") == args.run_id
        ]
    summary = summarize(rows, args)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_markdown(rows, summary, md_path)
    print(json.dumps(summary, indent=2))
    print(f"Wrote {out_path.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {trace_path.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {tool_trace_path.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {summary_path.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {md_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
