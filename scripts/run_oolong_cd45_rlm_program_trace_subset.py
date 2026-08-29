#!/usr/bin/env python3
"""Capture standard-rlms generated program traces on a frozen Oolong manifest.

The runner supports either a qualitative subset or every row in a frozen
manifest. It retains the standard/unlabeled input, raw response, token usage,
cost, and the `rlms` trajectory so generated programs remain inspectable.
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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from eval_oolong_slice import (  # noqa: E402
    extract_answer_from_slm_output,
    get_oolong_context,
    parse_gold,
    score_prediction,
)
from probe_typed_oolong_proxy import hydrate_selected_examples  # noqa: E402


DEFAULT_IDS = [
    # One representative row from each task group/length style used in the
    # existing trace-example artifact.
    "912090010",
    "312030020",
    "710070026",
]

FIELDNAMES = [
    "run_id",
    "example_id",
    "task_group",
    "context_len",
    "prediction",
    "gold",
    "score",
    "exact",
    "cost_usd",
    "error",
    "iteration_count",
    "code_block_count",
    "final_answer_seen",
    "question",
]


def load_env_file() -> None:
    env_path = os.environ.get("RLM_ENV_PATH")
    if not env_path:
        return
    path = Path(env_path).expanduser()
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def selected_examples(manifest_path: Path, ids: list[str], split: str) -> list[dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if ids:
        id_set = set(ids)
        selected = [ex for ex in manifest["examples"] if str(ex["id"]) in id_set]
        missing = sorted(id_set - {str(ex["id"]) for ex in selected})
        if missing:
            raise ValueError(f"IDs not found in manifest: {missing}")
    else:
        selected = list(manifest["examples"])
    hydrated = hydrate_selected_examples(selected, split=split)
    for ex in hydrated:
        ex["_oolong_context_variant"] = "standard"
    return hydrated


def usage_to_cost_and_tokens(usage: Any) -> tuple[float, int, int]:
    if usage is None:
        return 0.0, 0, 0
    cost = getattr(usage, "total_cost", None)
    if cost is None:
        cost = 0.0
    return (
        float(cost or 0.0),
        int(getattr(usage, "total_input_tokens", 0) or 0),
        int(getattr(usage, "total_output_tokens", 0) or 0),
    )


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


def run_one(payload: dict[str, Any]) -> dict[str, Any]:
    from rlm import RLM
    from rlm.logger.rlm_logger import RLMLogger

    load_env_file()
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENROUTER_API_KEY not set")

    ex = payload["example"]
    model = payload["model"]
    backend_kwargs = {
        "api_key": api_key,
        "model_name": model,
        "sampling_args": {"temperature": 0},
    }
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
    )
    started = time.time()
    result = rlm.completion(get_oolong_context(ex), root_prompt=ex.get("question", ""))
    elapsed = time.time() - started
    prediction = extract_answer_from_slm_output(result.response or "", ex.get("answer_type", ""))
    cost, input_tokens, output_tokens = usage_to_cost_and_tokens(getattr(result, "usage_summary", None))
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
        "cost_usd": cost,
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
        return {"ok": False, "error": f"TimeoutError: standard_rlm trace run timed out after {timeout_seconds}s"}
    if queue.empty():
        return {"ok": False, "error": f"RuntimeError: subprocess exited code {proc.exitcode} without result"}
    return queue.get()


def existing_ids(path: Path, run_id: str) -> set[str]:
    if not path.exists():
        return set()
    with path.open(newline="", encoding="utf-8") as f:
        return {row["example_id"] for row in csv.DictReader(f) if row.get("run_id") == run_id}


def summarize(rows: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    exact = sum(1 for r in rows if r.get("exact"))
    total_cost = sum(float(r.get("cost_usd") or 0) for r in rows)
    return {
        "run_type": args.run_type,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": args.run_id,
        "model": args.rlm_model,
        "artifact_title": args.artifact_title,
        "artifact_description": args.artifact_description,
        "contract": args.contract,
        "source_manifest": args.manifest,
        "dataset_split": args.dataset_split,
        "requested_ids": "ALL_MANIFEST_EXAMPLES" if args.all_manifest_examples else args.example_ids,
        "n": len(rows),
        "exact_count": exact,
        "score_sum": round(sum(float(r.get("score") or 0) for r in rows), 4),
        "cost_usd": round(total_cost, 6),
        "errors": sum(1 for r in rows if r.get("error")),
        "with_trajectory": sum(1 for r in rows if r.get("trajectory_available")),
        "code_block_count": sum(int(r.get("code_block_count") or 0) for r in rows),
        "paper_framing": args.paper_framing,
    }


def write_markdown(rows: list[dict[str, Any]], summary: dict[str, Any], path: Path) -> None:
    lines = [
        f"# {summary['artifact_title']}",
        "",
        summary["artifact_description"],
        "",
        "## Summary",
        "",
        f"- Run ID: `{summary['run_id']}`",
        f"- Model: `{summary['model']}`",
        f"- Rows: {summary['n']}",
        f"- Exact: {summary['exact_count']}/{summary['n']}",
        f"- Total cost: `${summary['cost_usd']}`",
        f"- Rows with trajectories: {summary['with_trajectory']}/{summary['n']}",
        f"- Code blocks captured: {summary['code_block_count']}",
        "",
        "## Rows",
        "",
        "| example | group | len | gold | pred | score | iterations | code blocks | cost | error |",
        "|---|---|---:|---|---|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['example_id']} | {row['task_group']} | {row['context_len']} | {row['gold']} | {row['prediction']} | "
            f"{float(row['score']):.3f} | {row['iteration_count']} | {row['code_block_count']} | "
            f"${float(row['cost_usd']):.6f} | {row.get('error','')} |"
        )
    lines.extend(["", "## First Generated Code Block Per Completed Row", ""])
    for row in rows:
        traj = row.get("trajectory") or {}
        first_code = ""
        for iteration in traj.get("iterations", []):
            for block in iteration.get("code_blocks", []):
                if block.get("code"):
                    first_code = block["code"]
                    break
            if first_code:
                break
        if first_code:
            first_code = re.sub(r"\s+$", "", first_code)
            if len(first_code) > 1800:
                first_code = first_code[:1800] + "\n# ... [truncated in markdown; full code in JSONL]"
            lines.extend([f"### {row['example_id']}", "", "```python", first_code, "```", ""])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="results/oolong_context_disjoint_n45_manifest_20260715.json")
    parser.add_argument("--example-ids", default=",".join(DEFAULT_IDS))
    parser.add_argument("--all-manifest-examples", action="store_true",
                        help="Run every frozen manifest row; overrides --example-ids.")
    parser.add_argument("--dataset-split", choices=["test", "validation"], default="test",
                        help="Explicit Oolong split used to hydrate the frozen manifest.")
    parser.add_argument("--out", default="results/oolong_context_disjoint_cd45_rlm_program_trace_subset_20260716.csv")
    parser.add_argument("--trace-out", default="results/oolong_context_disjoint_cd45_rlm_program_trace_subset_20260716.jsonl")
    parser.add_argument("--summary-out", default="results/oolong_context_disjoint_cd45_rlm_program_trace_subset_20260716_summary.json")
    parser.add_argument("--md-out", default="results/oolong_context_disjoint_cd45_rlm_program_trace_subset_20260716.md")
    parser.add_argument("--run-id", default="oolong_context_disjoint_cd45_rlm_program_trace_subset_20260716")
    parser.add_argument("--run-type", default="cd45_standard_rlm_program_trace_subset")
    parser.add_argument(
        "--contract",
        default=(
            "Qualitative subset rerun with standard rlms v0.1.3 on standard/unlabeled "
            "context_window_text and full trajectory capture; not a new aggregate benchmark row."
        ),
    )
    parser.add_argument("--artifact-title", default="Standard-RLM Program Trace Artifact")
    parser.add_argument(
        "--artifact-description",
        default=(
            "Frozen Oolong rows rerun with the standard `rlms` scaffold and trajectory logger; "
            "generated programs, raw responses, token usage, and costs are retained."
        ),
    )
    parser.add_argument(
        "--paper-framing",
        default=(
            "Qualitative standard-RLM program-trace evidence; not an official "
            "SRLM/lambda-RLM result."
        ),
    )
    parser.add_argument("--rlm-model", default="google/gemini-2.5-flash")
    parser.add_argument("--timeout-seconds", type=int, default=360)
    parser.add_argument("--max-iterations", type=int, default=15)
    parser.add_argument("--max-budget", type=float, default=0.50)
    parser.add_argument("--max-prompt-chars", type=int, default=1000)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    load_env_file()
    ids = [] if args.all_manifest_examples else [x.strip() for x in args.example_ids.split(",") if x.strip()]
    examples = selected_examples(PROJECT_ROOT / args.manifest, ids, args.dataset_split)
    out_path = PROJECT_ROOT / args.out
    trace_path = PROJECT_ROOT / args.trace_out
    summary_path = PROJECT_ROOT / args.summary_out
    md_path = PROJECT_ROOT / args.md_out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = set() if args.overwrite else existing_ids(out_path, args.run_id)
    mode = "w" if args.overwrite or not out_path.exists() else "a"

    rows: list[dict[str, Any]] = []
    with out_path.open(mode, newline="", encoding="utf-8") as csv_f, trace_path.open(mode, encoding="utf-8") as trace_f:
        writer = csv.DictWriter(csv_f, fieldnames=FIELDNAMES)
        if mode == "w":
            writer.writeheader()
        for idx, ex in enumerate(examples, start=1):
            eid = str(ex["id"])
            if eid in done:
                continue
            print(f"[{idx}/{len(examples)}] trace standard RLM id={eid} group={ex['task_group']}")
            gold = parse_gold(ex.get("answer", ""), ex.get("answer_type", ""))
            payload = {
                "example": ex,
                "model": args.rlm_model,
                "max_iterations": args.max_iterations,
                "max_budget": args.max_budget,
                "max_prompt_chars": args.max_prompt_chars,
            }
            result = run_with_timeout(payload, args.timeout_seconds)
            prediction = ""
            score = 0.0
            cost = 0.0
            error = ""
            if result.get("ok"):
                prediction = str(result.get("prediction") or "")
                score = score_prediction(prediction, gold, ex.get("answer_type", ""))
                cost = float(result.get("cost_usd") or 0.0)
            else:
                error = str(result.get("error") or "unknown error")
            row = {
                "run_id": args.run_id,
                "example_id": eid,
                "task_group": ex["task_group"],
                "context_len": ex["context_len"],
                "prediction": prediction,
                "gold": str(gold),
                "score": round(score, 4),
                "exact": score >= 1.0,
                "cost_usd": round(cost, 6),
                "error": error,
                "iteration_count": int(result.get("iteration_count") or 0),
                "code_block_count": int(result.get("code_block_count") or 0),
                "final_answer_seen": bool(result.get("final_answer_seen")),
                "question": ex.get("question", ""),
                "input_context": get_oolong_context(ex),
                "raw_response": str(result.get("response") or ""),
                "input_tokens": int(result.get("input_tokens") or 0),
                "output_tokens": int(result.get("output_tokens") or 0),
                "elapsed_seconds": float(result.get("elapsed_seconds") or 0.0),
                "trajectory_available": bool((result.get("trajectory") or {}).get("available")),
                "trajectory": result.get("trajectory") or {},
            }
            writer.writerow({k: row[k] for k in FIELDNAMES})
            csv_f.flush()
            trace_f.write(json.dumps(row, ensure_ascii=False) + "\n")
            trace_f.flush()
            rows.append(row)
            print(
                f"  pred={prediction!r} gold={str(gold)!r} score={score:.3f} "
                f"iters={row['iteration_count']} code_blocks={row['code_block_count']} cost=${cost:.4f} error={error!r}"
            )

    if not rows:
        with trace_path.open(encoding="utf-8") as f:
            rows = [json.loads(line) for line in f if line.strip() and json.loads(line).get("run_id") == args.run_id]
    summary = summarize(rows, args)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_markdown(rows, summary, md_path)
    print(json.dumps(summary, indent=2))
    print(f"Wrote {out_path.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {trace_path.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {summary_path.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {md_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
