#!/usr/bin/env python3
"""Paired semantic analysis for the interrupted-then-resumed BrowseComp+ N=80."""

from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESULT_DIR = ROOT / "results/browsecomp_plus_positive_regime"
COMPACT = RESULT_DIR / "bcp_qwen36_n80_deterministic_compact_restricted.json"
JUDGES = RESULT_DIR / "bcp_gemma4_judge_n80_20260720_restricted.jsonl"
GENERATION_SUMMARY = RESULT_DIR / "bcp_qwen36_resume_r38_80_20260720_summary.json"
JUDGE_SUMMARY = RESULT_DIR / "bcp_gemma4_judge_n80_20260720_summary.json"
CASE_AUDIT = RESULT_DIR / "bcp_semantic_disagreement_case_audit_n80_20260720.json"
OUT = RESULT_DIR / "semantic_n80_resumed_primary_analysis.json"
REPORT = RESULT_DIR / "semantic_n80_resumed_primary_analysis.md"
METHODS = ("standard_rlm_qwen36", "bm25_qwen36", "text_decompose_qwen36")
LABELS = {
    "standard_rlm_qwen36": "Standard RLM",
    "bm25_qwen36": "BM25 + same model",
    "text_decompose_qwen36": "Text decomposition + same model",
}
GENERATION_RATE = 4.39
PRE_RESUMPTION_GENERATION_LISTED_USD = 14.558426469635


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def wilson(k: int, n: int, z: float = 1.959963984540054) -> list[float]:
    p = k / n
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [center - half, center + half]


def exact_mcnemar(b: int, c: int) -> float:
    n = b + c
    if not n:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(0, min(b, c) + 1)) / (2**n)
    return min(1.0, 2 * tail)


def bootstrap_diff(left: list[bool], right: list[bool], seed: int, reps: int = 50_000) -> list[float]:
    rng = random.Random(seed)
    n = len(left)
    values = []
    for _ in range(reps):
        ids = [rng.randrange(n) for _ in range(n)]
        values.append(sum(int(left[i]) - int(right[i]) for i in ids) / n)
    values.sort()
    return [values[int(0.025 * reps)], values[min(reps - 1, int(0.975 * reps))]]


def paired(left: list[bool], right: list[bool], seed: int) -> dict[str, Any]:
    b = sum(x and not y for x, y in zip(left, right))
    c = sum(y and not x for x, y in zip(left, right))
    return {
        "n": len(left),
        "left_only": b,
        "right_only": c,
        "difference": sum(left) / len(left) - sum(right) / len(right),
        "paired_bootstrap_95": bootstrap_diff(left, right, seed),
        "mcnemar_exact_two_sided_p": exact_mcnemar(b, c),
    }


