#!/usr/bin/env python3
"""Analyze a retrospective CD-15 positive-side diagnostic.

This is a no-call analysis over:
- the frozen CD-15 repeatability manifest;
- three completed standard-RLM/Gemini repeats;
- a direct Gemini replay on the exact same rows;
- stored SLM+typed and original CD-45 rows filtered to the CD-15 IDs.

The subset was frozen for repeatability after parent CD-45 outcomes were known.
The positive-side interpretation was formulated after the RLM repeats. This
script therefore reports descriptive rollout sensitivity, not a prospectively
selected positive regime or a 45-pair RLM-vs-direct hypothesis test.
"""

from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
from datetime import datetime, timezone
from math import comb
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT_PREFIX = ROOT / "results/oolong_context_disjoint_cd15_positive_regime_lock_20260718"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def exact(row: dict[str, str]) -> bool:
    return float(row.get("correct", "0") or 0.0) >= 0.999


def cost(rows: list[dict[str, str]]) -> float:
    return round(sum(float(r.get("cost_usd", "0") or 0.0) for r in rows), 6)


def summarize(rows: list[dict[str, str]]) -> dict[str, Any]:
    n = len(rows)
    exact_count = sum(exact(r) for r in rows)
    score_sum = sum(float(r.get("correct", "0") or 0.0) for r in rows)
    return {
        "n": n,
        "exact_count": exact_count,
        "exact_rate": round(exact_count / n, 6) if n else 0.0,
        "mean_score": round(score_sum / n, 6) if n else 0.0,
        "cost_usd": cost(rows),
        "errors": sum(1 for r in rows if r.get("error")),
    }


def mcnemar(a_rows: dict[str, dict[str, str]], b_rows: dict[str, dict[str, str]]) -> dict[str, Any]:
    ids = sorted(set(a_rows) & set(b_rows))
    b_count = c_count = both = neither = 0
    for ex_id in ids:
        a = exact(a_rows[ex_id])
        b = exact(b_rows[ex_id])
        if a and not b:
            b_count += 1
        elif b and not a:
            c_count += 1
        elif a and b:
            both += 1
        else:
            neither += 1
    n_disc = b_count + c_count
    if n_disc == 0:
        p = 1.0
    else:
        tail = sum(comb(n_disc, k) for k in range(0, min(b_count, c_count) + 1)) / (2 ** n_disc)
        p = min(1.0, 2 * tail)
    return {
        "n": len(ids),
        "a_only": b_count,
        "b_only": c_count,
        "both_exact": both,
        "neither_exact": neither,
        "two_sided_exact_p": round(p, 6),
        "exact_diff_points": round((b_count - c_count) / len(ids) * 100, 1) if ids else 0.0,
    }


