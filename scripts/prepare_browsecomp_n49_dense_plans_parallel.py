#!/usr/bin/env python3
"""Resume locked BrowseComp dense plans with parallel independent API calls."""

from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from run_browsecomp_n49_dense_hybrid_sensitivity import (
    BM25_CANDIDATES,
    EMBED_BATCH,
    EMBED_DOC_CHARS,
    EMBED_MODEL,
    MANIFEST_PATH,
    MANIFEST_SHA256,
    PROTOCOL,
    PROTOCOL_SHA256,
    QUERY_INSTRUCTION,
    RESULT_DIR,
    STUDY_ID,
    append_jsonl,
    bm25_rank_multi,
    clip_for_embedding,
    embed_batch,
    fit_bm25_docs,
    load_env,
    load_jsonl_gz,
    load_needed_corpus,
    load_selected_queries,
    sha256_file,
    sha256_text,
    utc_now,
)


ROOT = Path(__file__).resolve().parents[1]
AMENDMENT = ROOT / "protocols/BROWSECOMP_PLUS_N49_DENSE_HYBRID_SENSITIVITY_EXECUTION_AMENDMENT_20260721.md"
ORIGINAL_RUNNER = ROOT / "scripts/run_browsecomp_n49_dense_hybrid_sensitivity.py"


def request_with_audit(key: str, inputs: list[str], purpose: str) -> tuple[list[list[float]], dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for attempt in range(1, 4):
        try:
            vectors, audit = embed_batch(key, inputs, purpose)
            audit["scheduler_attempt"] = attempt
            audit["prior_failed_attempts"] = failures
            return vectors, audit
        except Exception as exc:
            failures.append({
                "attempt": attempt,
                "error": f"{type(exc).__name__}: {exc}",
                "at": utc_now(),
            })
            if attempt == 3:
                raise
            time.sleep(5 * attempt)
    raise AssertionError("unreachable")


def build_plan_parallel(
    key: str,
    rank: int,
    query_id: str,
    question: str,
    docs: list[dict[str, str]],
    manifest_row: dict[str, Any],
    original_runner_hash: str,
    orchestrator_hash: str,
    amendment_hash: str,
) -> dict[str, Any]:
    lexical_ranking = bm25_rank_multi(docs, [question])[0][:BM25_CANDIDATES]
    candidates = [docs[index] for index in lexical_ranking]
    query_text = f"Instruct: {QUERY_INSTRUCTION}\nQuery: {question}"
    doc_inputs = [clip_for_embedding(doc["text"]) for doc in candidates]
    jobs: list[tuple[str, list[str]]] = [(f"rank_{rank}_query", [query_text])]
    for offset in range(0, len(doc_inputs), EMBED_BATCH):
        jobs.append((
            f"rank_{rank}_documents_{offset}_{min(offset + EMBED_BATCH, len(doc_inputs)) - 1}",
            doc_inputs[offset:offset + EMBED_BATCH],
        ))

    results: dict[str, tuple[list[list[float]], dict[str, Any]]] = {}
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futures = {
            pool.submit(request_with_audit, key, inputs, purpose): purpose
            for purpose, inputs in jobs
        }
        for future in as_completed(futures):
            purpose = futures[future]
            results[purpose] = future.result()

    query_vectors, query_audit = results[f"rank_{rank}_query"]
    document_vectors: list[list[float]] = []
    request_audits: list[dict[str, Any]] = [query_audit]
    for offset in range(0, len(doc_inputs), EMBED_BATCH):
        purpose = f"rank_{rank}_documents_{offset}_{min(offset + EMBED_BATCH, len(doc_inputs)) - 1}"
        vectors, audit = results[purpose]
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
        "study_id": STUDY_ID,
        "query_id": query_id,
        "query_sha256": sha256_text(question),
        "document_pool_hash": manifest_row["document_pool_hash"],
        "manifest_sha256": MANIFEST_SHA256,
        "protocol_sha256": PROTOCOL_SHA256,
        "runner_sha256": original_runner_hash,
        "planner_orchestrator_sha256": orchestrator_hash,
        "execution_amendment_sha256": amendment_hash,
        "execution_scheduler": "two ranks concurrently; five independent rank requests concurrently",
        "created_utc": utc_now(),
    }


def main() -> None:
    load_env()
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="bcp_n49_dense_hybrid_sensitivity_20260721")
    parser.add_argument("--start-rank", type=int, default=1)
    parser.add_argument("--end-rank", type=int, default=49)
    parser.add_argument("--rank-workers", type=int, default=2)
    args = parser.parse_args()
    if not (1 <= args.start_rank <= args.end_rank <= 49):
        raise SystemExit("invalid rank interval")
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY is required")
    if sha256_file(MANIFEST_PATH) != MANIFEST_SHA256:
        raise SystemExit("manifest hash mismatch")
    if sha256_file(PROTOCOL) != PROTOCOL_SHA256:
        raise SystemExit("protocol hash mismatch")

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    plan_path = RESULT_DIR / f"{args.run_id}_retrieval_plans_restricted.jsonl.gz"
    existing = {int(row["rank"]): row for row in load_jsonl_gz(plan_path)}
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    rows = [
        row for row in manifest["rows"]
        if args.start_rank <= int(row["rank"]) <= args.end_rank and int(row["rank"]) not in existing
    ]
    query_ids = {str(row["query_id"]) for row in rows}
    document_ids = {str(docid) for row in rows for docid in row["document_ids_in_order"]}
    queries = load_selected_queries(query_ids)
    corpus = load_needed_corpus(document_ids)
    original_runner_hash = sha256_file(ORIGINAL_RUNNER)
    orchestrator_hash = sha256_file(Path(__file__))
    amendment_hash = sha256_file(AMENDMENT)

    def prepare(row: dict[str, Any]) -> dict[str, Any]:
        rank = int(row["rank"])
        query_id = str(row["query_id"])
        question = queries[query_id]["query"]
        docs = [{"docid": docid, "text": corpus[docid]} for docid in row["document_ids_in_order"]]
        return build_plan_parallel(
            key, rank, query_id, question, docs, row,
            original_runner_hash, orchestrator_hash, amendment_hash,
        )

    with ThreadPoolExecutor(max_workers=args.rank_workers) as pool:
        futures = {pool.submit(prepare, row): int(row["rank"]) for row in rows}
        for future in as_completed(futures):
            rank = futures[future]
            plan = future.result()
            append_jsonl(plan_path, plan)
            print(f"parallel retrieval rank={rank} complete", flush=True)
    plan_path.chmod(0o600)
    complete = {int(row["rank"]) for row in load_jsonl_gz(plan_path)}
    expected = set(range(args.start_rank, args.end_rank + 1))
    if not expected.issubset(complete):
        raise RuntimeError(f"plan coverage incomplete: {sorted(expected-complete)}")
    print(json.dumps({
        "plans_total": len(complete),
        "original_runner_sha256": original_runner_hash,
        "planner_orchestrator_sha256": orchestrator_hash,
        "execution_amendment_sha256": amendment_hash,
    }, indent=2))


if __name__ == "__main__":
    main()
