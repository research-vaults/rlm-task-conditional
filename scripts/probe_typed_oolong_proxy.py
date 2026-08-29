#!/usr/bin/env python3
"""
Typed-combinator Oolong proxy for the RLM preprocessing audit.

This is a cheap, deterministic diagnostic baseline on the exact public
Oolong-synth N=80 slice used by `eval_oolong_slice.py`:

    seed=42, test split, context_len <= 8192, stratified_sample(..., n=80)

The goal is not to reproduce lambda-RLM.  It is a bounded proxy for the
mechanism question that lambda-RLM raises: does the Oolong timeline/user
advantage require open-ended RLM code generation, or can a small typed operator
library over parsed rows close the gap?

No model/API calls are made.  The script reads the local Hugging Face snapshot
if present; if absent, it falls back to `datasets.load_dataset`.
"""

from __future__ import annotations

import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_oolong_slice import (  # noqa: E402
    parse_gold,
    score_prediction,
    stratified_sample,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRIOR_CSV = PROJECT_ROOT / "results" / "oolong_rlm_faithful_n80_20260707T095020Z.csv"
OUT_CSV = PROJECT_ROOT / "results" / "typed_oolong_proxy_n80_20260711.csv"
OUT_JSON = PROJECT_ROOT / "results" / "typed_oolong_proxy_n80_20260711_summary.json"

HF_SNAPSHOT = Path(
    "<local-user-home>/.cache/huggingface/hub/datasets--oolongbench--oolong-synth/"
    "snapshots/f0d59eaf0febf130664cfceb710436c8e3216b2b/data"
)


ROW_RE = re.compile(
    r"Date:\s*(?P<date>[A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})"
    r"\s*\|\|\s*User:\s*(?P<user>\d+)"
    r"\s*\|\|\s*Instance:\s*(?P<instance>.*?)"
    r"\s*\|\|\s*Label:\s*(?P<label>[^\|\n]+)",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class Row:
    date_str: str
    date: date
    user: str
    label: str
    instance: str

    @property
    def month_key(self) -> tuple[int, int]:
        return (self.date.year, self.date.month)


def parse_date_any(text: str) -> date | None:
    text = text.strip()
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def month_name(year: int, month: int) -> str:
    return datetime(year, month, 1).strftime("%B")


def parse_rows(context: str) -> list[Row]:
    rows: list[Row] = []
    for m in ROW_RE.finditer(context):
        d = parse_date_any(m.group("date"))
        if not d:
            continue
        rows.append(
            Row(
                date_str=m.group("date").strip(),
                date=d,
                user=m.group("user").strip(),
                instance=m.group("instance").strip(),
                label=m.group("label").strip(),
            )
        )
    return rows


def normalize_label(s: str) -> str:
    return s.strip().strip("'\".").lower()


def labels_in_question(question: str) -> list[str]:
    malformed_first = re.search(
        r"label\s+'?(.+?)\s+first occur.*?label\s+'?([^']+)'?",
        question,
        flags=re.IGNORECASE,
    )
    if malformed_first:
        return [normalize_label(malformed_first.group(1)), normalize_label(malformed_first.group(2))]

    # First use proper quoted labels. This preserves labels with spaces,
    # slashes, and ampersands, e.g. "Education & Reference".
    quoted = [normalize_label(x) for x in re.findall(r"label\s+'([^']+)'", question, flags=re.IGNORECASE)]
    if len(quoted) >= 1:
        return quoted

    labels: list[str] = []
    # Fallback for unquoted labels and Oolong's occasional missing closing quote:
    #   label False:
    #   label 'neutral first occur ...
    for m in re.finditer(r"label\s+'?([A-Za-z0-9_/-]+)", question, flags=re.IGNORECASE):
        token = normalize_label(m.group(1))
        if token not in {"is", "are", "the"}:
            labels.append(token)
    if labels:
        seen = set()
        uniq = []
        for label in labels:
            if label not in seen:
                seen.add(label)
                uniq.append(label)
        return uniq
    m = re.search(r"labels?:\s*([^.\n]+)", question, flags=re.IGNORECASE)
    if not m:
        return []
    raw = m.group(1)
    parts = [normalize_label(x) for x in re.split(r",|\bor\b", raw)]
    return [p for p in parts if p]


def _users(question: str) -> list[str]:
    out: list[str] = []
    for m in re.finditer(r"\bUser\s+(\d+)\b", question, flags=re.IGNORECASE):
        out.append(m.group(1))
    for m in re.finditer(r"user IDs?\s+([0-9,\s]+)", question, flags=re.IGNORECASE):
        out.extend(re.findall(r"\d+", m.group(1)))
    # Preserve order but remove duplicates.
    seen = set()
    uniq = []
    for u in out:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq


def apply_filters(rows: list[Row], question: str) -> tuple[list[Row], list[str]]:
    q = question.lower()
    filtered = list(rows)
    ops: list[str] = []

    # Date range: "between Jul 07, 2023 and May 21, 2024, inclusive"
    m = re.search(
        r"between\s+([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})\s+and\s+"
        r"([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})",
        question,
        flags=re.IGNORECASE,
    )
    if m:
        lo, hi = parse_date_any(m.group(1)), parse_date_any(m.group(2))
        if lo and hi:
            filtered = [r for r in filtered if lo <= r.date <= hi]
            ops.append("filter_date_range")

    # Month filter: "occur in October of any year"
    m = re.search(r"occur(?:s|ing)?\s+in\s+([A-Za-z]+)\s+of any year", question, flags=re.IGNORECASE)
    if m:
        try:
            mo = datetime.strptime(m.group(1)[:3], "%b").month
            filtered = [r for r in filtered if r.date.month == mo]
            ops.append("filter_month")
        except ValueError:
            pass

    # User subset: "associated with user IDs 25751, 12345"
    if "associated with user id" in q or "associated with these user" in q:
        us = _users(question)
        if us:
            allowed = set(us)
            filtered = [r for r in filtered if r.user in allowed]
            ops.append("filter_user_subset")

    return filtered, ops


def counts_for(rows: Iterable[Row], field: str) -> Counter:
    if field == "label":
        return Counter(normalize_label(r.label) for r in rows)
    if field == "user":
        return Counter(r.user for r in rows)
    if field == "date":
        return Counter(r.date_str for r in rows)
    if field == "month":
        return Counter(r.month_key for r in rows)
    raise ValueError(field)


def arg_by_count(counts: Counter, mode: str):
    if not counts:
        return None
    items = list(counts.items())
    if mode == "max":
        best = max(v for _, v in items)
        return next(k for k, v in items if v == best)
    if mode == "min":
        best = min(v for _, v in items)
        # Match the existing fixed parser's conservative Oolong behavior:
        # Counter.most_common()[-1] selects the last observed member of a tie.
        return next(k for k, v in reversed(items) if v == best)
    if mode == "second_max":
        ranking = sorted(items, key=lambda kv: (-kv[1], str(kv[0])))
        return ranking[1][0] if len(ranking) > 1 else ranking[0][0]
    raise ValueError(mode)


def compare_counts(a: int, b: int, short: bool = False) -> str:
    if a > b:
        return "more common" if short else "more common than"
    if a < b:
        return "less common" if short else "less common than"
    return "same frequency" if short else "same frequency as"


def solve_typed(example: dict) -> tuple[str | None, list[str], str]:
    ctx = example.get("context_window_text_with_labels") or example.get("context_window_text") or ""
    rows = parse_rows(ctx)
    if not rows:
        return None, ["parse_failed"], "no_rows"

    question = example.get("question", "")
    task = example.get("task", "")
    answer_type = example.get("answer_type", "")
    q = question.lower()
    rows_f, ops = apply_filters(rows, question)

    labels = labels_in_question(question)
    users = _users(question)

    # Compare two named users by count of a label. This must run before the
    # generic "which user has most label" branch, otherwise pairwise questions
    # are incorrectly answered with the global argmax user.
    if answer_type == "ANSWER_TYPE.USER" and len(users) >= 2 and labels:
        target = labels[0]
        c = counts_for([r for r in rows_f if normalize_label(r.label) == target], "user")
        if c.get(users[0], 0) >= c.get(users[1], 0):
            return users[0], ops + ["filter_label", "compare_named_user_counts"], "user_pair_compare"
        return users[1], ops + ["filter_label", "compare_named_user_counts"], "user_pair_compare"

    # User ranked by label count: "which user has the most instances with label X?"
    if answer_type == "ANSWER_TYPE.USER" and re.search(r"which user has .*instances with (?:the )?label|which user has .*label", q):
        if labels:
            target = labels[0]
            target_rows = [r for r in rows_f if normalize_label(r.label) == target]
            user = arg_by_count(counts_for(target_rows, "user"), "max" if "most" in q or "more" in q else "min")
            return (str(user) if user else None), ops + ["filter_label", "arg_user_by_count"], "user_by_label"

    # Before/after temporal comparison for a single label.
    m = re.search(r"before\s+(\d{4}-\d{2}-\d{2}).*after\s+\1", question, flags=re.IGNORECASE)
    if "RELATIVE_FREQ" in task and m and labels:
        pivot = parse_date_any(m.group(1))
        if pivot:
            target = labels[0]
            before = sum(1 for r in rows if r.date < pivot and normalize_label(r.label) == target)
            after = sum(1 for r in rows if r.date > pivot and normalize_label(r.label) == target)
            before_total = sum(1 for r in rows if r.date < pivot)
            after_total = sum(1 for r in rows if r.date > pivot)
            before_rate = before / before_total if before_total else 0.0
            after_rate = after / after_total if after_total else 0.0
            if before_rate > after_rate:
                pred = "more common"
            elif before_rate < after_rate:
                pred = "less common"
            else:
                pred = "same frequency"
            return pred, ops + ["split_before_after", "compare_label_rates"], "before_after_label_rate"

    # First month where label A occurs more often than label B.
    if answer_type == "ANSWER_TYPE.MONTH_YEAR" and "RELATIVE_FREQ" in task and len(labels) >= 2:
        a, b = labels[0], labels[1]
        monthly: dict[tuple[int, int], Counter] = defaultdict(Counter)
        for r in rows_f:
            monthly[r.month_key][normalize_label(r.label)] += 1
        for (yr, mo) in sorted(monthly):
            if monthly[(yr, mo)].get(a, 0) > monthly[(yr, mo)].get(b, 0):
                return f"{month_name(yr, mo)} {yr}", ops + ["group_month", "first_month_gt"], "first_month_label_gt"
        return None, ops + ["group_month", "first_month_gt"], "no_month_satisfies"

    # Count months where a target label is uniquely most frequent.
    if answer_type == "ANSWER_TYPE.NUMERIC" and re.search(r"for how many months .*single most", q) and labels:
        target = labels[0]
        monthly: dict[tuple[int, int], Counter] = defaultdict(Counter)
        for r in rows_f:
            monthly[r.month_key][normalize_label(r.label)] += 1
        n = 0
        for cnt in monthly.values():
            if not cnt:
                continue
            max_v = max(cnt.values())
            winners = [k for k, v in cnt.items() if v == max_v]
            if len(winners) == 1 and winners[0] == target:
                n += 1
        return str(n), ops + ["group_month", "count_unique_monthly_winner"], "months_single_most"

    # Count months where label A occurs more frequently than label B.
    if (
        answer_type == "ANSWER_TYPE.NUMERIC"
        and "RELATIVE_FREQ" in task
        and re.search(r"for how many months .* occur more frequently than", q)
        and len(labels) >= 2
    ):
        a, b = labels[0], labels[1]
        monthly: dict[tuple[int, int], Counter] = defaultdict(Counter)
        for r in rows_f:
            monthly[r.month_key][normalize_label(r.label)] += 1
        n = sum(1 for cnt in monthly.values() if cnt.get(a, 0) > cnt.get(b, 0))
        return str(n), ops + ["group_month", "count_months_label_gt"], "months_label_gt"

    # Generic label frequency tasks after optional typed filters.
    if answer_type == "ANSWER_TYPE.LABEL":
        cnt = counts_for(rows_f, "label")
        if "SECOND_MOST_FREQ" in task:
            v = arg_by_count(cnt, "second_max")
            return (str(v) if v else None), ops + ["count_label", "second_argmax"], "label_second_most"
        if "MOST_FREQ" in task:
            v = arg_by_count(cnt, "max")
            return (str(v) if v else None), ops + ["count_label", "argmax"], "label_most"
        if "LEAST_FREQ" in task:
            v = arg_by_count(cnt, "min")
            return (str(v) if v else None), ops + ["count_label", "argmin"], "label_least"

    if answer_type == "ANSWER_TYPE.NUMERIC":
        if "NUMERIC_ONE_CLASS" in task and labels:
            target = labels[0]
            return str(sum(1 for r in rows_f if normalize_label(r.label) == target)), ops + ["filter_label", "count"], "numeric_label_count"
        if "REPRESENTED_N_TIMES" in task:
            m_n = re.search(r"exactly\s+(\d+)\s+time", question, flags=re.IGNORECASE)
            n = int(m_n.group(1)) if m_n else 1
            field = "date" if "date" in q else "user" if "user" in q else "label"
            cnt = counts_for(rows_f, field)
            return str(sum(1 for v in cnt.values() if v == n)), ops + [f"count_{field}", "count_values_with_frequency_n"], "represented_n"

    if answer_type == "ANSWER_TYPE.COMPARISON" and "RELATIVE_FREQ" in task and len(labels) >= 2:
        cnt = counts_for(rows_f, "label")
        short = "before" in q and "after" in q
        return compare_counts(cnt.get(labels[0], 0), cnt.get(labels[1], 0), short=short), ops + ["count_label", "compare"], "label_compare"

    if answer_type == "ANSWER_TYPE.USER":
        cnt = counts_for(rows_f, "user")
        if "SECOND_MOST_FREQ" in task:
            v = arg_by_count(cnt, "second_max")
            return (str(v) if v else None), ops + ["count_user", "second_argmax"], "user_second_most"
        if "MOST_FREQ" in task:
            v = arg_by_count(cnt, "max")
            return (str(v) if v else None), ops + ["count_user", "argmax"], "user_most"
        if "LEAST_FREQ" in task:
            v = arg_by_count(cnt, "min")
            return (str(v) if v else None), ops + ["count_user", "argmin"], "user_least"

    if answer_type == "ANSWER_TYPE.DATE":
        cnt = counts_for(rows_f, "date")
        if "SECOND_MOST_FREQ" in task:
            v = arg_by_count(cnt, "second_max")
            return (str(v) if v else None), ops + ["count_date", "second_argmax"], "date_second_most"
        if "MOST_FREQ" in task:
            v = arg_by_count(cnt, "max")
            return (str(v) if v else None), ops + ["count_date", "argmax"], "date_most"
        if "LEAST_FREQ" in task:
            v = arg_by_count(cnt, "min")
            return (str(v) if v else None), ops + ["count_date", "argmin"], "date_least"

    return None, ops + ["unsupported"], "unsupported"


def load_test_metadata() -> list[dict]:
    if HF_SNAPSHOT.exists() and list(HF_SNAPSHOT.glob("test-*.parquet")):
        rows: list[dict] = []
        cols = [
            "id",
            "context_len",
            "dataset",
            "question",
            "task_group",
            "task",
            "answer_type",
            "answer",
        ]
        for p in sorted(HF_SNAPSHOT.glob("test-*.parquet")):
            rows.extend(pq.read_table(p, columns=cols).to_pylist())
        return rows

    from datasets import load_dataset

    return [
        {
            "id": x["id"],
            "context_len": x["context_len"],
            "dataset": x.get("dataset", ""),
            "question": x["question"],
            "task_group": x["task_group"],
            "task": x["task"],
            "answer_type": x["answer_type"],
            "answer": x["answer"],
        }
        for x in load_dataset("oolongbench/oolong-synth", split="test")
    ]


def hydrate_selected_examples(selected_meta: list[dict], split: str = "test") -> list[dict]:
    """Load context columns only for selected IDs from an explicit Oolong split."""
    if split not in {"test", "validation"}:
        raise ValueError(f"Unsupported Oolong split: {split!r}")
    selected_ids = {str(x["id"]) for x in selected_meta}
    meta_by_id = {str(x["id"]): dict(x) for x in selected_meta}

    if HF_SNAPSHOT.exists() and list(HF_SNAPSHOT.glob(f"{split}-*.parquet")):
        context_cols = ["id", "context_window_text", "context_window_text_with_labels"]
        for p in sorted(HF_SNAPSHOT.glob(f"{split}-*.parquet")):
            try:
                table = pq.read_table(
                    p,
                    columns=context_cols,
                    filters=[("id", "in", list(selected_ids))],
                )
            except Exception:
                table = pq.read_table(p, columns=context_cols)
            for row in table.to_pylist():
                eid = str(row["id"])
                if eid in meta_by_id:
                    meta_by_id[eid].update(row)
        missing = [eid for eid, ex in meta_by_id.items() if "context_window_text_with_labels" not in ex]
        if missing:
            raise RuntimeError(f"Could not hydrate selected Oolong contexts: {missing[:5]}")
        return [meta_by_id[str(x["id"])] for x in selected_meta]

    from datasets import load_dataset

    ds = load_dataset("oolongbench/oolong-synth", split=split)
    for x in ds:
        eid = str(x["id"])
        if eid in meta_by_id:
            meta_by_id[eid].update(dict(x))
    return [meta_by_id[str(x["id"])] for x in selected_meta]


def wilson(k: float, n: int, z: float = 1.96) -> tuple[float, float, float]:
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return p, max(0.0, center - margin), min(1.0, center + margin)


def summarize(rows: list[dict], prior_rows: list[dict]) -> dict:
    methods = ["typed_proxy", "rlm", "fixed_python", "slm_direct", "slm_cot"]
    prior = {(r["example_id"], r["method"]): r for r in prior_rows}
    typed = {r["example_id"]: r for r in rows}

    by_method: dict[str, list[float]] = defaultdict(list)
    by_group: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for eid, row in typed.items():
        by_method["typed_proxy"].append(float(row["correct"]))
        by_group[row["task_group"]]["typed_proxy"].append(float(row["correct"]))
        for m in methods[1:]:
            pr = prior.get((eid, m))
            if pr is not None:
                by_method[m].append(float(pr["correct"]))
                by_group[row["task_group"]][m].append(float(pr["correct"]))

    def pack(vals: list[float]) -> dict:
        k = sum(vals)
        n = len(vals)
        p, lo, hi = wilson(k, n)
        return {"score_sum": round(k, 4), "n": n, "accuracy": p, "ci95": [lo, hi]}

    out = {
        "metadata": {
            "slice": "oolongbench/oolong-synth test, context_len<=8192, n=80, seed=42",
            "method": "typed_proxy deterministic typed-combinator library; no model/API calls",
            "prior_csv": str(PRIOR_CSV.relative_to(PROJECT_ROOT)),
            "output_csv": str(OUT_CSV.relative_to(PROJECT_ROOT)),
        },
        "overall": {m: pack(by_method[m]) for m in methods},
        "by_group": {
            g: {m: pack(vals) for m, vals in sorted(mm.items())}
            for g, mm in sorted(by_group.items())
        },
        "typed_solver_status": dict(Counter(r["status"] for r in rows)),
        "typed_solver_ops": dict(Counter(op for r in rows for op in json.loads(r["operators"]))),
    }

    # Paired exact-score deltas, using Oolong partial score.
    paired = {}
    for m in methods[1:]:
        diffs = []
        for eid, row in typed.items():
            pr = prior.get((eid, m))
            if pr:
                diffs.append(float(row["correct"]) - float(pr["correct"]))
        paired[m] = {
            "mean_score_delta_typed_minus_method": sum(diffs) / len(diffs),
            "n": len(diffs),
        }
    out["paired_deltas"] = paired
    return out


def main() -> None:
    prior_rows = list(csv.DictReader(PRIOR_CSV.open()))
    prior_ids = [r["example_id"] for r in prior_rows if r["method"] == "rlm"]

    all_rows = [r for r in load_test_metadata() if int(r["context_len"]) <= 8192]
    selected_meta = stratified_sample(all_rows, 80, 42)
    examples = hydrate_selected_examples(selected_meta)
    ids = [str(ex["id"]) for ex in examples]
    if ids != prior_ids:
        raise RuntimeError("Sample mismatch against prior Oolong CSV; refusing to compare.")

    fieldnames = [
        "example_id",
        "context_len",
        "task_group",
        "task",
        "answer_type",
        "method",
        "prediction",
        "gold",
        "correct",
        "cost_usd",
        "status",
        "operators",
        "question",
    ]

    out_rows: list[dict] = []
    for ex in examples:
        pred, ops, status = solve_typed(ex)
        gold = parse_gold(ex.get("answer", ""), ex.get("answer_type", ""))
        score = score_prediction("" if pred is None else pred, gold, ex.get("answer_type", ""))
        out_rows.append(
            {
                "example_id": str(ex["id"]),
                "context_len": ex["context_len"],
                "task_group": ex["task_group"],
                "task": ex["task"],
                "answer_type": ex["answer_type"],
                "method": "typed_proxy",
                "prediction": "" if pred is None else str(pred),
                "gold": str(gold),
                "correct": round(score, 4),
                "cost_usd": 0.0,
                "status": status,
                "operators": json.dumps(ops),
                "question": ex["question"],
            }
        )

    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    summary = summarize(out_rows, prior_rows)
    OUT_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary["overall"], indent=2))
    print("\nBy group:")
    print(json.dumps(summary["by_group"], indent=2))
    print(f"\nWrote {OUT_CSV}")
    print(f"Wrote {OUT_JSON}")


if __name__ == "__main__":
    main()
