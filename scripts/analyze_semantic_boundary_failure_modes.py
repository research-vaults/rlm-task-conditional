#!/usr/bin/env python3
"""No-call failure-mode analysis for the semantic-boundary diagnostics.

This script combines the project-generated paraphrase slice and the public
HotpotQA support-fact slice. It adds reviewer-readable failure decomposition
without making new model calls or changing any benchmark denominator.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]

HOTPOT_METHODS = [
    "tfidf_top2",
    "llm_generated_lexical_operator",
    "slm_tfidf_reranker",
    "slm_direct",
    "llm_direct",
]
PARAPHRASE_METHODS = [
    "literal_operator",
    "llm_generated_lexical_operator",
    "slm_worker_labels",
    "slm_direct",
    "llm_direct",
]

METHOD_LABELS = {
    "tfidf_top2": "TF-IDF",
    "literal_operator": "Literal",
    "llm_generated_lexical_operator": "LLM lex.",
    "slm_tfidf_reranker": "G. rerank",
    "slm_worker_labels": "G. worker",
    "slm_direct": "G. direct",
    "llm_direct": "Gemini",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def precision_lt_one(row: dict[str, Any]) -> bool:
    return float(row.get("evidence_precision", 0.0)) < 0.999


def recall_lt_one(row: dict[str, Any]) -> bool:
    return float(row.get("evidence_recall", 0.0)) < 0.999


def summarize_hotpot(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_method[row["method"]].append(row)

    out: dict[str, dict[str, Any]] = {}
    for method in HOTPOT_METHODS:
        items = by_method[method]
        counters = Counter()
        for row in items:
            if row["support_exact"]:
                counters["support_exact"] += 1
            if row["answer_correct"]:
                counters["answer_correct"] += 1
            if recall_lt_one(row):
                counters["missed_gold_evidence"] += 1
            if precision_lt_one(row):
                counters["extra_non_gold_evidence"] += 1
            if float(row.get("selected_context_recall", 1.0)) < 0.999:
                counters["candidate_recall_miss"] += 1
            if row["answer_correct"] and not row["support_exact"]:
                counters["answer_correct_support_wrong"] += 1
            if (not row["answer_correct"]) and row["support_exact"]:
                counters["answer_wrong_support_exact"] += 1
        n = len(items)
        out[method] = {
            "n": n,
            "support_exact": counters["support_exact"],
            "support_exact_rate": round(counters["support_exact"] / n, 6) if n else 0.0,
            "answer_correct": counters["answer_correct"],
            "answer_accuracy": round(counters["answer_correct"] / n, 6) if n else 0.0,
            "missed_gold_evidence": counters["missed_gold_evidence"],
            "extra_non_gold_evidence": counters["extra_non_gold_evidence"],
            "candidate_recall_miss": counters["candidate_recall_miss"],
            "answer_correct_support_wrong": counters["answer_correct_support_wrong"],
            "answer_wrong_support_exact": counters["answer_wrong_support_exact"],
            "mean_evidence_f1": round(sum(float(row["evidence_f1"]) for row in items) / n, 6) if n else 0.0,
            "cost_usd": round(sum(float(row["cost_usd"]) for row in items), 9),
        }
    return out


def summarize_paraphrase(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_method[row["method"]].append(row)

    out: dict[str, dict[str, Any]] = {}
    for method in PARAPHRASE_METHODS:
        items = by_method[method]
        counters = Counter()
        for row in items:
            if row["correct_count"]:
                counters["exact_count"] += 1
            delta = int(row["prediction"]) - int(row["gold_count"])
            if delta > 0:
                counters["overcount"] += 1
            elif delta < 0:
                counters["undercount"] += 1
            if recall_lt_one(row):
                counters["missed_gold_evidence"] += 1
            if precision_lt_one(row):
                counters["extra_non_gold_evidence"] += 1
        n = len(items)
        out[method] = {
            "n": n,
            "exact_count": counters["exact_count"],
            "exact_rate": round(counters["exact_count"] / n, 6) if n else 0.0,
            "overcount": counters["overcount"],
            "undercount": counters["undercount"],
            "missed_gold_evidence": counters["missed_gold_evidence"],
            "extra_non_gold_evidence": counters["extra_non_gold_evidence"],
            "mean_evidence_f1": round(sum(float(row["evidence_f1"]) for row in items) / n, 6) if n else 0.0,
            "cost_usd": round(sum(float(row["cost_usd"]) for row in items), 9),
        }
    return out


def by_example(rows: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    out: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        out[row["example_id"]][row["method"]] = row
    return out


def build_cases(hotpot_rows: list[dict[str, Any]], paraphrase_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    hotpot = by_example(hotpot_rows)
    paraphrase = by_example(paraphrase_rows)

    for eid, methods in hotpot.items():
        lexical = methods["llm_generated_lexical_operator"]
        direct = methods["llm_direct"]
        if (not lexical["support_exact"]) and precision_lt_one(lexical) and direct["support_exact"]:
            cases.append(
                {
                    "case_type": "Hotpot lexical false-positive filter",
                    "example_id": eid,
                    "question": lexical["question"],
                    "gold": ",".join(lexical["gold_ids"]),
                    "method_a": "llm_generated_lexical_operator",
                    "method_a_prediction": ",".join(lexical["prediction_ids"]),
                    "method_b": "llm_direct",
                    "method_b_prediction": ",".join(direct["prediction_ids"]),
                    "lesson": "Generated lexical include/exclude phrases can select adjacent non-gold support even when a direct semantic reader selects the exact support set.",
                }
            )
            break

    for eid, methods in hotpot.items():
        rerank = methods["slm_tfidf_reranker"]
        direct = methods["llm_direct"]
        if float(rerank.get("selected_context_recall", 1.0)) < 0.999 and direct["support_exact"]:
            cases.append(
                {
                    "case_type": "Hotpot candidate-recall bottleneck",
                    "example_id": eid,
                    "question": rerank["question"],
                    "gold": ",".join(rerank["gold_ids"]),
                    "method_a": "slm_tfidf_reranker",
                    "method_a_prediction": ",".join(rerank["prediction_ids"]),
                    "method_b": "llm_direct",
                    "method_b_prediction": ",".join(direct["prediction_ids"]),
                    "lesson": "Cheap semantic reranking cannot recover gold evidence absent from the candidate set; retrieval recall is a first-order mechanism.",
                }
            )
            break

    for eid, methods in paraphrase.items():
        lexical = methods["llm_generated_lexical_operator"]
        slm = methods["slm_direct"]
        if (not lexical["correct_count"]) and int(lexical["prediction"]) > int(lexical["gold_count"]) and slm["correct_count"]:
            cases.append(
                {
                    "case_type": "Paraphrase lexical overcount",
                    "example_id": eid,
                    "question": lexical["question"],
                    "gold": str(lexical["gold_count"]),
                    "method_a": "llm_generated_lexical_operator",
                    "method_a_prediction": str(lexical["prediction"]),
                    "method_b": "slm_direct",
                    "method_b_prediction": str(slm["prediction"]),
                    "lesson": "Lexical operators overcount semantically adjacent distractors; cheap semantic reading can preserve the intended criterion.",
                }
            )
            break

    for eid, methods in paraphrase.items():
        worker = methods["slm_worker_labels"]
        direct = methods["slm_direct"]
        if worker["correct_count"] and direct["correct_count"]:
            cases.append(
                {
                    "case_type": "Paraphrase SLM direct/worker agreement",
                    "example_id": eid,
                    "question": worker["question"],
                    "gold": str(worker["gold_count"]),
                    "method_a": "slm_worker_labels",
                    "method_a_prediction": str(worker["prediction"]),
                    "method_b": "slm_direct",
                    "method_b_prediction": str(direct["prediction"]),
                    "lesson": "For local semantic interpretation, direct SLM reading and SLM worker labeling often agree without dynamic program generation.",
                }
            )
            break

    return cases


def write_summary_csv(path: Path, hotpot: dict[str, dict[str, Any]], paraphrase: dict[str, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "diagnostic",
        "method",
        "n",
        "primary_exact",
        "primary_exact_rate",
        "mean_evidence_f1",
        "cost_usd",
        "missed_gold_evidence",
        "extra_non_gold_evidence",
        "candidate_recall_miss",
        "overcount",
        "undercount",
        "answer_correct",
        "answer_correct_support_wrong",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for method in HOTPOT_METHODS:
            row = hotpot[method]
            writer.writerow(
                {
                    "diagnostic": "HotpotQA support facts",
                    "method": method,
                    "n": row["n"],
                    "primary_exact": row["support_exact"],
                    "primary_exact_rate": row["support_exact_rate"],
                    "mean_evidence_f1": row["mean_evidence_f1"],
                    "cost_usd": row["cost_usd"],
                    "missed_gold_evidence": row["missed_gold_evidence"],
                    "extra_non_gold_evidence": row["extra_non_gold_evidence"],
                    "candidate_recall_miss": row["candidate_recall_miss"],
                    "overcount": "",
                    "undercount": "",
                    "answer_correct": row["answer_correct"],
                    "answer_correct_support_wrong": row["answer_correct_support_wrong"],
                }
            )
        for method in PARAPHRASE_METHODS:
            row = paraphrase[method]
            writer.writerow(
                {
                    "diagnostic": "Paraphrase semantic counting",
                    "method": method,
                    "n": row["n"],
                    "primary_exact": row["exact_count"],
                    "primary_exact_rate": row["exact_rate"],
                    "mean_evidence_f1": row["mean_evidence_f1"],
                    "cost_usd": row["cost_usd"],
                    "missed_gold_evidence": row["missed_gold_evidence"],
                    "extra_non_gold_evidence": row["extra_non_gold_evidence"],
                    "candidate_recall_miss": "",
                    "overcount": row["overcount"],
                    "undercount": row["undercount"],
                    "answer_correct": "",
                    "answer_correct_support_wrong": "",
                }
            )


def write_cases_csv(path: Path, cases: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "case_type",
        "example_id",
        "question",
        "gold",
        "method_a",
        "method_a_prediction",
        "method_b",
        "method_b_prediction",
        "lesson",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(cases)


FIGURE_FONT = "BoundaryFigureSans"
FIGURE_FONT_BOLD = "BoundaryFigureSans-Bold"


def register_figure_fonts() -> None:
    def register(font_name: str, afm_name: str, pfb_name: str) -> None:
        afm_path = subprocess.check_output(["kpsewhich", afm_name], text=True).strip()
        pfb_path = subprocess.check_output(["kpsewhich", pfb_name], text=True).strip()
        if not afm_path or not pfb_path:
            raise FileNotFoundError(f"TeX Type-1 font files not found: {afm_name}, {pfb_name}")
        face = pdfmetrics.EmbeddedType1Face(afm_path, pfb_path)
        pdfmetrics.registerTypeFace(face)
        pdfmetrics.registerFont(pdfmetrics.Font(font_name, face.name, "WinAnsiEncoding"))

    register(FIGURE_FONT, "qhvr.afm", "qhvr.pfb")
    register(FIGURE_FONT_BOLD, "qhvb.afm", "qhvb.pfb")


def draw_panel(
    c: canvas.Canvas,
    x: float,
    y: float,
    plot_w: float,
    title: str,
    methods: list[str],
    data: dict[str, dict[str, Any]],
    keys: list[tuple[str, str, colors.Color]],
) -> None:
    group_w = plot_w / len(methods)
    bar_w = 5.8
    gap = 1.2
    plot_h = 35
    max_v = 24
    c.setFillColor(colors.black)
    c.setFont(FIGURE_FONT_BOLD, 9.5)
    c.drawString(x, y + plot_h + 43, title)

    for index, (_key, label, color) in enumerate(keys):
        legend_x = x + (index % 2) * (plot_w / 2)
        legend_y = y + plot_h + 28 - (index // 2) * 11
        c.setFillColor(color)
        c.rect(legend_x, legend_y - 1, 7, 7, fill=1, stroke=0)
        c.setFillColor(colors.black)
        c.setFont(FIGURE_FONT, 6.5)
        c.drawString(legend_x + 10, legend_y, label)

    c.setStrokeColor(colors.lightgrey)
    c.setLineWidth(0.4)
    for tick in range(0, 25, 6):
        ty = y + (tick / max_v) * plot_h
        c.line(x, ty, x + plot_w, ty)
        c.setFillColor(colors.black)
        c.setFont(FIGURE_FONT, 6.5)
        c.drawRightString(x - 5, ty - 2, str(tick))
    c.saveState()
    c.translate(x - 24, y + plot_h / 2)
    c.rotate(90)
    c.setFont(FIGURE_FONT, 6.5)
    c.drawCentredString(0, 0, "Rows (of 24)")
    c.restoreState()

    cluster_w = len(keys) * bar_w + (len(keys) - 1) * gap
    for i, method in enumerate(methods):
        gx = x + i * group_w + (group_w - cluster_w) / 2
        for j, (key, _label, color) in enumerate(keys):
            value = int(data[method].get(key, 0))
            h = (value / max_v) * plot_h
            bx = gx + j * (bar_w + gap)
            c.setFillColor(color)
            c.rect(bx, y, bar_w, h, fill=1, stroke=0)
            c.setFillColor(colors.black)
            c.setFont(FIGURE_FONT, 6.2)
            c.drawCentredString(bx + bar_w / 2, y + h + 2 + (j % 2) * 5, str(value))
        c.setFillColor(colors.black)
        c.setFont(FIGURE_FONT, 6.5)
        c.drawCentredString(x + (i + 0.5) * group_w, y - 13, METHOD_LABELS[method])


def draw_pdf(path: Path, hotpot: dict[str, dict[str, Any]], paraphrase: dict[str, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    register_figure_fonts()
    width, height = 228, 224  # 3.17 x 3.11 inches at final single-column placement.
    c = canvas.Canvas(
        str(path),
        pagesize=(width, height),
        initialFontName=FIGURE_FONT,
        initialFontSize=6.5,
    )
    margin = 30
    hotpot_keys = [
        ("support_exact", "exact", colors.HexColor("#4C78A8")),
        ("missed_gold_evidence", "missed gold", colors.HexColor("#F58518")),
        ("extra_non_gold_evidence", "extra evidence", colors.HexColor("#E45756")),
        ("candidate_recall_miss", "candidate miss", colors.HexColor("#72B7B2")),
    ]
    paraphrase_keys = [
        ("exact_count", "exact", colors.HexColor("#4C78A8")),
        ("overcount", "overcount", colors.HexColor("#F58518")),
        ("undercount", "undercount", colors.HexColor("#E45756")),
        ("extra_non_gold_evidence", "extra evidence", colors.HexColor("#72B7B2")),
    ]
    plot_w = width - 2 * margin
    draw_panel(c, margin, 136, plot_w, "(a) HotpotQA support facts", HOTPOT_METHODS, hotpot, hotpot_keys)
    draw_panel(c, margin, 18, plot_w, "(b) Paraphrase counting", PARAPHRASE_METHODS, paraphrase, paraphrase_keys)
    c.save()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--hotpot-results",
        type=Path,
        default=ROOT / "results/hotpotqa_public_semantic_n24_20260713_results.jsonl",
    )
    parser.add_argument(
        "--paraphrase-results",
        type=Path,
        default=ROOT / "results/semantic_paraphrase_longcontext_n24_20260713_results.jsonl",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=ROOT / "results/semantic_boundary_failure_modes_20260713.json",
    )
    parser.add_argument(
        "--table-out",
        type=Path,
        default=ROOT / "results/semantic_boundary_failure_modes_20260713_table.csv",
    )
    parser.add_argument(
        "--cases-out",
        type=Path,
        default=ROOT / "results/semantic_boundary_failure_modes_20260713_cases.csv",
    )
    parser.add_argument(
        "--figure-out",
        type=Path,
        default=ROOT / "figures/semantic_boundary_failure_modes_20260713.pdf",
    )
    args = parser.parse_args()

    required_inputs = (args.hotpot_results, args.paraphrase_results)
    missing_inputs = [path for path in required_inputs if not path.exists()]
    if missing_inputs:
        print("LOCAL_ONLY: required upstream rows are intentionally withheld from the anonymous release.")
        for path in missing_inputs:
            display = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
            print(f"  withheld input: {display}")
        print("Run `python3 verify_release.py` for public aggregate verification.")
        return 2
    hotpot_rows = read_jsonl(args.hotpot_results)
    paraphrase_rows = read_jsonl(args.paraphrase_results)
    hotpot = summarize_hotpot(hotpot_rows)
    paraphrase = summarize_paraphrase(paraphrase_rows)
    cases = build_cases(hotpot_rows, paraphrase_rows)

    analysis = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "note": "No-call failure-mode analysis over frozen semantic-boundary diagnostics; not a new model run.",
        "source_results": {
            "hotpotqa": str(args.hotpot_results.relative_to(ROOT)),
            "semantic_paraphrase": str(args.paraphrase_results.relative_to(ROOT)),
        },
        "hotpotqa_support_fact_failure_modes": hotpot,
        "semantic_paraphrase_failure_modes": paraphrase,
        "representative_cases": cases,
        "interpretation": {
            "public_semantic_boundary": (
                "On HotpotQA, frontier direct reading is strongest, but cheap Gemma direct remains answer-useful; "
                "lexical filters and candidate-limited reranking expose distinct evidence-selection bottlenecks."
            ),
            "paraphrase_boundary": (
                "On generated paraphrase counting, Gemma direct/worker paths beat lexical/programmatic filters, "
                "whose main error is overcounting semantically adjacent distractors."
            ),
            "paper_claim": (
                "This supports a task-conditioned primitive choice: semantic retrieval or SLM semantic workers for semantic evidence, "
                "typed deterministic operators for known aggregation, and RLM fallback when no task-appropriate harness exists."
            ),
        },
    }
    args.json_out.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    write_summary_csv(args.table_out, hotpot, paraphrase)
    write_cases_csv(args.cases_out, cases)
    draw_pdf(args.figure_out, hotpot, paraphrase)
    print(json.dumps({"hotpotqa": hotpot, "semantic_paraphrase": paraphrase, "cases": len(cases)}, indent=2))
    print(f"Wrote {args.json_out}")
    print(f"Wrote {args.table_out}")
    print(f"Wrote {args.cases_out}")
    print(f"Wrote {args.figure_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
