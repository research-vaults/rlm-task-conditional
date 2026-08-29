"""
eval_oolong_slice.py
====================
Evaluation script comparing four methods on a slice of the Oolong-synth benchmark
(arXiv:2511.02817, github.com/abertsch72/oolong).

WHAT WE'RE COMPARING
--------------------
Method 1 – Official RLM scaffold
    Uses the `rlm` library (v0.1.3, package name "rlms" on PyPI).
    RLM spawns a Python REPL where the context is available as a variable;
    the model iteratively writes and executes code, calls sub-LLMs, and submits
    a final answer.  This is the "Recursive Language Model" baseline from the paper.

Method 2 – Fixed Python aggregator (T-STRUCT equivalent)
    A deterministic, regex-based extractor that parses the structured rows in the
    Oolong context (Date / User / Label columns) and computes the answer with
    standard Python (Counter, sorted, etc.).  Falls back to an SLM call if parsing
    yields no rows.  This is the "fixed operator" control: no learned reasoning,
    just correct structure exploitation.

Method 3 – SLM direct inference
    A single-shot API call to a large SLM (Gemma-4 27B via OpenRouter, or any
    Claude / GPT-4o compatible model).  Context + question are packed into one
    prompt.  No chain-of-thought, no code execution.

Method 4 – SLM + CoT calibrated
    Same single-shot call but with an explicit chain-of-thought instruction and
    a calibration suffix that asks the model to enumerate counts before answering.
    This is the "reasoning elicitation" ablation.

WHY THESE FOUR?
---------------
We want to isolate the contribution of (a) recursive code execution vs. a single
LLM call, and (b) deterministic aggregation vs. learned aggregation, on the exact
style of long-document counting/aggregation tasks that Oolong was designed to
stress-test.  Methods 1 vs 3 isolates RLM scaffolding.  Methods 2 vs 3 isolates
deterministic preprocessing.  Methods 3 vs 4 isolates CoT elicitation.

REQUIREMENTS
------------
    pip install rlms datasets anthropic openai python-dotenv dateutil

CREDENTIALS
-----------
Set one of the following environment variables (or place them in a .env file
alongside this script):

    OPENROUTER_API_KEY   – used for Methods 3 and 4 (SLM calls)
    ANTHROPIC_API_KEY    – used for the RLM backend if you choose "anthropic"

    # To use OpenAI or Anthropic as the RLM backend, also set:
    OPENAI_API_KEY       – for "openai" RLM backend

RUNNING
-------
    python eval_oolong_slice.py [--n 80] [--seed 42] [--out results.csv]
                                [--rlm-backend anthropic]
                                [--rlm-model claude-sonnet-4-6]
                                [--slm-model google/gemma-4-27b-it]

    --n             Number of examples to evaluate (default 80, max 500)
    --seed          Random seed for reproducible stratified sampling (default 42)
    --out           Output CSV path (default: oolong_slice_results.csv)
    --rlm-backend   RLM client backend: "anthropic", "openai", "openrouter" (default: anthropic)
    --rlm-model     Model for the RLM (default: claude-sonnet-4-6)
    --slm-model     Model for Methods 3 and 4 via OpenRouter (default: google/gemma-4-27b-it)
    --max-ctx-len   Skip examples longer than this many tokens (default: 8192)
    --skip-rlm      Skip Method 1 entirely (useful if you have no RLM API key)
    --dry-run       Parse and print the first example only, no API calls

COST ESTIMATION
---------------
Costs are estimated from token counts using the pricing table at the bottom of
this file.  For the RLM method, the cost covers all sub-LLM calls tracked by the
RLM's UsageSummary.  Actual billed cost may differ slightly.

OUTPUT CSV COLUMNS
------------------
    example_id    – Oolong numeric ID
    context_len   – token count of context_window_text (from dataset)
    task_group    – counting / timeline / user
    task          – TASK_TYPE.*
    answer_type   – ANSWER_TYPE.*
    method        – rlm / fixed_python / slm_direct / slm_cot
    prediction    – extracted string prediction
    gold          – gold answer string
    correct       – 1.0 = exact, 0.75^|delta| for numeric near-miss, else 0.0
    cost_usd      – estimated cost in USD for this (example, method) pair
    error         – error message if the call failed, else empty
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import os
import random
import re
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Optional: load a .env file sitting next to this script
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    pass  # dotenv not installed; rely on shell env vars

# ---------------------------------------------------------------------------
# Pricing table (USD per 1 000 tokens, as of 2026-07)
# Update these if prices change.
# ---------------------------------------------------------------------------
PRICE_TABLE: dict[str, dict[str, float]] = {
    # Anthropic
    "claude-sonnet-4-6":            {"input": 0.003,  "output": 0.015},
    "claude-sonnet-4-5":            {"input": 0.003,  "output": 0.015},
    "claude-opus-4-5":              {"input": 0.015,  "output": 0.075},
    "claude-haiku-4-5":             {"input": 0.00025,"output": 0.00125},
    # Anthropic model IDs as exposed through OpenRouter.
    "anthropic/claude-sonnet-4.6":   {"input": 0.003,  "output": 0.015},
    # OpenAI
    "gpt-4o":                       {"input": 0.0025, "output": 0.010},
    "gpt-4o-mini":                  {"input": 0.00015,"output": 0.0006},
    # OpenRouter model page, checked 2026-07-15:
    # - openai/gpt-5: $1.25/M input, $10/M output, 400K context
    "openai/gpt-5":                 {"input": 0.00125,"output": 0.010},
    # Google via OpenRouter
    # OpenRouter model pages, checked 2026-07-12:
    # - google/gemini-2.5-flash: $0.30/M input, $2.50/M output
    # - google/gemma-4-26b-a4b-it: $0.06/M input, $0.33/M output
    "google/gemini-2.5-flash":      {"input": 0.0003, "output": 0.0025},
    # OpenRouter model list, checked 2026-07-13:
    # - google/gemini-3.1-flash-lite: $0.25/M input, $1.50/M output
    # - google/gemini-3.5-flash: $1.50/M input, $9.00/M output
    "google/gemini-3.1-flash-lite": {"input": 0.00025, "output": 0.0015},
    "google/gemini-3.5-flash":      {"input": 0.0015,  "output": 0.009},
    "google/gemma-4-26b-a4b-it":    {"input": 0.00006,"output": 0.00033},
    "google/gemma-4-27b-it":        {"input": 0.0002, "output": 0.0002},
    "google/gemma-3-27b-it":        {"input": 0.0001, "output": 0.0001},
    # Generic fallback
    "_default":                     {"input": 0.001,  "output": 0.003},
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return estimated cost in USD for a single LLM call."""
    prices = PRICE_TABLE.get(model) or PRICE_TABLE.get("_default")
    return (input_tokens * prices["input"] + output_tokens * prices["output"]) / 1000.0


