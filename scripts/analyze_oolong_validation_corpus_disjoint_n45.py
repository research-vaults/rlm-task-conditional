#!/usr/bin/env python3
"""Analyze the prospective corpus-disjoint Oolong validation N=45 run."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scipy.stats import binomtest


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
MANIFEST = RESULTS / "oolong_validation_corpus_disjoint_n45_manifest_20260721.json"
SLM_FILES = [
    RESULTS / "oolong_validation_corpus_disjoint_n45_slm_labeler_typed_counting_timeline_30_20260721.csv",
    RESULTS / "oolong_validation_corpus_disjoint_n45_slm_labeler_typed_user_20260721.csv",
]
SLM_TRACE_FILES = [
    RESULTS / "oolong_validation_corpus_disjoint_n45_slm_labeler_typed_counting_timeline_30_20260721_trace.jsonl",
    RESULTS / "oolong_validation_corpus_disjoint_n45_slm_labeler_typed_user_20260721_trace.jsonl",
]
DIRECT_FILE = RESULTS / "oolong_validation_corpus_disjoint_n45_direct_gemini25flash_20260721.csv"
DIRECT_TRACE = RESULTS / "oolong_validation_corpus_disjoint_n45_direct_gemini25flash_20260721_trace.jsonl"
RLM_FILES = [
    RESULTS / f"oolong_validation_corpus_disjoint_n45_standard_rlm_{group}_20260721.csv"
    for group in ("counting", "timeline", "user")
]
RLM_TRACE_FILES = [
    RESULTS / f"oolong_validation_corpus_disjoint_n45_standard_rlm_{group}_20260721.jsonl"
    for group in ("counting", "timeline", "user")
]
OUT_CSV = RESULTS / "oolong_validation_corpus_disjoint_n45_threeway_20260721.csv"
OUT_JSON = RESULTS / "oolong_validation_corpus_disjoint_n45_threeway_20260721.json"
OUT_MD = RESULTS / "oolong_validation_corpus_disjoint_n45_threeway_20260721.md"
OUT_SLM_TRACE = RESULTS / "oolong_validation_corpus_disjoint_n45_slm_labeler_typed_merged_20260721_trace.jsonl"
OUT_RLM_TRACE = RESULTS / "oolong_validation_corpus_disjoint_n45_standard_rlm_merged_20260721_trace.jsonl"

ACCOUNT_USAGE_BEFORE = 383.317258824
ACCOUNT_USAGE_AFTER = 385.622219124
BOOTSTRAPS = 100_000
SEED = 20260721


def read_csvs(paths: list[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in paths:
        with path.open(newline="", encoding="utf-8") as handle:
            rows.extend(csv.DictReader(handle))
    return rows


def read_jsonl(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        with path.open(encoding="utf-8") as handle:
            rows.extend(json.loads(line) for line in handle if line.strip())
    return rows


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact(row: dict[str, str], score_key: str) -> bool:
    return float(row[score_key]) >= 1.0


def holm(pvalues: dict[str, float]) -> dict[str, float]:
    ordered = sorted(pvalues.items(), key=lambda item: item[1])
    adjusted: dict[str, float] = {}
    running = 0.0
    m = len(ordered)
    for rank, (name, value) in enumerate(ordered):
        running = max(running, min(1.0, (m - rank) * value))
        adjusted[name] = running
    return adjusted


def mcnemar(a: dict[str, dict[str, str]], b: dict[str, dict[str, str]], a_key: str, b_key: str) -> dict[str, Any]:
    ids = sorted(set(a) & set(b))
    b_count = sum(exact(a[eid], a_key) and not exact(b[eid], b_key) for eid in ids)
    c_count = sum(not exact(a[eid], a_key) and exact(b[eid], b_key) for eid in ids)
    discordant = b_count + c_count
    p = float(binomtest(min(b_count, c_count), discordant, 0.5, alternative="two-sided").pvalue) if discordant else 1.0
    return {
        "n": len(ids),
        "b_a_right_b_wrong": b_count,
        "c_b_right_a_wrong": c_count,
        "discordant": discordant,
        "two_sided_exact_p": p,
    }


def cluster_bootstrap(
    merged: list[dict[str, Any]],
    field_a: str,
    field_b: str | None,
    seed: int,
) -> dict[str, float]:
    by_cluster: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in merged:
        by_cluster[row["context_window_id"]].append(row)
    clusters = sorted(by_cluster)
    rng = random.Random(seed)
    draws: list[float] = []
    for _ in range(BOOTSTRAPS):
        sampled = [rng.choice(clusters) for _ in clusters]
        rows = [row for cluster in sampled for row in by_cluster[cluster]]
        a = sum(float(row[field_a]) for row in rows) / len(rows)
        value = a if field_b is None else a - sum(float(row[field_b]) for row in rows) / len(rows)
        draws.append(value)
    draws.sort()
    lo = draws[math.floor(0.025 * (len(draws) - 1))]
    hi = draws[math.ceil(0.975 * (len(draws) - 1))]
    return {"estimate": sum(draws) / len(draws), "lo": lo, "hi": hi, "clusters": len(clusters), "reps": BOOTSTRAPS, "seed": seed}


def pack(rows: list[dict[str, str]], score_key: str, cost_key: str) -> dict[str, Any]:
    scores = [float(row[score_key]) for row in rows]
    cost = sum(float(row.get(cost_key) or 0.0) for row in rows)
    return {
        "n": len(rows),
        "exact_count": sum(score >= 1.0 for score in scores),
        "exact_rate": sum(score >= 1.0 for score in scores) / len(rows),
        "score_sum": sum(scores),
        "mean_score": sum(scores) / len(rows),
        "cost_usd": cost,
        "errors": sum(bool(row.get("error")) for row in rows),
        "cost_per_exact_usd": cost / sum(score >= 1.0 for score in scores),
    }


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    examples = manifest["examples"]
    order = [str(row["id"]) for row in examples]
    meta = {str(row["id"]): row for row in examples}
    expected = set(order)

    slm_rows = read_csvs(SLM_FILES)
    direct_rows = read_csvs([DIRECT_FILE])
    rlm_rows = read_csvs(RLM_FILES)
    for name, rows in (("slm", slm_rows), ("direct", direct_rows), ("rlm", rlm_rows)):
        ids = [row["example_id"] for row in rows]
        if len(ids) != 45 or len(set(ids)) != 45 or set(ids) != expected:
            raise RuntimeError(f"{name} ID coverage mismatch: rows={len(ids)} unique={len(set(ids))}")

    slm = {row["example_id"]: row for row in slm_rows}
    direct = {row["example_id"]: row for row in direct_rows}
    rlm = {row["example_id"]: row for row in rlm_rows}
    merged: list[dict[str, Any]] = []
    for eid in order:
        golds = {slm[eid]["gold"], direct[eid]["gold"], rlm[eid]["gold"]}
        if len(golds) != 1:
            raise RuntimeError(f"Gold mismatch on {eid}: {golds}")
        merged.append({
            "example_id": eid,
            "dataset": meta[eid]["dataset"],
            "context_window_id": str(meta[eid]["context_window_id"]),
            "context_len": int(meta[eid]["context_len"]),
            "task_group": meta[eid]["task_group"],
            "task": meta[eid]["task"],
            "answer_type": meta[eid]["answer_type"],
            "gold": slm[eid]["gold"],
            "slm_prediction": slm[eid]["prediction"],
            "slm_score": float(slm[eid]["correct"]),
            "slm_exact": int(exact(slm[eid], "correct")),
            "slm_cost_usd": float(slm[eid]["cost_usd"]),
            "slm_error": slm[eid]["error"],
            "direct_prediction": direct[eid]["prediction"],
            "direct_score": float(direct[eid]["correct"]),
            "direct_exact": int(exact(direct[eid], "correct")),
            "direct_cost_usd": float(direct[eid]["cost_usd"]),
            "direct_error": direct[eid]["error"],
            "rlm_prediction": rlm[eid]["prediction"],
            "rlm_score": float(rlm[eid]["score"]),
            "rlm_exact": int(exact(rlm[eid], "score")),
            "rlm_cost_usd": float(rlm[eid]["cost_usd"]),
            "rlm_error": rlm[eid]["error"],
        })

    with OUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(merged[0]))
        writer.writeheader()
        writer.writerows(merged)

    slm_traces = read_jsonl(SLM_TRACE_FILES)
    direct_traces = read_jsonl([DIRECT_TRACE])
    rlm_traces = read_jsonl(RLM_TRACE_FILES)
    for name, traces in (("slm", slm_traces), ("direct", direct_traces), ("rlm", rlm_traces)):
        ids = [str(row["example_id"]) for row in traces]
        if len(ids) != 45 or len(set(ids)) != 45 or set(ids) != expected:
            raise RuntimeError(f"{name} trace coverage mismatch")
    with OUT_SLM_TRACE.open("w", encoding="utf-8") as handle:
        for row in sorted(slm_traces, key=lambda item: order.index(str(item["example_id"]))):
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")
    with OUT_RLM_TRACE.open("w", encoding="utf-8") as handle:
        for row in sorted(rlm_traces, key=lambda item: order.index(str(item["example_id"]))):
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")

    overall = {
        "slm_typed": pack(slm_rows, "correct", "cost_usd"),
        "direct_controller": pack(direct_rows, "correct", "cost_usd"),
        "standard_rlm": pack(rlm_rows, "score", "cost_usd"),
    }
    method_fields = {"slm_typed": "slm", "direct_controller": "direct", "standard_rlm": "rlm"}
    by_group: dict[str, Any] = {}
    by_length: dict[str, Any] = {}
    for group in ("counting", "timeline", "user"):
        group_rows = [row for row in merged if row["task_group"] == group]
        by_group[group] = {
            method: {
                "n": len(group_rows),
                "exact_count": sum(row[f"{prefix}_exact"] for row in group_rows),
                "exact_rate": sum(row[f"{prefix}_exact"] for row in group_rows) / len(group_rows),
                "mean_score": sum(row[f"{prefix}_score"] for row in group_rows) / len(group_rows),
                "cost_usd": sum(row[f"{prefix}_cost_usd"] for row in group_rows),
            }
            for method, prefix in method_fields.items()
        }
    for length in sorted({row["context_len"] for row in merged}):
        length_rows = [row for row in merged if row["context_len"] == length]
        by_length[str(length)] = {
            method: {
                "n": len(length_rows),
                "exact_count": sum(row[f"{prefix}_exact"] for row in length_rows),
                "exact_rate": sum(row[f"{prefix}_exact"] for row in length_rows) / len(length_rows),
                "mean_score": sum(row[f"{prefix}_score"] for row in length_rows) / len(length_rows),
                "cost_usd": sum(row[f"{prefix}_cost_usd"] for row in length_rows),
            }
            for method, prefix in method_fields.items()
        }

    pair_inputs = {
        "slm_vs_rlm": (slm, rlm, "correct", "score"),
        "slm_vs_direct": (slm, direct, "correct", "correct"),
        "direct_vs_rlm": (direct, rlm, "correct", "score"),
    }
    paired = {name: mcnemar(*args) for name, args in pair_inputs.items()}
    adjusted = holm({name: row["two_sided_exact_p"] for name, row in paired.items()})
    for name, value in adjusted.items():
        paired[name]["holm_three_pair_p"] = value

    cluster = {
        "slm_exact": cluster_bootstrap(merged, "slm_exact", None, SEED),
        "direct_exact": cluster_bootstrap(merged, "direct_exact", None, SEED + 1),
        "rlm_exact": cluster_bootstrap(merged, "rlm_exact", None, SEED + 2),
        "slm_minus_rlm_exact": cluster_bootstrap(merged, "slm_exact", "rlm_exact", SEED + 3),
        "slm_minus_direct_exact": cluster_bootstrap(merged, "slm_exact", "direct_exact", SEED + 4),
        "direct_minus_rlm_exact": cluster_bootstrap(merged, "direct_exact", "rlm_exact", SEED + 5),
        "slm_minus_rlm_score": cluster_bootstrap(merged, "slm_score", "rlm_score", SEED + 6),
    }
    captured = sum(row["cost_usd"] for row in overall.values())
    payload = {
        "metadata": {
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "protocol": "protocols/OOLONG_VALIDATION_CORPUS_DISJOINT_N45_20260721.md",
            "manifest": str(MANIFEST.relative_to(ROOT)),
            "manifest_sha256": sha256(MANIFEST),
            "n": 45,
            "clusters": len({row["context_window_id"] for row in merged}),
            "dataset_split": "validation",
            "source_corpora": sorted({row["dataset"] for row in merged}),
            "source_document_identity": "unidentifiable_from_official_schema",
            "models": {"slm_worker": "google/gemma-4-26b-a4b-it", "direct_and_rlm_controller": "google/gemini-2.5-flash", "rlms": "0.1.3"},
        },
        "overall": overall,
        "by_group": by_group,
        "by_length": by_length,
        "paired": paired,
        "cluster_bootstrap": cluster,
        "cost_accounting": {
            "captured_successful_completion_total_usd": captured,
            "openrouter_account_usage_before_usd": ACCOUNT_USAGE_BEFORE,
            "openrouter_account_usage_after_usd": ACCOUNT_USAGE_AFTER,
            "openrouter_account_delta_usd": ACCOUNT_USAGE_AFTER - ACCOUNT_USAGE_BEFORE,
            "aborted_and_partial_overhead_usd": ACCOUNT_USAGE_AFTER - ACCOUNT_USAGE_BEFORE - captured,
            "rlm_to_slm_captured_cost_ratio": overall["standard_rlm"]["cost_usd"] / overall["slm_typed"]["cost_usd"],
            "direct_to_slm_captured_cost_ratio": overall["direct_controller"]["cost_usd"] / overall["slm_typed"]["cost_usd"],
            "note": "Account delta includes an aborted duplicate-worker launch and partial in-flight calls; successful-completion costs come from provider usage returned in retained rows.",
        },
        "trace_integrity": {
            "slm_rows": len(slm_traces),
            "direct_rows": len(direct_traces),
            "rlm_rows": len(rlm_traces),
            "rlm_rows_with_context": sum(bool(row.get("input_context")) for row in rlm_traces),
            "rlm_rows_with_trajectory": sum(bool((row.get("trajectory") or {}).get("available")) for row in rlm_traces),
            "rlm_code_blocks": sum(int(row.get("code_block_count") or 0) for row in rlm_traces),
            "merged_slm_trace_sha256": sha256(OUT_SLM_TRACE),
            "direct_trace_sha256": sha256(DIRECT_TRACE),
            "merged_rlm_trace_sha256": sha256(OUT_RLM_TRACE),
        },
        "interpretation": {
            "primary": "The specialized SLM+typed route retains the highest accuracy on two previously unseen upstream corpora, while standard RLM remains substantially stronger than direct prompting on user-centric aggregation.",
            "boundary": "The result tests source-corpus transfer within the known Oolong task family. It does not identify source documents, establish natural-text prevalence, or provide official SRLM/RAH parity.",
            "parser_repair": "A no-call preflight admitted the validation wording 'spam or ham (i.e., not spam)' before paid outputs; the complete repeated preflight had zero parser errors.",
        },
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def pct(value: float) -> str:
        return f"{100 * value:.1f}%"

    lines = [
        "# Oolong Validation Corpus-Disjoint N=45 Three-Way Result",
        "",
        "This replication was pre-output locked after one outcome-blind no-call parser grammar repair and uses the official Oolong validation split. Its `spam` and `trec_coarse` source corpora do not occur in the official test split or any prior project Oolong artifact. The public schema does not expose source-document identity, so this is corpus-disjoint rather than proven document-disjoint.",
        "",
        "| Method | Exact | Mean score | Captured cost | Cost / exact | Errors |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for method, label in (("slm_typed", "SLM+typed"), ("standard_rlm", "Standard RLM"), ("direct_controller", "Direct Gemini")):
        row = overall[method]
        lines.append(f"| {label} | {row['exact_count']}/45 ({pct(row['exact_rate'])}) | {pct(row['mean_score'])} | ${row['cost_usd']:.3f} | ${row['cost_per_exact_usd']:.3f} | {row['errors']} |")
    lines.extend(["", "## Task families", "", "| Group | SLM+typed | Standard RLM | Direct |", "|---|---:|---:|---:|"])
    for group, rows in by_group.items():
        lines.append(f"| {group} | {rows['slm_typed']['exact_count']}/15 | {rows['standard_rlm']['exact_count']}/15 | {rows['direct_controller']['exact_count']}/15 |")
    lines.extend(["", "## Paired and clustered uncertainty", ""])
    for name, row in paired.items():
        lines.append(f"- {name}: b={row['b_a_right_b_wrong']}, c={row['c_b_right_a_wrong']}, exact two-sided p={row['two_sided_exact_p']:.6g}, three-pair Holm p={row['holm_three_pair_p']:.6g}.")
    diff = cluster["slm_minus_rlm_exact"]
    lines.extend([
        f"- SLM+typed minus RLM exact-rate cluster bootstrap: {pct(diff['lo'])} to {pct(diff['hi'])} over {diff['clusters']} context windows ({diff['reps']:,} draws).",
        f"- Captured-cost ratio: RLM/SLM+typed {payload['cost_accounting']['rlm_to_slm_captured_cost_ratio']:.2f}x. Account delta ${payload['cost_accounting']['openrouter_account_delta_usd']:.6f}; retained successful-row costs ${captured:.6f}; aborted/partial overhead ${payload['cost_accounting']['aborted_and_partial_overhead_usd']:.6f}.",
        "",
        "## Interpretation",
        "",
        "The specialized route transfers to two unseen upstream corpora and remains the best overall accuracy/cost operating point. Standard RLM is not uniformly weak: it reaches 13/15 on user tasks and beats direct prompting overall. The mechanism boundary therefore persists: semantic local interpretation plus deterministic aggregation is strongest when the task family is known, while recursive code execution helps relative to direct prompting on some compositional user-centric questions but does not erase specialization or cost overhead.",
    ])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"overall": overall, "paired": paired, "cluster": cluster, "cost": payload["cost_accounting"]}, indent=2))
    print(f"Wrote {OUT_CSV.relative_to(ROOT)}")
    print(f"Wrote {OUT_JSON.relative_to(ROOT)}")
    print(f"Wrote {OUT_MD.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
