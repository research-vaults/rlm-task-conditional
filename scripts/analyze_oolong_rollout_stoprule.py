#!/usr/bin/env python3
"""Analyze the bounded Oolong rollout-repeat stop-rule artifact.

The goal is not to create a new benchmark row. It documents why scaling the
standard-RLM repeatability run beyond the first three 8k rows was not a good
pre-submission spend: the first repeated RLM row flipped from correct to wrong
and the next two rows timed out at the configured cap.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"

MANIFEST = RESULTS / "oolong_rollout_variability_n15_manifest_20260714.json"
BASE = {
    "base_slm": RESULTS / "oolong_standard_validation_n45_slm_labeler_typed_20260713.csv",
    "base_direct": RESULTS / "oolong_standard_validation_n45_direct_controller_gemini25flash_20260713.csv",
    "base_rlm": RESULTS / "oolong_standard_validation_n45_rlm_20260713.csv",
    "direct_repeat_full_n15": RESULTS / "oolong_rollout_variability_n15_replay_direct_full_20260714.csv",
    "rlm_repeat_stoprule_n3": RESULTS / "oolong_rollout_variability_n15_replay_rlm_full_20260714.csv",
}
TRACE_FILES = {
    "direct_repeat_full_n15": RESULTS / "oolong_rollout_variability_n15_replay_direct_full_20260714_trace.jsonl",
    "rlm_repeat_stoprule_n3": RESULTS / "oolong_rollout_variability_n15_replay_rlm_full_20260714_trace.jsonl",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def pack(rows: list[dict[str, str]]) -> dict[str, Any]:
    scores = [float(r.get("correct") or 0.0) for r in rows]
    return {
        "n": len(rows),
        "exact_count": sum(1 for s in scores if s >= 1.0),
        "exact_rate": round(sum(1 for s in scores if s >= 1.0) / len(rows), 6) if rows else 0.0,
        "mean_score": round(sum(scores) / len(rows), 6) if rows else 0.0,
        "cost_usd": round(sum(float(r.get("cost_usd") or 0.0) for r in rows), 8),
        "errors": sum(1 for r in rows if r.get("error")),
        "latency_s": round(sum(float(r.get("latency_s") or 0.0) for r in rows), 3),
    }


def by_group(rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("task_group", "")].append(row)
    return {group: pack(items) for group, items in sorted(grouped.items())}


def trace_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def compare_rows(a: list[dict[str, str]], b: list[dict[str, str]]) -> dict[str, Any]:
    by_a = {r["example_id"]: r for r in a}
    by_b = {r["example_id"]: r for r in b}
    ids = sorted(set(by_a) & set(by_b))
    prediction_stable = 0
    correctness_stable = 0
    flips: list[dict[str, Any]] = []
    for eid in ids:
        ra, rb = by_a[eid], by_b[eid]
        pred_stable = (ra.get("prediction") or "") == (rb.get("prediction") or "")
        score_stable = float(ra.get("correct") or 0.0) == float(rb.get("correct") or 0.0)
        prediction_stable += int(pred_stable)
        correctness_stable += int(score_stable)
        if not pred_stable or not score_stable:
            flips.append(
                {
                    "example_id": eid,
                    "task_group": rb.get("task_group"),
                    "context_len": int(rb.get("context_len") or 0),
                    "base_prediction": ra.get("prediction"),
                    "repeat_prediction": rb.get("prediction"),
                    "gold": rb.get("gold"),
                    "base_correct": float(ra.get("correct") or 0.0),
                    "repeat_correct": float(rb.get("correct") or 0.0),
                    "repeat_error": rb.get("error", ""),
                }
            )
    return {
        "paired_n": len(ids),
        "prediction_stable": prediction_stable,
        "correctness_stable": correctness_stable,
        "flips": flips,
    }


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    ids = [str(ex["id"]) for ex in manifest["examples"]]
    rows: dict[str, list[dict[str, str]]] = {}
    for name, path in BASE.items():
        all_rows = read_csv(path)
        rows[name] = [r for r in all_rows if r.get("example_id") in ids]

    rlm_ids = {r["example_id"] for r in rows["rlm_repeat_stoprule_n3"]}
    first_three_ids = ids[:3]
    if sorted(rlm_ids) != sorted(first_three_ids):
        raise SystemExit(f"RLM stop-rule rows are not the first three manifest IDs: {sorted(rlm_ids)} vs {first_three_ids}")

    summary = {
        "metadata": {
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "scope": "bounded rollout-repeat stop-rule artifact, not a benchmark-scale variance estimate",
            "manifest": str(MANIFEST.relative_to(ROOT)),
            "manifest_n": len(ids),
            "manifest_context_lengths": sorted({int(ex["context_len"]) for ex in manifest["examples"]}),
            "manifest_task_groups": sorted({str(ex["task_group"]) for ex in manifest["examples"]}),
            "stop_rule": (
                "Run full N=15 direct-controller replay as a cheap baseline. Start standard-RLM N=15 replay, "
                "but stop after the first three 8k rows produced one wrong answer and two 360-second timeouts; "
                "do not scale this unstable path before submission."
            ),
        },
        "overall": {name: pack(items) for name, items in rows.items()},
        "by_group": {name: by_group(items) for name, items in rows.items()},
        "trace_rows": {name: trace_count(path) for name, path in TRACE_FILES.items()},
        "comparisons": {
            "direct_base_vs_repeat_n15": compare_rows(rows["base_direct"], rows["direct_repeat_full_n15"]),
            "rlm_base_vs_stoprule_n3": compare_rows(
                [r for r in rows["base_rlm"] if r["example_id"] in rlm_ids],
                rows["rlm_repeat_stoprule_n3"],
            ),
        },
        "rlm_stoprule_rows": rows["rlm_repeat_stoprule_n3"],
    }

    out_json = RESULTS / "oolong_rollout_variability_n15_stoprule_20260714.json"
    out_csv = RESULTS / "oolong_rollout_variability_n15_stoprule_20260714.csv"
    out_md = RESULTS / "oolong_rollout_variability_n15_stoprule_20260714.md"

    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "source",
            "n",
            "exact_count",
            "exact_rate",
            "mean_score",
            "cost_usd",
            "errors",
            "latency_s",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for source, stats in summary["overall"].items():
            writer.writerow({"source": source, **stats})

    lines = [
        "# Oolong N=15 Rollout Repeat Stop-Rule Artifact (2026-07-14)",
        "",
        "Scope: bounded repeatability/stop-rule artifact over the frozen 15-row validation manifest. This is not a benchmark-scale variance estimate.",
        "",
        "## Overall",
        "",
        "| Source | N | Exact | Mean score | Cost | Errors | Latency s |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for source, stats in summary["overall"].items():
        lines.append(
            f"| {source} | {stats['n']} | {stats['exact_count']}/{stats['n']} | "
            f"{stats['mean_score']:.3f} | ${stats['cost_usd']:.6f} | {stats['errors']} | {stats['latency_s']:.1f} |"
        )
    direct_cmp = summary["comparisons"]["direct_base_vs_repeat_n15"]
    rlm_cmp = summary["comparisons"]["rlm_base_vs_stoprule_n3"]
    lines.extend(
        [
            "",
            "## Stability Checks",
            "",
            f"- Direct Gemini base vs full N=15 replay: {direct_cmp['prediction_stable']}/{direct_cmp['paired_n']} predictions stable and {direct_cmp['correctness_stable']}/{direct_cmp['paired_n']} correctness labels stable.",
            f"- Standard RLM base vs stop-rule N=3 replay: {rlm_cmp['prediction_stable']}/{rlm_cmp['paired_n']} predictions stable and {rlm_cmp['correctness_stable']}/{rlm_cmp['paired_n']} correctness labels stable.",
            "",
            "## RLM Stop-Rule Rows",
            "",
            "| Example | Group | Length | Base correct | Repeat prediction | Gold | Repeat correct | Repeat error |",
            "|---|---|---:|---:|---|---|---:|---|",
        ]
    )
    base_by_id = {r["example_id"]: r for r in rows["base_rlm"]}
    for row in rows["rlm_repeat_stoprule_n3"]:
        base = base_by_id[row["example_id"]]
        lines.append(
            f"| {row['example_id']} | {row['task_group']} | {row['context_len']} | "
            f"{float(base['correct']):.3f} | {row['prediction'] or '(none)'} | {row['gold']} | "
            f"{float(row['correct']):.3f} | {row.get('error','')} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- The full direct-controller N=15 replay exactly reproduces the original direct-controller correctness pattern: 5/15 exact, mean score 0.429, no errors.",
            "- The standard-RLM repeat was intentionally stopped after the first three 8k rows: the original N45 run solved all three, but the repeat produced one wrong fast answer and two 360-second timeouts.",
            "- This is stronger repeatability evidence than the original N=3 micro-audit because it also shows the full N=15 direct baseline is stable while the attempted RLM extension fails the stop rule immediately.",
            "- The right paper-facing use is conservative: do not claim an RLM-family benchmark-scale variance estimate; use it to justify not spending on a larger standard-rlms repeat before submission without a more stable harness.",
        ]
    )
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary["overall"], indent=2))
    print(f"Wrote {out_json.relative_to(ROOT)}")
    print(f"Wrote {out_csv.relative_to(ROOT)}")
    print(f"Wrote {out_md.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