def rough_token_count(text: str) -> int:
    """Cheap approximation: ~4 characters per token (GPT-style)."""
    return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# Scoring (mirrors oolong/src/eval/eval_helpers.py::synth_process_response)
# ---------------------------------------------------------------------------

def parse_gold(answer_raw: str, answer_type: str):
    """Parse the gold answer string into a Python value."""
    try:
        parsed = ast.literal_eval(answer_raw)
        if isinstance(parsed, list):
            return parsed[0]
        return parsed
    except Exception:
        pass
    if "datetime" in answer_raw:
        try:
            return datetime.strptime(answer_raw, "[datetime.date(%Y, %m, %d)]")
        except Exception:
            pass
    return answer_raw


def score_prediction(prediction: str, gold, answer_type: str) -> float:
    """
    Returns a score in [0, 1].
    - Exact string match → 1.0
    - Relative-frequency comparison strings (more/less common) → 1.0 if substring
    - Numeric: partial credit via 0.75^|delta|
    - Date: exact datetime equality
    """
    pred_s = str(prediction).strip().lower()
    gold_s = str(gold).strip().lower()

    if pred_s == gold_s:
        return 1.0

    # Relative-frequency labels
    rel_labels = ("more common", "less common", "same frequency")
    if pred_s in rel_labels and pred_s in gold_s:
        return 1.0

    if answer_type == "ANSWER_TYPE.NUMERIC":
        try:
            return 0.75 ** abs(int(prediction) - int(gold))
        except (ValueError, TypeError):
            return 0.0

    if answer_type == "ANSWER_TYPE.DATE":
        try:
            import dateutil.parser
            return 1.0 if dateutil.parser.parse(prediction) == gold else 0.0
        except Exception:
            return 0.0

    return 0.0


# ---------------------------------------------------------------------------
# Oolong context parser (for Method 2 – fixed Python aggregator)
# ---------------------------------------------------------------------------