def main() -> None:
    compact = json.loads(COMPACT.read_text(encoding="utf-8"))
    if len(compact) != 240:
        raise ValueError(f"expected 240 compact cells, got {len(compact)}")
    source = {(int(row["rank"]), str(row["method"])): row for row in compact}
    expected = {(rank, method) for rank in range(1, 81) for method in METHODS}
    if set(source) != expected:
        raise ValueError("compact coverage mismatch")

    judge: dict[tuple[int, str], bool] = {}
    parsed = 0
    for line in JUDGES.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        key = (int(row["rank"]), str(row["method"]))
        if key in judge:
            raise ValueError(f"duplicate judge cell {key}")
        if key not in expected:
            raise ValueError(f"unexpected judge cell {key}")
        parsed += int(bool(row["judge"].get("parsed")))
        judge[key] = bool(row["judge"].get("correct"))
    successful = {key for key, row in source.items() if row["ok"] and str(row["prediction"]).strip()}
    if set(judge) != successful:
        raise ValueError(f"judge coverage mismatch: missing={successful - set(judge)} extra={set(judge) - successful}")
    judge_format_failures = len(judge) - parsed

    generation_summary = json.loads(GENERATION_SUMMARY.read_text(encoding="utf-8"))
    judge_summary = json.loads(JUDGE_SUMMARY.read_text(encoding="utf-8"))
    if generation_summary.get("cleanup", {}).get("http_status") != 204:
        raise ValueError("generation pod cleanup missing")
    if judge_summary.get("cleanup", {}).get("http_status") != 204:
        raise ValueError("judge pod cleanup missing")

    out: dict[str, Any] = {
        "study_id": "browsecomp_plus_positive_regime_v1_4_resumption",
        "analysis_contract": (
            "originally frozen N=80 manifest completed across two execution episodes after a disclosed "
            "user interruption and post-stop visibility of ranks 1-37; all failures count incorrect"
        ),
        "n": 80,
        "semantic_judge": "google/gemma-4-26B-A4B-it",
        "judge_revision": "01e5b3ee840d3a9e0b0b493c593e85398a30ef75",
        "judge_attempted": len(judge),
        "judge_parsed": parsed,
        "judge_format_failures_scored_incorrect": judge_format_failures,
        "post_stop_score_visibility": True,
        "uninterrupted_or_preregistered_claim_allowed": False,
        "source_hashes": {
            "compact": sha256_file(COMPACT),
            "judge": sha256_file(JUDGES),
            "generation_summary": sha256_file(GENERATION_SUMMARY),
            "judge_summary": sha256_file(JUDGE_SUMMARY),
        },
        "methods": {},
        "paired": {},
        "episode_sensitivity": {},
        "semantic_vs_containment_disagreements": [],
        "cost": {
            "openrouter_usd": 0.0,
            "pre_resumption_generation_listed_rate_usd": PRE_RESUMPTION_GENERATION_LISTED_USD,
            "resumption_generation_listed_rate_usd": float(generation_summary["listed_rate_cost_estimate_usd"]),
            "n80_judge_listed_rate_usd": float(judge_summary["listed_rate_cost_estimate_usd"]),
        },
    }
    out["cost"]["generation_attempted_listed_rate_usd"] = (
        out["cost"]["pre_resumption_generation_listed_rate_usd"]
        + out["cost"]["resumption_generation_listed_rate_usd"]
    )
    out["cost"]["generation_plus_judge_listed_rate_usd"] = (
        out["cost"]["generation_attempted_listed_rate_usd"] + out["cost"]["n80_judge_listed_rate_usd"]
    )

    correctness: dict[str, list[bool]] = {}
    for method in METHODS:
        rows = [source[(rank, method)] for rank in range(1, 81)]
        values = [judge.get((rank, method), False) for rank in range(1, 81)]
        correctness[method] = values
        k = sum(values)
        complete = sum(int(row["ok"] and bool(str(row["prediction"]).strip())) for row in rows)
        latency = [float(row["wall_seconds"]) for row in rows]
        out["methods"][method] = {
            "attempted": 80,
            "completed": complete,
            "completion_rate": complete / 80,
            "semantic_correct": k,
            "semantic_accuracy": k / 80,
            "wilson_95": wilson(k, 80),
            "strict_exact": sum(int(row["strict_exact"]) for row in rows),
            "normalized_contains": sum(int(row["normalized_contains"]) for row in rows),
            "wall_seconds_total": sum(latency),
            "wall_seconds_median": statistics.median(latency),
            "wall_seconds_max": max(latency),
            "active_runtime_listed_rate_usd": sum(latency) / 3600 * GENERATION_RATE,
            "rlm_iterations": sum(int(row["iterations"]) for row in rows),
            "rlm_code_blocks": sum(int(row["code_blocks"]) for row in rows),
        }
    out["cost"]["generation_pod_listed_rate_usd_per_hour"] = GENERATION_RATE
    out["cost"]["active_runtime_routes_total_usd"] = sum(
        row["active_runtime_listed_rate_usd"] for row in out["methods"].values()
    )
    out["cost"]["route_attribution_scope"] = (
        "active row wall time times the generation-pod listed hourly rate; excludes startup/idle, "
        "the earlier failed H100 attempt, and semantic judging"
    )

    for i, left in enumerate(METHODS):
        for j, right in enumerate(METHODS[i + 1 :], i + 1):
            out["paired"][f"{left}__vs__{right}"] = paired(
                correctness[left], correctness[right], 20260720 + i * 10 + j
            )

    for label, ranks in (("pre_interruption_r1_37", range(1, 38)), ("resumed_r38_80", range(38, 81))):
        section: dict[str, Any] = {"n": len(ranks), "methods": {}, "paired": {}}
        episode_values: dict[str, list[bool]] = {}
        for method in METHODS:
            vals = [judge.get((rank, method), False) for rank in ranks]
            episode_values[method] = vals
            section["methods"][method] = {
                "semantic_correct": sum(vals),
                "semantic_accuracy": sum(vals) / len(vals),
                "completed": sum(int(source[(rank, method)]["ok"] and bool(str(source[(rank, method)]["prediction"]).strip())) for rank in ranks),
            }
        for i, left in enumerate(METHODS):
            for j, right in enumerate(METHODS[i + 1 :], i + 1):
                section["paired"][f"{left}__vs__{right}"] = paired(
                    episode_values[left], episode_values[right], 20260820 + i * 10 + j + len(ranks)
                )
        out["episode_sensitivity"][label] = section

    for key, row in sorted(source.items()):
        semantic = judge.get(key, False)
        if semantic != bool(row["normalized_contains"]):
            out["semantic_vs_containment_disagreements"].append(
                {
                    "rank": key[0],
                    "method": key[1],
                    "normalized_contains": bool(row["normalized_contains"]),
                    "semantic_correct": semantic,
                    "question_sha256": hashlib.sha256(str(row["question"]).encode()).hexdigest(),
                    "reference_sha256": hashlib.sha256(str(row["answer"]).encode()).hexdigest(),
                    "prediction_sha256": hashlib.sha256(str(row["prediction"]).encode()).hexdigest(),
                }
            )

    case_audit = json.loads(CASE_AUDIT.read_text(encoding="utf-8"))
    audit_rows = {(int(row["rank"]), str(row["method"])): row for row in case_audit["cases"]}
    disagreement_keys = {
        (int(row["rank"]), str(row["method"]))
        for row in out["semantic_vs_containment_disagreements"]
    }
    if set(audit_rows) != disagreement_keys:
        raise ValueError("N=80 case audit does not exactly cover semantic/containment disagreements")
    for key, audit in audit_rows.items():
        row = source[key]
        expected_hashes = {
            "question_sha256": hashlib.sha256(str(row["question"]).encode()).hexdigest(),
            "reference_sha256": hashlib.sha256(str(row["answer"]).encode()).hexdigest(),
            "prediction_sha256": hashlib.sha256(str(row["prediction"]).encode()).hexdigest(),
        }
        if any(audit[field] != value for field, value in expected_hashes.items()):
            raise ValueError(f"case-audit source hash mismatch for {key}")
        if bool(audit["semantic_judge_correct"]) != bool(judge.get(key, False)):
            raise ValueError(f"case-audit judge mismatch for {key}")
    sensitivity_values: dict[str, list[bool]] = {}
    for method in METHODS:
        sensitivity_values[method] = [
            bool(audit_rows[(rank, method)]["case_audit_correct"])
            if (rank, method) in audit_rows
            else bool(judge.get((rank, method), False))
            for rank in range(1, 81)
        ]
    out["case_audit"] = {
        "artifact": str(CASE_AUDIT.relative_to(ROOT)),
        "audited": len(audit_rows),
        "agreement_with_semantic_judge": sum(
            int(bool(row["case_audit_correct"]) == bool(row["semantic_judge_correct"]))
            for row in audit_rows.values()
        ),
        "independent_human_validation": False,
        "method_identity_visible": True,
        "judge_label_visible": True,
        "sensitivity": {"methods": {}, "paired": {}},
    }
    for method in METHODS:
        vals = sensitivity_values[method]
        out["case_audit"]["sensitivity"]["methods"][method] = {
            "correct": sum(vals),
            "accuracy": sum(vals) / 80,
        }
    for i, left in enumerate(METHODS):
        for j, right in enumerate(METHODS[i + 1 :], i + 1):
            out["case_audit"]["sensitivity"]["paired"][f"{left}__vs__{right}"] = paired(
                sensitivity_values[left], sensitivity_values[right], 20260920 + i * 10 + j
            )

    OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# BrowseComp+ N=80 Interrupted-Then-Resumed Semantic Analysis",
        "",
        "The originally frozen N=80 manifest is complete across two execution episodes. Ranks 1--37 were scored before resumption; this is disclosed and the result is not described as an uninterrupted preregistered run. Failed generations count incorrect.",
        "",
        "| Method | Complete | Semantic accuracy (Wilson 95%) | Median / max wall time | Active-runtime listed-rate cost |",
        "|---|---:|---:|---:|---:|",
    ]
    for method in METHODS:
        row = out["methods"][method]
        lo, hi = row["wilson_95"]
        lines.append(
            f"| {LABELS[method]} | {row['completed']}/80 | {row['semantic_correct']}/80 = {100*row['semantic_accuracy']:.1f}% ({100*lo:.1f}--{100*hi:.1f}) | "
            f"{row['wall_seconds_median']:.1f}s / {row['wall_seconds_max']:.1f}s | ${row['active_runtime_listed_rate_usd']:.3f} |"
        )
    lines += ["", "## Paired comparisons", "", "| Comparison | Difference | Left/right-only | Paired bootstrap 95% | McNemar p |", "|---|---:|---:|---:|---:|"]
    for key, row in out["paired"].items():
        left, right = key.split("__vs__")
        lo, hi = row["paired_bootstrap_95"]
        lines.append(
            f"| {LABELS[left]} vs {LABELS[right]} | {100*row['difference']:+.1f} pp | {row['left_only']}/{row['right_only']} | "
            f"{100*lo:+.1f} to {100*hi:+.1f} pp | {row['mcnemar_exact_two_sided_p']:.4f} |"
        )
    lines += ["", "## Episode sensitivity", ""]
    for label, section in out["episode_sensitivity"].items():
        values = ", ".join(
            f"{LABELS[method]} {row['semantic_correct']}/{section['n']}"
            for method, row in section["methods"].items()
        )
        lines.append(f"- `{label}`: {values}.")
    lines += [
        "",
        "## Cost and interpretation",
        "",
        f"Conservative listed-rate generation cost across both execution episodes is ${out['cost']['generation_attempted_listed_rate_usd']:.3f}; the N=80 semantic judge adds ${out['cost']['n80_judge_listed_rate_usd']:.3f}, for ${out['cost']['generation_plus_judge_listed_rate_usd']:.3f}. Route-attributed active-runtime costs exclude startup/idle and judging.",
        "",
        f"The semantic judge differs from normalized containment on {len(out['semantic_vs_containment_disagreements'])} cells. Three judge responses violated the required prefix but began with an unambiguous `no`; they are conservatively scored incorrect without a rerun. A hash-linked project-side audit agrees on {out['case_audit']['agreement_with_semantic_judge']}/{out['case_audit']['audited']} disagreements; it was not method-blinded or independent human validation. Replacing those disagreement labels by the audit labels changes only text decomposition from 48/80 to {out['case_audit']['sensitivity']['methods']['text_decompose_qwen36']['correct']}/80 and does not change the ranking.",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
