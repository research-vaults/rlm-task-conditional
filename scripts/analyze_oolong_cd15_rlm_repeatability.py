#!/usr/bin/env python3
"""Aggregate the frozen CD-15 standard-RLM repeatability stop-rule runs."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = PROJECT_ROOT / "results/oolong_context_disjoint_cd15_repeatability_manifest_20260715.json"
REPEAT_FILES = [
    PROJECT_ROOT / "results/oolong_context_disjoint_cd15_rlm_repeat1_20260716.csv",
    PROJECT_ROOT / "results/oolong_context_disjoint_cd15_rlm_repeat2_20260716.csv",
    PROJECT_ROOT / "results/oolong_context_disjoint_cd15_rlm_repeat3_20260716.csv",
]
OUT_JSON = PROJECT_ROOT / "results/oolong_context_disjoint_cd15_rlm_repeatability_20260716_summary.json"
OUT_CSV = PROJECT_ROOT / "results/oolong_context_disjoint_cd15_rlm_repeatability_20260716_per_example.csv"
OUT_MD = PROJECT_ROOT / "results/oolong_context_disjoint_cd15_rlm_repeatability_20260716.md"


def load_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def exact(row: dict) -> int:
    return int(float(row["correct"]) >= 1.0)


def pct(num: float, den: float) -> float:
    return round(100.0 * num / den, 1) if den else 0.0


def summarize_rows(rows: list[dict]) -> dict:
    n = len(rows)
    exact_count = sum(exact(r) for r in rows)
    score_sum = sum(float(r["correct"]) for r in rows)
    cost = sum(float(r["cost_usd"] or 0.0) for r in rows)
    internal_error_predictions = sum(1 for r in rows if str(r["prediction"]).lower().startswith("error:"))
    freeform_nonanswers = sum(
        1
        for r in rows
        if float(r["correct"]) < 1.0
        and len(str(r["prediction"]).split()) > 6
        and not str(r["prediction"]).lower().startswith("error:")
    )
    return {
        "n": n,
        "score_sum": round(score_sum, 4),
        "mean_score": round(score_sum / n, 6) if n else 0.0,
        "exact_count": exact_count,
        "exact_rate": round(exact_count / n, 6) if n else 0.0,
        "cost_usd": round(cost, 6),
        "harness_error_rows": sum(1 for r in rows if r.get("error")),
        "internal_error_predictions": internal_error_predictions,
        "freeform_nonanswers": freeform_nonanswers,
    }


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    examples = {str(ex["id"]): ex for ex in manifest["examples"]}
    repeat_rows = [load_rows(path) for path in REPEAT_FILES]

    per_repeat = {}
    by_group = defaultdict(dict)
    for idx, rows in enumerate(repeat_rows, start=1):
        label = f"repeat{idx}"
        per_repeat[label] = summarize_rows(rows)
        groups = defaultdict(list)
        for row in rows:
            groups[row["task_group"]].append(row)
        for group, group_rows in sorted(groups.items()):
            by_group[group][label] = summarize_rows(group_rows)

    per_example = []
    rows_by_id: dict[str, list[dict]] = defaultdict(list)
    for rows in repeat_rows:
        for row in rows:
            rows_by_id[row["example_id"]].append(row)

    for ex_id, ex in examples.items():
        rows = rows_by_id[ex_id]
        exacts = [exact(r) for r in rows]
        scores = [float(r["correct"]) for r in rows]
        predictions = [r["prediction"] for r in rows]
        per_example.append({
            "example_id": ex_id,
            "task_group": ex["task_group"],
            "context_len": ex["context_len"],
            "task": ex["task"],
            "answer_type": ex["answer_type"],
            "gold": rows[0]["gold"] if rows else "",
            "exact_pattern": "".join(str(v) for v in exacts),
            "exact_count": sum(exacts),
            "score_sum": round(sum(scores), 4),
            "predictions": predictions,
            "question": ex["question"],
        })
    per_example.sort(key=lambda r: (r["task_group"], int(r["context_len"]), r["example_id"]))

    stability_counts = defaultdict(int)
    for row in per_example:
        stability_counts[str(row["exact_count"])] += 1

    all_rows = [row for rows in repeat_rows for row in rows]
    aggregate = summarize_rows(all_rows)
    total_cost = aggregate["cost_usd"]
    summary = {
        "metadata": {
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "manifest": str(MANIFEST.relative_to(PROJECT_ROOT)),
            "repeat_files": [str(path.relative_to(PROJECT_ROOT)) for path in REPEAT_FILES],
            "controller": "google/gemini-2.5-flash via OpenRouter",
            "context_variant": "standard/unlabeled",
            "row_timeout_seconds": 360,
            "note": "This is a predeclared frozen CD-15 repeatability stop-rule; it does not replace the main CD-45 or SU-150 estimates.",
        },
        "aggregate_over_45_repeat_rows": aggregate,
        "per_repeat": per_repeat,
        "by_group": by_group,
        "per_example_stability_counts": dict(sorted(stability_counts.items())),
        "per_example": per_example,
    }
    OUT_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "example_id",
                "task_group",
                "context_len",
                "task",
                "answer_type",
                "gold",
                "exact_pattern",
                "exact_count",
                "score_sum",
                "prediction_repeat1",
                "prediction_repeat2",
                "prediction_repeat3",
                "question",
            ],
        )
        writer.writeheader()
        for row in per_example:
            writer.writerow({
                **{k: row[k] for k in [
                    "example_id",
                    "task_group",
                    "context_len",
                    "task",
                    "answer_type",
                    "gold",
                    "exact_pattern",
                    "exact_count",
                    "score_sum",
                    "question",
                ]},
                "prediction_repeat1": row["predictions"][0],
                "prediction_repeat2": row["predictions"][1],
                "prediction_repeat3": row["predictions"][2],
            })

    md = []
    md.append("# Oolong CD-15 Standard-RLM Repeatability Stop-Rule")
    md.append("")
    md.append("Three independent standard-RLM repeats were run on the frozen context-disjoint CD-15 manifest with the same standard/unlabeled context and 360-second row cap. This is a bounded variance check, not a replacement for the main CD-45 or SU-150 estimates.")
    md.append("")
    md.append("## Headline")
    md.append("")
    md.append(
        f"- Across 45 repeat rows, exact accuracy was {aggregate['exact_count']}/45 "
        f"({pct(aggregate['exact_count'], aggregate['n'])}%), score-sum was {aggregate['score_sum']}/45, "
        f"and total OpenRouter cost was ${total_cost:.3f}."
    )
    md.append("- Per-repeat exact counts were: " + ", ".join(
        f"{label} {stats['exact_count']}/15 ({pct(stats['exact_count'], stats['n'])}%)"
        for label, stats in per_repeat.items()
    ) + ".")
    md.append(
        f"- Stability over the 15 frozen examples: {stability_counts.get('3', 0)} correct in all three repeats, "
        f"{stability_counts.get('2', 0)} correct in two repeats, {stability_counts.get('1', 0)} correct in one repeat, "
        f"and {stability_counts.get('0', 0)} correct in none."
    )
    md.append(
        f"- Harness-level error rows: {aggregate['harness_error_rows']}; internal error-string predictions: "
        f"{aggregate['internal_error_predictions']}; free-form non-answer failures: {aggregate['freeform_nonanswers']}."
    )
    md.append("")
    md.append("## Per-Repeat Summary")
    md.append("")
    md.append("| Repeat | Exact | Score sum | Cost | Counting exact | Timeline exact | User exact |")
    md.append("|---|---:|---:|---:|---:|---:|---:|")
    for label, stats in per_repeat.items():
        md.append(
            f"| {label} | {stats['exact_count']}/15 | {stats['score_sum']:.4g}/15 | ${stats['cost_usd']:.3f} | "
            f"{by_group['counting'][label]['exact_count']}/5 | "
            f"{by_group['timeline'][label]['exact_count']}/5 | "
            f"{by_group['user'][label]['exact_count']}/5 |"
        )
    md.append("")
    md.append("## Unstable Examples")
    md.append("")
    md.append("| Example | Group | Length | Task | Exact pattern | Gold | Predictions |")
    md.append("|---|---|---:|---|---|---|---|")
    for row in per_example:
        if row["exact_count"] == 3:
            continue
        preds = " / ".join(str(p).replace("|", "\\|") for p in row["predictions"])
        md.append(
            f"| {row['example_id']} | {row['task_group']} | {row['context_len']} | "
            f"{row['task'].replace('|', '/')} | {row['exact_pattern']} | "
            f"{str(row['gold']).replace('|', '/')} | {preds} |"
        )
    md.append("")
    md.append("## Interpretation")
    md.append("")
    md.append("The stop-rule supports the manuscript's claim that standard RLM is not simply a deterministic preprocessing scaffold in this setting. On a fixed, balanced, context-disjoint subset, the same controller/protocol ranges from 13/15 to 6/15 exact. The instability is concentrated in relative-frequency, extraction-format, and user/timeline rows where the generated operator plan or final answer normalization can drift into wrong labels, prose non-answers, or internally surfaced connection-error strings. This strengthens the case for reporting task-conditional regimes and for treating RLM as a fallback when task type is unknown, not as a uniformly dominant default.")
    OUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")

    print(json.dumps({
        "wrote": [
            str(OUT_JSON.relative_to(PROJECT_ROOT)),
            str(OUT_CSV.relative_to(PROJECT_ROOT)),
            str(OUT_MD.relative_to(PROJECT_ROOT)),
        ],
        "aggregate_exact": aggregate["exact_count"],
        "aggregate_n": aggregate["n"],
        "total_cost_usd": total_cost,
    }, indent=2))


if __name__ == "__main__":
    main()