# Each data row looks like:
#   Date: Oct 06, 2022 || User: 81824 || Instance: <text> || Label: correct
_ROW_PATTERN = re.compile(
    r"Date:\s*(?P<date>[A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})"
    r"\s*\|\|\s*User:\s*(?P<user>\d+)"
    r".*?\|\|\s*Label:\s*(?P<label>[^\|\n]+)",
    re.IGNORECASE,
)

_MONTH_ABBR = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _parse_date(date_str: str) -> tuple[int, int] | None:
    """Return (year, month) or None."""
    m = re.match(r"([A-Za-z]{3,9})\s+\d{1,2},\s+(\d{4})", date_str.strip())
    if not m:
        return None
    month_s = m.group(1).lower()[:3]
    year = int(m.group(2))
    month = _MONTH_ABBR.get(month_s)
    return (year, month) if month else None


def parse_oolong_rows(context: str) -> list[dict]:
    """
    Parse all structured rows from an Oolong context string.
    Returns a list of dicts with keys: date_str, year, month, user, label.
    Returns [] if no rows found (triggers SLM fallback).
    """
    rows = []
    for m in _ROW_PATTERN.finditer(context):
        date_str = m.group("date").strip()
        user = m.group("user").strip()
        label = m.group("label").strip().lower()
        ym = _parse_date(date_str)
        rows.append({
            "date_str": date_str,
            "year": ym[0] if ym else None,
            "month": ym[1] if ym else None,
            "user": user,
            "label": label,
        })
    return rows


