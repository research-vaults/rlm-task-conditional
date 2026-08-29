#!/usr/bin/env python3
"""Build a release-safe N80 cell ledger and a restricted blinded audit packet."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "results" / "browsecomp_plus_positive_regime"
COMPACT = BASE / "bcp_qwen36_n80_deterministic_compact_restricted.json"
JUDGE = BASE / "bcp_gemma4_judge_n80_20260720_restricted.jsonl"
ANALYSIS = BASE / "semantic_n80_resumed_primary_analysis.json"

LEDGER = BASE / "bcp_n80_privacy_safe_cell_ledger_20260720.jsonl"
LEDGER_SUMMARY = BASE / "bcp_n80_privacy_safe_cell_ledger_20260720_summary.json"
BLIND_PACKET = BASE / "bcp_n80_second_model_blind_packet_20260720_restricted.jsonl"
BLIND_MAP = BASE / "bcp_n80_second_model_blind_map_20260720_restricted.json"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def error_category(row: dict) -> str:
    if row.get("ok") and str(row.get("prediction", "")).strip():
        return "none"
    text = str(row.get("error", "")).lower()
    if "timeout" in text:
        return "timeout"
    if "404" in text or "endpoint" in text or "provider" in text:
        return "provider_or_endpoint"
    if not str(row.get("prediction", "")).strip():
        return "no_prediction"
    return "other_failure"


def main() -> None:
    compact = json.loads(COMPACT.read_text(encoding="utf-8"))
    judge_rows = read_jsonl(JUDGE)
    analysis = json.loads(ANALYSIS.read_text(encoding="utf-8"))

    judge_by_key = {(int(r["rank"]), r["method"]): r for r in judge_rows}
    semantic_by_key = {
        (int(r["rank"]), r["method"]): bool(r["semantic_correct"])
        for r in analysis["semantic_vs_containment_disagreements"]
    }
    for key, row in judge_by_key.items():
        semantic_by_key[key] = bool(row["judge"].get("correct", False))

    ledger_rows: list[dict] = []
    source_by_key: dict[tuple[int, str], dict] = {}
    for row in sorted(compact, key=lambda r: (int(r["rank"]), r["method"])):
        key = (int(row["rank"]), row["method"])
        source_by_key[key] = row
        judged = judge_by_key.get(key)
        completed = bool(row.get("ok") and str(row.get("prediction", "")).strip())
        parsed = bool(judged and judged["judge"].get("parsed"))
        if not completed:
            judge_status = "no_generation_scored_incorrect"
        elif parsed:
            judge_status = "parsed"
        else:
            judge_status = "malformed_scored_incorrect"
        ledger_rows.append(
            {
                "rank": key[0],
                "method": key[1],
                "episode": row["episode"],
                "question_sha256": sha(row["question"]),
                "reference_sha256": sha(row["answer"]),
                "prediction_sha256": sha(row.get("prediction", "")),
                "source_row_sha256": row["source_sha256"],
                "completed": completed,
                "semantic_correct": bool(semantic_by_key.get(key, False)),
                "normalized_contains": bool(row["normalized_contains"]),
                "strict_exact": bool(row["strict_exact"]),
                "judge_parse_status": judge_status,
                "judge_response_sha256": judged["judge"].get("response_sha256") if judged else None,
                "error_category": error_category(row),
                "wall_seconds": row.get("wall_seconds"),
                "iterations": row.get("iterations"),
                "code_blocks": row.get("code_blocks"),
                "context_chars": row.get("context_chars"),
            }
        )

    assert len(ledger_rows) == 240
    assert len({(r["rank"], r["method"]) for r in ledger_rows}) == 240
    LEDGER.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in ledger_rows), encoding="utf-8")

    method_summary: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in ledger_rows:
        method_summary[row["method"]]["n"] += 1
        method_summary[row["method"]]["completed"] += int(row["completed"])
        method_summary[row["method"]]["semantic_correct"] += int(row["semantic_correct"])
        method_summary[row["method"]]["judge_malformed"] += int(row["judge_parse_status"] == "malformed_scored_incorrect")

    disagreements = {
        (int(r["rank"]), r["method"])
        for r in analysis["semantic_vs_containment_disagreements"]
    }
    malformed = {
        key for key, row in judge_by_key.items() if not bool(row["judge"].get("parsed"))
    }

    # Deterministic agreement sample: up to three examples per method and
    # semantic class, ordered by a hash unrelated to rank or outcome direction.
    strata: dict[tuple[str, bool], list[tuple[int, str]]] = defaultdict(list)
    for row in ledger_rows:
        key = (row["rank"], row["method"])
        if row["completed"] and row["semantic_correct"] == row["normalized_contains"] and key not in disagreements:
            strata[(row["method"], row["semantic_correct"])].append(key)
    agreement_sample: set[tuple[int, str]] = set()
    for stratum, keys in strata.items():
        ordered = sorted(keys, key=lambda key: sha(f"n80-blind-sample|{stratum}|{key}"))
        agreement_sample.update(ordered[:3])

    selected = disagreements | malformed | agreement_sample
    blind_rows: list[dict] = []
    mapping: dict[str, dict] = {}
    for key in selected:
        row = source_by_key[key]
        case_id = "case_" + sha(f"n80-independent-audit|{key[0]}|{key[1]}")[:12]
        blind_rows.append(
            {
                "case_id": case_id,
                "question": row["question"],
                "reference_answer": row["answer"],
                "candidate_response": row.get("prediction", ""),
            }
        )
        mapping[case_id] = {
            "rank": key[0],
            "method": key[1],
            "episode": row["episode"],
            "selection_strata": sorted(
                name
                for name, member in [
                    ("semantic_vs_containment_disagreement", key in disagreements),
                    ("malformed_primary_judge", key in malformed),
                    ("stratified_agreement_sample", key in agreement_sample),
                ]
                if member
            ),
            "primary_semantic_correct": bool(semantic_by_key.get(key, False)),
            "normalized_contains": bool(row["normalized_contains"]),
            "question_sha256": sha(row["question"]),
            "reference_sha256": sha(row["answer"]),
            "prediction_sha256": sha(row.get("prediction", "")),
        }

    blind_rows.sort(key=lambda r: sha("blind-order|" + r["case_id"]))
    BLIND_PACKET.write_text("".join(json.dumps(r, ensure_ascii=True) + "\n" for r in blind_rows), encoding="utf-8")
    BLIND_MAP.write_text(json.dumps({"contract": "restricted; do not give this mapping to the adjudicator", "cases": mapping}, indent=2) + "\n", encoding="utf-8")

    summary = {
        "study_id": "browsecomp_plus_qwen36_n80_resumed_primary",
        "privacy_contract": "No question, reference, prediction, query ID, or free-text rationale is released in the cell ledger.",
        "n_cells": len(ledger_rows),
        "n_ranks": len({r["rank"] for r in ledger_rows}),
        "methods": {method: dict(values) for method, values in sorted(method_summary.items())},
        "blind_audit": {
            "n_cases": len(blind_rows),
            "all_disagreements": len(disagreements),
            "malformed_primary_judge": len(malformed),
            "stratified_agreement_sample": len(agreement_sample),
            "method_and_primary_labels_hidden_from_adjudicator": True,
            "packet_sha256": hashlib.sha256(BLIND_PACKET.read_bytes()).hexdigest(),
        },
        "ledger_sha256": hashlib.sha256(LEDGER.read_bytes()).hexdigest(),
    }
    LEDGER_SUMMARY.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
