#!/usr/bin/env python3
"""Evaluate an SLM-labeler + typed-aggregation baseline on standard Oolong.

This runner targets the project P0 gap: prior Oolong evidence mostly used
`context_window_text_with_labels`, where row labels are already exposed.  Here
the input is standard Oolong `context_window_text` with unlabeled rows.  A small
language model labels each row, then the existing typed deterministic
aggregator solves the task over the predicted labels.

The method is not an RLM: it does no generated code execution and uses one SLM
worker call for local semantic labeling.  It intentionally still uses Oolong's
question/task metadata for the final typed aggregation, so reports should call
it "SLM-labeler + typed aggregation" rather than a fully autonomous agent.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import json
import os
import re
import signal
import sys
import time
from contextlib import contextmanager
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from eval_oolong_frozen_manifest_methods import selected_manifest_examples  # noqa: E402
from eval_oolong_slice import (  # noqa: E402
    estimate_cost,
    parse_gold,
    rough_token_count,
    score_prediction,
)
from probe_typed_oolong_proxy import (  # noqa: E402
    hydrate_selected_examples,
    labels_in_question,
    parse_rows as parse_labeled_rows,
    solve_typed,
)


FIELDNAMES = [
    "run_id",
    "example_id",
    "context_len",
    "task_group",
    "task",
    "answer_type",
    "context_variant",
    "method",
    "slm_model",
    "prediction",
    "gold",
    "correct",
    "cost_usd",
    "row_count",
    "row_label_exact",
    "row_label_accuracy",
    "error",
    "question",
]


ROW_LINE_RE = re.compile(
    r"^\s*Date:\s*(?P<date>[A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})"
    r"\s*\|\|\s*User:\s*(?P<user>\d+)"
    r"\s*\|\|\s*Instance:\s*(?P<instance>.*?)"
    r"(?:\s*\|\|\s*Label:\s*(?P<label>[^\|\n]+))?\s*$",
    re.IGNORECASE,
)


class HardTimeoutError(TimeoutError):
    """Raised when a signal-based wall-clock timeout expires."""


@contextmanager
def hard_timeout(seconds: float, label: str):
    if seconds <= 0:
        yield
        return
    if not hasattr(signal, "SIGALRM"):
        yield
        return

    def _handler(signum, frame):  # noqa: ARG001
        raise HardTimeoutError(f"{label} exceeded {seconds:.1f}s")

    old_handler = signal.getsignal(signal.SIGALRM)
    old_timer = signal.setitimer(signal.ITIMER_REAL, seconds)
    signal.signal(signal.SIGALRM, _handler)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
        if old_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, old_timer[0], old_timer[1])


def safe_slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text)).strip("_")[:160]


def load_project_env() -> None:
    """Load ~/<local-config>/.env when the shell has not exported API keys."""
    env_path = Path.home() / "<local-config>" / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip("'\"")


def parse_unlabeled_rows(context: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in context.splitlines():
        m = ROW_LINE_RE.match(line)
        if not m:
            continue
        rows.append(
            {
                "date": m.group("date").strip(),
                "user": m.group("user").strip(),
                "instance": m.group("instance").strip(),
            }
        )
    return rows


def extract_allowed_labels(context: str, question: str) -> list[str]:
    labels: list[str] = []

    # Prefer labels declared in the dataset description before the first row.
    prefix = context.split("Date:", 1)[0]
    for quoted in re.findall(r"'([^']+)'", prefix):
        candidate = quoted.strip()
        if candidate and candidate.lower() not in {"answer", "x"}:
            labels.append(candidate)

    # Oolong standard contexts often describe binary labels without quotes:
    # "Each review can be classified as positive or negative; ..."
    # "Each sentence can be classified as informal or formal; ..."
    for m in re.finditer(
        r"classified as\s+([A-Za-z0-9_& /-]+?)\s+or\s+([A-Za-z0-9_& /-]+?)(?:[;(,.\n]| there\b| so\b)",
        prefix,
        flags=re.IGNORECASE,
    ):
        labels.extend([m.group(1).strip(), m.group(2).strip()])

    # Add labels named by the question in case the intro parser misses them.
    labels.extend(labels_in_question(question))

    seen: set[str] = set()
    out: list[str] = []
    for label in labels:
        key = label.casefold()
        if key not in seen:
            seen.add(key)
            out.append(label)
    return out


def build_label_prompt(rows: list[dict[str, str]], labels: list[str], question: str) -> str:
    row_payload = [
        {
            "i": i,
            "date": row["date"],
            "user": row["user"],
            "instance": row["instance"],
        }
        for i, row in enumerate(rows, start=1)
    ]
    return (
        "You are the semantic labeling worker for an aggregation benchmark.\n"
        "Classify each row's instance into exactly one allowed label. Do not answer "
        "the aggregate question; only label the rows.\n\n"
        f"Allowed labels: {json.dumps(labels, ensure_ascii=False)}\n"
        f"Aggregate question, for context only: {question}\n\n"
        "Return JSON only, with this exact schema:\n"
        '{"labels":[{"i":1,"label":"..."},{"i":2,"label":"..."}]}\n'
        f"The JSON must contain exactly {len(rows)} items, one for each row index.\n\n"
        "Rows:\n"
        f"{json.dumps(row_payload, ensure_ascii=False)}"
    )


def call_openrouter(prompt: str, model: str, max_tokens: int, request_timeout: float) -> tuple[str, int, int]:
    load_project_env()
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENROUTER_API_KEY not set")
    import openai

    client = openai.OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        timeout=request_timeout,
    )
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=max_tokens,
    )
    text = response.choices[0].message.content or ""
    usage = response.usage
    in_tok = usage.prompt_tokens if usage else rough_token_count(prompt)
    out_tok = usage.completion_tokens if usage else rough_token_count(text)
    return text, in_tok, out_tok


def block_cache_path(
    block_cache_dir: Path | None,
    run_id: str,
    example_id: str,
    start_index: int,
    row_count: int,
    model: str,
) -> Path | None:
    if block_cache_dir is None:
        return None
    end_index = start_index + row_count - 1
    filename = (
        f"{safe_slug(run_id)}__ex-{safe_slug(example_id)}__"
        f"rows-{start_index:05d}-{end_index:05d}__model-{safe_slug(model)}.json"
    )
    return block_cache_dir / safe_slug(run_id) / filename


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def compute_uncached_block(
    *,
    prompt: str,
    labels: list[str],
    chunk_len: int,
    model: str,
    dry_run: bool,
    request_timeout: float,
    example_id: str,
    start_index: int,
    block_retries: int,
    block_retry_sleep: float,
    use_signal_timeout: bool,
) -> dict[str, Any]:
    attempts = 0
    while True:
        attempts += 1
        try:
            if dry_run:
                raw = json.dumps({"labels": [{"i": i, "label": labels[0]} for i in range(1, chunk_len + 1)]})
                in_tok = rough_token_count(prompt)
                out_tok = rough_token_count(raw)
                cost = 0.0
            else:
                if use_signal_timeout:
                    with hard_timeout(request_timeout, f"OpenRouter block {example_id}:{start_index}"):
                        raw, in_tok, out_tok = call_openrouter(
                            prompt,
                            model,
                            max_tokens=max(512, 24 * chunk_len + 256),
                            request_timeout=request_timeout,
                        )
                else:
                    raw, in_tok, out_tok = call_openrouter(
                        prompt,
                        model,
                        max_tokens=max(512, 24 * chunk_len + 256),
                        request_timeout=request_timeout,
                    )
                cost = estimate_cost(model, in_tok, out_tok)
            chunk_labels = parse_predicted_labels(raw, chunk_len, labels)
            return {
                "raw_response": raw,
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "cost_usd": cost,
                "predicted_labels": chunk_labels,
                "attempts": attempts,
            }
        except Exception:
            if attempts > block_retries + 1:
                raise
            time.sleep(max(0.0, block_retry_sleep) * attempts)


def label_rows_with_slm(
    rows: list[dict[str, str]],
    labels: list[str],
    question: str,
    model: str,
    dry_run: bool,
    chunk_size: int,
    request_timeout: float,
    run_id: str,
    example_id: str,
    block_cache_dir: Path | None,
    overwrite_block_cache: bool,
    block_concurrency: int,
    block_retries: int,
    block_retry_sleep: float,
) -> tuple[list[str], float, int, int, str, list[dict[str, Any]]]:
    predicted: list[str] = []
    total_cost = 0.0
    total_in_tok = 0
    total_out_tok = 0
    raw_joined: list[str] = []
    blocks: list[dict[str, Any]] = []

    if chunk_size <= 0:
        chunks = [(1, rows)]
    else:
        chunks = [(start + 1, rows[start:start + chunk_size]) for start in range(0, len(rows), chunk_size)]

    specs: list[dict[str, Any]] = []
    results_by_start: dict[int, dict[str, Any]] = {}
    for start_index, chunk in chunks:
        prompt = build_label_prompt(chunk, labels, question)
        cache_path = block_cache_path(block_cache_dir, run_id, example_id, start_index, len(chunk), model)
        specs.append(
            {
                "start_index": start_index,
                "chunk": chunk,
                "prompt": prompt,
                "cache_path": cache_path,
            }
        )

        if cache_path is not None and cache_path.exists() and not overwrite_block_cache:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            results_by_start[start_index] = {
                "raw_response": str(cached["raw_response"]),
                "input_tokens": int(cached["input_tokens"]),
                "output_tokens": int(cached["output_tokens"]),
                "cost_usd": float(cached["cost_usd"]),
                "predicted_labels": [str(x) for x in cached["predicted_labels"]],
                "cache_hit": True,
                "attempts": int(cached.get("attempts", 1)),
            }

    uncached_specs = [spec for spec in specs if spec["start_index"] not in results_by_start]
    workers = max(1, int(block_concurrency or 1))

    def finish_uncached(spec: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        cache_path = spec["cache_path"]
        start_index = int(spec["start_index"])
        chunk = spec["chunk"]
        payload = {**payload, "cache_hit": False}
        if cache_path is not None:
            write_json_atomic(
                cache_path,
                {
                    "run_id": run_id,
                    "example_id": example_id,
                    "model": model,
                    "start_row": start_index,
                    "end_row": start_index + len(chunk) - 1,
                    "row_count": len(chunk),
                    "prompt": spec["prompt"],
                    "raw_response": payload["raw_response"],
                    "predicted_labels": payload["predicted_labels"],
                    "input_tokens": payload["input_tokens"],
                    "output_tokens": payload["output_tokens"],
                    "cost_usd": payload["cost_usd"],
                    "attempts": payload.get("attempts", 1),
                    "created_utc": datetime.now(timezone.utc).isoformat(),
                    "dry_run_estimated_cost_if_real_usd": (
                        estimate_cost(model, payload["input_tokens"], payload["output_tokens"])
                        if dry_run else None
                    ),
                },
            )
        return payload

    if workers <= 1:
        for spec in uncached_specs:
            payload = compute_uncached_block(
                prompt=spec["prompt"],
                labels=labels,
                chunk_len=len(spec["chunk"]),
                model=model,
                dry_run=dry_run,
                request_timeout=request_timeout,
                example_id=example_id,
                start_index=int(spec["start_index"]),
                block_retries=block_retries,
                block_retry_sleep=block_retry_sleep,
                use_signal_timeout=True,
            )
            results_by_start[int(spec["start_index"])] = finish_uncached(spec, payload)
    elif uncached_specs:
        # Signal alarms only work in the main thread.  Concurrent mode relies on
        # the OpenAI client timeout for each worker and preserves block caches so
        # interrupted runs can resume without repeating completed paid calls.
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_spec = {
                executor.submit(
                    compute_uncached_block,
                    prompt=spec["prompt"],
                    labels=labels,
                    chunk_len=len(spec["chunk"]),
                    model=model,
                    dry_run=dry_run,
                    request_timeout=request_timeout,
                    example_id=example_id,
                    start_index=int(spec["start_index"]),
                    block_retries=block_retries,
                    block_retry_sleep=block_retry_sleep,
                    use_signal_timeout=False,
                ): spec
                for spec in uncached_specs
            }
            for future in concurrent.futures.as_completed(future_to_spec):
                spec = future_to_spec[future]
                payload = future.result()
                results_by_start[int(spec["start_index"])] = finish_uncached(spec, payload)

    for spec in specs:
        start_index = int(spec["start_index"])
        chunk = spec["chunk"]
        prompt = spec["prompt"]
        cache_path = spec["cache_path"]
        result = results_by_start[start_index]
        raw = str(result["raw_response"])
        in_tok = int(result["input_tokens"])
        out_tok = int(result["output_tokens"])
        cost = float(result["cost_usd"])
        chunk_labels = [str(x) for x in result["predicted_labels"]]
        predicted.extend(chunk_labels)
        total_cost += cost
        total_in_tok += in_tok
        total_out_tok += out_tok
        raw_joined.append(raw)
        blocks.append(
            {
                "start_row": start_index,
                "end_row": start_index + len(chunk) - 1,
                "row_count": len(chunk),
                "prompt": prompt,
                "raw_response": raw,
                "predicted_labels": chunk_labels,
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "cost_usd": cost,
                "dry_run_estimated_cost_if_real_usd": estimate_cost(model, in_tok, out_tok) if dry_run else None,
                "cache_hit": bool(result.get("cache_hit")),
                "attempts": int(result.get("attempts", 1)),
                "cache_path": str(cache_path.relative_to(PROJECT_ROOT)) if cache_path and cache_path.is_relative_to(PROJECT_ROOT) else str(cache_path) if cache_path else None,
            }
        )

    return predicted, total_cost, total_in_tok, total_out_tok, "\n\n---BLOCK---\n\n".join(raw_joined), blocks


def _json_from_text(text: str) -> Any:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"(\{.*\}|\[.*\])", text, flags=re.DOTALL)
    if not m:
        raise ValueError("No JSON object or array found in SLM response")
    return json.loads(m.group(1))


def parse_predicted_labels(text: str, n_rows: int, allowed: list[str]) -> list[str]:
    payload = _json_from_text(text)
    items = payload.get("labels", payload) if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise ValueError("SLM response JSON has no list of labels")

    by_index: dict[int, str] = {}
    sequential: list[str] = []
    for item in items:
        if isinstance(item, dict):
            label = str(item.get("label", "")).strip()
            try:
                idx = int(item.get("i"))
            except Exception:
                idx = len(sequential) + 1
            if label:
                by_index[idx] = label
                sequential.append(label)
        elif isinstance(item, str):
            sequential.append(item.strip())

    labels = [by_index.get(i) for i in range(1, n_rows + 1)]
    if any(label is None for label in labels):
        labels = sequential[:n_rows]
    if len(labels) != n_rows:
        raise ValueError(f"Expected {n_rows} labels, received {len(labels)}")

    allowed_by_case = {label.casefold(): label for label in allowed}
    normalized: list[str] = []
    for label in labels:
        label_s = str(label).strip().strip("'\"")
        normalized.append(allowed_by_case.get(label_s.casefold(), label_s))
    return normalized


def labeled_context_from_predictions(rows: list[dict[str, str]], labels: list[str], original_context: str) -> str:
    intro = original_context.split("Date:", 1)[0]
    lines = [
        f"Date: {row['date']} || User: {row['user']} || Instance: {row['instance']} || Label: {label}"
        for row, label in zip(rows, labels)
    ]
    return intro + "\n".join(lines)


def gold_row_labels(example: dict) -> list[str]:
    rows = parse_labeled_rows(example.get("context_window_text_with_labels", ""))
    return [r.label for r in rows]


def run_example(
    example: dict,
    model: str,
    run_id: str,
    dry_run: bool = False,
    chunk_size: int = 0,
    request_timeout: float = 120.0,
    block_cache_dir: Path | None = None,
    overwrite_block_cache: bool = False,
    block_concurrency: int = 1,
    block_retries: int = 0,
    block_retry_sleep: float = 2.0,
) -> tuple[str, float, dict[str, Any]]:
    context = example.get("context_window_text", "")
    rows = parse_unlabeled_rows(context)
    if not rows:
        raise ValueError("No unlabeled rows parsed from standard context")
    labels = extract_allowed_labels(context, example.get("question", ""))
    if not labels:
        raise ValueError("Could not infer allowed label set")

    predicted_labels, cost, in_tok, out_tok, raw, blocks = label_rows_with_slm(
        rows=rows,
        labels=labels,
        question=example.get("question", ""),
        model=model,
        dry_run=dry_run,
        chunk_size=chunk_size,
        request_timeout=request_timeout,
        run_id=run_id,
        example_id=str(example["id"]),
        block_cache_dir=block_cache_dir,
        overwrite_block_cache=overwrite_block_cache,
        block_concurrency=block_concurrency,
        block_retries=block_retries,
        block_retry_sleep=block_retry_sleep,
    )

    ex2 = dict(example)
    ex2["context_window_text_with_labels"] = labeled_context_from_predictions(rows, predicted_labels, context)
    prediction, ops, status = solve_typed(ex2)
    if prediction is None:
        prediction = ""

    gold_labels = gold_row_labels(example)
    label_matches = sum(
        1 for pred, gold in zip(predicted_labels, gold_labels)
        if pred.casefold() == str(gold).casefold()
    )
    row_label_accuracy = label_matches / len(gold_labels) if gold_labels else None
    meta = {
        "method": "slm_labeler_typed",
        "context_variant": "standard",
        "model": model,
        "allowed_labels": labels,
        "row_count": len(rows),
        "chunk_size": chunk_size,
        "request_timeout_seconds": request_timeout,
        "block_count": len(blocks),
        "block_concurrency": block_concurrency,
        "block_retries": block_retries,
        "block_retry_sleep_seconds": block_retry_sleep,
        "block_cache_dir": str(block_cache_dir.relative_to(PROJECT_ROOT)) if block_cache_dir and block_cache_dir.is_relative_to(PROJECT_ROOT) else str(block_cache_dir) if block_cache_dir else None,
        "block_cache_hits": sum(1 for b in blocks if b.get("cache_hit")),
        "prompt": blocks[0]["prompt"] if len(blocks) == 1 else "see blocks",
        "raw_response": raw,
        "blocks": blocks,
        "predicted_labels": predicted_labels,
        "gold_labels": gold_labels,
        "row_label_exact": label_matches,
        "row_label_accuracy": row_label_accuracy,
        "typed_ops": ops,
        "typed_status": status,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "estimated_cost_usd": cost,
        "dry_run_estimated_cost_if_real_usd": sum(
            b.get("dry_run_estimated_cost_if_real_usd") or 0.0 for b in blocks
        ) if dry_run else None,
    }
    return str(prediction), cost, meta


def existing_keys(out_path: Path, run_id: str | None = None, retry_errors: bool = False) -> set[str]:
    if not out_path.exists():
        return set()
    keys: set[str] = set()
    with out_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if run_id is not None and row.get("run_id") != run_id:
                continue
            if retry_errors and row.get("error"):
                continue
            keys.add(row["example_id"])
    return keys


def summarize(rows: list[dict[str, str]], out_path: Path, run_id: str) -> dict[str, Any]:
    by_group: dict[str, list[float]] = defaultdict(list)
    overall: list[float] = []
    cost = 0.0
    label_accs: list[float] = []
    errors = 0
    for row in rows:
        score = float(row["correct"])
        overall.append(score)
        by_group[row["task_group"]].append(score)
        cost += float(row["cost_usd"] or 0.0)
        if row.get("row_label_accuracy"):
            label_accs.append(float(row["row_label_accuracy"]))
        if row.get("error"):
            errors += 1

    def pack(vals: list[float]) -> dict[str, Any]:
        exact = sum(1 for v in vals if v >= 1.0)
        return {
            "n": len(vals),
            "score_sum": round(sum(vals), 4),
            "mean_score": round(sum(vals) / len(vals), 6) if vals else 0.0,
            "exact_count": exact,
            "exact_rate": round(exact / len(vals), 6) if vals else 0.0,
        }

    return {
        "metadata": {
            "run_id": run_id,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "source_csv": str(out_path.relative_to(PROJECT_ROOT)),
            "method": "slm_labeler_typed",
            "context_variant": "standard",
        },
        "overall": {
            "slm_labeler_typed": {
                **pack(overall),
                "cost_usd": round(cost, 6),
                "errors": errors,
                "mean_row_label_accuracy": round(sum(label_accs) / len(label_accs), 6) if label_accs else None,
            }
        },
        "by_group": {
            group: {"slm_labeler_typed": pack(vals)}
            for group, vals in sorted(by_group.items())
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="results/oolong_heldout_frozen_manifest_20260712.json")
    parser.add_argument("--out", default="results/oolong_standard_unlabeled_slm_labeler_typed_20260712.csv")
    parser.add_argument("--summary-out", default="results/oolong_standard_unlabeled_slm_labeler_typed_20260712_summary.json")
    parser.add_argument("--trace-out", default="results/oolong_standard_unlabeled_slm_labeler_typed_20260712_trace.jsonl")
    parser.add_argument("--per-group-limit", type=int, default=None)
    parser.add_argument("--model", default="google/gemma-4-26b-a4b-it")
    parser.add_argument("--dataset-split", choices=["test", "validation"], default="test",
                        help="Explicit Oolong split used to hydrate the frozen manifest.")
    parser.add_argument("--chunk-size", type=int, default=0,
                        help="Rows per SLM labeling call. 0 labels all rows in one call.")
    parser.add_argument("--request-timeout", type=float, default=120.0,
                        help="Per OpenRouter request timeout in seconds.")
    parser.add_argument("--block-cache-dir", default=None,
                        help="Optional directory for per-block prompt/response/cache JSON files.")
    parser.add_argument("--overwrite-block-cache", action="store_true",
                        help="Ignore existing per-block cache files and call the SLM again.")
    parser.add_argument("--block-concurrency", type=int, default=1,
                        help="Maximum concurrent uncached block calls per example. 1 preserves sequential hard-timeout behavior.")
    parser.add_argument("--block-retries", type=int, default=0,
                        help="Retry count for each uncached block call before failing the example.")
    parser.add_argument("--block-retry-sleep", type=float, default=2.0,
                        help="Base seconds to sleep between block retries; multiplied by the attempt number.")
    parser.add_argument("--retry-errors", action="store_true",
                        help="Do not treat existing error rows as completed examples.")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="No API call; emits first-label dummy predictions for parser testing.")
    args = parser.parse_args()

    manifest_path = PROJECT_ROOT / args.manifest
    out_path = PROJECT_ROOT / args.out
    summary_path = PROJECT_ROOT / args.summary_out
    trace_path = PROJECT_ROOT / args.trace_out
    block_cache_dir = PROJECT_ROOT / args.block_cache_dir if args.block_cache_dir else None
    run_id = args.run_id or datetime.now(timezone.utc).strftime("oolong_standard_slm_labeler_%Y%m%dT%H%M%SZ")

    selected_meta = selected_manifest_examples(manifest_path, args.per_group_limit)
    examples = hydrate_selected_examples(selected_meta, split=args.dataset_split)

    done = set() if args.overwrite else existing_keys(out_path, run_id=run_id, retry_errors=args.retry_errors)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not out_path.exists() or args.overwrite
    mode = "w" if args.overwrite else "a"
    trace_mode = "w" if args.overwrite else "a"
    written_rows: list[dict[str, str]] = []

    with out_path.open(mode, newline="", encoding="utf-8") as f, trace_path.open(trace_mode, encoding="utf-8") as trace_f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if new_file:
            writer.writeheader()
        for i, ex in enumerate(examples, start=1):
            if str(ex["id"]) in done:
                print(f"[{i}/{len(examples)}] id={ex['id']}: skip existing")
                continue
            gold = parse_gold(ex.get("answer", ""), ex.get("answer_type", ""))
            prediction = ""
            cost = 0.0
            error = ""
            meta: dict[str, Any] = {}
            try:
                prediction, cost, meta = run_example(
                    ex,
                    args.model,
                    run_id=run_id,
                    dry_run=args.dry_run,
                    chunk_size=args.chunk_size,
                    request_timeout=args.request_timeout,
                    block_cache_dir=block_cache_dir,
                    overwrite_block_cache=args.overwrite_block_cache,
                    block_concurrency=args.block_concurrency,
                    block_retries=args.block_retries,
                    block_retry_sleep=args.block_retry_sleep,
                )
                score = score_prediction(prediction, gold, ex.get("answer_type", ""))
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                score = 0.0
                meta = {"error": error}

            row = {
                "run_id": run_id,
                "example_id": str(ex["id"]),
                "context_len": str(ex["context_len"]),
                "task_group": ex["task_group"],
                "task": ex["task"],
                "answer_type": ex["answer_type"],
                "context_variant": "standard",
                "method": "slm_labeler_typed",
                "slm_model": args.model,
                "prediction": str(prediction),
                "gold": str(gold),
                "correct": str(round(score, 4)),
                "cost_usd": str(round(cost, 6)),
                "row_count": str(meta.get("row_count", "")),
                "row_label_exact": str(meta.get("row_label_exact", "")),
                "row_label_accuracy": str(round(meta["row_label_accuracy"], 6)) if meta.get("row_label_accuracy") is not None else "",
                "error": error,
                "question": ex["question"],
            }
            writer.writerow(row)
            f.flush()
            trace_payload = {
                "run_id": run_id,
                "example_id": str(ex["id"]),
                "task_group": ex["task_group"],
                "task": ex["task"],
                "answer_type": ex["answer_type"],
                "question": ex["question"],
                "gold": str(gold),
                "prediction": str(prediction),
                "score": score,
                **meta,
            }
            trace_f.write(json.dumps(trace_payload, ensure_ascii=False) + "\n")
            trace_f.flush()
            written_rows.append(row)
            print(
                f"[{i}/{len(examples)}] id={ex['id']} pred={prediction!r} "
                f"gold={str(gold)!r} score={score:.3f} cost=${cost:.5f} error={error!r}"
            )

    # Summarize all rows for this run_id, including rows written before resume.
    all_rows: list[dict[str, str]] = []
    with out_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("run_id") == run_id:
                all_rows.append(row)
    summary = summarize(all_rows, out_path, run_id)
    summary["metadata"]["chunk_size"] = args.chunk_size
    summary["metadata"]["dataset_split"] = args.dataset_split
    summary["metadata"]["dry_run"] = args.dry_run
    summary["metadata"]["request_timeout_seconds"] = args.request_timeout
    summary["metadata"]["block_concurrency"] = args.block_concurrency
    summary["metadata"]["block_retries"] = args.block_retries
    summary["metadata"]["block_retry_sleep_seconds"] = args.block_retry_sleep
    summary["metadata"]["block_cache_dir"] = (
        str(block_cache_dir.relative_to(PROJECT_ROOT))
        if block_cache_dir and block_cache_dir.is_relative_to(PROJECT_ROOT)
        else str(block_cache_dir) if block_cache_dir else None
    )
    if block_cache_dir is not None:
        run_cache_dir = block_cache_dir / safe_slug(run_id)
        summary["metadata"]["block_cache_files"] = (
            sum(1 for _ in run_cache_dir.glob("*.json")) if run_cache_dir.exists() else 0
        )
    summary["metadata"]["retry_errors"] = args.retry_errors
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Wrote {out_path.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {summary_path.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {trace_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
