#!/usr/bin/env python3
"""
Run selected model/API methods on a frozen Oolong manifest.

This is the model-call counterpart to freeze_eval_oolong_heldout.py. It never
chooses examples itself; it reads a frozen manifest and optionally limits to the
first K examples per group for smoke tests. Outputs are append/resume-friendly
CSV rows so a failed run does not destroy completed calls.
"""

from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as mp
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from eval_oolong_slice import (  # noqa: E402
    parse_gold,
    run_fixed_python_method,
    run_rlm_method,
    run_slm_cot_method,
    run_slm_direct_method,
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
    "rlm_backend",
    "rlm_model",
    "slm_model",
    "prediction",
    "gold",
    "correct",
    "cost_usd",
    "error",
    "question",
]


def selected_manifest_examples(manifest_path: Path, per_group_limit: int | None) -> list[dict]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    examples = manifest["examples"]
    if per_group_limit is None:
        return examples

    seen: dict[str, int] = defaultdict(int)
    selected: list[dict] = []
    for ex in examples:
        group = str(ex["task_group"])
        if seen[group] < per_group_limit:
            selected.append(ex)
            seen[group] += 1
    return selected


def existing_keys(out_path: Path, run_id: str | None = None) -> set[tuple[str, str]]:
    if not out_path.exists():
        return set()
    keys = set()
    with out_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if run_id is not None and row.get("run_id") != run_id:
                continue
            keys.add((row["example_id"], row["method"]))
    return keys


def run_method_direct(
    method: str,
    ex: dict,
    rlm_backend: str,
    rlm_model: str,
    slm_model: str,
    rlm_max_tokens: int | None = None,
) -> tuple[str, float]:
    if method == "rlm":
        return run_rlm_method(ex, rlm_backend, rlm_model, rlm_max_tokens=rlm_max_tokens)
    if method == "fixed_python":
        return run_fixed_python_method(ex, slm_model)
    if method == "slm_direct":
        return run_slm_direct_method(ex, slm_model)
    if method == "slm_cot":
        return run_slm_cot_method(ex, slm_model)
    raise ValueError(f"Unknown method: {method}")


def _method_worker(
    queue: mp.Queue,
    method: str,
    ex: dict,
    rlm_backend: str,
    rlm_model: str,
    slm_model: str,
    rlm_max_tokens: int | None,
) -> None:
    try:
        prediction, cost = run_method_direct(method, ex, rlm_backend, rlm_model, slm_model, rlm_max_tokens)
        queue.put({"ok": True, "prediction": prediction, "cost": cost})
    except BaseException as exc:  # subprocess boundary: serialize all failures
        queue.put({"ok": False, "error": f"{type(exc).__name__}: {exc}"})


def _stop_worker(proc: mp.Process) -> None:
    """Best-effort cleanup for model-call subprocesses."""
    if not proc.is_alive():
        return
    proc.terminate()
    proc.join(10)
    if proc.is_alive():
        proc.kill()
        proc.join()


def run_method_with_optional_timeout(
    method: str,
    ex: dict,
    rlm_backend: str,
    rlm_model: str,
    slm_model: str,
    rlm_max_tokens: int | None,
    timeout_seconds: int,
) -> tuple[str, float]:
    if timeout_seconds <= 0:
        return run_method_direct(method, ex, rlm_backend, rlm_model, slm_model, rlm_max_tokens)

    ctx = mp.get_context("spawn")
    queue: mp.Queue = ctx.Queue()
    proc = ctx.Process(
        target=_method_worker,
        args=(queue, method, ex, rlm_backend, rlm_model, slm_model, rlm_max_tokens),
    )
    proc.start()
    try:
        proc.join(timeout_seconds)
    except BaseException:
        _stop_worker(proc)
        raise
    if proc.is_alive():
        _stop_worker(proc)
        raise TimeoutError(f"{method} timed out after {timeout_seconds}s on example {ex.get('id')}")

    if queue.empty():
        raise RuntimeError(f"{method} subprocess exited with code {proc.exitcode} without returning a result")
    payload = queue.get()
    if not payload.get("ok"):
        raise RuntimeError(payload.get("error", "unknown subprocess error"))
    return payload["prediction"], float(payload["cost"])


