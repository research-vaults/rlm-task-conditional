#!/usr/bin/env python3
"""Blindly adjudicate all successful BrowseComp+ replication predictions."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "results/browsecomp_plus_positive_regime_replication"
SOURCE = BASE / "bcp_repl_n49_deterministic_compact_restricted.json"
OUTPUT = BASE / "bcp_repl_gpt56_luna_blind_audit_n49_restricted.jsonl"
SUMMARY = BASE / "bcp_repl_gpt56_luna_blind_audit_n49_summary.json"
CATALOG = BASE / "openrouter_gpt56_luna_catalog_execution_20260721.json"
PROTOCOL = ROOT / "protocols/BROWSECOMP_PLUS_REPLICATION_GPT56_SOL_BLIND_AUDIT_20260720.md"
AMENDMENT = ROOT / "protocols/BROWSECOMP_PLUS_REPLICATION_GPT56_LUNA_BLIND_AUDIT_AMENDMENT_20260720.md"
MODEL = "openai/gpt-5.6-luna"
BATCH_SIZE = 16
URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM = """You are an exacting semantic answer evaluator. For every case, decide whether the candidate response correctly answers the question given the reference answer. Accept aliases, harmless wording variation, and additional noncontradictory detail. Reject a different entity or value, contradiction, material ambiguity, refusal, empty answer, or non-answer. Do not infer any method identity. Return only one JSON object with key labels, whose value is an array of objects containing exactly case_id, correct (boolean), and rationale (one short sentence)."""


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_env() -> None:
    if os.environ.get("OPENROUTER_API_KEY"):
        return
    for raw in Path("<local-user-home>/<local-config>/.env").read_text(encoding="utf-8").splitlines():
        if raw.strip() and not raw.lstrip().startswith("#") and "=" in raw:
            key, value = raw.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def parse_json(text: str) -> dict[str, Any]:
    clean = text.strip()
    clean = re.sub(r"^```(?:json)?\s*", "", clean, flags=re.I)
    clean = re.sub(r"\s*```$", "", clean)
    return json.loads(clean)


def main() -> None:
    load_env()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default=str(SOURCE.relative_to(ROOT)),
    )
    parser.add_argument(
        "--output-dir",
        default=str(BASE.relative_to(ROOT)),
    )
    parser.add_argument(
        "--run-id",
        default="bcp_repl_gpt56_luna_blind_audit_n49",
    )
    parser.add_argument("--model", default=MODEL)
    parser.add_argument(
        "--protocol",
        default=str(PROTOCOL.relative_to(ROOT)),
    )
    parser.add_argument(
        "--amendment",
        default=str(AMENDMENT.relative_to(ROOT)),
    )
    parser.add_argument(
        "--study-id",
        default="browsecomp_plus_untouched_replication_n59_v1",
    )
    parser.add_argument("--order-salt", default="BCP-REPL-SOL-v1")
    parser.add_argument("--case-salt", default="BCP-REPL-SOL-CASE-v1")
    args = parser.parse_args()

    source = (ROOT / args.input).resolve()
    output_dir = (ROOT / args.output_dir).resolve()
    if ROOT.resolve() not in source.parents or ROOT.resolve() not in output_dir.parents:
        raise ValueError("input and output directory must remain inside the project")
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{args.run_id}_restricted.jsonl"
    summary_path = output_dir / f"{args.run_id}_summary.json"
    catalog_path = output_dir / f"{args.run_id}_catalog.json"
    protocol = (ROOT / args.protocol).resolve()
    amendment = (ROOT / args.amendment).resolve() if args.amendment else None
    model = args.model

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY is required")
    if output.exists() or summary_path.exists():
        raise FileExistsError("blind-audit output already exists")

    rows = json.loads(source.read_text(encoding="utf-8"))
    successful = [row for row in rows if row["ok"] and str(row["prediction"]).strip()]
    successful.sort(key=lambda row: sha256_text(f"{args.order_salt}|{row['rank']}|{row['method']}"))
    cases = []
    mapping = {}
    for row in successful:
        case_id = sha256_text(f"{args.case_salt}|{row['rank']}|{row['method']}")[:24]
        cases.append({
            "case_id": case_id,
            "question": row["question"],
            "reference_answer": row["answer"],
            "candidate_response": row["prediction"],
        })
        mapping[case_id] = {"rank": row["rank"], "method": row["method"]}

    before = requests.get(
        "https://openrouter.ai/api/v1/auth/key",
        headers={"Authorization": f"Bearer {key}"}, timeout=60,
    ).json().get("data", {})
    credits_before = requests.get(
        "https://openrouter.ai/api/v1/credits",
        headers={"Authorization": f"Bearer {key}"}, timeout=60,
    ).json().get("data", {})
    catalogue = requests.get("https://openrouter.ai/api/v1/models", timeout=60).json()
    model_record = next((row for row in catalogue.get("data", []) if row.get("id") == model), None)
    if not model_record:
        raise RuntimeError(f"live model catalogue does not contain {model}")
    catalog_path.write_text(json.dumps({
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "model": model_record,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary: dict[str, Any] = {
        "study_id": args.study_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "reasoning_effort": "high",
        "input": str(source.relative_to(ROOT)),
        "input_sha256": sha256_file(source),
        "runner_sha256": sha256_file(Path(__file__)),
        "protocol": str(protocol.relative_to(ROOT)),
        "protocol_sha256": sha256_file(protocol),
        "catalogue_record": str(catalog_path.relative_to(ROOT)),
        "catalogue_record_sha256": sha256_file(catalog_path),
        "successful_predictions": len(successful),
        "batch_size": BATCH_SIZE,
        "order_salt": args.order_salt,
        "case_salt": args.case_salt,
        "system_prompt": SYSTEM,
        "system_prompt_sha256": sha256_text(SYSTEM),
        "provider_usage_before": before.get("usage"),
        "provider_total_credits_before": credits_before.get("total_credits"),
        "provider_total_usage_before": credits_before.get("total_usage"),
        "calls": [],
        "completed_cases": 0,
        "failed_cases": 0,
        "reported_usage_cost_usd": 0.0,
    }
    if amendment is not None:
        summary["amendment"] = str(amendment.relative_to(ROOT))
        summary["amendment_sha256"] = sha256_file(amendment)

    with output.open("x", encoding="utf-8") as handle:
        for batch_id, start in enumerate(range(0, len(cases), BATCH_SIZE), 1):
            batch = cases[start : start + BATCH_SIZE]
            body = {
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": json.dumps({"cases": batch}, ensure_ascii=False)},
                ],
                "reasoning": {"effort": "high"},
                "max_tokens": 6000,
                "seed": 20,
                "response_format": {"type": "json_object"},
            }
            started = time.monotonic()
            response = None
            transport_attempts = []
            for attempt in (1, 2):
                attempt_started = time.monotonic()
                try:
                    response = requests.post(
                        URL,
                        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                        json=body,
                        timeout=1800,
                    )
                    transport_attempts.append({
                        "attempt": attempt,
                        "status_code": response.status_code,
                        "latency_seconds": time.monotonic() - attempt_started,
                    })
                    if response.ok or response.status_code not in {408, 429, 500, 502, 503, 504}:
                        break
                except requests.RequestException as exc:
                    transport_attempts.append({
                        "attempt": attempt,
                        "exception_type": type(exc).__name__,
                        "exception": str(exc),
                        "latency_seconds": time.monotonic() - attempt_started,
                    })
                    if attempt == 2:
                        raise
            if response is None:
                raise RuntimeError(f"batch {batch_id}: no transport response")
            if not response.ok:
                raise RuntimeError(f"batch {batch_id}: HTTP {response.status_code}: {response.text[:1000]}")
            payload = response.json()
            raw = str(payload["choices"][0]["message"].get("content") or "")
            parsed = parse_json(raw)
            labels = parsed.get("labels")
            if not isinstance(labels, list):
                raise ValueError(f"batch {batch_id}: labels missing")
            by_id = {str(label.get("case_id")): label for label in labels}
            expected = {case["case_id"] for case in batch}
            if set(by_id) != expected:
                raise ValueError(f"batch {batch_id}: case coverage mismatch")
            usage = dict(payload.get("usage") or {})
            cost = float(usage.get("cost") or 0.0)
            call = {
                "batch_id": batch_id,
                "case_ids": sorted(expected),
                "request": body,
                "request_sha256": sha256_text(json.dumps(body, sort_keys=True, ensure_ascii=False)),
                "raw_response": raw,
                "response_sha256": sha256_text(raw),
                "usage": usage,
                "reported_cost_usd": cost,
                "provider_response_id": payload.get("id"),
                "latency_seconds": time.monotonic() - started,
                "transport_attempts": transport_attempts,
            }
            summary["calls"].append(call)
            summary["reported_usage_cost_usd"] += cost
            for case in batch:
                label = by_id[case["case_id"]]
                valid = isinstance(label.get("correct"), bool) and bool(str(label.get("rationale") or "").strip())
                meta = mapping[case["case_id"]]
                record = {
                    "case_id": case["case_id"],
                    "rank": meta["rank"],
                    "method": meta["method"],
                    "question": case["question"],
                    "reference_answer": case["reference_answer"],
                    "candidate_response": case["candidate_response"],
                    "correct": bool(label.get("correct")) if valid else False,
                    "parsed": valid,
                    "rationale": str(label.get("rationale") or ""),
                    "batch_id": batch_id,
                }
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
                handle.flush()
                summary["completed_cases"] += int(valid)
                summary["failed_cases"] += int(not valid)
            print(f"batch={batch_id} cases={len(batch)} valid={sum(int(isinstance(by_id[c['case_id']].get('correct'), bool)) for c in batch)} cost=${cost:.6f}", flush=True)
    output.chmod(0o600)
    after = requests.get(
        "https://openrouter.ai/api/v1/auth/key",
        headers={"Authorization": f"Bearer {key}"}, timeout=60,
    ).json().get("data", {})
    credits_after = requests.get(
        "https://openrouter.ai/api/v1/credits",
        headers={"Authorization": f"Bearer {key}"}, timeout=60,
    ).json().get("data", {})
    summary["provider_usage_after"] = after.get("usage")
    summary["provider_total_credits_after"] = credits_after.get("total_credits")
    summary["provider_total_usage_after"] = credits_after.get("total_usage")
    if before.get("usage") is not None and after.get("usage") is not None:
        summary["provider_usage_delta_usd"] = float(after["usage"]) - float(before["usage"])
    if credits_before.get("total_usage") is not None and credits_after.get("total_usage") is not None:
        summary["provider_total_usage_delta_usd"] = float(credits_after["total_usage"]) - float(credits_before["total_usage"])
    summary["finished_utc"] = datetime.now(timezone.utc).isoformat()
    summary["output_sha256"] = sha256_file(output)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary_path.chmod(0o600)
    print(json.dumps({k: summary[k] for k in ("completed_cases", "failed_cases", "reported_usage_cost_usd", "provider_usage_delta_usd")}, indent=2))


if __name__ == "__main__":
    main()
