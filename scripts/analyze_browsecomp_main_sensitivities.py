#!/usr/bin/env python3
"""Audit the stopped-prefix stability and route-cost utility of BrowseComp N=49."""

from __future__ import annotations

import hashlib
import json
import math
import random
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "browsecomp_plus_positive_regime_replication"
COMPACT = RESULTS / "bcp_repl_n49_deterministic_compact_restricted.json"
JUDGES = RESULTS / "bcp_repl_gemma4_judge_n49_20260720_restricted.jsonl"
PRIMARY = RESULTS / "semantic_replication_n49_primary_analysis.json"
OUT_JSON = RESULTS / "main_inference_cost_sensitivity_20260722.json"
OUT_MD = RESULTS / "main_inference_cost_sensitivity_20260722.md"

METHODS = ("standard_rlm_qwen36", "text_decompose_qwen36", "bm25_qwen36")
LABELS = {
    "standard_rlm_qwen36": "Standard RLM",
    "text_decompose_qwen36": "Text decomposition",
    "bm25_qwen36": "BM25",
}
BOOTSTRAPS = 50_000


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def exact_mcnemar(b: int, c: int) -> float:
    n = b + c
    if not n:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(min(b, c) + 1)) / (2**n)
    return min(1.0, 2 * tail)


def paired_summary(left: list[bool], right: list[bool], seed: int) -> dict[str, Any]:
    if len(left) != len(right) or not left:
        raise ValueError("paired vectors must be nonempty and aligned")
    n = len(left)
    b = sum(a and not z for a, z in zip(left, right))
    c = sum(z and not a for a, z in zip(left, right))
    rng = random.Random(seed)
    draws = []
    for _ in range(BOOTSTRAPS):
        idx = [rng.randrange(n) for _ in range(n)]
        draws.append(sum(int(left[i]) - int(right[i]) for i in idx) / n)
    draws.sort()
    return {
        "n": n,
        "left_correct": sum(left),
        "right_correct": sum(right),
        "difference": sum(left) / n - sum(right) / n,
        "left_only": b,
        "right_only": c,
        "mcnemar_exact_two_sided_p": exact_mcnemar(b, c),
        "paired_percentile_bootstrap_95": [
            draws[int(0.025 * BOOTSTRAPS)],
            draws[min(BOOTSTRAPS - 1, int(0.975 * BOOTSTRAPS))],
        ],
        "bootstrap_repetitions": BOOTSTRAPS,
        "bootstrap_seed": seed,
    }


