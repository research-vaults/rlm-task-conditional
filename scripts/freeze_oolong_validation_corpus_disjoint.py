#!/usr/bin/env python3
"""Freeze an untouched corpus-disjoint Oolong validation slice.

The official Oolong-synth schema has no source-document identifier.  It does,
however, expose the upstream classification corpus in ``dataset``.  The pinned
validation split uses spam/trec_coarse, while the test split used by all prior
project Oolong experiments uses eight different corpora.  This freezer makes
that corpus-level boundary explicit without claiming unidentifiable
source-document disjointness.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = "f0d59eaf0febf130664cfceb710436c8e3216b2b"
DEFAULT_DATA = (
    Path.home()
    / ".cache/huggingface/hub/datasets--oolongbench--oolong-synth"
    / "snapshots"
    / SNAPSHOT
    / "data"
)
EXPECTED_COLUMNS = [
    "id",
    "context_len",
    "dataset",
    "context_window_text",
    "context_window_text_with_labels",
    "question",
    "task_group",
    "task",
    "answer",
    "answer_type",
    "input_subset",
    "num_labels",
    "context_window_id",
]
METADATA_COLUMNS = [c for c in EXPECTED_COLUMNS if not c.startswith("context_window_text")]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_split(data_dir: Path, split: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    files = sorted(data_dir.glob(f"{split}-*.parquet"))
    if not files:
        raise FileNotFoundError(f"No {split} parquet shards under {data_dir}")
    rows: list[dict[str, Any]] = []
    inventory: list[dict[str, Any]] = []
    for path in files:
        parquet = pq.ParquetFile(path)
        columns = parquet.schema.names
        if columns != EXPECTED_COLUMNS:
            raise RuntimeError(f"Unexpected schema in {path.name}: {columns}")
        rows.extend(pq.read_table(path, columns=METADATA_COLUMNS).to_pylist())
        inventory.append(
            {
                "name": path.name,
                "rows": parquet.metadata.num_rows,
                "bytes": path.stat().st_size,
                "blob": path.resolve().name,
            }
        )
    return rows, inventory


def collect_prior_oolong(results_dir: Path) -> tuple[set[str], set[str], set[str], list[dict[str, Any]]]:
    ids: set[str] = set()
    contexts: set[str] = set()
    datasets: set[str] = set()
    details: list[dict[str, Any]] = []

    for path in sorted(results_dir.glob("*oolong*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        examples = payload.get("examples") if isinstance(payload, dict) else payload
        if not isinstance(examples, list):
            continue
        local_ids: set[str] = set()
        local_contexts: set[str] = set()
        local_datasets: set[str] = set()
        for row in examples:
            if not isinstance(row, dict):
                continue
            if row.get("id") is not None:
                local_ids.add(str(row["id"]))
            if row.get("context_window_id") is not None:
                local_contexts.add(str(row["context_window_id"]))
            if row.get("dataset") is not None:
                local_datasets.add(str(row["dataset"]))
        if local_ids or local_contexts or local_datasets:
            ids |= local_ids
            contexts |= local_contexts
            datasets |= local_datasets
            details.append(
                {
                    "path": str(path.relative_to(ROOT)),
                    "rows": len(examples),
                    "ids": len(local_ids),
                    "contexts": len(local_contexts),
                    "datasets": sorted(local_datasets),
                }
            )

    for path in sorted(results_dir.glob("*oolong*.csv")):
        try:
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
        except Exception:
            continue
        local_ids = {
            str(row.get("example_id") or row.get("id"))
            for row in rows
            if row.get("example_id") or row.get("id")
        }
        local_contexts = {
            str(row["context_window_id"])
            for row in rows
            if row.get("context_window_id")
        }
        local_datasets = {str(row["dataset"]) for row in rows if row.get("dataset")}
        if local_ids or local_contexts or local_datasets:
            ids |= local_ids
            contexts |= local_contexts
            datasets |= local_datasets
            details.append(
                {
                    "path": str(path.relative_to(ROOT)),
                    "rows": len(rows),
                    "ids": len(local_ids),
                    "contexts": len(local_contexts),
                    "datasets": sorted(local_datasets),
                }
            )
    return ids, contexts, datasets, details


def choose(
    rows: list[dict[str, Any]],
    groups: list[str],
    lengths: list[int],
    per_cell: int,
    max_per_context: int,
    seed: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rng = random.Random(seed)
    used: Counter[str] = Counter()
    selected: list[dict[str, Any]] = []
    cells: dict[str, Any] = {}

    for group in groups:
        for length in lengths:
            candidates = [
                row for row in rows
                if row["task_group"] == group and int(row["context_len"]) == length
            ]
            by_context: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for row in candidates:
                by_context[str(row["context_window_id"])].append(row)
            context_order = sorted(by_context)
            rng.shuffle(context_order)
            for context_rows in by_context.values():
                context_rows.sort(key=lambda row: str(row["id"]))
                rng.shuffle(context_rows)

            chosen: list[dict[str, Any]] = []
            while len(chosen) < per_cell:
                progressed = False
                for context_id in context_order:
                    if len(chosen) >= per_cell:
                        break
                    if used[context_id] >= max_per_context or not by_context[context_id]:
                        continue
                    chosen.append(by_context[context_id].pop())
                    used[context_id] += 1
                    progressed = True
                if not progressed:
                    raise RuntimeError(
                        f"Insufficient rows for {group}/{length}: "
                        f"selected {len(chosen)} of {per_cell} under max_per_context={max_per_context}"
                    )
            selected.extend(chosen)
            cells[f"{group}/{length}"] = {
                "candidate_rows": len(candidates),
                "candidate_contexts": len(by_context),
                "selected": len(chosen),
                "selected_ids": [str(row["id"]) for row in chosen],
                "selected_contexts": sorted({str(row["context_window_id"]) for row in chosen}),
            }
    return selected, cells


def compact(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "context_len": int(row["context_len"]),
        "dataset": str(row["dataset"]),
        "question": row["question"],
        "task_group": row["task_group"],
        "task": row["task"],
        "answer": row["answer"],
        "answer_type": row["answer_type"],
        "input_subset": row["input_subset"],
        "num_labels": int(row["num_labels"]),
        "context_window_id": str(row["context_window_id"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA))
    parser.add_argument("--seed", type=int, default=20260721)
    parser.add_argument("--groups", default="counting,timeline,user")
    parser.add_argument("--lengths", default="1024,4096,262144")
    parser.add_argument("--per-cell", type=int, default=5)
    parser.add_argument("--max-per-context", type=int, default=3)
    parser.add_argument("--manifest-out", default="results/oolong_validation_corpus_disjoint_n45_manifest_20260721.json")
    parser.add_argument("--summary-out", default="results/oolong_validation_corpus_disjoint_n45_manifest_20260721_summary.json")
    parser.add_argument("--md-out", default="results/oolong_validation_corpus_disjoint_n45_manifest_20260721.md")
    args = parser.parse_args()

    data_dir = Path(args.data_dir).expanduser().resolve()
    groups = [value.strip() for value in args.groups.split(",") if value.strip()]
    lengths = [int(value.strip()) for value in args.lengths.split(",") if value.strip()]
    validation, validation_inventory = load_split(data_dir, "validation")
    test, test_inventory = load_split(data_dir, "test")
    prior_ids, prior_contexts, prior_datasets, prior_details = collect_prior_oolong(ROOT / "results")

    validation_ids = {str(row["id"]) for row in validation}
    test_ids = {str(row["id"]) for row in test}
    validation_contexts = {str(row["context_window_id"]) for row in validation}
    test_contexts = {str(row["context_window_id"]) for row in test}
    validation_datasets = {str(row["dataset"]) for row in validation}
    test_datasets = {str(row["dataset"]) for row in test}

    overlap = {
        "validation_test_ids": sorted(validation_ids & test_ids),
        "validation_test_contexts": sorted(validation_contexts & test_contexts),
        "validation_test_datasets": sorted(validation_datasets & test_datasets),
        "validation_prior_ids": sorted(validation_ids & prior_ids),
        "validation_prior_contexts": sorted(validation_contexts & prior_contexts),
        "validation_prior_datasets": sorted(validation_datasets & prior_datasets),
    }
    if any(overlap.values()):
        raise RuntimeError(f"Corpus-disjoint freeze blocked by overlap: {overlap}")

    selected_rows, cells = choose(
        validation,
        groups,
        lengths,
        args.per_cell,
        args.max_per_context,
        args.seed,
    )
    selected = [compact(row) for row in selected_rows]
    selected_ids = [row["id"] for row in selected]
    selected_contexts = Counter(row["context_window_id"] for row in selected)
    if len(selected_ids) != len(set(selected_ids)):
        raise RuntimeError("Duplicate selected IDs")
    if max(selected_contexts.values()) > args.max_per_context:
        raise RuntimeError("Context reuse cap violated")

    readme = data_dir.parent / "README.md"
    inventory_payload = {"validation": validation_inventory, "test": test_inventory}
    metadata = {
        "dataset": "oolongbench/oolong-synth",
        "revision": SNAPSHOT,
        "split": "validation",
        "input_contract": "standard_unlabeled_context_window_text",
        "context_variant": "standard",
        "prospective_freeze": True,
        "frozen_before_new_method_outputs": True,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "seed": args.seed,
        "groups": groups,
        "lengths": lengths,
        "per_cell": args.per_cell,
        "max_per_context_window_id": args.max_per_context,
        "source_corpus_disjoint_from_prior_project_oolong": True,
        "source_document_disjoint_claim": "unidentifiable: official schema has no source-document identifier",
        "authoritative_source_corpus_field": "dataset",
        "validation_source_corpora": sorted(validation_datasets),
        "test_source_corpora": sorted(test_datasets),
        "official_schema": EXPECTED_COLUMNS,
        "schema_has_source_document_id": False,
        "readme_sha256": sha256_bytes(readme.read_bytes()),
        "parquet_inventory_sha256": sha256_bytes(
            json.dumps(inventory_payload, sort_keys=True, separators=(",", ":")).encode()
        ),
    }
    manifest = {"metadata": metadata, "examples": selected}
    summary = {
        "metadata": metadata,
        "n": len(selected),
        "groups": dict(sorted(Counter(row["task_group"] for row in selected).items())),
        "lengths": dict(sorted(Counter(str(row["context_len"]) for row in selected).items())),
        "datasets": dict(sorted(Counter(row["dataset"] for row in selected).items())),
        "unique_context_window_ids": len(selected_contexts),
        "max_questions_per_context_window_id": max(selected_contexts.values()),
        "context_reuse_histogram": dict(sorted(Counter(selected_contexts.values()).items())),
        "universe": {
            "validation_rows": len(validation),
            "validation_contexts": len(validation_contexts),
            "test_rows": len(test),
            "test_contexts": len(test_contexts),
            "prior_ids": len(prior_ids),
            "prior_contexts": len(prior_contexts),
            "prior_artifacts": len(prior_details),
        },
        "overlap": {name: len(values) for name, values in overlap.items()},
        "cells": cells,
        "selected_ids_sha256": sha256_bytes("\n".join(selected_ids).encode()),
        "prior_inputs": prior_details,
    }

    manifest_path = ROOT / args.manifest_out
    summary_path = ROOT / args.summary_out
    md_path = ROOT / args.md_out
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    markdown = [
        "# Oolong Validation Corpus-Disjoint N=45 Freeze",
        "",
        f"- Manifest: `{manifest_path.relative_to(ROOT)}`",
        f"- Pinned revision: `{SNAPSHOT}`",
        f"- N: **{summary['n']}**",
        f"- Groups: `{summary['groups']}`",
        f"- Lengths: `{summary['lengths']}`",
        f"- Source corpora: `{summary['datasets']}`",
        f"- Unique context windows: **{summary['unique_context_window_ids']}**",
        f"- Maximum questions per context: **{summary['max_questions_per_context_window_id']}**",
        "",
        "## Disjointness",
        "",
        "The official validation split uses only `spam` and `trec_coarse`; the test split and every prior project Oolong manifest with an explicit corpus field use different corpora. Validation and test IDs and context-window IDs are also disjoint, and no validation ID/window/corpus appears in prior project Oolong artifacts. This supports a **source-corpus-disjoint** claim.",
        "",
        "The official schema has no source-document identifier. This artifact therefore does **not** claim independently verified source-document disjointness within a corpus.",
        "",
        "## Cell Availability and Selection",
        "",
        "| Cell | Candidate rows | Candidate contexts | Selected |",
        "|---|---:|---:|---:|",
    ]
    for cell, values in cells.items():
        markdown.append(
            f"| `{cell}` | {values['candidate_rows']} | {values['candidate_contexts']} | {values['selected']} |"
        )
    markdown.extend(
        [
            "",
            "## Execution Boundary",
            "",
            "This manifest was frozen before any method output on these rows. Model execution may begin only after hashes and overlap checks pass. All attempted rows, failures, costs, and stop events must remain in the denominator.",
            "",
        ]
    )
    md_path.write_text("\n".join(markdown), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ["n", "groups", "lengths", "datasets", "unique_context_window_ids", "max_questions_per_context_window_id", "overlap", "selected_ids_sha256"]}, indent=2))
    print(f"Wrote {manifest_path.relative_to(ROOT)}")
    print(f"Wrote {summary_path.relative_to(ROOT)}")
    print(f"Wrote {md_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
