#!/usr/bin/env python3
"""Run the untouched BrowseComp+ N=59 replication on an isolated RunPod pod.

This driver is deliberately accuracy-blind while generating predictions. It
records every restricted input/output, official-RLM trace, request parameter,
usage field, latency, pod event, and cleanup action. It never deletes pods it
did not create.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "external_repos/rlm-official"))

from run_browsecomp_plus_positive_regime import (  # noqa: E402
    answer_prompt,
    bm25_rank_multi,
    fit_documents,
    format_context,
    load_env,
    load_needed_corpus,
    load_selected_queries,
    parse_planner_queries,
    sanitize_rlm_metadata,
    sha256_file,
    sha256_text,
)
from rlm import RLM  # noqa: E402
from rlm.logger import RLMLogger  # noqa: E402


STUDY_ID = "browsecomp_plus_untouched_replication_n59_v1"
MODEL_REPO = "Qwen/Qwen3.6-35B-A3B-FP8"
MODEL_REVISION = "95a723d08a9490559dae23d0cff1d9466213d989"
SERVED_MODEL = "qwen36-35b-a3b-fp8"
VLLM_IMAGE = "vllm/vllm-openai@sha256:e4f88a835143cd22aee2397a26ec6bb80b3a4a6fe0c882bcbc63822904766089"
OFFICIAL_RLM_COMMIT = "72d6940142ddfb84ee6be573dc999a37e633e671"
MANIFEST_PATH = ROOT / "results/browsecomp_plus_positive_regime_replication/manifest_n59_restricted.json"
MANIFEST_SHA256 = "3aa19bb692f37d567a8983396ae950a11aca5b6ba5664e9b2c05160a0df6fea2"
RUNPOD_REST = "https://rest.runpod.io/v1"
METHODS = ("standard_rlm_qwen36", "bm25_qwen36", "text_decompose_qwen36")
RESULT_DIR = ROOT / "results/browsecomp_plus_positive_regime_replication"

GENERATION = {
    "temperature": 0.7,
    "top_p": 0.8,
    "top_k": 20,
    "presence_penalty": 1.5,
    "seed": 20,
    "enable_thinking": False,
}


class RowTimeout(Exception):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    opener = gzip.open if path.suffix == ".gz" else path.open
    with opener(path, "at", encoding="utf-8") if path.suffix == ".gz" else opener("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n")
        handle.flush()
        if path.suffix != ".gz":
            os.fsync(handle.fileno())
    os.chmod(path, 0o600)


def api_request(
    method: str,
    url: str,
    key: str,
    *,
    payload: dict[str, Any] | None = None,
    timeout: float = 120,
) -> requests.Response:
    return requests.request(
        method,
        url,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=payload,
        timeout=timeout,
    )


def checked_json(response: requests.Response, label: str) -> Any:
    if not response.ok:
        raise RuntimeError(f"{label}: HTTP {response.status_code}: {response.text[:1000]}")
    return response.json() if response.content else None


def list_pods(key: str) -> list[dict[str, Any]]:
    payload = checked_json(api_request("GET", f"{RUNPOD_REST}/pods", key), "list pods")
    if isinstance(payload, list):
        return payload
    return list(payload.get("items", payload.get("pods", [])))


def create_pod(key: str, hf_token: str, stamp: str) -> dict[str, Any]:
    payload = {
        "name": f"rlm-audit-bcp-repl-qwen36-{stamp}",
        "imageName": VLLM_IMAGE,
        "gpuTypeIds": [
            "NVIDIA H200 NVL",
            "NVIDIA H200",
        ],
        "gpuCount": 1,
        "containerDiskInGb": 120,
        "volumeInGb": 0,
        "ports": ["8000/http"],
        "env": {"HF_TOKEN": hf_token},
        "dockerStartCmd": [
            "--model", MODEL_REPO,
            "--revision", MODEL_REVISION,
            "--served-model-name", SERVED_MODEL,
            "--max-model-len", "65536",
            "--gpu-memory-utilization", "0.94",
            "--max-num-seqs", "4",
            "--enable-prefix-caching",
            "--trust-remote-code",
            "--host", "0.0.0.0",
            "--port", "8000",
        ],
    }
    return checked_json(api_request("POST", f"{RUNPOD_REST}/pods", key, payload=payload), "create pod")


def delete_pod(key: str, pod_id: str | None) -> dict[str, Any]:
    if not pod_id:
        return {"skipped": True}
    response = api_request("DELETE", f"{RUNPOD_REST}/pods/{pod_id}", key)
    return {"pod_id": pod_id, "http_status": response.status_code, "body": response.text[:500]}


def launch_watchdog(pod_id: str, key: str, cancel_path: Path, log_path: Path, timeout_s: int) -> int:
    if cancel_path.exists():
        cancel_path.unlink()
    code = r'''
import os, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path
pod, timeout_s, cancel_raw, log_raw = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
cancel, log_path = Path(cancel_raw), Path(log_raw)
def log(msg):
    with log_path.open("a", encoding="utf-8") as h:
        h.write(f"{datetime.now(timezone.utc).isoformat()} {msg}\n")
log(f"started pod={pod} timeout={timeout_s}")
deadline=time.monotonic()+timeout_s
while time.monotonic()<deadline:
    if cancel.exists():
        log("cancelled_after_driver_cleanup"); raise SystemExit(0)
    time.sleep(15)
req=urllib.request.Request(
    f"https://rest.runpod.io/v1/pods/{pod}", method="DELETE",
    headers={"Authorization":"Bearer "+os.environ["RUNPOD_API_KEY"]})
try:
    with urllib.request.urlopen(req, timeout=120) as r: log(f"deleted status={r.status}")
except Exception as exc: log(f"delete_error={type(exc).__name__}:{exc}")
'''
    process = subprocess.Popen(
        [sys.executable, "-c", code, pod_id, str(timeout_s), str(cancel_path), str(log_path)],
        env={"RUNPOD_API_KEY": key, "PATH": os.environ.get("PATH", "")},
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return int(process.pid)


def wait_for_model(base_url: str, key: str, timeout_s: int) -> tuple[list[str], float]:
    started = time.monotonic()
    last = ""
    while time.monotonic() - started < timeout_s:
        try:
            response = api_request("GET", f"{base_url}/models", key, timeout=180)
            if response.ok:
                models = [str(item.get("id")) for item in response.json().get("data", [])]
                if SERVED_MODEL in models:
                    return models, time.monotonic() - started
            last = f"HTTP {response.status_code}: {response.text[:300]}"
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"
        time.sleep(20)
    raise TimeoutError(f"model readiness exceeded {timeout_s}s; last={last}")


def usage_payload(body: dict[str, Any]) -> dict[str, Any]:
    return dict(body.get("usage") or {})


def chat_call(
    base_url: str,
    key: str,
    messages: list[dict[str, str]],
    purpose: str,
    max_tokens: int,
) -> dict[str, Any]:
    request_body = {
        "model": SERVED_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": GENERATION["temperature"],
        "top_p": GENERATION["top_p"],
        "seed": GENERATION["seed"],
        "presence_penalty": GENERATION["presence_penalty"],
        "chat_template_kwargs": {"enable_thinking": GENERATION["enable_thinking"]},
        "extra_body": {"top_k": GENERATION["top_k"]},
    }
    # vLLM accepts top_k at the request top-level, unlike the OpenAI SDK.
    request_body["top_k"] = request_body.pop("extra_body")["top_k"]
    started = time.monotonic()
    response = api_request(
        "POST", f"{base_url}/chat/completions", key,
        payload=request_body, timeout=900,
    )
    body = checked_json(response, purpose)
    content = str(body["choices"][0]["message"].get("content") or "")
    return {
        "purpose": purpose,
        "request": request_body,
        "request_sha256": sha256_text(json.dumps(request_body, sort_keys=True, ensure_ascii=False)),
        "response": content,
        "response_sha256": sha256_text(content),
        "usage": usage_payload(body),
        "provider_response_id": body.get("id"),
        "latency_seconds": time.monotonic() - started,
    }


def readiness_probe(base_url: str, key: str) -> dict[str, Any]:
    return chat_call(
        base_url, key,
        [{"role": "user", "content": "Return exactly READY."}],
        "endpoint_readiness_probe", 32,
    )


def rlm_sampling(max_tokens: int) -> dict[str, Any]:
    return {
        "max_completion_tokens": max_tokens,
        "temperature": GENERATION["temperature"],
        "top_p": GENERATION["top_p"],
        "presence_penalty": GENERATION["presence_penalty"],
        "seed": GENERATION["seed"],
        "extra_body": {
            "top_k": GENERATION["top_k"],
            "chat_template_kwargs": {"enable_thinking": GENERATION["enable_thinking"]},
        },
    }


def bound_trace_value(value: Any, max_chars: int = 20_000) -> Any:
    """Bound reconstructable REPL stdout without discarding its audit hash."""
    if isinstance(value, str):
        if len(value) <= max_chars:
            return value
        half = max_chars // 2
        return {
            "storage": "head_tail_bounded",
            "original_chars": len(value),
            "sha256": sha256_text(value),
            "head": value[:half],
            "tail": value[-half:],
        }
    if isinstance(value, list):
        return [bound_trace_value(item, max_chars) for item in value]
    if isinstance(value, dict):
        return {str(key): bound_trace_value(item, max_chars) for key, item in value.items()}
    return value


def alarm_handler(_signum: int, _frame: Any) -> None:
    raise RowTimeout("row timeout")


def run_rlm(base_url: str, key: str, context: str, question: str, timeout_s: int) -> dict[str, Any]:
    root_prompt = (
        "The REPL context contains exactly 1,000 documents. Answer the research question by "
        "inspecting and searching that context with Python. Combine clues across documents when "
        "needed; use llm_query for local semantic interpretation when useful. Return only a concise "
        f"final answer.\n\nQuestion: {question}"
    )
    logger = RLMLogger()
    result = None
    error = ""
    started = time.monotonic()
    previous = signal.signal(signal.SIGALRM, alarm_handler)
    signal.alarm(timeout_s)
    try:
        policy = RLM(
            backend="openai",
            backend_kwargs={
                "base_url": base_url,
                "model_name": SERVED_MODEL,
                "api_key": key,
                "timeout": 600.0,
                "max_retries": 0,
            },
            environment="local",
            max_iterations=20,
            max_depth=1,
            max_timeout=float(timeout_s - 30),
            max_errors=4,
            sampling_args=rlm_sampling(8192),
            sub_sampling_args=rlm_sampling(4096),
            logger=logger,
        )
        result = policy.completion(prompt=context, root_prompt=root_prompt)
    except BaseException as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)
    metadata = result.metadata if result is not None else logger.get_trajectory()
    usage = result.usage_summary.to_dict() if result is not None and result.usage_summary else None
    return {
        "ok": bool(result is not None and not error),
        "error": error,
        "response": result.response if result is not None else "",
        "latency_seconds": time.monotonic() - started,
        "root_prompt": root_prompt,
        "root_prompt_sha256": sha256_text(root_prompt),
        "context_sha256": sha256_text(context),
        "context_chars": len(context),
        "usage_summary": usage,
        "trace": bound_trace_value(sanitize_rlm_metadata(metadata)),
        "generation": GENERATION,
    }


def clip_doc(doc: dict[str, str], max_chars: int) -> dict[str, str]:
    """Deterministically preserve both ends of a long document."""
    text = doc["text"]
    if len(text) <= max_chars:
        return dict(doc)
    head = max_chars // 2
    tail = max_chars - head
    clipped = (
        text[:head]
        + f"\n\n[... {len(text) - max_chars} characters clipped deterministically ...]\n\n"
        + text[-tail:]
    )
    return {"docid": doc["docid"], "text": clipped}


def fit_bm25_docs(docs: list[dict[str, str]], ranking: list[int]) -> list[dict[str, str]]:
    chosen: list[dict[str, str]] = []
    total = 0
    for idx in ranking:
        candidate = clip_doc(docs[idx], 80_000)
        if chosen and total + len(candidate["text"]) > 220_000:
            continue
        chosen.append(candidate)
        total += len(candidate["text"])
        if len(chosen) >= 12:
            break
    return chosen


def run_bm25(base_url: str, key: str, question: str, docs: list[dict[str, str]]) -> dict[str, Any]:
    started = time.monotonic()
    ranking = bm25_rank_multi(docs, [question])[0]
    selected = fit_bm25_docs(docs, ranking)
    call = chat_call(base_url, key, answer_prompt(question, selected), "bm25_qwen36_answer", 4096)
    return {
        "ok": True,
        "error": "",
        "response": call["response"],
        "latency_seconds": time.monotonic() - started,
        "retrieved_doc_ids": [doc["docid"] for doc in selected],
        "retrieved_chars": sum(len(doc["text"]) for doc in selected),
        "calls": [call],
    }


def run_text_decompose(base_url: str, key: str, question: str, docs: list[dict[str, str]]) -> dict[str, Any]:
    started = time.monotonic()
    calls: list[dict[str, Any]] = []
    planner_messages = [
        {"role": "system", "content": "Plan lexical retrieval over a fixed offline corpus. Return JSON only as {\"queries\": [up to four short searches]}. Include rare phrases, names, dates, or intermediate entities that could expose different hops. Do not answer."},
        {"role": "user", "content": question},
    ]
    planner = chat_call(base_url, key, planner_messages, "text_decompose_planner", 1024)
    calls.append(planner)
    queries = parse_planner_queries(planner["response"], question)
    rankings = bm25_rank_multi(docs, queries)
    indices: list[int] = []
    for depth in range(8):
        for ranking in rankings:
            idx = ranking[depth]
            if idx not in indices:
                indices.append(idx)
            if len(indices) >= 20:
                break
        if len(indices) >= 20:
            break
    candidates = [docs[idx] for idx in indices]
    notes: list[str] = []
    for offset in range(0, len(candidates), 4):
        raw_batch = candidates[offset:offset + 4]
        batch = [clip_doc(doc, 50_000) for doc in raw_batch]
        worker_messages = [
            {"role": "system", "content": "Extract only evidence useful for the question from this document batch. Preserve document IDs, intermediate entities, and contradictions. Do not guess the final answer."},
            {"role": "user", "content": f"Question: {question}\n\nDocuments:\n{format_context(batch)}"},
        ]
        worker = chat_call(base_url, key, worker_messages, f"text_decompose_worker_{offset // 4 + 1}", 2048)
        calls.append(worker)
        notes.append(worker["response"])
    final_messages = [
        {"role": "system", "content": "Answer from the evidence notes, combining multiple hops where required. Return only the concise final answer."},
        {"role": "user", "content": f"Question: {question}\n\nEvidence notes:\n" + "\n\n".join(notes)},
    ]
    final = chat_call(base_url, key, final_messages, "text_decompose_finalizer", 4096)
    calls.append(final)
    return {
        "ok": True,
        "error": "",
        "response": final["response"],
        "latency_seconds": time.monotonic() - started,
        "planner_queries": queries,
        "retrieved_doc_ids": [doc["docid"] for doc in candidates],
        "calls": calls,
    }


def existing_keys(path: Path) -> set[tuple[int, str]]:
    if not path.exists():
        return set()
    out: set[tuple[int, str]] = set()
    opener = gzip.open(path, "rt", encoding="utf-8") if path.suffix == ".gz" else path.open("r", encoding="utf-8")
    with opener as handle:
        lines = handle
        for line in lines:
            if line.strip():
                row = json.loads(line)
                out.add((int(row["rank"]), str(row["method"])))
    return out


def main() -> None:
    load_env()
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-rank", type=int, default=1)
    parser.add_argument("--end-rank", type=int, default=12)
    parser.add_argument("--methods", nargs="+", choices=METHODS, default=list(METHODS))
    parser.add_argument("--row-timeout-seconds", type=int, default=1200)
    parser.add_argument("--endpoint-wait-seconds", type=int, default=2400)
    parser.add_argument("--watchdog-seconds", type=int, default=43200)
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()
    if not (1 <= args.start_rank <= args.end_rank <= 59):
        raise SystemExit("Ranks must satisfy 1 <= start <= end <= 59")
    key, hf_token = os.environ.get("RUNPOD_API_KEY", ""), os.environ.get("HF_TOKEN", "")
    if not key or not hf_token:
        raise SystemExit("RUNPOD_API_KEY and HF_TOKEN are required")
    if sha256_file(MANIFEST_PATH) != MANIFEST_SHA256:
        raise SystemExit("Frozen manifest hash mismatch")
    commit = subprocess.check_output(
        ["git", "-C", str(ROOT / "external_repos/rlm-official"), "rev-parse", "HEAD"], text=True
    ).strip()
    if commit != OFFICIAL_RLM_COMMIT:
        raise SystemExit(f"Official RLM commit mismatch: {commit}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_id = args.run_id or f"bcp_repl_qwen36_r{args.start_rank}_{args.end_rank}_{stamp}"
    output = RESULT_DIR / f"{run_id}_restricted.jsonl.gz"
    summary_path = RESULT_DIR / f"{run_id}_summary.json"
    watchdog_cancel = RESULT_DIR / f"{run_id}_watchdog.cancel"
    watchdog_log = RESULT_DIR / f"{run_id}_watchdog.log"
    if output.exists():
        raise FileExistsError(output)

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    selected = [r for r in manifest["rows"] if args.start_rank <= int(r["rank"]) <= args.end_rank]
    query_ids = {str(r["query_id"]) for r in selected}
    doc_ids = {str(d) for r in selected for d in r["document_ids_in_order"]}
    print(f"loading frozen ranks {args.start_rank}-{args.end_rank}; correctness suppressed", flush=True)
    queries = load_selected_queries(query_ids)
    corpus = load_needed_corpus(doc_ids)

    before_pods = list_pods(key)
    pod_id: str | None = None
    watchdog_pid: int | None = None
    created_monotonic: float | None = None
    events: dict[str, Any] = {
        "study_id": STUDY_ID,
        "run_id": run_id,
        "created_utc": utc_now(),
        "model_repo": MODEL_REPO,
        "model_revision": MODEL_REVISION,
        "served_model": SERVED_MODEL,
        "vllm_image": VLLM_IMAGE,
        "official_rlm_commit": commit,
        "manifest_sha256": MANIFEST_SHA256,
        "runner_sha256": sha256_file(Path(__file__)),
        "ranks": [args.start_rank, args.end_rank],
        "methods": args.methods,
        "generation": GENERATION,
        "preexisting_pods": [{"id": p.get("id"), "name": p.get("name")} for p in before_pods],
        "events": [],
        "completed": 0,
        "errors": 0,
        "run_incomplete": True,
    }
    try:
        pod = create_pod(key, hf_token, stamp)
        created_monotonic = time.monotonic()
        pod_id = str(pod["id"])
        base_url = f"https://{pod_id}-8000.proxy.runpod.net/v1"
        events["pod"] = {
            "id": pod_id,
            "name": pod.get("name"),
            "cost_per_hr": pod.get("costPerHr"),
            "gpu_count": pod.get("gpuCount"),
            "raw_creation_response_redacted": {k: v for k, v in pod.items() if k not in {"env"}},
        }
        events["events"].append({"event": "pod_created", "at": utc_now()})
        watchdog_pid = launch_watchdog(pod_id, key, watchdog_cancel, watchdog_log, args.watchdog_seconds)
        events["watchdog"] = {"pid": watchdog_pid, "timeout_s": args.watchdog_seconds}
        write_json(summary_path, events)

        models, wait_s = wait_for_model(base_url, key, args.endpoint_wait_seconds)
        events["models"] = models
        events["model_wait_seconds"] = wait_s
        events["events"].append({"event": "model_ready", "at": utc_now(), "wait_seconds": wait_s})
        probe = readiness_probe(base_url, key)
        events["readiness_probe"] = probe
        events["events"].append({"event": "probe_complete", "at": utc_now()})
        write_json(summary_path, events)

        done = existing_keys(output)
        consecutive_errors = 0
        for row in selected:
            rank, qid = int(row["rank"]), str(row["query_id"])
            question, answer = queries[qid]["query"], queries[qid]["answer"]
            docs = [{"docid": did, "text": corpus[did]} for did in row["document_ids_in_order"]]
            context: str | None = None
            for method in args.methods:
                if (rank, method) in done:
                    continue
                item_started = time.monotonic()
                try:
                    if method == "standard_rlm_qwen36":
                        context = context if context is not None else format_context(docs)
                        result = run_rlm(base_url, key, context, question, args.row_timeout_seconds)
                    elif method == "bm25_qwen36":
                        result = run_bm25(base_url, key, question, docs)
                    else:
                        result = run_text_decompose(base_url, key, question, docs)
                except BaseException as exc:
                    result = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "response": ""}
                record = {
                    "study_id": STUDY_ID,
                    "run_id": run_id,
                    "created_utc": utc_now(),
                    "rank": rank,
                    "query_id": qid,
                    "query_id_hash": row["query_id_hash"],
                    "query": question,
                    "answer": answer,
                    "query_sha256": sha256_text(question),
                    "answer_sha256": sha256_text(answer),
                    "document_pool_hash": row["document_pool_hash"],
                    "document_count": row["document_count"],
                    "context_chars_manifest": row["context_chars"],
                    "method": method,
                    "result": result,
                    "wall_seconds": time.monotonic() - item_started,
                    "manifest_sha256": MANIFEST_SHA256,
                    "runner_sha256": events["runner_sha256"],
                    "model_repo": MODEL_REPO,
                    "model_revision": MODEL_REVISION,
                }
                append_jsonl(output, record)
                ok = bool(result.get("ok"))
                events["completed"] += int(ok)
                events["errors"] += int(not ok)
                consecutive_errors = 0 if ok else consecutive_errors + 1
                events["events"].append({"event": "method_finished", "at": utc_now(), "rank": rank, "method": method, "ok": ok})
                write_json(summary_path, events)
                print(f"rank={rank} method={method} ok={ok} completed={events['completed']} errors={events['errors']}", flush=True)
                if consecutive_errors >= 3:
                    raise RuntimeError("stability stop: three consecutive method errors")
    except BaseException as exc:
        events["fatal_error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        events["cleanup"] = delete_pod(key, pod_id)
        if watchdog_pid is not None:
            watchdog_cancel.write_text(utc_now() + " driver cleanup complete\n", encoding="utf-8")
        events["finished_utc"] = utc_now()
        events["creation_to_cleanup_seconds"] = time.monotonic() - created_monotonic if created_monotonic else 0.0
        listed = ((events.get("pod") or {}).get("cost_per_hr") or 0.0)
        events["listed_rate_cost_estimate_usd"] = float(listed) * events["creation_to_cleanup_seconds"] / 3600
        events["remaining_project_pods"] = [
            {"id": p.get("id"), "name": p.get("name")} for p in list_pods(key)
            if str(p.get("id")) == str(pod_id)
        ]
        expected_cells = len(selected) * len(args.methods)
        events["run_incomplete"] = events["completed"] + events["errors"] != expected_cells
        events["output"] = str(output.relative_to(ROOT)) if output.exists() else None
        events["output_sha256"] = sha256_file(output) if output.exists() else None
        write_json(summary_path, events)
    print(json.dumps({k: events[k] for k in ("run_id", "completed", "errors", "creation_to_cleanup_seconds", "listed_rate_cost_estimate_usd")}, indent=2))


if __name__ == "__main__":
    main()