def solve_with_fixed_python(example: dict) -> str | None:
    """
    Deterministic aggregation over parsed rows.
    Returns the answer string, or None if the task type is not supported
    (which triggers SLM fallback in the caller).

    Design principle: only handle query patterns where we can reliably infer the
    aggregation target from the question text.  Questions that sub-filter by a
    specific user before counting labels (e.g. "Among instances associated with
    user X, which label is most common?") or that compare users by label counts
    (e.g. "Which user has more instances with label Y?") are compound queries
    that are returned as None → SLM fallback.  This keeps the aggregator honest:
    it never guesses, it just delegates.

    Supported tasks (covers ~70-80% of Oolong-synth without sub-filtering):
        MOST_FREQ, LEAST_FREQ, NUMERIC_ONE_CLASS, RELATIVE_FREQ,
        REPRESENTED_N_TIMES, SECOND_MOST_FREQ
    on: labels (counting group), users (user group), dates/months (timeline group).
    """
    ctx = get_oolong_context(example)
    rows = parse_oolong_rows(ctx)
    if not rows:
        return None  # Parse yielded nothing → SLM fallback

    task = example.get("task", "")
    question = example.get("question", "")
    task_group = example.get("task_group", "")
    answer_type = example.get("answer_type", "")
    q_lower = question.lower()

    # ---- Detect compound / ambiguous questions – delegate to SLM. ----
    # These patterns indicate the question involves secondary filtering or
    # cross-dimensional aggregation that the simple aggregator cannot handle:
    #   • "only consider the subset associated with user IDs X"
    #   • "among instances associated with these users"
    #   • "which user has more/most instances with label Y" (user ranked by label)
    #   • "for how many months is label X the most frequent" (count of months)
    compound_patterns = [
        r"only consider (?:the )?subset",
        r"among instances associated with",
        r"which user has (?:more|fewer|most|least) instances",
        r"how many instances does user",
        r"for how many (?:months|dates|users)",
        r"how many months is (?:the )?label",
        r"which user.*label",            # cross-dimension: user ranked by label
        r"which.*has the most instances with the label",
    ]
    if any(re.search(p, q_lower) for p in compound_patterns):
        return None  # Too complex for simple aggregation

    # ---- Infer aggregation target from answer_type (most reliable signal) ----
    if answer_type == "ANSWER_TYPE.USER":
        field = "user"
    elif answer_type in ("ANSWER_TYPE.MONTH_YEAR", "ANSWER_TYPE.DATE"):
        field = "date"
    elif answer_type == "ANSWER_TYPE.LABEL":
        field = "label"
    elif answer_type == "ANSWER_TYPE.NUMERIC":
        # For numeric answers the field being counted depends on the question
        if "user" in q_lower and "label" not in q_lower:
            field = "user"
        elif "date" in q_lower or "month" in q_lower:
            field = "date"
        else:
            field = "label"
    elif answer_type == "ANSWER_TYPE.COMPARISON":
        # "more/less common" comparisons are always between labels
        field = "label"
    else:
        field = "label"

    # ---- Build counts ----
    if field == "label":
        counts = Counter(r["label"] for r in rows)
    elif field == "user":
        counts = Counter(r["user"] for r in rows)
    else:
        # date field – aggregate by full date string (preserves day-level granularity)
        # Use the raw date_str so the mode can be reported as the model expects it.
        counts = Counter(r["date_str"] for r in rows if r["date_str"])

    if not counts:
        return None

    if "MOST_FREQ" in task and "SECOND" not in task:
        return str(counts.most_common(1)[0][0])

    if "LEAST_FREQ" in task:
        return str(counts.most_common()[-1][0])

    if "SECOND_MOST_FREQ" in task:
        ranking = counts.most_common()
        if len(ranking) < 2:
            return str(ranking[0][0])
        return str(ranking[1][0])

    if "NUMERIC_ONE_CLASS" in task:
        # "how many data points classified as label X?"
        label_m = re.search(r"label\s+'([^']+)'", question, re.IGNORECASE)
        if not label_m:
            # Try: "how many data points should be classified as <field>"
            # If we can't determine the target, return None
            return None
        target_label = label_m.group(1).strip().lower()
        return str(counts.get(target_label, 0))

    if "RELATIVE_FREQ" in task:
        # "is label A more common, less common, or same frequency as label B?"
        labels_m = re.findall(r"label\s+'([^']+)'", question, re.IGNORECASE)
        if len(labels_m) < 2:
            return None  # Can't identify both labels → SLM fallback
        a_label = labels_m[0].strip().lower()
        b_label = labels_m[1].strip().lower()
        a_count = counts.get(a_label, 0)
        b_count = counts.get(b_label, 0)
        if a_count > b_count:
            return "more common than"
        elif a_count < b_count:
            return "less common than"
        else:
            return "same frequency as"

    if "REPRESENTED_N_TIMES" in task:
        # "how many <dates/users/labels> are represented exactly N times?"
        # The question directly states whether it's asking about dates, users, or labels.
        # We must re-derive the counts using the question text, not answer_type.
        n_m = re.search(r"exactly\s+(\d+)\s+time", question, re.IGNORECASE)
        n = int(n_m.group(1)) if n_m else 1

        # Re-derive counts based on question text for accuracy
        if re.search(r"\bdate", q_lower):
            rep_counts = Counter(r["date_str"] for r in rows)
        elif re.search(r"\buser", q_lower):
            rep_counts = Counter(r["user"] for r in rows)
        else:
            rep_counts = Counter(r["label"] for r in rows)

        return str(sum(1 for v in rep_counts.values() if v == n))

    # Timeline group: "In which month did label X first occur more often than label Y?"
    if task_group == "timeline" and answer_type in ("ANSWER_TYPE.MONTH_YEAR", "ANSWER_TYPE.DATE"):
        labels_m = re.findall(r"label\s+'([^']+)'", question, re.IGNORECASE)
        if len(labels_m) < 2:
            return None
        a_label = labels_m[0].strip().lower()
        b_label = labels_m[1].strip().lower()

        from collections import defaultdict
        monthly: dict[tuple, Counter] = defaultdict(Counter)
        for r in rows:
            if r["year"] and r["month"]:
                monthly[(r["year"], r["month"])][r["label"]] += 1

        for ym in sorted(monthly.keys()):
            mc = monthly[ym]
            if mc.get(a_label, 0) > mc.get(b_label, 0):
                yr, mo = ym
                month_name = datetime(yr, mo, 1).strftime("%B")
                return f"{month_name} {yr}"
        return None  # Condition never met → SLM fallback

    return None  # Unsupported task type → SLM fallback


# ---------------------------------------------------------------------------
# SLM call (OpenRouter, Anthropic, or OpenAI)
# ---------------------------------------------------------------------------

def _get_openrouter_client():
    """Return an openai.OpenAI client pointed at OpenRouter."""
    import openai
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENROUTER_API_KEY not set. "
            "Get a key from https://openrouter.ai/ and export it."
        )
    return openai.OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )


_OPENROUTER_CLIENT = None  # lazy singleton


