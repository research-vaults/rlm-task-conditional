#!/usr/bin/env python3
"""Run the locked BrowseComp+ N=49 RLM no-subcall ablation on RunPod.

The route retains the pinned released RLM root loop and local REPL while
fail-closing every submodel-call function. Generation remains accuracy-blind.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import multiprocessing as mp
import os
import re
import subprocess
import sys
import tempfile
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
import rlm.core.rlm as rlm_core  # noqa: E402
from rlm.environments.local_repl import LocalREPL  # noqa: E402
from rlm.logger import RLMLogger  # noqa: E402


STUDY_ID = "browsecomp_plus_n49_rlm_no_subcall_ablation_v1"
MODEL_REPO = "Qwen/Qwen3.6-35B-A3B-FP8"
MODEL_REVISION = "95a723d08a9490559dae23d0cff1d9466213d989"
SERVED_MODEL = "qwen36-35b-a3b-fp8"
VLLM_IMAGE = "vllm/vllm-openai@sha256:e4f88a835143cd22aee2397a26ec6bb80b3a4a6fe0c882bcbc63822904766089"
OFFICIAL_RLM_COMMIT = "72d6940142ddfb84ee6be573dc999a37e633e671"
MANIFEST_PATH = ROOT / "results/browsecomp_plus_positive_regime_replication/manifest_n59_restricted.json"
MANIFEST_SHA256 = "3aa19bb692f37d567a8983396ae950a11aca5b6ba5664e9b2c05160a0df6fea2"
RUNPOD_REST = "https://rest.runpod.io/v1"
METHODS = ("rlm_no_subcall_qwen36",)
RESULT_DIR = ROOT / "results/browsecomp_plus_positive_regime_replication/no_subcall_ablation"
PROTOCOL_PATH = ROOT / "protocols/BROWSECOMP_PLUS_N49_RLM_NO_SUBCALL_ABLATION_20260722.md"
PROTOCOL_SHA256 = "f7aeafc93f785703c41a511cf1ff59a32ebb6f1d2174be27f05ac7d7f760cc81"

GENERATION = {
    "temperature": 0.7,
    "top_p": 0.8,
    "top_k": 20,
    "presence_penalty": 1.5,
    "seed": 20,
    "enable_thinking": False,
}


NO_SUBCALL_SYSTEM_PROMPT = """You are a programmatic long-context reasoner. The important context is stored in a persistent Python REPL.

Use one ```repl``` block per turn to inspect and search `context` with Python. The REPL also provides `SHOW_VARS()` and an `answer` dict initialized as {{"content": "", "ready": False}}. Submodel calls are unavailable in this ablation: do not call `llm_query`, `llm_query_batched`, `rlm_query`, or `rlm_query_batched`. Use deterministic Python string, regex, indexing, counting, sorting, and aggregation operations to narrow evidence. Print only bounded evidence needed for the next decision.

When the evidence is sufficient, set `answer["content"]` to the concise final answer and `answer["ready"] = True` in a ```repl``` block. Inspect the context before finalizing. If the turn budget is nearly exhausted, submit the best evidence-grounded answer you have.
{custom_tools_section}
"""


class NoSubcallLocalREPL(LocalREPL):
    """Released local REPL with all model-call tools replaced fail-closed."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.disabled_calls: list[dict[str, Any]] = []
        super().__init__(*args, **kwargs)

    def _disabled_tool(self, name: str):
        def disabled(*args: Any, **kwargs: Any) -> str:
            prompt = args[0] if args else kwargs.get("prompt", kwargs.get("prompts", ""))
            self.disabled_calls.append(
                {
                    "tool": name,
                    "prompt_sha256": sha256_text(json.dumps(prompt, sort_keys=True, ensure_ascii=False)),
                    "prompt_chars": len(str(prompt)),
                }
            )
            if name.endswith("batched") and isinstance(prompt, list):
                return ["Error: submodel calls are disabled in this ablation"] * len(prompt)
            return "Error: submodel calls are disabled in this ablation"
        return disabled

    def _bind_disabled_tools(self) -> None:
        for name in ("llm_query", "llm_query_batched", "rlm_query", "rlm_query_batched"):
            self.globals[name] = self._disabled_tool(name)

    def setup(self) -> None:
        super().setup()
        self._bind_disabled_tools()

    def _restore_scaffold(self) -> None:
        super()._restore_scaffold()
        self._bind_disabled_tools()


_CREATED_ENVIRONMENTS: list[NoSubcallLocalREPL] = []


def no_subcall_environment(environment_type: str, environment_kwargs: dict[str, Any]):
    if environment_type != "local":
        raise RuntimeError(f"No-subcall ablation requires local REPL, got {environment_type}")
    environment = NoSubcallLocalREPL(**environment_kwargs)
    for name in ("llm_query", "llm_query_batched", "rlm_query", "rlm_query_batched"):
        probe = environment.globals[name]
        if getattr(probe, "__name__", "") != "disabled":
            raise RuntimeError(f"Fail-closed binding missing for {name}")
    _CREATED_ENVIRONMENTS.append(environment)
    return environment


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
        "name": f"rlm-audit-bcp-nosubcall-qwen36-{stamp}",
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