def rows_by_id(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {str(r["example_id"]): r for r in rows}


def by_group(rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["task_group"]].append(row)
    return {group: summarize(group_rows) for group, group_rows in sorted(grouped.items())}


def item_clustered_descriptive(
    ids: list[str],
    rlm_repeat_rows: dict[str, list[dict[str, str]]],
    direct_by_id: dict[str, dict[str, str]],
    *,
    seed: int = 20260719,
    n_bootstrap: int = 100_000,
) -> dict[str, Any]:
    """Describe RLM-repeat minus direct accuracy using the 15 items as clusters.

    Each item contributes its mean exact outcome across the three observed RLM
    rollouts minus the one observed direct outcome. The percentile interval is
    conditional on these four observed executions; it does not estimate fresh
    rollout variance or turn the three dependent repeat rows into independent
    pairs.
    """

    rlm_by_repeat = {name: rows_by_id(rows) for name, rows in rlm_repeat_rows.items()}
    item_differences = {
        ex_id: (
            sum(float(exact(rows[ex_id])) for rows in rlm_by_repeat.values()) / len(rlm_by_repeat)
            - float(exact(direct_by_id[ex_id]))
        )
        for ex_id in ids
    }
    observed = sum(item_differences.values()) / len(ids)
    rng = random.Random(seed)
    draws = []
    for _ in range(n_bootstrap):
        sampled = [ids[rng.randrange(len(ids))] for _ in ids]
        draws.append(sum(item_differences[ex_id] for ex_id in sampled) / len(sampled))
    draws.sort()
    lo = draws[round(0.025 * (n_bootstrap - 1))]
    hi = draws[round(0.975 * (n_bootstrap - 1))]
    return {
        "unit": "unique_example_id",
        "n_item_clusters": len(ids),
        "rlm_rollouts_per_item": len(rlm_repeat_rows),
        "direct_rollouts_per_item": 1,
        "observed_difference_points": round(observed * 100, 1),
        "item_cluster_bootstrap_95_points": [round(lo * 100, 1), round(hi * 100, 1)],
        "bootstrap_draws": n_bootstrap,
        "seed": seed,
        "conditioning": "conditional_on_three_observed_rlm_rollouts_and_one_observed_direct_rollout",
        "inferential_nonclaim": "not_an_independent_45_pair_test_and_not_total_fresh_rollout_uncertainty",
        "per_item_rlm_minus_direct": {ex_id: round(value, 6) for ex_id, value in item_differences.items()},
    }


def main() -> None:
    manifest = json.loads((ROOT / "results/oolong_context_disjoint_cd15_repeatability_manifest_20260715.json").read_text(encoding="utf-8"))
    ids = [str(ex["id"]) for ex in manifest["examples"]]
    id_set = set(ids)

    direct_rows = read_csv(ROOT / "results/oolong_context_disjoint_cd15_direct_gemini25_repeat_20260718.csv")
    rlm_repeat_rows = {
        f"standard_rlm_repeat{i}": read_csv(ROOT / f"results/oolong_context_disjoint_cd15_rlm_repeat{i}_20260716.csv")
        for i in [1, 2, 3]
    }
    cd45_slm_rows = [
        r for r in read_csv(ROOT / "results/oolong_context_disjoint_n45_slm_labeler_question_parsed_typed_20260715.csv")
        if str(r["example_id"]) in id_set
    ]
    cd45_direct_rows = [
        r for r in read_csv(ROOT / "results/oolong_context_disjoint_n45_direct_controller_gemini25flash_20260715.csv")
        if str(r["example_id"]) in id_set
    ]
    cd45_rlm_rows = [
        r for r in read_csv(ROOT / "results/oolong_context_disjoint_n45_rlm_20260715.csv")
        if str(r["example_id"]) in id_set
    ]

    direct_by_id = rows_by_id(direct_rows)
    aggregate_rlm_rows: list[dict[str, str]] = []
    paired: dict[str, Any] = {}
    per_repeat: dict[str, Any] = {}
    for name, rows in rlm_repeat_rows.items():
        aggregate_rlm_rows.extend(rows)
        per_repeat[name] = {
            "standard_rlm": summarize(rows),
            "direct_gemini_replay": summarize(direct_rows),
            "by_group_standard_rlm": by_group(rows),
            "paired_vs_direct": mcnemar(rows_by_id(rows), direct_by_id),
        }
        paired[f"{name}_vs_direct_gemini_replay"] = per_repeat[name]["paired_vs_direct"]

    summary = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "artifact_type": "retrospective_positive_side_cd15_rollout_analysis",
        "scope": {
            "manifest": "results/oolong_context_disjoint_cd15_repeatability_manifest_20260715.json",
            "n_unique_examples": len(ids),
            "contract": "standard/unlabeled context_window_text; same Oolong scorer; no label-provided context",
            "chronology": (
                "The subset was frozen for repeatability after parent CD-45 outcomes were known; "
                "the positive-side interpretation was formulated after the RLM repeats."
            ),
            "descriptive_claim": (
                "Across three observed standard-RLM rollouts, mean exact accuracy is numerically above "
                "one direct-Gemini replay on this retrospective subset, with wide item-clustered uncertainty."
            ),
            "non_claims": [
                "not a prospectively selected positive regime",
                "not 45 independent RLM-vs-direct pairs",
                "not a powered RLM-over-direct claim",
                "not a full Oolong leaderboard",
                "not evidence that RLM beats SLM+typed",
                "not official SRLM/lambda-RLM/RAH parity",
            ],
        },
        "overall": {
            "slm_typed_stored_cd15": summarize(cd45_slm_rows),
            "direct_gemini_original_cd15": summarize(cd45_direct_rows),
            "standard_rlm_original_cd15": summarize(cd45_rlm_rows),
            "direct_gemini_replay_cd15": summarize(direct_rows),
            "standard_rlm_three_repeats_aggregate": summarize(aggregate_rlm_rows),
        },
        "by_group": {
            "direct_gemini_replay_cd15": by_group(direct_rows),
            "standard_rlm_three_repeats_aggregate": by_group(aggregate_rlm_rows),
            "slm_typed_stored_cd15": by_group(cd45_slm_rows),
        },
        "per_repeat": per_repeat,
        "item_clustered_descriptive": item_clustered_descriptive(
            ids, rlm_repeat_rows, direct_by_id
        ),
        "paired": {
            **paired,
            "slm_typed_stored_cd15_vs_direct_gemini_replay": mcnemar(rows_by_id(cd45_slm_rows), direct_by_id),
            "slm_typed_stored_cd15_vs_standard_rlm_original_cd15": mcnemar(rows_by_id(cd45_slm_rows), rows_by_id(cd45_rlm_rows)),
        },
        "cost_note": {
            "new_openrouter_spend_usd": cost(direct_rows),
            "observed_direct_replay_cost_usd": cost(direct_rows),
            "counterfactual_three_direct_runs_projection_usd": round(cost(direct_rows) * 3, 6),
            "method": "Direct Gemini replay only; standard-RLM repeats and SLM rows reused existing logged artifacts.",
            "projection_nonclaim": "The three-run direct figure is a linear counterfactual projection, not observed spend.",
        },
    }

    json_path = OUT_PREFIX.with_suffix(".json")
    csv_path = OUT_PREFIX.with_suffix(".csv")
    md_path = OUT_PREFIX.with_suffix(".md")
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["method", "n", "exact", "exact_rate", "mean_score", "cost_usd", "errors"])
        for method, stats in summary["overall"].items():
            writer.writerow([
                method,
                stats["n"],
                stats["exact_count"],
                stats["exact_rate"],
                stats["mean_score"],
                stats["cost_usd"],
                stats["errors"],
            ])

    clustered = summary["item_clustered_descriptive"]
    md_lines = [
        "# CD-15 Retrospective Positive-Side Rollout Diagnostic",
        "",
        "The subset was frozen for repeatability after the parent CD-45 outcomes were known. The positive-side interpretation was formulated only after the RLM repeats. This is therefore a retrospective descriptive diagnostic, not a prospectively selected positive regime.",
        "",
        "## Overall",
        "",
        "| Method | N | Exact | Mean score | Cost | Errors |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for method, stats in summary["overall"].items():
        md_lines.append(
            f"| {method} | {stats['n']} | {stats['exact_count']}/{stats['n']} ({stats['exact_rate']*100:.1f}%) | "
            f"{stats['mean_score']*100:.1f}% | ${stats['cost_usd']:.6f} | {stats['errors']} |"
        )
    md_lines.extend([
        "",
        "## Item-Clustered Descriptive Summary",
        "",
        f"- Mean observed RLM-repeat accuracy minus the one observed direct replay: {clustered['observed_difference_points']} percentage points.",
        f"- Item-cluster bootstrap (15 unique items; conditional on three observed RLM rollouts and one observed direct rollout): {clustered['item_cluster_bootstrap_95_points'][0]} to {clustered['item_cluster_bootstrap_95_points'][1]} points.",
        "- No aggregate McNemar test is reported: the 45 RLM repeat rows are nested within 15 items and the direct comparator was observed once, so duplicating it would create pseudoreplication.",
        "- Interpretation: the observed average is RLM-favorable relative to this direct replay, but uncertainty is wide and SLM+typed remains 15/15 exact and cheaper.",
        "",
        "## Per Repeat",
        "",
        "| Repeat | RLM exact | Direct exact | RLM-only | Direct-only | p |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for name, stats in summary["per_repeat"].items():
        pair = stats["paired_vs_direct"]
        rlm_stats = stats["standard_rlm"]
        direct_stats = stats["direct_gemini_replay"]
        md_lines.append(
            f"| {name} | {rlm_stats['exact_count']}/{rlm_stats['n']} | "
            f"{direct_stats['exact_count']}/{direct_stats['n']} | {pair['a_only']} | {pair['b_only']} | {pair['two_sided_exact_p']} |"
        )
    md_lines.extend([
        "",
        "## Evidence Tier",
        "",
        "- Positive-side RLM evidence: retrospective and descriptive only; not a powered RLM-over-direct result.",
        "- Default-route evidence: no, because SLM+typed remains stronger and cheaper.",
        "- Stronger-family evidence: no, because this is standard `rlms` with Gemini 2.5 Flash.",
        "",
        f"New OpenRouter spend for this pass: `${summary['cost_note']['new_openrouter_spend_usd']:.6f}`.",
        f"A three-run direct cost of `${summary['cost_note']['counterfactual_three_direct_runs_projection_usd']:.6f}` would be a counterfactual linear projection, not observed spend.",
    ])
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(json.dumps(summary["overall"], indent=2))
    print(f"Wrote {json_path.relative_to(ROOT)}")
    print(f"Wrote {csv_path.relative_to(ROOT)}")
    print(f"Wrote {md_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