def get_openrouter_client():
    global _OPENROUTER_CLIENT
    if _OPENROUTER_CLIENT is None:
        _OPENROUTER_CLIENT = _get_openrouter_client()
    return _OPENROUTER_CLIENT


def call_slm(
    prompt: str,
    model: str,
    max_retries: int = 4,
    base_delay: float = 2.0,
) -> tuple[str, int, int]:
    """
    Call an SLM via OpenRouter with exponential-backoff retry.

    Returns (response_text, input_tokens, output_tokens).
    Raises RuntimeError after max_retries exhausted.
    """
    client = get_openrouter_client()
    last_exc: Exception | None = None

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=512,
            )
            text = response.choices[0].message.content or ""
            usage = response.usage
            in_tok = usage.prompt_tokens if usage else rough_token_count(prompt)
            out_tok = usage.completion_tokens if usage else rough_token_count(text)
            return text, in_tok, out_tok
        except Exception as exc:
            last_exc = exc
            wait = base_delay * (2 ** attempt) + random.uniform(0, 1)
            print(f"    [SLM] attempt {attempt + 1} failed ({type(exc).__name__}: {exc}); "
                  f"retrying in {wait:.1f}s …", file=sys.stderr)
            time.sleep(wait)

    raise RuntimeError(f"SLM call failed after {max_retries} attempts: {last_exc}")


# ---------------------------------------------------------------------------
# Answer extraction helpers
# ---------------------------------------------------------------------------

def extract_answer_from_slm_output(text: str, answer_type: str) -> str:
    """
    Mirror of oolong/src/eval/eval_helpers.py::synth_attempt_answer_parse.
    Returns the trimmed prediction string.
    """
    text = text.strip().replace("*", "")
    text = text.replace("[", "").replace("]", "")

    # Relative-frequency shorthand
    for phrase in ("more common than", "less common than", "same frequency as",
                   "more common", "less common", "same frequency"):
        if phrase in text.lower():
            return phrase

    # Try to find "Answer: X" or "Label: X" or "User: X" patterns
    for prefix in ("answer:", "label:", "user:", "date:"):
        idx = text.lower().rfind(prefix)
        if idx != -1:
            candidate = text[idx + len(prefix):].strip().split("\n")[0].strip()
            return candidate

    # Fallback: last non-empty line
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    return lines[-1] if lines else text


def get_oolong_context(example: dict) -> str:
    """Return the requested Oolong context field.

    Historical project runs used Oolong's label-provided aggregation ablation
    (`context_window_text_with_labels`). New standard-Oolong follow-up runs
    should set `_oolong_context_variant="standard"` to force unlabeled
    `context_window_text`.
    """
    variant = example.get("_oolong_context_variant", "label_provided")
    if variant in {"standard", "unlabeled"}:
        return example.get("context_window_text", "")
    return example.get("context_window_text_with_labels") or example.get("context_window_text", "")


# ---------------------------------------------------------------------------
# Method 1 – RLM scaffold
# ---------------------------------------------------------------------------