def run_rlm_inner(base_url: str, key: str, context: str, question: str, timeout_s: int) -> dict[str, Any]:
    root_prompt = (
        "The REPL context contains exactly 1,000 documents. Answer the research question by "
        "inspecting and searching that context with Python. Combine clues across documents when "
        "needed. Submodel calls are disabled; use only the persistent Python REPL. Return only a concise "
        f"final answer.\n\nQuestion: {question}"
    )
    logger = RLMLogger()
    result = None
    error = ""
    started = time.monotonic()
    original_get_environment = rlm_core.get_environment
    _CREATED_ENVIRONMENTS.clear()
    try:
        rlm_core.get_environment = no_subcall_environment
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
            custom_system_prompt=NO_SUBCALL_SYSTEM_PROMPT,
            orchestrator=False,
            logger=logger,
        )
        result = policy.completion(prompt=context, root_prompt=root_prompt)
    except BaseException as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        rlm_core.get_environment = original_get_environment
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
        "disabled_subcall_attempts": [
            call for environment in _CREATED_ENVIRONMENTS for call in environment.disabled_calls
        ],
        "intervention": {
            "released_root_loop": True,
            "released_local_repl": True,
            "submodel_calls": "fail_closed",
            "max_iterations": 20,
            "row_timeout_seconds": timeout_s,
        },
        "generation": GENERATION,
    }


def run_rlm_worker(output_path: str, base_url: str, key: str, context: str, question: str, timeout_s: int) -> None:
    """Execute one row in a child process and publish only a complete JSON result."""
    payload = run_rlm_inner(base_url, key, context, question, timeout_s)
    target = Path(output_path)
    temporary = target.with_suffix(target.suffix + ".writing")
    temporary.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=True), encoding="utf-8")
    temporary.replace(target)


def run_rlm(base_url: str, key: str, context: str, question: str, timeout_s: int) -> dict[str, Any]:
    """Enforce the declared cap outside the scaffold's socket/thread stack."""
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    descriptor, output_path = tempfile.mkstemp(prefix="no_subcall_row_", suffix=".json", dir=RESULT_DIR)
    os.close(descriptor)
    Path(output_path).unlink()
    process = mp.get_context("fork").Process(
        target=run_rlm_worker,
        args=(output_path, base_url, key, context, question, timeout_s),
        daemon=False,
    )
    started = time.monotonic()
    process.start()
    process.join(timeout_s)
    timed_out = process.is_alive()
    if timed_out:
        process.terminate()
        process.join(10)
        if process.is_alive():
            process.kill()
            process.join(10)
    target = Path(output_path)
    try:
        if timed_out:
            return {
                "ok": False,
                "error": f"RowTimeout: parent-enforced cap of {timeout_s}s",
                "response": "",
                "latency_seconds": time.monotonic() - started,
                "disabled_subcall_attempts": [],
                "intervention": {
                    "released_root_loop": True,
                    "released_local_repl": True,
                    "submodel_calls": "fail_closed",
                    "parent_enforced_timeout_seconds": timeout_s,
                },
                "generation": GENERATION,
            }
        if process.exitcode != 0:
            return {
                "ok": False,
                "error": f"ChildProcessError: exit code {process.exitcode}",
                "response": "",
                "latency_seconds": time.monotonic() - started,
                "disabled_subcall_attempts": [],
                "generation": GENERATION,
            }
        if not target.exists() or not target.stat().st_size:
            return {
                "ok": False,
                "error": "ChildProcessError: no complete result file",
                "response": "",
                "latency_seconds": time.monotonic() - started,
                "disabled_subcall_attempts": [],
                "generation": GENERATION,
            }
        result = json.loads(target.read_text(encoding="utf-8"))
        result["parent_enforced_wall_seconds"] = time.monotonic() - started
        return result
    finally:
        target.unlink(missing_ok=True)
        target.with_suffix(target.suffix + ".writing").unlink(missing_ok=True)


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
    parser.add_argument("--end-rank", type=int, default=49)
    parser.add_argument("--methods", nargs="+", choices=METHODS, default=list(METHODS))
    parser.add_argument("--row-timeout-seconds", type=int, default=1200)
    parser.add_argument("--endpoint-wait-seconds", type=int, default=2400)
    parser.add_argument("--watchdog-seconds", type=int, default=43200)
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()
    if not (1 <= args.start_rank <= args.end_rank <= 49):
        raise SystemExit("Ranks must satisfy 1 <= start <= end <= 49")
    key, hf_token = os.environ.get("RUNPOD_API_KEY", ""), os.environ.get("HF_TOKEN", "")
    if not key or not hf_token:
        raise SystemExit("RUNPOD_API_KEY and HF_TOKEN are required")
    if sha256_file(MANIFEST_PATH) != MANIFEST_SHA256:
        raise SystemExit("Frozen manifest hash mismatch")
    if sha256_file(PROTOCOL_PATH) != PROTOCOL_SHA256:
        raise SystemExit("Frozen no-subcall protocol hash mismatch")
    commit = subprocess.check_output(
        ["git", "-C", str(ROOT / "external_repos/rlm-official"), "rev-parse", "HEAD"], text=True
    ).strip()
    if commit != OFFICIAL_RLM_COMMIT:
        raise SystemExit(f"Official RLM commit mismatch: {commit}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_id = args.run_id or f"bcp_n49_rlm_no_subcall_qwen36_r{args.start_rank}_{args.end_rank}_{stamp}"
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
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
        "protocol": str(PROTOCOL_PATH.relative_to(ROOT)),
        "protocol_sha256": PROTOCOL_SHA256,
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
                    if method == "rlm_no_subcall_qwen36":
                        context = context if context is not None else format_context(docs)
                        result = run_rlm(base_url, key, context, question, args.row_timeout_seconds)
                    else:
                        raise RuntimeError(f"Unknown method: {method}")
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
