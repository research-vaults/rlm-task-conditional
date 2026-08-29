#!/usr/bin/env python3
"""Analyze full CD-45 standard-RLM repeatability.

This complements the smaller CD-15 stop-rule by comparing the original CD-45
standard-RLM rollout against a full independent repeat on the same frozen
context-window-ID-disjoint manifest.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS = PROJECT_ROOT / "results"

MANIFEST = RESULTS / "oolong_context_disjoint_n45_manifest_20260715.json"
SLM_CSV = RESULTS / "oolong_context_disjoint_n45_slm_labeler_question_parsed_typed_20260715.csv"
DIRECT_CSV = RESULTS / "oolong_context_disjoint_n45_direct_controller_gemini25flash_20260715.csv"
ORIGINAL_RLM_CSV = RESULTS / "oolong_context_disjoint_n45_rlm_20260715.csv"
REPEAT_RLM_CSV = RESULTS / "oolong_context_disjoint_n45_rlm_repeat1_20260716.csv"

OUT_JSON = RESULTS / "oolong_context_disjoint_n45_rlm_repeatability_20260716_summary.json"
OUT_CSV = RESULTS / "oolong_context_disjoint_n45_rlm_repeatability_20260716_per_example.csv"
OUT_MD = RESULTS / "oolong_context_disjoint_n45_rlm_repeatability_20260716.md"


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def by_id(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {str(r["example_id"]): r for r in rows}


def is_exact(row: dict[str, str]) -> int:
    return int(float(row.get("correct", "0") or 0.0) >= 1.0)


def summarize(rows: list[dict[str, str]]) -> dict[str, float | int]:
    n = len(rows)
    exact = sum(is_exact(r) for r in rows)
    score_sum = sum(float(r.get("correct", "0") or 0.0) for r in rows)
    cost = sum(float(r.get("cost_usd", "0") or 0.0) for r in rows)
    return {
        "n": n,
        "exact_count": exact,
        "exact_rate": round(exact / n, 6) if n else 0.0,
        "score_sum": round(score_sum, 4),
        "mean_score": round(score_sum / n, 6) if n else 0.0,
        "cost_usd": round(cost, 6),
        "errors": sum(1 for r in rows if r.get("error")),
        "internal_error_predictions": sum(1 for r in rows if str(r.get("prediction", "")).lower().startswith("error:")),
        "freeform_nonanswers": sum(
            1
            for r in rows
            if float(r.get("correct", "0") or 0.0) < 1.0
            and len(str(r.get("prediction", "")).split()) > 6
            and not str(r.get("prediction", "")).lower().startswith("error:")
        ),
    }


def paired(a: dict[str, dict[str, str]], b: dict[str, dict[str, str]]) -> dict[str, int | float]:
    ids = sorted(set(a) & set(b), key=lambda x: int(x))
    b_count = sum(1 for eid in ids if is_exact(a[eid]) and not is_exact(b[eid]))
    c_count = sum(1 for eid in ids if is_exact(b[eid]) and not is_exact(a[eid]))
    both = sum(1 for eid in ids if is_exact(a[eid]) and is_exact(b[eid]))
    neither = sum(1 for eid in ids if not is_exact(a[eid]) and not is_exact(b[eid]))
    return {
        "n": len(ids),
        "a_only": b_count,
        "b_only": c_count,
        "both_exact": both,
        "neither_exact": neither,
        "exact_diff_points": round(100.0 * (b_count - c_count) / len(ids), 1) if ids else 0.0,
    }


def group_summary(rows: list[dict[str, str]], key: str) -> dict[str, dict[str, float | int]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[str(row[key])].append(row)
    return {g: summarize(rs) for g, rs in sorted(groups.items())}


def pct(num: float, den: float) -> str:
    return f"{100.0 * num / den:.1f}%" if den else "0.0%"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "_reproduced" / "oolong_cd45_repeatability",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out_json = args.output_dir / OUT_JSON.name
    out_csv = args.output_dir / OUT_CSV.name
    out_md = args.output_dir / OUT_MD.name

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    examples = {str(ex["id"]): ex for ex in manifest["examples"]}

    slm = load_csv(SLM_CSV)
    direct = load_csv(DIRECT_CSV)
    original = load_csv(ORIGINAL_RLM_CSV)
    repeat = load_csv(REPEAT_RLM_CSV)
    if len(repeat) != 45:
        raise SystemExit(f"Repeat CSV is incomplete: expected 45 rows, found {len(repeat)}")

    slm_by_id = by_id(slm)
    direct_by_id = by_id(direct)
    original_by_id = by_id(original)
    repeat_by_id = by_id(repeat)

    per_example = []
    stability = Counter()
    for eid in sorted(examples, key=lambda x: int(x)):
        ex = examples[eid]
        o = original_by_id[eid]
        r = repeat_by_id[eid]
        exact_pair = f"{is_exact(o)}{is_exact(r)}"
        stability[exact_pair] += 1
        per_example.append({
            "example_id": eid,
            "task_group": ex["task_group"],
            "context_len": ex["context_len"],
            "task": ex["task"],
            "answer_type": ex["answer_type"],
            "gold": o["gold"],
            "slm_exact": is_exact(slm_by_id[eid]),
            "direct_exact": is_exact(direct_by_id[eid]),
            "original_rlm_exact": is_exact(o),
            "repeat_rlm_exact": is_exact(r),
            "rlm_exact_pair": exact_pair,
            "original_rlm_prediction": o["prediction"],
            "repeat_rlm_prediction": r["prediction"],
            "repeat_rlm_error": r.get("error", ""),
            "question": ex["question"],
        })

    summary = {
        "metadata": {
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "manifest": str(MANIFEST.relative_to(PROJECT_ROOT)),
            "original_rlm_csv": str(ORIGINAL_RLM_CSV.relative_to(PROJECT_ROOT)),
            "repeat_rlm_csv": str(REPEAT_RLM_CSV.relative_to(PROJECT_ROOT)),
            "context_variant": "standard/unlabeled",
            "controller": "google/gemini-2.5-flash via OpenRouter",
            "row_timeout_seconds": 360,
            "interpretation": "Full CD-45 repeatability diagnostic; it estimates execution variability for the central RLM row but does not create a source-document-disjoint benchmark.",
        },
        "overall": {
            "slm_qparsed_typed": summarize(slm),
            "direct_gemini25_flash": summarize(direct),
            "standard_rlm_original": summarize(original),
            "standard_rlm_repeat1": summarize(repeat),
        },
        "by_group": {
            "standard_rlm_original": group_summary(original, "task_group"),
            "standard_rlm_repeat1": group_summary(repeat, "task_group"),
        },
        "by_length": {
            "standard_rlm_original": group_summary(original, "context_len"),
            "standard_rlm_repeat1": group_summary(repeat, "context_len"),
        },
        "paired_exact": {
            "slm_vs_original_rlm": paired(slm_by_id, original_by_id),
            "slm_vs_repeat_rlm": paired(slm_by_id, repeat_by_id),
            "direct_vs_original_rlm": paired(direct_by_id, original_by_id),
            "direct_vs_repeat_rlm": paired(direct_by_id, repeat_by_id),
            "original_rlm_vs_repeat_rlm": paired(original_by_id, repeat_by_id),
        },
        "rlm_exact_pair_counts": dict(sorted(stability.items())),
        "per_example": per_example,
    }
    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(per_example[0].keys()))
        writer.writeheader()
        writer.writerows(per_example)

    original_stats = summary["overall"]["standard_rlm_original"]
    repeat_stats = summary["overall"]["standard_rlm_repeat1"]
    slm_stats = summary["overall"]["slm_qparsed_typed"]
    pair = summary["paired_exact"]["original_rlm_vs_repeat_rlm"]
    slm_repeat = summary["paired_exact"]["slm_vs_repeat_rlm"]

    md = [
        "# Oolong CD-45 Standard-RLM Full Repeatability Diagnostic",
        "",
        "This artifact compares the original CD-45 standard-RLM/Gemini rollout with a full independent repeat on the same frozen context-window-ID-disjoint Oolong manifest. Both runs use `context_window_text`, Gemini 2.5 Flash through OpenRouter, and a 360-second row cap. The diagnostic targets execution variability, not source-document independence.",
        "",
        "## Headline",
        "",
        f"- Original standard RLM: {original_stats['exact_count']}/45 exact ({pct(original_stats['exact_count'], 45)}), mean score {100 * original_stats['mean_score']:.1f}%, cost ${original_stats['cost_usd']:.3f}, errors {original_stats['errors']}.",
        f"- Repeat standard RLM: {repeat_stats['exact_count']}/45 exact ({pct(repeat_stats['exact_count'], 45)}), mean score {100 * repeat_stats['mean_score']:.1f}%, cost ${repeat_stats['cost_usd']:.3f}, errors {repeat_stats['errors']}.",
        f"- SLM+typed reference row: {slm_stats['exact_count']}/45 exact ({pct(slm_stats['exact_count'], 45)}).",
        f"- Original-vs-repeat exact stability: {summary['rlm_exact_pair_counts']}. Discordance original-only/repeat-only = {pair['a_only']}/{pair['b_only']} ({pair['exact_diff_points']} points original minus repeat).",
        f"- SLM+typed versus repeat RLM discordance: {slm_repeat['a_only']}/{slm_repeat['b_only']} ({slm_repeat['exact_diff_points']} points SLM minus repeat).",
        "",
        "## Per-Group RLM Summary",
        "",
        "| Group | Original exact | Repeat exact | Original mean | Repeat mean |",
        "|---|---:|---:|---:|---:|",
    ]
    for group in ["counting", "timeline", "user"]:
        o = summary["by_group"]["standard_rlm_original"][group]
        r = summary["by_group"]["standard_rlm_repeat1"][group]
        md.append(f"| {group} | {o['exact_count']}/15 | {r['exact_count']}/15 | {100 * o['mean_score']:.1f}% | {100 * r['mean_score']:.1f}% |")
    md.extend([
        "",
        "## Interpretation",
        "",
        "The result should be used as rollout-aware uncertainty evidence for the central CD-45 row. If the repeat stays near the original aggregate, it strengthens the finding that the SLM+typed advantage is not a one-run artifact; if it swings substantially, it supports the manuscript's narrower claim that standard RLM is stochastic enough that small frozen slices need explicit execution-variance disclosure. In either case, the paper should describe CD-45 bootstrap intervals as conditional on the observed RLM executions rather than as total uncertainty over both examples and scaffold rollouts.",
    ])
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")

    print(json.dumps({
        "wrote": [
            str(out_json),
            str(out_csv),
            str(out_md),
        ],
        "original_exact": original_stats["exact_count"],
        "repeat_exact": repeat_stats["exact_count"],
        "slm_exact": slm_stats["exact_count"],
        "original_vs_repeat": pair,
        "slm_vs_repeat": slm_repeat,
    }, indent=2))


if __name__ == "__main__":
    main()