def run_rlm_method(
    example: dict,
    rlm_backend: str,
    rlm_model: str,
    rlm_max_tokens: int | None = None,
    max_retries: int = 3,
    base_delay: float = 3.0,
) -> tuple[str, float]:
    """
    Run the official RLM scaffold on one Oolong example.

    The RLM receives the full context as a string (stored in its REPL `context`
    variable) and the question as the root_prompt.  It iteratively writes Python
    code to parse and aggregate the rows, submitting the answer via
    answer["content"] / answer["ready"] = True.

    Returns (prediction_string, cost_usd).
    Raises RuntimeError on repeated failure.

    NOTE ON THE RLM API (rlms v0.1.3)
    -----------------------------------
    • Instantiate RLM with backend / backend_kwargs / max_iterations / max_budget.
    • Call rlm.completion(context_string, root_prompt=question_string).
    • The return value is an RLMChatCompletion dataclass with:
        .response       – the final answer string submitted by the model
        .usage_summary  – UsageSummary (token counts per model; cost only if
                          provider reports it, which OpenRouter does)
    • Cost: usage_summary.total_cost if available; else estimate from tokens.
    """
    from rlm import RLM  # rlms package exports RLM at top level

    context_text = get_oolong_context(example)
    question = example.get("question", "")

    # Build backend kwargs depending on the chosen provider
    if rlm_backend == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY not set for RLM Anthropic backend.")
        backend_kwargs = {"api_key": api_key, "model_name": rlm_model, "max_tokens": 4096}
    elif rlm_backend == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENAI_API_KEY not set for RLM OpenAI backend.")
        backend_kwargs = {"api_key": api_key, "model_name": rlm_model}
    elif rlm_backend == "openrouter":
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENROUTER_API_KEY not set for RLM OpenRouter backend.")
        backend_kwargs = {"api_key": api_key, "model_name": rlm_model}
    else:
        raise ValueError(f"Unknown RLM backend: {rlm_backend!r}")

    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            rlm = RLM(
                backend=rlm_backend,
                backend_kwargs=backend_kwargs,
                environment="local",   # use the local IPython/exec REPL
                max_depth=1,           # depth=1 → one recursion level of sub-LLMs
                max_iterations=15,     # guard against runaway loops
                max_budget=0.50,       # USD safety cap per example
                max_tokens=rlm_max_tokens,
                verbose=False,
            )
            result = rlm.completion(context_text, root_prompt=question)

            prediction = extract_answer_from_slm_output(
                result.response or "", example.get("answer_type", "")
            )

            # Cost: prefer provider-reported total_cost; fall back to token estimate
            usage = result.usage_summary
            if usage and usage.total_cost is not None:
                cost = usage.total_cost
            elif usage:
                in_tok = usage.total_input_tokens
                out_tok = usage.total_output_tokens
                cost = estimate_cost(rlm_model, in_tok, out_tok)
            else:
                cost = 0.0

            return prediction, cost

        except Exception as exc:
            last_exc = exc
            wait = base_delay * (2 ** attempt) + random.uniform(0, 1)
            print(f"    [RLM] attempt {attempt + 1} failed ({type(exc).__name__}: {exc}); "
                  f"retrying in {wait:.1f}s …", file=sys.stderr)
            time.sleep(wait)

    raise RuntimeError(f"RLM failed after {max_retries} attempts: {last_exc}")


# ---------------------------------------------------------------------------
# Method 2 – Fixed Python aggregator
# ---------------------------------------------------------------------------

def run_fixed_python_method(
    example: dict,
    slm_model: str,
    slm_cost_per_fallback: float | None = None,
) -> tuple[str, float]:
    """
    Deterministic Python aggregation with SLM fallback.

    1. Try parse_oolong_rows + solve_with_fixed_python.
    2. If that returns None (parse failed or task unsupported), call the SLM
       with a minimal prompt and count it as a fallback.

    Returns (prediction_string, cost_usd).
    """
    prediction = solve_with_fixed_python(example)

    if prediction is not None:
        # Pure deterministic path – zero API cost
        return prediction, 0.0

    # ---- Fallback: SLM ----
    # Build a compact prompt without chain-of-thought
    ctx = get_oolong_context(example)
    question = example.get("question", "")
    prompt = (
        "You are a precise data analyst. Read the following dataset and answer "
        "the question exactly as instructed. Do not guess; calculate from the data.\n\n"
        f"Dataset:\n{ctx}\n\nQuestion:\n{question}"
    )
    text, in_tok, out_tok = call_slm(prompt, model=slm_model)
    prediction = extract_answer_from_slm_output(text, example.get("answer_type", ""))
    cost = estimate_cost(slm_model, in_tok, out_tok)
    return prediction, cost


# ---------------------------------------------------------------------------
# Method 3 – SLM direct inference
# ---------------------------------------------------------------------------

def run_slm_direct_method(example: dict, slm_model: str) -> tuple[str, float]:
    """
    Single-shot SLM call.  No chain-of-thought, no code execution.
    The full context + question are packed into one user turn.

    This is the baseline that the RLM and fixed-Python methods are compared against.

    Returns (prediction_string, cost_usd).
    """
    ctx = get_oolong_context(example)
    question = example.get("question", "")
    prompt = (
        "You are a precise data analyst. Read the following dataset and answer "
        "the question exactly as instructed in the question. "
        "Do not guess; count or calculate from the data provided.\n\n"
        f"Dataset:\n{ctx}\n\nQuestion:\n{question}"
    )
    text, in_tok, out_tok = call_slm(prompt, model=slm_model)
    prediction = extract_answer_from_slm_output(text, example.get("answer_type", ""))
    cost = estimate_cost(slm_model, in_tok, out_tok)
    return prediction, cost