def main() -> None:
    compact = json.loads(COMPACT.read_text(encoding="utf-8"))
    primary = json.loads(PRIMARY.read_text(encoding="utf-8"))
    source = {(int(row["rank"]), str(row["method"])): row for row in compact}
    expected = {(rank, method) for rank in range(1, 50) for method in METHODS}
    if set(source) != expected:
        raise ValueError("unexpected compact replication coverage")

    judge: dict[tuple[int, str], bool] = {}
    for line in JUDGES.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        key = (int(row["rank"]), str(row["method"]))
        judge[key] = bool(row["judge"].get("correct"))

    successful = {
        key for key, row in source.items() if row["ok"] and str(row["prediction"]).strip()
    }
    if set(judge) != successful:
        raise ValueError("judge coverage does not match successful generations")

    terminal = {method: source[(49, method)] for method in METHODS}
    if any(row["ok"] or str(row["prediction"]).strip() for row in terminal.values()):
        raise ValueError("rank 49 is not the expected all-route terminal failure")

    vectors = {
        method: [judge.get((rank, method), False) for rank in range(1, 50)]
        for method in METHODS
    }
    prefix_vectors = {method: values[:48] for method, values in vectors.items()}

    comparisons = {}
    for index, alternative in enumerate(METHODS[1:]):
        key = f"standard_rlm_qwen36__vs__{alternative}"
        comparisons[key] = {
            "attempted_n49": paired_summary(vectors[METHODS[0]], vectors[alternative], 20260721 + index),
            "fully_generated_prefix_n48": paired_summary(
                prefix_vectors[METHODS[0]], prefix_vectors[alternative], 20260722 + index
            ),
        }

    utility = {}
    rlm = primary["methods"]["standard_rlm_qwen36"]
    for alternative in METHODS[1:]:
        row = primary["methods"][alternative]
        net_additional_correct = int(rlm["semantic_correct"]) - int(row["semantic_correct"])
        incremental_cost = float(rlm["active_runtime_listed_rate_usd"]) - float(
            row["active_runtime_listed_rate_usd"]
        )
        if net_additional_correct <= 0 or incremental_cost <= 0:
            raise ValueError("expected positive BrowseComp accuracy and cost increments")
        utility[alternative] = {
            "alternative_label": LABELS[alternative],
            "attempted_n": 49,
            "net_additional_correct_answers": net_additional_correct,
            "incremental_route_attributed_cost_usd": incremental_cost,
            "incremental_cost_per_attempted_query_usd": incremental_cost / 49,
            "route_dollar_cost_per_net_additional_correct_answer": incremental_cost
            / net_additional_correct,
        }

    payload = {
        "analysis_type": "descriptive_stopped_prefix_and_route_cost_utility_sensitivity",
        "source_hashes": {
            "compact": sha256_file(COMPACT),
            "judges": sha256_file(JUDGES),
            "primary_analysis": sha256_file(PRIMARY),
        },
        "terminal_rank": 49,
        "terminal_rank_all_routes_failed": True,
        "comparisons": comparisons,
        "route_cost_utility": utility,
        "interpretation_boundary": [
            "Dropping the terminal all-route failure tests whether that row drives the paired result; it is not a stopping-adjusted population analysis.",
            "The bootstrap intervals and McNemar tests describe the observed attempted prefix and do not guarantee coverage under the reliability-triggered stop.",
            "The dollar threshold values only route-attributed active-runtime cost and excludes latency value, engineering, maintenance, reliability, and failed-call billing outside returned usage.",
            "No same-budget nonrecursive search route is evaluated, so the analysis does not isolate recursion from additional inference budget.",
        ],
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    md = [
        "# BrowseComp N=49 Main-Paper Sensitivities",
        "",
        "This deterministic audit uses the frozen compact execution ledger, the complete primary-judge ledger and the canonical route-cost analysis. It makes no model calls.",
        "",
        "## Terminal-rank sensitivity",
        "",
        "| Comparison | Attempted N=49 | Fully generated prefix N=48 |",
        "|---|---|---|",
    ]
    for key, row in comparisons.items():
        left, right = key.split("__vs__")
        n49 = row["attempted_n49"]
        n48 = row["fully_generated_prefix_n48"]
        md.append(
            f"| {LABELS[left]} vs {LABELS[right]} | {100*n49['difference']:.1f} pp; "
            f"b/c={n49['left_only']}/{n49['right_only']}; p={n49['mcnemar_exact_two_sided_p']:.4f} | "
            f"{100*n48['difference']:.1f} pp; b/c={n48['left_only']}/{n48['right_only']}; "
            f"p={n48['mcnemar_exact_two_sided_p']:.4f} |"
        )
    md.extend(
        [
            "",
            "The terminal rank is incorrect for all routes. Removing it leaves every paired discordance and exact McNemar p-value unchanged. This is a descriptive stability check, not stopping-adjusted population inference.",
            "",
            "## Route-dollar utility sensitivity",
            "",
            "| Alternative | Net extra RLM correct | Incremental RLM route cost | Dollars per net extra correct |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in utility.values():
        md.append(
            f"| {row['alternative_label']} | {row['net_additional_correct_answers']} | "
            f"${row['incremental_route_attributed_cost_usd']:.3f} | "
            f"${row['route_dollar_cost_per_net_additional_correct_answer']:.3f} |"
        )
    md.extend(
        [
            "",
            "These thresholds value only route-attributed active-runtime dollars. They omit latency value, engineering, maintenance, reliability and uncaptured failed-call billing. No same-budget nonrecursive route is present, so they describe the observed tradeoff rather than attributing it uniquely to recursion.",
        ]
    )
    OUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
