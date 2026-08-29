#!/usr/bin/env python3
"""Compute parameterized engineering-cost break-even thresholds from frozen runs."""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
OUT_JSON = RESULTS / "engineering_break_even_20260722.json"
OUT_CSV = RESULTS / "engineering_break_even_20260722.csv"
OUT_MD = RESULTS / "engineering_break_even_20260722.md"

ASSUMED_BUDGETS_USD = (100, 1_000, 10_000)


def load_json(name: str) -> dict:
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


def scenario(label: str, source: str, n: int, rlm_cost: float, typed_cost: float) -> dict:
    savings = (rlm_cost - typed_cost) / n
    if savings <= 0:
        raise ValueError(f"Expected positive per-case savings for {label}: {savings}")
    return {
        "label": label,
        "source": source,
        "n": n,
        "standard_rlm_cost_usd": rlm_cost,
        "slm_typed_cost_usd": typed_cost,
        "observed_api_savings_per_case_usd": savings,
        "break_even_cases": {
            str(budget): math.ceil(budget / savings) for budget in ASSUMED_BUDGETS_USD
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "_reproduced" / "engineering_break_even",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out_json = args.output_dir / OUT_JSON.name
    out_csv = args.output_dir / OUT_CSV.name
    out_md = args.output_dir / OUT_MD.name

    su = load_json("oolong_standard_validation_n150_threeway_analysis_20260714.json")
    vc = load_json("oolong_validation_corpus_disjoint_n45_threeway_20260721.json")

    rows = [
        scenario(
            "SU-150 method-lock replication",
            "results/oolong_standard_validation_n150_threeway_analysis_20260714.json",
            int(su["overall"]["standard_rlm"]["n"]),
            float(su["overall"]["standard_rlm"]["cost_usd"]),
            float(su["overall"]["slm_qparsed_typed"]["cost_usd"]),
        ),
        scenario(
            "VC-45 unseen-corpus replication",
            "results/oolong_validation_corpus_disjoint_n45_threeway_20260721.json",
            int(vc["overall"]["standard_rlm"]["n"]),
            float(vc["overall"]["standard_rlm"]["cost_usd"]),
            float(vc["overall"]["slm_typed"]["cost_usd"]),
        ),
    ]

    payload = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "analysis_type": "parameterized_api_savings_break_even",
        "assumed_one_time_engineering_budgets_usd": list(ASSUMED_BUDGETS_USD),
        "formula": "ceil(assumed_one_time_engineering_budget_usd / observed_api_savings_per_case_usd)",
        "scenarios": rows,
        "interpretation_boundary": [
            "The assumed budgets are sensitivity parameters, not measured labor or maintenance costs.",
            "Thresholds equal ceil(budget / unrounded observed API savings per case).",
            "Thresholds use observed successful-completion API costs and do not include failed-call billing, latency value, maintenance, or reliability differences.",
            "SU-150 reuses earlier context windows; VC-45 transfers to unseen source corpora but is not document-disjoint.",
            "The calculation addresses amortization of API savings only and is not a total-cost-of-ownership estimate.",
        ],
    }
    out_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    with out_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "label",
                "n",
                "standard_rlm_cost_usd",
                "slm_typed_cost_usd",
                "observed_api_savings_per_case_usd",
                "assumed_engineering_budget_usd",
                "break_even_cases",
            ],
        )
        writer.writeheader()
        for row in rows:
            for budget in ASSUMED_BUDGETS_USD:
                writer.writerow(
                    {
                        "label": row["label"],
                        "n": row["n"],
                        "standard_rlm_cost_usd": row["standard_rlm_cost_usd"],
                        "slm_typed_cost_usd": row["slm_typed_cost_usd"],
                        "observed_api_savings_per_case_usd": row["observed_api_savings_per_case_usd"],
                        "assumed_engineering_budget_usd": budget,
                        "break_even_cases": row["break_even_cases"][str(budget)],
                    }
                )

    md = [
        "# Parameterized Engineering-Cost Break-Even Audit",
        "",
        "This deterministic analysis converts frozen per-case API-cost differences into the number of cases needed to amortize an assumed one-time engineering budget. The budgets are sensitivity parameters, not measured labor or total cost of ownership.",
        "",
        "Formula: `ceil(budget / unrounded observed API savings per case)`. Displayed savings are rounded only for presentation.",
        "",
        "| Evidence row | API savings/case | $100 budget | $1,000 budget | $10,000 budget |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        be = row["break_even_cases"]
        md.append(
            f"| {row['label']} | ${row['observed_api_savings_per_case_usd']:.6f} | "
            f"{be['100']:,} | {be['1000']:,} | {be['10000']:,} |"
        )
    md.extend(
        [
            "",
            "Interpretation: observed API savings alone amortize even a modest implementation budget only at nontrivial deployment volume. This qualifies the marginal-cost comparison rather than estimating engineering labor.",
            "",
            "Boundaries: successful-completion costs only; no failed-call billing, latency valuation, maintenance, reliability valuation, or human labor estimate. SU-150 is method-lock evidence with reused windows. VC-45 is source-corpus transfer without document-level independence.",
        ]
    )
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"outputs": [str(out_json), str(out_csv), str(out_md)], "scenarios": rows}, indent=2))


if __name__ == "__main__":
    main()