# ---------------------------------------------------------------------------
# Method 4 – SLM + CoT calibrated
# ---------------------------------------------------------------------------

_COT_SUFFIX = (
    "\n\nThink step by step:\n"
    "1. List every unique value for the relevant field (label / user / date).\n"
    "2. Count how many times each value appears.\n"
    "3. Use those counts to answer the question.\n"
    "Give your final answer in the format specified by the question."
)


def run_slm_cot_method(example: dict, slm_model: str) -> tuple[str, float]:
    """
    SLM call with an explicit chain-of-thought instruction appended.

    The model is asked to enumerate counts before answering.
    This is the 'CoT calibration' ablation from the RLM preprocessing paper.

    Returns (prediction_string, cost_usd).
    """
    ctx = get_oolong_context(example)
    question = example.get("question", "")
    prompt = (
        "You are a precise data analyst. Read the following dataset and answer "
        "the question exactly as instructed. Do not guess; count from the data.\n\n"
        f"Dataset:\n{ctx}\n\nQuestion:\n{question}"
        + _COT_SUFFIX
    )
    text, in_tok, out_tok = call_slm(prompt, model=slm_model)
    prediction = extract_answer_from_slm_output(text, example.get("answer_type", ""))
    cost = estimate_cost(slm_model, in_tok, out_tok)
    return prediction, cost


# ---------------------------------------------------------------------------
# Stratified sampling
# ---------------------------------------------------------------------------

def stratified_sample(dataset, n: int, seed: int) -> list[dict]:
    """
    Draw n examples stratified by (task_group, task) so that the slice
    represents the full task-type distribution of the dataset.
    """
    rng = random.Random(seed)
    by_stratum: dict[tuple, list[dict]] = {}
    for ex in dataset:
        key = (ex["task_group"], ex["task"])
        by_stratum.setdefault(key, []).append(dict(ex))

    total = len(dataset)
    samples: list[dict] = []
    for key, exs in by_stratum.items():
        k = max(1, round(n * len(exs) / total))
        rng.shuffle(exs)
        samples.extend(exs[:k])

    # Trim or top-up to exactly n
    rng.shuffle(samples)
    if len(samples) > n:
        samples = samples[:n]
    elif len(samples) < n:
        all_exs = [dict(ex) for ex in dataset]
        rng.shuffle(all_exs)
        ids_seen = {s["id"] for s in samples}
        for ex in all_exs:
            if ex["id"] not in ids_seen:
                samples.append(ex)
                ids_seen.add(ex["id"])
            if len(samples) == n:
                break

    return samples


# ---------------------------------------------------------------------------
# Main evaluation loop
# ---------------------------------------------------------------------------

