#!/usr/bin/env python3
"""Freeze a deterministic T-MIXED current-contract N=30 extension manifest.

The historical matched-model T-MIXED generator used Python's salted ``hash(domain)``
inside RNG seeds. This script keeps the same domain pools and task format but
uses a stable SHA-256-derived domain offset. The resulting manifest is intended
for the current final-answer contract check: direct Gemini versus RLM with
``answer['content']`` JSON finalization.
"""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
SOURCE = ROOT / "run_tmixed_matched_model.py"
OUT_JSON = RESULTS / "tmixed_current_contract_n30_manifest_20260714.json"
OUT_CSV = RESULTS / "tmixed_current_contract_n30_manifest_20260714.csv"


def load_domain_data() -> dict[str, Any]:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "DOMAIN_DATA":
                    return ast.literal_eval(node.value)
    raise RuntimeError(f"DOMAIN_DATA assignment not found in {SOURCE}")


def stable_domain_offset(domain: str) -> int:
    return int(hashlib.sha256(domain.encode("utf-8")).hexdigest()[:8], 16) % 100


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_examples(domain_data: dict[str, Any], seeds_per_domain: int) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    for domain in sorted(domain_data):
        data = domain_data[domain]
        gold_pool = data["gold"]
        foil_pool = data["foil"]
        dist_pool = data["distractors"]
        offset = stable_domain_offset(domain)
        for seed_i in range(seeds_per_domain):
            rng = random.Random(seed_i * 100 + offset)
            n_gold = rng.choice([2, 3, 4])
            n_foil = rng.randint(1, min(2, len(foil_pool)))
            n_dist = rng.randint(2, min(4, len(dist_pool)))
            gold = rng.sample(gold_pool, min(n_gold, len(gold_pool)))
            foil = rng.sample(foil_pool, min(n_foil, len(foil_pool)))
            dist = rng.sample(dist_pool, min(n_dist, len(dist_pool)))
            passages = gold + foil + dist
            rng.shuffle(passages)
            context = "\n\n".join(f"[P{j+1:02d}] {p}" for j, p in enumerate(passages))
            examples.append(
                {
                    "example_id": f"TMIXED_CC_{domain[:8]}_{seed_i:02d}",
                    "domain": domain,
                    "seed": seed_i,
                    "stable_domain_offset": offset,
                    "query": data["query"],
                    "context": context,
                    "context_sha256": sha256_text(context),
                    "gold_count": len(gold),
                    "n_gold": len(gold),
                    "n_foil": len(foil),
                    "n_dist": len(dist),
                    "n_total": len(passages),
                }
            )
    examples.sort(key=lambda r: (r["domain"], r["seed"]))
    return examples


def main() -> int:
    domain_data = load_domain_data()
    examples = make_examples(domain_data, seeds_per_domain=15)
    domain_counts: dict[str, int] = {}
    for row in examples:
        domain_counts[row["domain"]] = domain_counts.get(row["domain"], 0) + 1

    payload = {
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "n": len(examples),
        "source": str(SOURCE.relative_to(ROOT)),
        "purpose": (
            "Deterministic T-MIXED current-contract extension. Use for direct Gemini "
            "versus repaired/content-contract RLM; do not merge with historical salted "
            "Round 22 examples without stating the generator boundary."
        ),
        "generator": {
            "historical_difference": "Uses stable sha256(domain) offset instead of Python's salted hash(domain).",
            "seeds_per_domain": 15,
            "domain_order": sorted(domain_data),
        },
        "domain_counts": domain_counts,
        "examples": examples,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    fieldnames = [
        "example_id",
        "domain",
        "seed",
        "stable_domain_offset",
        "query",
        "gold_count",
        "n_gold",
        "n_foil",
        "n_dist",
        "n_total",
        "context_sha256",
    ]
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in examples:
            writer.writerow({key: row[key] for key in fieldnames})

    print(json.dumps({"n": len(examples), "domain_counts": domain_counts}, indent=2))
    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