def summarize(out_path: Path, run_id: str) -> dict:
    rows = []
    with out_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("run_id") == run_id:
                rows.append(row)
    by_method: dict[str, list[float]] = defaultdict(list)
    by_group: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    costs: dict[str, float] = defaultdict(float)
    group_costs: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    errors: dict[str, int] = defaultdict(int)
    group_errors: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        method = row["method"]
        group = row["task_group"]
        score = float(row["correct"])
        by_method[method].append(score)
        by_group[group][method].append(score)
        costs[method] += float(row["cost_usd"] or 0.0)
        group_costs[group][method] += float(row["cost_usd"] or 0.0)
        if row["error"]:
            errors[method] += 1
            group_errors[group][method] += 1

    def pack(vals: list[float], cost: float, error_count: int) -> dict:
        n = len(vals)
        exact = sum(1 for v in vals if v >= 1.0)
        return {
            "n": n,
            "score_sum": round(sum(vals), 4),
            "mean_score": round(sum(vals) / n, 6) if n else 0.0,
            "exact_count": exact,
            "exact_rate": round(exact / n, 6) if n else 0.0,
            "cost_usd": round(cost, 6),
            "errors": error_count,
        }

    return {
        "metadata": {
            "run_id": run_id,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "source_csv": str(out_path.relative_to(PROJECT_ROOT)),
        },
        "overall": {m: pack(v, costs[m], errors.get(m, 0)) for m, v in sorted(by_method.items())},
        "by_group": {
            g: {m: pack(v, group_costs[g][m], group_errors[g].get(m, 0)) for m, v in sorted(mm.items())}
            for g, mm in sorted(by_group.items())
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="results/oolong_heldout_frozen_manifest_20260712.json")
    parser.add_argument("--out", default="results/oolong_heldout_model_methods_20260712.csv")
    parser.add_argument("--summary-out", default="results/oolong_heldout_model_methods_20260712_summary.json")
    parser.add_argument("--methods", default="rlm",
                        help="Comma-separated subset of: rlm,fixed_python,slm_direct,slm_cot")
    parser.add_argument("--per-group-limit", type=int, default=None,
                        help="For smoke tests, run only first K frozen examples per group.")
    parser.add_argument("--rlm-backend", default="openrouter",
                        choices=["anthropic", "openai", "openrouter"])
    parser.add_argument("--rlm-model", default="google/gemini-2.5-flash")
    parser.add_argument("--rlm-max-tokens", type=int, default=None,
                        help="Optional max_tokens passed to rlms.RLM for this sensitivity run.")
    parser.add_argument("--slm-model", default="google/gemma-4-26b-a4b-it")
    parser.add_argument("--context-variant", choices=["label_provided", "standard"],
                        default="label_provided",
                        help="label_provided uses context_window_text_with_labels; standard uses unlabeled context_window_text.")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--timeout-seconds", type=int, default=0,
                        help="Run each method call in a subprocess and record an error row if it exceeds this timeout. 0 disables.")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    manifest_path = PROJECT_ROOT / args.manifest
    out_path = PROJECT_ROOT / args.out
    summary_path = PROJECT_ROOT / args.summary_out
    methods = [m.strip() for m in args.methods.split(",") if m.strip()]
    bad = set(methods) - {"rlm", "fixed_python", "slm_direct", "slm_cot"}
    if bad:
        raise ValueError(f"Unknown methods: {sorted(bad)}")

    run_id = args.run_id or datetime.now(timezone.utc).strftime("oolong_heldout_%Y%m%dT%H%M%SZ")
    selected_meta = selected_manifest_examples(manifest_path, args.per_group_limit)
    examples = hydrate_selected_examples(selected_meta)
    for ex in examples:
        ex["_oolong_context_variant"] = args.context_variant

    done = set() if args.overwrite else existing_keys(out_path, run_id=run_id)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not out_path.exists() or args.overwrite
    mode = "w" if args.overwrite else "a"

    with out_path.open(mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if new_file:
            writer.writeheader()

        for i, ex in enumerate(examples, start=1):
            gold = parse_gold(ex.get("answer", ""), ex.get("answer_type", ""))
            print(f"[{i}/{len(examples)}] id={ex['id']} group={ex['task_group']} task={ex['task']}")
            for method in methods:
                key = (str(ex["id"]), method)
                if key in done:
                    print(f"  - {method}: skip existing")
                    continue
                prediction = ""
                cost = 0.0
                error = ""
                try:
                    prediction, cost = run_method_with_optional_timeout(
                        method,
                        ex,
                        args.rlm_backend,
                        args.rlm_model,
                        args.slm_model,
                        args.rlm_max_tokens,
                        args.timeout_seconds,
                    )
                    score = score_prediction(prediction, gold, ex.get("answer_type", ""))
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"
                    score = 0.0
                    prediction = ""
                    cost = 0.0
                    print(f"  ! {method}: {error}")
                else:
                    print(f"  - {method}: pred={prediction!r} gold={str(gold)!r} score={score:.3f} cost=${cost:.5f}")

                writer.writerow({
                    "run_id": run_id,
                    "example_id": str(ex["id"]),
                    "context_len": ex["context_len"],
                    "task_group": ex["task_group"],
                    "task": ex["task"],
                    "answer_type": ex["answer_type"],
                    "context_variant": args.context_variant,
                    "method": method,
                    "rlm_backend": args.rlm_backend,
                    "rlm_model": args.rlm_model,
                    "slm_model": args.slm_model,
                    "prediction": str(prediction),
                    "gold": str(gold),
                    "correct": round(score, 4),
                    "cost_usd": round(cost, 6),
                    "error": error,
                    "question": ex["question"],
                })
                f.flush()

    summary = summarize(out_path, run_id)
    summary["metadata"]["context_variant"] = args.context_variant
    summary["metadata"]["rlm_max_tokens"] = args.rlm_max_tokens
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Wrote {out_path.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {summary_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