def run_eval(args: argparse.Namespace) -> None:
    # ---- Load dataset ----
    print("Loading oolongbench/oolong-synth …")
    from datasets import load_dataset
    ds = load_dataset("oolongbench/oolong-synth", split="test")
    print(f"  Full test split: {len(ds)} examples")

    # Filter by context length
    ds = ds.filter(lambda x: x["context_len"] <= args.max_ctx_len)
    print(f"  After ctx-len filter (≤{args.max_ctx_len}): {len(ds)} examples")

    # Sample
    examples = stratified_sample(ds, args.n, args.seed)
    for ex in examples:
        ex["_oolong_context_variant"] = args.context_variant
    print(f"  Sampled {len(examples)} examples (seed={args.seed})")

    if args.dry_run:
        ex = examples[0]
        print("\n=== DRY RUN: first example ===")
        print(f"  id={ex['id']}  task={ex['task']}  answer={ex['answer']}")
        ctx = get_oolong_context(ex)
        rows = parse_oolong_rows(ctx)
        print(f"  Parsed rows: {len(rows)}")
        print(f"  Fixed-python prediction: {solve_with_fixed_python(ex)!r}")
        sys.exit(0)

    # ---- Output CSV ----
    out_path = Path(args.out)
    fieldnames = [
        "example_id", "context_len", "task_group", "task", "answer_type",
        "context_variant",
        "method", "prediction", "gold", "correct", "cost_usd", "error",
    ]
    csv_file = out_path.open("w", newline="", encoding="utf-8")
    writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
    writer.writeheader()

    methods_to_run = []
    if not args.skip_rlm:
        methods_to_run.append("rlm")
    methods_to_run += ["fixed_python", "slm_direct", "slm_cot"]

    total_cost = 0.0
    method_scores: dict[str, list[float]] = {m: [] for m in methods_to_run}
    method_costs: dict[str, float] = {m: 0.0 for m in methods_to_run}

    n_examples = len(examples)
    for i, ex in enumerate(examples):
        ex_id = ex["id"]
        gold_raw = ex.get("answer", "")
        answer_type = ex.get("answer_type", "")
        gold = parse_gold(gold_raw, answer_type)
        ctx_len = ex.get("context_len", 0)
        task_group = ex.get("task_group", "")
        task = ex.get("task", "")

        print(f"\n[{i + 1}/{n_examples}] id={ex_id} task={task} ctx={ctx_len}")

        for method in methods_to_run:
            prediction = ""
            cost = 0.0
            error_msg = ""
            score = 0.0

            try:
                if method == "rlm":
                    print(f"  → RLM scaffold …")
                    prediction, cost = run_rlm_method(
                        ex, args.rlm_backend, args.rlm_model
                    )

                elif method == "fixed_python":
                    print(f"  → Fixed Python aggregator …")
                    prediction, cost = run_fixed_python_method(ex, args.slm_model)

                elif method == "slm_direct":
                    print(f"  → SLM direct …")
                    prediction, cost = run_slm_direct_method(ex, args.slm_model)

                elif method == "slm_cot":
                    print(f"  → SLM + CoT …")
                    prediction, cost = run_slm_cot_method(ex, args.slm_model)

                score = score_prediction(prediction, gold, answer_type)

            except Exception as exc:
                error_msg = f"{type(exc).__name__}: {exc}"
                print(f"    ERROR: {error_msg}", file=sys.stderr)
                prediction = ""
                score = 0.0
                cost = 0.0

            method_scores[method].append(score)
            method_costs[method] += cost
            total_cost += cost

            print(f"    pred={prediction!r:30s}  gold={str(gold)!r:20s}  "
                  f"score={score:.2f}  cost=${cost:.5f}")

            writer.writerow({
                "example_id":  ex_id,
                "context_len": ctx_len,
                "task_group":  task_group,
                "task":        task,
                "answer_type": answer_type,
                "context_variant": args.context_variant,
                "method":      method,
                "prediction":  str(prediction),
                "gold":        str(gold),
                "correct":     round(score, 4),
                "cost_usd":    round(cost, 6),
                "error":       error_msg,
            })
            csv_file.flush()  # ensure partial results are always on disk

    csv_file.close()

    # ---- Summary ----
    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print(f"{'Method':<20} {'Accuracy':>10} {'Avg score':>10} {'Total $':>10}")
    print("-" * 55)
    for method in methods_to_run:
        scores = method_scores[method]
        if scores:
            avg = sum(scores) / len(scores)
            exact = sum(1 for s in scores if s >= 1.0) / len(scores)
        else:
            avg = exact = 0.0
        c = method_costs[method]
        print(f"{method:<20} {exact:>10.1%} {avg:>10.3f} {c:>10.5f}")
    print("-" * 55)
    print(f"{'TOTAL COST':<40} ${total_cost:.5f}")
    print(f"\nResults written to: {out_path.resolve()}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate four methods on a slice of Oolong-synth.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--n", type=int, default=80,
                        help="Number of examples to evaluate (1–500).")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for stratified sampling.")
    parser.add_argument("--out", default="oolong_slice_results.csv",
                        help="Output CSV file path.")
    parser.add_argument("--rlm-backend", default="anthropic",
                        choices=["anthropic", "openai", "openrouter"],
                        help="Backend for the RLM scaffold (Method 1).")
    parser.add_argument("--rlm-model", default="claude-sonnet-4-6",
                        help="Model identifier for the RLM.")
    parser.add_argument("--slm-model", default="google/gemma-4-27b-it",
                        help="Model for Methods 3 and 4 (via OpenRouter).")
    parser.add_argument("--max-ctx-len", type=int, default=8192,
                        help="Skip examples with context_len > this value.")
    parser.add_argument("--context-variant", choices=["label_provided", "standard"],
                        default="label_provided",
                        help="label_provided uses context_window_text_with_labels (historical aggregation ablation); standard uses unlabeled context_window_text.")
    parser.add_argument("--skip-rlm", action="store_true",
                        help="Skip Method 1 (RLM) — useful if API key unavailable.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse first example only; no API calls.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_eval(args)
