#!/usr/bin/env python3
"""Freeze the 30 CD-45 rows not already evaluated by official RLM-Qwen.

This script makes no model calls. It computes an ordered set difference between
the frozen context-window-disjoint CD-45 parent and the predeclared CD-15
repeatability subset, preserving the parent example records verbatim.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
PARENT = RESULTS / "oolong_context_disjoint_n45_manifest_20260715.json"
REUSE = RESULTS / "oolong_context_disjoint_cd15_repeatability_manifest_20260715.json"
OUT = RESULTS / "oolong_context_disjoint_cd30_official_qwen_remaining_manifest_20260719.json"
OUT_MD = RESULTS / "oolong_context_disjoint_cd30_official_qwen_remaining_manifest_20260719.md"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parent = json.loads(PARENT.read_text(encoding="utf-8"))
    reuse = json.loads(REUSE.read_text(encoding="utf-8"))
    parent_examples = parent["examples"]
    reuse_ids = {str(item["id"]) for item in reuse["examples"]}
    parent_ids = [str(item["id"]) for item in parent_examples]

    if len(parent_ids) != 45 or len(set(parent_ids)) != 45:
        raise RuntimeError("Parent must contain exactly 45 unique IDs")
    if len(reuse_ids) != 15 or not reuse_ids.issubset(set(parent_ids)):
        raise RuntimeError("Reuse manifest must contain 15 unique IDs within CD-45")

    remaining = [item for item in parent_examples if str(item["id"]) not in reuse_ids]
    if len(remaining) != 30 or len({str(item["id"]) for item in remaining}) != 30:
        raise RuntimeError("Expected exactly 30 unique remaining examples")

    groups = Counter(str(item["task_group"]) for item in remaining)
    lengths = Counter(str(item["context_len"]) for item in remaining)
    contexts = Counter(str(item["context_window_id"]) for item in remaining)
    payload = {
        "metadata": {
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "purpose": "Predeclared no-call set difference for completing official RLM-Qwen coverage from CD-15 to frozen CD-45.",
            "parent_manifest": str(PARENT.relative_to(ROOT)),
            "parent_sha256": sha256(PARENT),
            "reuse_manifest": str(REUSE.relative_to(ROOT)),
            "reuse_sha256": sha256(REUSE),
            "selection_rule": "Preserve parent order and include every CD-45 row whose ID is absent from the frozen CD-15 subset.",
            "model_calls": 0,
            "outcome_blind": True,
        },
        "summary": {
            "parent_n": 45,
            "reuse_n": 15,
            "remaining_n": 30,
            "groups": dict(sorted(groups.items())),
            "lengths": dict(sorted(lengths.items(), key=lambda pair: int(pair[0]))),
            "unique_context_window_ids": len(contexts),
            "max_questions_per_context_window_id": max(contexts.values()),
            "parent_reuse_overlap": len(set(parent_ids) & reuse_ids),
            "remaining_reuse_overlap": len({str(item["id"]) for item in remaining} & reuse_ids),
        },
        "examples": remaining,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# Official RLM-Qwen CD-45 Remaining-30 Manifest",
        "",
        "No model calls were made. This is the ordered CD-45 minus CD-15 set difference frozen before the completion run.",
        "",
        f"- Parent: `{PARENT.relative_to(ROOT)}` ({sha256(PARENT)})",
        f"- Reuse subset: `{REUSE.relative_to(ROOT)}` ({sha256(REUSE)})",
        f"- Remaining N: {len(remaining)}",
        f"- Groups: {dict(sorted(groups.items()))}",
        f"- Lengths: {dict(sorted(lengths.items(), key=lambda pair: int(pair[0])))}",
        f"- Unique context windows: {len(contexts)}",
        "",
        "| example_id | task group | context length | context window |",
        "|---|---|---:|---|",
    ]
    lines.extend(
        f"| {item['id']} | {item['task_group']} | {item['context_len']} | {item['context_window_id']} |"
        for item in remaining
    )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    print(f"Wrote {OUT.relative_to(ROOT)}")
    print(f"Wrote {OUT_MD.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
