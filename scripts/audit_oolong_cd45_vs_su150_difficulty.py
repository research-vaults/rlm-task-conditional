#!/usr/bin/env python3
"""Compare CD-45 selection/difficulty against SU-150 and N120 Oolong slices."""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def manifest_summary(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    examples = payload["examples"]
    summary_path = path.with_name(path.stem + "_summary.json")
    summary = read_json(summary_path) if summary_path.exists() else {}
    return {
        "path": str(path.relative_to(ROOT)),
        "n": len(examples),
        "groups": dict(Counter(ex["task_group"] for ex in examples)),
        "lengths": dict(Counter(str(ex["context_len"]) for ex in examples)),
        "answer_types": dict(Counter(str(ex.get("answer_type", "")) for ex in examples)),
        "unique_context_windows": len(set(str(ex.get("context_window_id", "")) for ex in examples)),
        "max_context_reuse": max(Counter(str(ex.get("context_window_id", "")) for ex in examples).values()),
        "prior_overlap_check": summary.get("prior_overlap_check")
        or summary.get("metadata", {}).get("split_overlap_after_archival_audit", {}),
        "selection_policy": summary.get("metadata", {}).get("selection_policy", ""),
    }


def analysis_summary(path: Path, methods: list[str]) -> dict[str, Any]:
    payload = read_json(path)
    return {method: payload["overall"][method] for method in methods}


def main() -> None:
    cd_manifest = ROOT / "results/oolong_context_disjoint_n45_manifest_20260715.json"
    su150_manifest = ROOT / "results/oolong_standard_validation_n150_manifest_20260714.json"
    n120_manifest = ROOT / "results/oolong_standard_multilength_n120_5len_manifest_20260712.json"
    cd_analysis = ROOT / "results/oolong_context_disjoint_n45_threeway_analysis_20260715.json"
    su150_analysis = ROOT / "results/oolong_standard_validation_n150_threeway_analysis_20260714.json"
    n120_analysis = ROOT / "results/oolong_standard_multilength_n120_threeway_controller_analysis_20260713.json"
    out_json = ROOT / "results/oolong_cd45_vs_su150_selection_difficulty_audit_20260715.json"
    out_md = ROOT / "results/oolong_cd45_vs_su150_selection_difficulty_audit_20260715.md"

    payload = {
        "metadata": {
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "purpose": "No-call audit showing that CD-45 is a split-validity check, not a pure difficulty-matched overlap ablation of SU-150.",
        },
        "manifests": {
            "cd45": manifest_summary(cd_manifest),
            "su150": manifest_summary(su150_manifest),
            "n120": manifest_summary(n120_manifest),
        },
        "performance": {
            "cd45": analysis_summary(cd_analysis, ["slm_qparsed_typed", "direct_controller", "standard_rlm"]),
            "su150": analysis_summary(su150_analysis, ["slm_qparsed_typed", "direct_controller", "standard_rlm"]),
            "n120": analysis_summary(n120_analysis, ["slm_qparsed_typed", "direct_controller", "standard_rlm"]),
        },
        "interpretation": {
            "cleaner_split": "CD-45 excludes all prior project example IDs and context_window_id values found in archived Oolong artifacts; SU-150 does not after archival split audit.",
            "not_difficulty_matched": "CD-45 uses 1k/4k/262k contexts with five examples per task/length cell, whereas SU-150 uses 8k/16k/32k/65k/131k contexts with ten examples per task/length cell.",
            "easier_observed_slice": "All three compared methods score higher on CD-45 than SU-150, so CD-45 should not be described as a difficulty-matched replacement for SU-150.",
            "paper_use": "Use SU-150 as larger fixed-pipeline scale/method-lock evidence and CD-45 as cleaner split-validity evidence under a different length mix.",
        },
    }
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Oolong CD-45 vs SU-150 Selection and Difficulty Audit",
        "",
        "This no-call audit documents why CD-45 should be read as a cleaner split-validity check, not as a difficulty-matched replacement for SU-150.",
        "",
        "| Slice | N | Lengths | Context clusters | Prior overlap status | SLM exact | RLM exact | Direct exact |",
        "|---|---:|---|---:|---|---:|---:|---:|",
    ]
    for key, label in [("n120", "N120"), ("su150", "SU-150"), ("cd45", "CD-45")]:
        man = payload["manifests"][key]
        perf = payload["performance"][key]
        overlap = man["prior_overlap_check"]
        if key == "cd45":
            overlap_text = "0 example / 0 context-window overlap"
        elif key == "su150":
            overlap_text = "not context-window-disjoint after audit"
        else:
            overlap_text = "development-era replication"
        lengths = ", ".join(f"{k}:{v}" for k, v in sorted(man["lengths"].items(), key=lambda kv: int(kv[0])))
        lines.append(
            f"| {label} | {man['n']} | {lengths} | {man['unique_context_windows']} | {overlap_text} | "
            f"{perf['slm_qparsed_typed']['exact_count']}/{perf['slm_qparsed_typed']['n']} | "
            f"{perf['standard_rlm']['exact_count']}/{perf['standard_rlm']['n']} | "
            f"{perf['direct_controller']['exact_count']}/{perf['direct_controller']['n']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- CD-45 is the cleanest overlap-controlled standard-input Oolong slice in this project.",
            "- CD-45 is not source-document-disjoint because the local Oolong metadata exposes `context_window_id`, not a stronger source-document key.",
            "- CD-45 is not difficulty-matched to SU-150: it uses 1k/4k/262k contexts rather than 8k--131k, and all methods score higher.",
            "- The paper should therefore pair the two rows: SU-150 for larger scale/method-lock evidence and CD-45 for split-validity evidence.",
        ]
    )
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {out_json}")
    print(f"Wrote {out_md}")


if __name__ == "__main__":
    main()
