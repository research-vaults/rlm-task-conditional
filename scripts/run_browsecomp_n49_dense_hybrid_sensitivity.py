#!/usr/bin/env python3
"""Run the locked post-hoc BrowseComp N=49 learned-retrieval sensitivity."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from run_browsecomp_plus_qwen36_replication_runpod import (
    GENERATION,
    MANIFEST_PATH,
    MANIFEST_SHA256,
    MODEL_REPO,
    MODEL_REVISION,
    SERVED_MODEL,
    VLLM_IMAGE,
    answer_prompt,
    append_jsonl,
    bm25_rank_multi,
    chat_call,
    clip_doc,
    create_pod,
    delete_pod,
    existing_keys,
    fit_bm25_docs,
    launch_watchdog,
    list_pods,
    load_env,
    load_needed_corpus,
    load_selected_queries,
    readiness_probe,
    run_bm25,
    sha256_file,
    sha256_text,
    utc_now,
    wait_for_model,
    write_json,
)


ROOT = Path(__file__).resolve().parents[1]
RESULT_DIR = ROOT / "results/browsecomp_plus_positive_regime_replication/dense_hybrid_sensitivity"
PROTOCOL = ROOT / "protocols/BROWSECOMP_PLUS_N49_DENSE_HYBRID_SENSITIVITY_20260721.md"
PROTOCOL_SHA256 = "c7464339696a8c167b7a78229994c8ade931efb6b05eb0de9cad9b71095d91ea"
STUDY_ID = "browsecomp_plus_n49_dense_hybrid_sensitivity_v1"
EMBED_MODEL = "qwen/qwen3-embedding-8b"
EMBED_CONTEXT = 32_000
EMBED_DOC_CHARS = 12_000
BM25_CANDIDATES = 64
EMBED_BATCH = 16
METHODS = ("dense_hybrid_qwen3emb8b_qwen36", "bm25_replay_qwen36")
QUERY_INSTRUCTION = (
    "Given a web research question, retrieve documents that contain evidence needed to answer it."
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def restricted_mode(path: Path) -> None:
    path.chmod(0o600)


def load_jsonl_gz(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def openrouter_snapshot(key: str) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {key}"}
    auth = requests.get("https://openrouter.ai/api/v1/auth/key", headers=headers, timeout=60)
    credits = requests.get("https://openrouter.ai/api/v1/credits", headers=headers, timeout=60)
    auth.raise_for_status()
    credits.raise_for_status()
    a = auth.json().get("data", {})
    c = credits.json().get("data", {})
    return {
        "captured_utc": utc_now(),
        "usage": a.get("usage"),
        "usage_daily": a.get("usage_daily"),
        "usage_monthly": a.get("usage_monthly"),
        "total_credits": c.get("total_credits"),
        "total_usage": c.get("total_usage"),
    }


def embedding_catalog_row(key: str) -> dict[str, Any]:
    response = requests.get(
        "https://openrouter.ai/api/v1/embeddings/models",
        headers={"Authorization": f"Bearer {key}"},
        timeout=60,
    )
    response.raise_for_status()
    for row in response.json().get("data", []):
        if row.get("id") == EMBED_MODEL:
            return {
                field: row.get(field)
                for field in ("id", "name", "canonical_slug", "context_length", "pricing")
            }
    raise RuntimeError(f"Embedding model absent from live catalog: {EMBED_MODEL}")


def clip_for_embedding(text: str) -> str:
    if len(text) <= EMBED_DOC_CHARS:
        return text
    half = EMBED_DOC_CHARS // 2
    omitted = len(text) - EMBED_DOC_CHARS
    return text[:half] + f"\n\n[... {omitted} characters clipped for retrieval ...]\n\n" + text[-half:]


def l2_normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if not norm:
        raise RuntimeError("Zero-norm embedding")
    return [value / norm for value in vector]


def embed_batch(key: str, inputs: list[str], purpose: str) -> tuple[list[list[float]], dict[str, Any]]:
    request_body = {
        "model": EMBED_MODEL,
        "input": inputs,
        "encoding_format": "float",
    }
    started = time.monotonic()
    response = requests.post(
        "https://openrouter.ai/api/v1/embeddings",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=request_body,
        timeout=900,
    )
    if not response.ok:
        raise RuntimeError(f"{purpose}: HTTP {response.status_code}: {response.text[:1000]}")
    body = response.json()
    rows = sorted(body.get("data", []), key=lambda row: int(row.get("index", 0)))
    if len(rows) != len(inputs):
        raise RuntimeError(f"{purpose}: expected {len(inputs)} vectors, got {len(rows)}")
    vectors = [l2_normalize([float(value) for value in row["embedding"]]) for row in rows]
    dimensions = {len(vector) for vector in vectors}
    if len(dimensions) != 1:
        raise RuntimeError(f"{purpose}: inconsistent dimensions {dimensions}")
    audit = {
        "purpose": purpose,
        "input_count": len(inputs),
        "input_sha256": [sha256_text(value) for value in inputs],
        "input_chars": [len(value) for value in inputs],
        "request_sha256": sha256_text(json.dumps(request_body, sort_keys=True, ensure_ascii=False)),
        "provider_response_id": body.get("id"),
        "usage": body.get("usage") or {},
        "latency_seconds": time.monotonic() - started,
        "dimensions": list(dimensions)[0],
    }
    return vectors, audit


def build_dense_plan(
    key: str,
    rank: int,
    question: str,
    docs: list[dict[str, str]],
) -> dict[str, Any]:
    lexical_ranking = bm25_rank_multi(docs, [question])[0][:BM25_CANDIDATES]
    candidates = [docs[index] for index in lexical_ranking]
    query_text = f"Instruct: {QUERY_INSTRUCTION}\nQuery: {question}"
    query_vectors, query_audit = embed_batch(key, [query_text], f"rank_{rank}_query")
    doc_inputs = [clip_for_embedding(doc["text"]) for doc in candidates]
    document_vectors: list[list[float]] = []
    request_audits: list[dict[str, Any]] = [query_audit]
    for offset in range(0, len(doc_inputs), EMBED_BATCH):
        vectors, audit = embed_batch(
            key,
            doc_inputs[offset:offset + EMBED_BATCH],
            f"rank_{rank}_documents_{offset}_{min(offset + EMBED_BATCH, len(doc_inputs)) - 1}",
        )
        document_vectors.extend(vectors)
        request_audits.append(audit)
    query_vector = query_vectors[0]
    scored = [
        {
            "docid": doc["docid"],
            "bm25_candidate_rank": position + 1,
            "cosine": sum(a * b for a, b in zip(query_vector, vector)),
            "embedding_text_sha256": sha256_text(doc_inputs[position]),
            "embedding_text_chars": len(doc_inputs[position]),
        }
        for position, (doc, vector) in enumerate(zip(candidates, document_vectors))
    ]
    scored.sort(key=lambda row: (-row["cosine"], row["bm25_candidate_rank"], row["docid"]))
    doc_index = {doc["docid"]: index for index, doc in enumerate(docs)}
    dense_ranking = [doc_index[row["docid"]] for row in scored]
    selected = fit_bm25_docs(docs, dense_ranking)
    return {
        "rank": rank,
        "retrieval_contract": {
            "embedding_model": EMBED_MODEL,
            "query_instruction": QUERY_INSTRUCTION,
            "bm25_candidates": BM25_CANDIDATES,
            "embedding_doc_chars": EMBED_DOC_CHARS,
            "embedding_batch": EMBED_BATCH,
            "similarity": "cosine_l2_normalized",
            "answer_context_fitter": "fit_bm25_docs: max 12 docs, 220000 chars total, 80000 chars/doc",
        },
        "candidate_scores": scored,
        "selected_doc_ids": [doc["docid"] for doc in selected],
        "selected_chars": sum(len(doc["text"]) for doc in selected),
        "embedding_requests": request_audits,
    }


def dense_answer(
    base_url: str,
    runpod_key: str,
    question: str,
    docs: list[dict[str, str]],
    plan: dict[str, Any],
) -> dict[str, Any]:
    by_id = {doc["docid"]: doc for doc in docs}
    selected = [clip_doc(by_id[docid], 80_000) for docid in plan["selected_doc_ids"]]
    started = time.monotonic()
    call = chat_call(
        base_url,
        runpod_key,
        answer_prompt(question, selected),
        "dense_hybrid_qwen3emb8b_qwen36_answer",
        4096,
    )
    return {
        "ok": True,
        "error": "",
        "response": call["response"],
        "latency_seconds": time.monotonic() - started,
        "retrieved_doc_ids": [doc["docid"] for doc in selected],
        "retrieved_chars": sum(len(doc["text"]) for doc in selected),
        "retrieval_plan_sha256": sha256_text(json.dumps(plan, sort_keys=True, ensure_ascii=False)),
        "calls": [call],
    }


def main() -> None:
    load_env()
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-rank", type=int, default=1)
    parser.add_argument("--end-rank", type=int, default=49)
    parser.add_argument("--methods", nargs="+", choices=METHODS, default=list(METHODS))
    parser.add_argument("--endpoint-wait-seconds", type=int, default=2400)
    parser.add_argument("--watchdog-seconds", type=int, default=21600)
    parser.add_argument("--run-id", default="bcp_n49_dense_hybrid_sensitivity_20260721")
    args = parser.parse_args()
    if not (1 <= args.start_rank <= args.end_rank <= 49):
        raise SystemExit("Ranks must satisfy 1 <= start <= end <= 49")

    runpod_key = os.environ.get("RUNPOD_API_KEY", "")
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
    hf_token = os.environ.get("HF_TOKEN", "")
    if not runpod_key or not openrouter_key or not hf_token:
        raise SystemExit("RUNPOD_API_KEY, OPENROUTER_API_KEY, and HF_TOKEN are required")
    if sha256_file(MANIFEST_PATH) != MANIFEST_SHA256:
        raise SystemExit("Frozen manifest hash mismatch")
    if sha256_file(PROTOCOL) != PROTOCOL_SHA256:
        raise SystemExit("Protocol hash mismatch")

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    output = RESULT_DIR / f"{args.run_id}_restricted.jsonl.gz"
    plan_path = RESULT_DIR / f"{args.run_id}_retrieval_plans_restricted.jsonl.gz"
    summary_path = RESULT_DIR / f"{args.run_id}_summary.json"
    watchdog_cancel = RESULT_DIR / f"{args.run_id}_watchdog.cancel"
    watchdog_log = RESULT_DIR / f"{args.run_id}_watchdog.log"
    runner_hash = sha256_file(Path(__file__))

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    selected_rows = [
        row for row in manifest["rows"]
        if args.start_rank <= int(row["rank"]) <= args.end_rank
    ]
    query_ids = {str(row["query_id"]) for row in selected_rows}
    doc_ids = {str(docid) for row in selected_rows for docid in row["document_ids_in_order"]}
    queries = load_selected_queries(query_ids)
    corpus = load_needed_corpus(doc_ids)

    events: dict[str, Any] = {
        "study_id": STUDY_ID,
        "run_id": args.run_id,
        "created_utc": utc_now(),
        "chronology": "post_hoc_sensitivity_after_n49_outputs_and_scores_visible",
        "confirmatory": False,
        "protocol": str(PROTOCOL.relative_to(ROOT)),
        "protocol_sha256": PROTOCOL_SHA256,
        "runner_sha256": runner_hash,
        "manifest_sha256": MANIFEST_SHA256,
        "ranks": [args.start_rank, args.end_rank],
        "methods": args.methods,
        "embedding_catalog": embedding_catalog_row(openrouter_key),
        "embedding_contract": {
            "model": EMBED_MODEL,
            "context_length": EMBED_CONTEXT,
            "bm25_candidates": BM25_CANDIDATES,
            "document_char_clip": EMBED_DOC_CHARS,
            "batch_size": EMBED_BATCH,
            "query_instruction": QUERY_INSTRUCTION,
        },
        "answer_model": {
            "repo": MODEL_REPO,
            "revision": MODEL_REVISION,
            "served_model": SERVED_MODEL,
            "image": VLLM_IMAGE,
            "generation": GENERATION,
        },
        "openrouter_before": openrouter_snapshot(openrouter_key),
        "preexisting_pods": [
            {"id": pod.get("id"), "name": pod.get("name")} for pod in list_pods(runpod_key)
        ],
        "planned_cells": len(selected_rows) * len(args.methods),
        "completed": 0,
        "errors": 0,
        "events": [],
    }
    write_json(summary_path, events)

    existing_plans = {int(row["rank"]): row for row in load_jsonl_gz(plan_path)}
    for row in selected_rows:
        rank = int(row["rank"])
        if rank in existing_plans:
            continue
        question = queries[str(row["query_id"])]["query"]
        docs = [{"docid": docid, "text": corpus[docid]} for docid in row["document_ids_in_order"]]
        plan = build_dense_plan(openrouter_key, rank, question, docs)
        plan.update({
            "study_id": STUDY_ID,
            "query_id": str(row["query_id"]),
            "query_sha256": sha256_text(question),
            "document_pool_hash": row["document_pool_hash"],
            "manifest_sha256": MANIFEST_SHA256,
            "protocol_sha256": PROTOCOL_SHA256,
            "runner_sha256": runner_hash,
            "created_utc": utc_now(),
        })
        append_jsonl(plan_path, plan)
        existing_plans[rank] = plan
        events["events"].append({"event": "retrieval_plan_complete", "rank": rank, "at": utc_now()})
        write_json(summary_path, events)
        print(f"retrieval rank={rank} complete", flush=True)

    events["openrouter_after_embeddings"] = openrouter_snapshot(openrouter_key)
    events["retrieval_plan_path"] = str(plan_path.relative_to(ROOT))
    events["retrieval_plan_sha256"] = sha256_file(plan_path)
    write_json(summary_path, events)

    pod_id: str | None = None
    watchdog_pid: int | None = None
    created_monotonic: float | None = None
    try:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        pod = create_pod(runpod_key, hf_token, stamp)
        created_monotonic = time.monotonic()
        pod_id = str(pod["id"])
        base_url = f"https://{pod_id}-8000.proxy.runpod.net/v1"
        events["pod"] = {
            "id": pod_id,
            "name": pod.get("name"),
            "cost_per_hr": pod.get("costPerHr"),
            "gpu_count": pod.get("gpuCount"),
            "raw_creation_response_redacted": {key: value for key, value in pod.items() if key != "env"},
        }
        events["events"].append({"event": "pod_created", "at": utc_now()})
        watchdog_pid = launch_watchdog(
            pod_id, runpod_key, watchdog_cancel, watchdog_log, args.watchdog_seconds
        )
        events["watchdog"] = {"pid": watchdog_pid, "timeout_s": args.watchdog_seconds}
        write_json(summary_path, events)
        models, wait_seconds = wait_for_model(base_url, runpod_key, args.endpoint_wait_seconds)
        events["models"] = models
        events["model_wait_seconds"] = wait_seconds
        events["readiness_probe"] = readiness_probe(base_url, runpod_key)
        events["events"].append({"event": "model_ready", "at": utc_now()})
        write_json(summary_path, events)

        done = existing_keys(output)
        consecutive_errors = 0
        for row in selected_rows:
            rank = int(row["rank"])
            qid = str(row["query_id"])
            question = queries[qid]["query"]
            answer = queries[qid]["answer"]
            docs = [{"docid": docid, "text": corpus[docid]} for docid in row["document_ids_in_order"]]
            for method in args.methods:
                if (rank, method) in done:
                    continue
                started = time.monotonic()
                try:
                    if method == "dense_hybrid_qwen3emb8b_qwen36":
                        result = dense_answer(
                            base_url, runpod_key, question, docs, existing_plans[rank]
                        )
                    else:
                        result = run_bm25(base_url, runpod_key, question, docs)
                except BaseException as exc:
                    result = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "response": ""}
                record = {
                    "study_id": STUDY_ID,
                    "run_id": args.run_id,
                    "created_utc": utc_now(),
                    "chronology": events["chronology"],
                    "confirmatory": False,
                    "rank": rank,
                    "query_id": qid,
                    "query_id_hash": row["query_id_hash"],
                    "query": question,
                    "answer": answer,
                    "query_sha256": sha256_text(question),
                    "answer_sha256": sha256_text(answer),
                    "document_pool_hash": row["document_pool_hash"],
                    "document_count": row["document_count"],
                    "method": method,
                    "result": result,
                    "wall_seconds": time.monotonic() - started,
                    "manifest_sha256": MANIFEST_SHA256,
                    "protocol_sha256": PROTOCOL_SHA256,
                    "runner_sha256": runner_hash,
                    "model_repo": MODEL_REPO,
                    "model_revision": MODEL_REVISION,
                }
                append_jsonl(output, record)
                ok = bool(result.get("ok"))
                events["completed"] += int(ok)
                events["errors"] += int(not ok)
                consecutive_errors = 0 if ok else consecutive_errors + 1
                events["events"].append({
                    "event": "method_finished",
                    "at": utc_now(),
                    "rank": rank,
                    "method": method,
                    "ok": ok,
                })
                write_json(summary_path, events)
                print(f"rank={rank} method={method} ok={ok}", flush=True)
                if consecutive_errors >= 3:
                    raise RuntimeError("stability stop: three consecutive method errors")
    except BaseException as exc:
        events["fatal_error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        events["cleanup"] = delete_pod(runpod_key, pod_id)
        if watchdog_pid is not None:
            watchdog_cancel.write_text(utc_now() + " driver cleanup complete\n", encoding="utf-8")
        events["finished_utc"] = utc_now()
        events["creation_to_cleanup_seconds"] = (
            time.monotonic() - created_monotonic if created_monotonic else 0.0
        )
        listed = float((events.get("pod") or {}).get("cost_per_hr") or 0.0)
        events["listed_rate_cost_estimate_usd"] = (
            listed * events["creation_to_cleanup_seconds"] / 3600
        )
        events["remaining_created_pod"] = [
            {"id": pod.get("id"), "name": pod.get("name")}
            for pod in list_pods(runpod_key)
            if str(pod.get("id")) == str(pod_id)
        ]
        events["openrouter_after"] = openrouter_snapshot(openrouter_key)
        events["output"] = str(output.relative_to(ROOT)) if output.exists() else None
        events["output_sha256"] = sha256_file(output) if output.exists() else None
        events["run_incomplete"] = events["completed"] + events["errors"] != events["planned_cells"]
        write_json(summary_path, events)
        if output.exists():
            restricted_mode(output)
        if plan_path.exists():
            restricted_mode(plan_path)

    print(json.dumps({
        "run_id": args.run_id,
        "completed": events["completed"],
        "errors": events["errors"],
        "run_incomplete": events["run_incomplete"],
        "listed_rate_cost_estimate_usd": events["listed_rate_cost_estimate_usd"],
        "openrouter_usage_delta": (
            float(events["openrouter_after"]["total_usage"])
            - float(events["openrouter_before"]["total_usage"])
        ),
    }, indent=2))


if __name__ == "__main__":
    main()

