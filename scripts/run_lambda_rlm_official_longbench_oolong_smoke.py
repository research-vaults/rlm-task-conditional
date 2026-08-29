#!/usr/bin/env python3
"""Trace-preserving lambda-RLM official-entrypoint smoke.

This runner uses the public lambda-RLM repository's own LongBench-v2
`oolong` loader and LambdaRLM class, but writes fuller prompt/response/usage
traces than the stock benchmark script. It is intentionally not an Oolong-synth
same-contract run; it is an official-loader sanity check for stronger-family
protocol diligence.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import multiprocessing as mp
import os
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LAMBDA_REPO = ROOT / "external_repos" / "lambda-RLM"
BENCHMARK_PY = LAMBDA_REPO / "benchmarks" / "benchmark.py"


def load_project_env() -> None:
    """Load API keys from an explicitly supplied local env file."""
    env_spec = os.environ.get("RLM_ENV_PATH")
    if not env_spec:
        return
    env_path = Path(env_spec).expanduser()
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def import_lambda_benchmark():
    sys.path.insert(0, str(LAMBDA_REPO))
    spec = importlib.util.spec_from_file_location("lambda_official_benchmark", BENCHMARK_PY)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import {BENCHMARK_PY}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["lambda_official_benchmark"] = module
    spec.loader.exec_module(module)
    return module


def usage_to_dict(usage: Any) -> dict[str, Any]:
    if usage is None:
        return {}
    if hasattr(usage, "to_dict"):
        return usage.to_dict()
    return {"repr": repr(usage)}


def run_lambda_row_child(prompt: str, settings: dict[str, Any], queue: mp.Queue) -> None:
    """Run one lambda-RLM completion in a killable child process."""
    try:
        load_project_env()
        sys.path.insert(0, str(LAMBDA_REPO))
        from rlm import LambdaRLM  # type: ignore

        api_key = (
            os.environ.get("OPENROUTER_API_KEY")
            if "openrouter.ai" in settings["base_url"]
            else None
        )
        runner = LambdaRLM(
            backend=settings["backend"],
            backend_kwargs={
                "model_name": settings["model"],
                "temperature": settings["temperature"],
                "top_p": settings["top_p"],
                "max_tokens": settings["max_tokens"],
                "stream": False,
                "base_url": settings["base_url"],
                "api_key": api_key,
            },
            context_window_chars=settings["context_window_chars"],
            verbose=True,
        )
        completion = runner.completion(prompt)
        queue.put({
            "response": completion.response,
            "usage": usage_to_dict(completion.usage_summary),
            "execution_time": completion.execution_time,
            "error": None,
        })
    except Exception as exc:  # noqa: BLE001 - child must serialize failures
        queue.put({
            "response": "",
            "usage": {},
            "execution_time": None,
            "error": f"{type(exc).__name__}: {exc}",
        })


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="google/gemini-2.5-flash")
    parser.add_argument("--base-url", default="https://openrouter.ai/api/v1")
    parser.add_argument("--backend", default="openai")
    parser.add_argument("--n-samples-per-bucket", type=int, default=1)
    parser.add_argument("--max-samples", type=int, default=2)
    parser.add_argument("--context-window", type=int, default=100_000)
    parser.add_argument("--temperature", type=float, default=0.6)
    parser.add_argument("--top-p", type=float, default=0.7)
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--row-timeout-seconds", type=int, default=240)
    parser.add_argument("--out-prefix", default="results/lambda_rlm_official_longbench_oolong_smoke_20260714")
    args = parser.parse_args()

    load_project_env()
    bench = import_lambda_benchmark()

    out_prefix = ROOT / args.out_prefix
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_prefix.with_suffix(".jsonl")
    summary_path = Path(str(out_prefix) + "_summary.json")
    md_path = Path(str(out_prefix) + "_analysis.md")

    samples = bench.load_oolong(args.n_samples_per_bucket)
    samples = sorted(samples, key=lambda s: (s.token_len, s.idx))[: args.max_samples]
    if not samples:
        raise SystemExit("No official lambda-RLM LongBench-v2 oolong samples loaded.")

    settings = {
        "model": args.model,
        "backend": args.backend,
        "base_url": args.base_url,
        "context_window_chars": args.context_window,
        "temperature": args.temperature,
        "top_p": args.top_p,
        "max_tokens": args.max_tokens,
        "stream": False,
        "row_timeout_seconds": args.row_timeout_seconds,
        "n_samples_per_bucket": args.n_samples_per_bucket,
        "max_samples": args.max_samples,
    }

    rows: list[dict[str, Any]] = []
    with jsonl_path.open("w", encoding="utf-8") as f:
        for run_i, sample in enumerate(samples, start=1):
            prompt = bench._build_prompt(sample)
            started = time.perf_counter()
            error = None
            response = ""
            usage: dict[str, Any] = {}
            execution_time = None
            ctx = mp.get_context("fork")
            queue: mp.Queue = ctx.Queue()
            proc = ctx.Process(target=run_lambda_row_child, args=(prompt, settings, queue))
            proc.start()
            proc.join(args.row_timeout_seconds)
            if proc.is_alive():
                proc.terminate()
                proc.join(10)
                if proc.is_alive():
                    proc.kill()
                    proc.join(10)
                error = f"ProcessTimeout: row exceeded {args.row_timeout_seconds}s"
            else:
                child_result = queue.get() if not queue.empty() else {
                    "response": "",
                    "usage": {},
                    "execution_time": None,
                    "error": f"Child exited with code {proc.exitcode} and no result",
                }
                response = child_result["response"]
                usage = child_result["usage"]
                execution_time = child_result["execution_time"]
                error = child_result["error"]
            elapsed = time.perf_counter() - started
            row = {
                "run_i": run_i,
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "method": "lambda_rlm_official_longbench_v2_oolong_loader",
                "implementation": {
                    "repo": "external_repos/lambda-RLM",
                    "entrypoint_basis": "benchmarks/benchmark.py load_oolong + rlm.LambdaRLM",
                    "official_loader_dataset": "THUDM/LongBench-v2",
                    "official_loader_domain_filter": "Single-Document QA",
                    "not_same_contract_as_main_paper": True,
                },
                "settings": {
                    **settings,
                },
                "sample": asdict(sample),
                "prompt": prompt,
                "prediction": response,
                "gold": sample.gold,
                "scores": {
                    "f1": bench._f1(response, sample.gold),
                    "contains": bench._contains(response, sample.gold),
                    "exact": bench._exact(response, sample.gold),
                },
                "usage": usage,
                "elapsed_seconds": elapsed,
                "completion_execution_time_seconds": execution_time,
                "error": error,
            }
            rows.append(row)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            print(
                f"[{run_i}/{len(samples)}] {sample.bin_label} idx={sample.idx} "
                f"f1={row['scores']['f1']:.3f} exact={row['scores']['exact']:.0f} "
                f"elapsed={elapsed:.1f}s error={error}",
                flush=True,
            )

    completed = [r for r in rows if not r["error"]]
    total_cost = 0.0
    cost_known = False
    for row in rows:
        cost = row["usage"].get("total_cost")
        if cost is not None:
            total_cost += float(cost)
            cost_known = True
    summary = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "artifact_type": "lambda_rlm_official_entrypoint_smoke",
        "jsonl": str(jsonl_path.relative_to(ROOT)),
        "n": len(rows),
        "completed": len(completed),
        "errors": len(rows) - len(completed),
        "mean_f1": sum(r["scores"]["f1"] for r in rows) / len(rows),
        "exact_count": int(sum(r["scores"]["exact"] for r in rows)),
        "contains_count": int(sum(r["scores"]["contains"] for r in rows)),
        "total_cost_usd": total_cost if cost_known else None,
        "cost_known": cost_known,
        "model": args.model,
        "contract_warning": (
            "Uses lambda-RLM's official LongBench-v2 Single-Document QA loader, "
            "not the paper's standard-unlabeled Oolong-synth aggregation contract."
        ),
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    md_lines = [
        "# lambda-RLM Official LongBench-v2 Oolong Smoke",
        "",
        "This is a protocol-diligence artifact, not a headline same-contract benchmark row.",
        "",
        f"- Model: `{args.model}`",
        "- Implementation: public `external_repos/lambda-RLM` using `benchmarks/benchmark.py`'s `load_oolong` and `rlm.LambdaRLM`.",
        "- Dataset/loader: `THUDM/LongBench-v2`, domain filter `Single-Document QA`.",
        "- Contract warning: this is not the main paper's Oolong-synth aggregation contract.",
        f"- Rows: {summary['n']} loaded, {summary['completed']} completed, {summary['errors']} errors.",
        f"- Exact: {summary['exact_count']}/{summary['n']}; mean F1: {summary['mean_f1']:.3f}; contains: {summary['contains_count']}/{summary['n']}.",
        f"- Captured cost: {summary['total_cost_usd'] if summary['cost_known'] else 'not returned'}",
        "",
        "| Row | Bin | LB2 idx | Context chars | F1 | Exact | Error |",
        "|---:|---|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        s = row["sample"]
        md_lines.append(
            f"| {row['run_i']} | {s['bin_label']} | {s['idx']} | {s['ctx_len']} | "
            f"{row['scores']['f1']:.3f} | {int(row['scores']['exact'])} | {row['error'] or ''} |"
        )
    md_lines.extend([
        "",
        "Interpretation: if this smoke is useful, it supports only the claim that the released lambda-RLM code path was inspected and exercised on its own official-style LongBench-v2 task. It cannot establish that lambda-RLM fails or wins on the paper's standard-unlabeled Oolong-synth aggregation benchmark.",
    ])
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"Wrote {jsonl_path}")
    print(f"Wrote {summary_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
