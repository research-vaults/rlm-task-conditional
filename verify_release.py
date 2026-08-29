#!/usr/bin/env python3
import csv, hashlib, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GENERATED_DIR = "_reproduced"
SOURCE_PAYLOAD_KEYS = {
    "context", "context_text", "document", "document_text", "documents",
    "input_context", "prompt", "source_text",
}
MAX_RELEASE_SOURCE_PAYLOAD_CHARS = 8000
COMMON_TLD_EMAIL_RE = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.(?:com|org|net|edu|gov)\b",
    re.IGNORECASE,
)
TEXT_SCAN_EXCLUDED_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg"}
EXCLUDED_PARTS = {".git", ".venv", "__pycache__", GENERATED_DIR}

def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def validate_release_surface():
    errors = []
    manifest_path = ROOT / "SHA256SUMS.json"
    if not manifest_path.is_file():
        return ["SHA256SUMS.json is missing"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entries = manifest["files"]
    except Exception as exc:
        return [f"SHA256SUMS.json is invalid: {exc}"]
    expected = {
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if path.is_file()
        and path.name != "SHA256SUMS.json"
        and not EXCLUDED_PARTS.intersection(path.relative_to(ROOT).parts)
    }
    listed = {entry.get("path") for entry in entries}
    if listed != expected:
        errors.append(
            f"checksum member mismatch: missing={sorted(expected - listed)} "
            f"extra={sorted(listed - expected)}"
        )
    for entry in entries:
        rel = entry.get("path")
        path = ROOT / rel if isinstance(rel, str) else None
        if path is None or not path.is_file():
            errors.append(f"checksum member missing: {rel}")
            continue
        if path.stat().st_size != entry.get("bytes"):
            errors.append(f"byte-size mismatch: {rel}")
        if sha256(path) != entry.get("sha256"):
            errors.append(f"SHA-256 mismatch: {rel}")
    for path in sorted(ROOT.rglob("*")):
        if (
            not path.is_file()
            or EXCLUDED_PARTS.intersection(path.relative_to(ROOT).parts)
        ):
            continue
        rel = path.relative_to(ROOT).as_posix()
        try:
            if path.suffix.lower() not in TEXT_SCAN_EXCLUDED_SUFFIXES:
                text = path.read_text(encoding="utf-8", errors="ignore")
                if COMMON_TLD_EMAIL_RE.search(text):
                    errors.append(f"third-party email-like text remains: {rel}")
            if path.suffix == ".json":
                values = [json.loads(path.read_text(encoding="utf-8"))]
            elif path.suffix == ".jsonl":
                values = []
                for line_number, line in enumerate(
                    path.read_text(encoding="utf-8").split("\n"), start=1
                ):
                    if line.strip():
                        values.append(json.loads(line))
            elif path.suffix == ".csv":
                with path.open(newline="", encoding="utf-8") as handle:
                    values = list(csv.DictReader(handle))
            else:
                values = []

            def inspect_payload(value, key_path=()):
                if isinstance(value, dict):
                    for key, item in value.items():
                        child = key_path + (str(key),)
                        if (
                            isinstance(item, str)
                            and str(key).lower() in SOURCE_PAYLOAD_KEYS
                            and len(item) > MAX_RELEASE_SOURCE_PAYLOAD_CHARS
                        ):
                            errors.append(
                                f"source-document payload: {rel} "
                                f"key={'/'.join(child)} chars={len(item)}"
                            )
                        inspect_payload(item, child)
                elif isinstance(value, list):
                    for index, item in enumerate(value):
                        inspect_payload(item, key_path + (str(index),))

            for value in values:
                inspect_payload(value)

            if path.suffix == ".py":
                compile(path.read_text(encoding="utf-8"), rel, "exec")
        except Exception as exc:
            errors.append(f"{rel}: {exc}")
    for required in ("requirements.txt", "CLAIM_TO_COMMAND_MAP.md"):
        if not (ROOT / required).is_file():
            errors.append(f"{required} is missing")
    return errors

def load_csv(rel):
    with (ROOT / rel).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def load_jsonl(rel):
    return [json.loads(line) for line in (ROOT / rel).read_text().splitlines() if line.strip()]

def row_ok(row):
    if "correct" in row:
        return float(row.get("correct", "0") or 0.0) >= 0.999
    return str(row.get("exact", "")).strip().lower() in {"true", "1", "yes"}

def exact(rows):
    return sum(row_ok(r) for r in rows)

def cost(rows):
    return round(sum(float(r.get("cost_usd", "0") or 0.0) for r in rows), 6)

def by_id(rows):
    return {r["example_id"]: r for r in rows}

def paired(a_rows, b_rows):
    a = by_id(a_rows)
    b = by_id(b_rows)
    ids = sorted(set(a) & set(b))
    b_count = 0
    c_count = 0
    for eid in ids:
        a_ok = row_ok(a[eid])
        b_ok = row_ok(b[eid])
        if a_ok and not b_ok:
            b_count += 1
        elif b_ok and not a_ok:
            c_count += 1
    return len(ids), b_count, c_count

def check(label, got, exp):
    if got != exp:
        print(f"FAIL {label}: expected {exp}, got {got}")
        return 1
    print(f"PASS {label}: {got}")
    return 0

fails = 0
surface_errors = validate_release_surface()
fails += check("Repository checksum/parse/compile surface", surface_errors, [])
main_source = (ROOT / "paper/main_aaai_submission.tex").read_text(encoding="utf-8")
supplement_source = (ROOT / "paper/supplement_aaai.tex").read_text(encoding="utf-8")
fails += check(
    "Main defines binary-exact and partial-credit scoring",
    "both the binary exact rate and the partial-credit mean score" in main_source
    and "0.75^{|\\Delta|}" in main_source
    and "technical source" not in main_source,
    True,
)
fails += check(
    "Released supplement contains LP-80 strict sensitivity",
    "RLM is 64/80 (80.0\\%) strict exact" in supplement_source
    and "56/80 (70.0\\%) for fp+SLM" in supplement_source
    and "43/80 (53.8\\%) for SLM direct" in supplement_source
    and "37/80 (46.2\\%) for SLM+CoT" in supplement_source,
    True,
)
fails += check(
    "Released supplement contains N49 Holm sensitivity",
    "Holm adjustment over all three route pairs gives $p=0.0132$" in supplement_source
    and "$p=0.0077$ for RLM--text" in supplement_source,
    True,
)
repl_blind = json.loads((ROOT / "results/browsecomp_plus_positive_regime_replication/bcp_repl_n49_second_model_blind_audit_aggregate_20260721.json").read_text())
fails += check("N49 exhaustive independent-judge coverage", (repl_blind["successful_generations"], repl_blind["second_model_parsed"]), (137, 137))
fails += check("N49 independent-judge agreement/kappa", (repl_blind["successful_output_agreement"]["count"], round(repl_blind["successful_output_agreement"]["cohen_kappa"], 3)), (132, 0.927))
fails += check("N49 Luna RLM/text/BM25", tuple(repl_blind["methods"][m]["second_model_correct"] for m in ("standard_rlm_qwen36", "text_decompose_qwen36", "bm25_qwen36")), (33, 20, 19))
fails += check("N49 Luna Holm sensitivity", (round(repl_blind["second_model_pairwise"]["rlm_vs_text"]["holm_adjusted_p_three_route_pairs"], 4), round(repl_blind["second_model_pairwise"]["rlm_vs_bm25"]["holm_adjusted_p_three_route_pairs"], 4)), (0.013, 0.013))
fails += check("N49 second judge is not human validation", repl_blind["audit_contract"]["human_validation"], False)
fails += check(
    "Released supplement retains N49 independent-judge sensitivity",
    "132/137" in supplement_source
    and "Cohen's $\\kappa{=}0.927$" in supplement_source
    and "both three-pair Holm-adjusted values are $p{=}0.0130$" in supplement_source,
    True,
)
fixed_n45 = json.loads((ROOT / "results/browsecomp_plus_shard1_fixed_n45/semantic_replication_shard1_fixed_n45_primary_analysis.json").read_text())
fixed_n45_second = json.loads((ROOT / "results/browsecomp_plus_shard1_fixed_n45/bcp_shard1_fixed_n45_second_model_blind_audit_aggregate_20260723.json").read_text())
fixed_n45_verify = json.loads((ROOT / "results/browsecomp_plus_shard1_fixed_n45/fixed_n45_independent_verification_20260723.json").read_text())
fails += check("Fixed-N45 endpoint/coverage", (fixed_n45["attempted_n"], fixed_n45["fixed_endpoint_complete"], fixed_n45_verify["attempted_cells"]), (45, True, 135))
fails += check("Fixed-N45 RLM/text/BM25", tuple(fixed_n45["methods"][method]["semantic_correct"] for method in ("standard_rlm_qwen36", "text_decompose_qwen36", "bm25_qwen36")), (33, 29, 21))
fails += check("Fixed-N45 RLM-vs-BM25 discordance", (fixed_n45["paired"]["standard_rlm_qwen36__vs__bm25_qwen36"]["left_only"], fixed_n45["paired"]["standard_rlm_qwen36__vs__bm25_qwen36"]["right_only"]), (15, 3))
fails += check("Fixed-N45 RLM-vs-text discordance", (fixed_n45["paired"]["standard_rlm_qwen36__vs__text_decompose_qwen36"]["left_only"], fixed_n45["paired"]["standard_rlm_qwen36__vs__text_decompose_qwen36"]["right_only"]), (9, 5))
fixed_n45_common = fixed_n45["common_completion_sensitivity"]
fails += check("Fixed-N45 common-completion sensitivity tier/N", (fixed_n45_common["evidence_tier"], fixed_n45_common["n"]), ("post_treatment_sensitivity_only", 39))
fails += check("Fixed-N45 common-completion RLM/text/BM25", tuple(fixed_n45_common["methods"][method]["semantic_correct"] for method in ("standard_rlm_qwen36", "text_decompose_qwen36", "bm25_qwen36")), (30, 23, 19))
fails += check("Fixed-N45 common-completion RLM-vs-BM25", (fixed_n45_common["paired"]["standard_rlm_qwen36__vs__bm25_qwen36"]["left_only"], fixed_n45_common["paired"]["standard_rlm_qwen36__vs__bm25_qwen36"]["right_only"], round(fixed_n45_common["paired"]["standard_rlm_qwen36__vs__bm25_qwen36"]["mcnemar_exact_two_sided_p"], 4)), (12, 1, 0.0034))
fails += check("Fixed-N45 common-completion RLM-vs-text", (fixed_n45_common["paired"]["standard_rlm_qwen36__vs__text_decompose_qwen36"]["left_only"], fixed_n45_common["paired"]["standard_rlm_qwen36__vs__text_decompose_qwen36"]["right_only"], round(fixed_n45_common["paired"]["standard_rlm_qwen36__vs__text_decompose_qwen36"]["mcnemar_exact_two_sided_p"], 4)), (9, 2, 0.0654))
fails += check("Fixed-N45 second-judge agreement/kappa", (fixed_n45_second["successful_output_agreement"]["count"], round(fixed_n45_second["successful_output_agreement"]["cohen_kappa"], 3)), (128, 0.983))
fails += check("Fixed-N45 second judge is not human", fixed_n45_second["audit_contract"]["human_validation"], False)
fails += check(
    "Fixed-N45 attempted-row median/p95 latency",
    tuple(
        (
            round(fixed_n45["methods"][method]["wall_seconds_median"], 1),
            round(fixed_n45["methods"][method]["wall_seconds_p95"], 1),
        )
        for method in ("standard_rlm_qwen36", "text_decompose_qwen36", "bm25_qwen36")
    ),
    ((44.6, 425.7), (29.6, 44.9), (3.2, 19.6)),
)
fails += check(
    "Fixed-N45 model-call totals",
    tuple(
        fixed_n45["methods"][method]["model_calls_total"]
        for method in ("standard_rlm_qwen36", "text_decompose_qwen36", "bm25_qwen36")
    ),
    (607, 314, 42),
)
equal_n45 = json.loads((ROOT / "results/browsecomp_plus_shard1_equal_cap_n45/semantic_equal_cap_n45_primary_analysis.json").read_text())
equal_n45_second = json.loads((ROOT / "results/browsecomp_plus_shard1_equal_cap_n45/bcp_equal_cap_n45_second_model_blind_audit_aggregate_20260726.json").read_text())
equal_n45_verify = json.loads((ROOT / "results/browsecomp_plus_shard1_equal_cap_n45/equal_cap_n45_independent_verification_20260727.json").read_text())
equal_n45_diagnostics = json.loads((ROOT / "results/browsecomp_plus_shard1_equal_cap_n45/reviewer_diagnostics_public_20260727.json").read_text())
equal_n45_no_context = json.loads((ROOT / "results/browsecomp_plus_shard1_equal_cap_n45/no_context_parametric_probe/aggregate_public.json").read_text())
equal_methods = ("standard_rlm_qwen36", "iterative_search_qwen36", "text_decompose_qwen36", "bm25_qwen36")
fails += check("Equal-cap N45 endpoint/coverage", (equal_n45["attempted_n"], equal_n45["fixed_endpoint_complete"], equal_n45_verify["attempted_cells"]), (45, True, 180))
fails += check("Equal-cap N45 RLM/iterative/text/BM25", tuple(equal_n45["methods"][method]["semantic_correct"] for method in equal_methods), (31, 33, 37, 25))
fails += check("Equal-cap N45 completion", tuple(equal_n45["methods"][method]["completed"] for method in equal_methods), (41, 45, 45, 42))
fails += check("Equal-cap N45 calls", tuple(equal_n45["methods"][method]["model_calls_total"] for method in equal_methods), (476, 426, 311, 42))
fails += check("Equal-cap N45 all RLM Holm contrasts uncertain", all(value >= 0.05 for value in equal_n45["multiplicity"]["holm_adjusted_p"].values()), True)
fails += check("Equal-cap N45 common-completion N/counts", (equal_n45["common_completion_sensitivity"]["n"], tuple(equal_n45["common_completion_sensitivity"]["methods"][method]["semantic_correct"] for method in equal_methods)), (39, (30, 28, 31, 22)))
fails += check("Equal-cap N45 second-judge agreement/kappa", (equal_n45_second["successful_output_agreement"]["count"], round(equal_n45_second["successful_output_agreement"]["cohen_kappa"], 3)), (172, 0.985))
fails += check("Equal-cap N45 second judge is not human", equal_n45_second["audit_contract"]["human_validation"], False)
fails += check("Equal-cap N45 independent verifier", (equal_n45_verify["status"], equal_n45_verify["successful_generations"]), ("PASS", 173))
fails += check(
    "Equal-cap N45 exact paired intervals",
    tuple(
        tuple(equal_n45_diagnostics["paired_rlm_contrasts"][method]["paired_bootstrap_95"])
        for method in ("iterative", "text", "BM25")
    ),
    ((-0.2, 0.1111111111111111), (-0.3111111111111111, 0.044444444444444446), (-0.022222222222222223, 0.28888888888888886)),
)
fails += check(
    "Equal-cap N45 required-document strata",
    tuple(
        tuple(row["semantic_correct"][method] for method in ("RLM", "iterative", "text"))
        for row in equal_n45_diagnostics["required_document_granularity"]["post_hoc_descriptive_strata"]
    ),
    ((11, 12, 14), (12, 13, 16), (8, 8, 7)),
)
fails += check(
    "Equal-cap N45 route-specific judge agreement",
    tuple(
        (
            equal_n45_diagnostics["second_judge_agreement_by_route"][method]["agreement"],
            equal_n45_diagnostics["second_judge_agreement_by_route"][method]["successful_outputs"],
        )
        for method in ("RLM", "iterative", "text", "BM25")
    ),
    ((41, 41), (45, 45), (45, 45), (41, 42)),
)
fails += check(
    "Equal-cap N45 no-context diagnostic",
    (
        equal_n45_no_context["chronology"],
        equal_n45_no_context["fixed_denominator"],
        equal_n45_no_context["successful_generations"],
        equal_n45_no_context["gemma_judge"]["correct"],
        equal_n45_no_context["gpt56_judge"]["correct"],
    ),
    ("POST_HOC_EXPLORATORY", 45, 45, 0, 0),
)
seed21 = json.loads((ROOT / "results/browsecomp_plus_shard1_equal_cap_n45_seed21/semantic_equal_cap_n45_seed21_primary_analysis.json").read_text())
seed21_second = json.loads((ROOT / "results/browsecomp_plus_shard1_equal_cap_n45_seed21/bcp_equal_cap_n45_seed21_second_model_blind_audit_aggregate_20260728.json").read_text())
fails += check(
    "Seed-21 repeat chronology/coverage",
    (seed21["chronology"], seed21["attempted_n"], seed21["n_cells"], seed21["fixed_endpoint_complete"]),
    ("POST_HOC_EXPLORATORY", 45, 180, True),
)
fails += check(
    "Seed-21 RLM/iterative/text/BM25",
    tuple(seed21["methods"][method]["semantic_correct"] for method in equal_methods),
    (30, 31, 29, 22),
)
fails += check(
    "Seed-21 all RLM Holm contrasts uncertain",
    all(value >= 0.05 for value in seed21["multiplicity"]["holm_adjusted_p"].values()),
    True,
)
fails += check(
    "Seed-21 second-judge agreement/kappa",
    (
        seed21_second["second_model_parsed"],
        seed21_second["successful_output_agreement"]["count"],
        round(seed21_second["successful_output_agreement"]["cohen_kappa"], 3),
    ),
    (169, 166, 0.961),
)
fails += check("Seed-21 second judge is not human", seed21_second["audit_contract"]["human_validation"], False)
rights = (ROOT / "RELEASE_RIGHTS_AND_DATA_BOUNDARIES.md").read_text(encoding="utf-8")
normalized_rights = " ".join(rights.split())
fails += check(
    "Release rights/data/correction surface",
    (
        "No license to redistribute" in normalized_rights
        and "Source-document-scale benchmark content is excluded" in normalized_rights
        and "rejects oversized structured source-payload fields" in normalized_rights
        and "SHA256SUMS.json" in normalized_rights
        and "correction notices should be communicated" in normalized_rights
        and "submission channel" in normalized_rights
        and "redacts email-like strings" in normalized_rights
    ),
    True,
)
fails += check(
    "Released manuscript contains fixed-N45 evidence",
    "33/45 (73.3\\%)" in main_source
    and "128/129 successful outputs" in main_source
    and "Untouched-Shard Fixed-$N$ Replication" in supplement_source
    and "$\\kappa{=}0.983$" in supplement_source,
    True,
)
fails += check(
    "Released manuscript contains prospective equal-cap evidence",
    "31/45 (68.9\\%)" in main_source
    and "37/45 (82.2\\%)" in main_source
    and "discordances $6/8$, $5/11$ and $10/4$" in main_source
    and "Paired 95\\% intervals are $[-20.0,11.1]$, $[-31.1,4.4]$ and $[-2.2,28.9]$ points" in main_source
    and "41/41, 45/45, 45/45 and 41/42" in main_source
    and "question-only Qwen leakage probe scores 0/45 under both judges" in main_source
    and "Open search alone is not a sufficient routing signal" in main_source
    and "Prospective Equal-Cap Comparison and Rollout Repeat" in supplement_source
    and "RLM & 41/31 & 54.3--80.5 & 476" in supplement_source
    and "Text decomp. & 45/37 & 68.7--90.7 & 311" in supplement_source
    and "0.5387" in supplement_source
    and "172/173" in supplement_source
    and "$\\kappa{=}0.985$" in supplement_source
    and "Post-hoc seed-21 same-row rollout sensitivity" in supplement_source
    and "RLM & 37/36/30 & 52.1--78.6" in supplement_source
    and "0.346" in supplement_source
    and "28/23/20/18" in supplement_source
    and "166/169 successful outputs" in supplement_source
    and "an independent endpoint and is not pooled" in supplement_source,
    True,
)
dense = json.loads((ROOT / "results/browsecomp_plus_positive_regime_replication/dense_hybrid_sensitivity/semantic_dense_hybrid_sensitivity_n49_analysis.json").read_text())
fails += check("N49 learned retrieval/RLM semantic correct", (dense["results"]["dense_hybrid_qwen3emb8b_qwen36"]["semantic_correct"], dense["results"]["standard_rlm_qwen36"]["semantic_correct"]), (20, 35))
fails += check("N49 learned retrieval completion", dense["results"]["dense_hybrid_qwen3emb8b_qwen36"]["completed"], 43)
fails += check("N49 learned retrieval RLM discordance", (dense["paired_descriptive"]["dense_hybrid_qwen3emb8b_qwen36__vs__standard_rlm_qwen36"]["right_only"], dense["paired_descriptive"]["dense_hybrid_qwen3emb8b_qwen36__vs__standard_rlm_qwen36"]["left_only"]), (19, 4))
fails += check("N49 learned retrieval remains post-hoc", dense["evidence_tier"], "post_hoc_sensitivity_only")
fails += check(
    "Released package retains learned-retrieval sensitivity below the main evidence tier",
    "post-hoc BM25-64/Qwen3-Embedding rerank" not in main_source
    and "not full-corpus dense retrieval" in supplement_source
    and "all recall diagnostics were computed after output" in supplement_source,
    True,
)
no_sub = json.loads((ROOT / "results/browsecomp_plus_positive_regime_replication/no_subcall_ablation/bcp_n49_rlm_no_subcall_primary_analysis.json").read_text())
fails += check("N49 no-subcall attempted-prefix counts", (no_sub["attempted_prefix"]["n"], no_sub["attempted_prefix"]["standard_correct"], no_sub["attempted_prefix"]["no_subcall_correct"]), (30, 24, 20))
fails += check("N49 no-subcall attempted-prefix discordance", (no_sub["attempted_prefix"]["standard_only"], no_sub["attempted_prefix"]["no_subcall_only"]), (5, 1))
fails += check("N49 no-subcall full counts/completion", (no_sub["methods"]["standard_rlm_qwen36"]["semantic_correct"], no_sub["methods"]["rlm_no_subcall_qwen36"]["semantic_correct"], no_sub["methods"]["rlm_no_subcall_qwen36"]["completed"]), (35, 20, 24))
fails += check("N49 no-subcall disabled attempts", no_sub["methods"]["rlm_no_subcall_qwen36"]["disabled_subcall_attempts"], 0)
fails += check(
    "Released manuscript calibrates no-subcall control",
    "The no-subcall arm was not prospectively frozen at the same realized budget" not in main_source
    and (
        "recursion is not isolated from inference budget" in main_source
        or "We do not vary recursion depth" in main_source
        or "recursion depth is fixed" in main_source
    )
    and "attempted-prefix row is the relevant descriptive component sensitivity" in supplement_source
    and "not exact realized-dollar matching" in supplement_source,
    True,
)
main_sensitivity = json.loads((ROOT / "results/browsecomp_plus_positive_regime_replication/main_inference_cost_sensitivity_20260722.json").read_text())
main_text_pair = main_sensitivity["comparisons"]["standard_rlm_qwen36__vs__text_decompose_qwen36"]
main_bm25_pair = main_sensitivity["comparisons"]["standard_rlm_qwen36__vs__bm25_qwen36"]
fails += check("N49 terminal rank all-route failure", main_sensitivity["terminal_rank_all_routes_failed"], True)
fails += check(
    "N49 terminal-drop discordance unchanged",
    (
        main_text_pair["fully_generated_prefix_n48"]["left_only"],
        main_text_pair["fully_generated_prefix_n48"]["right_only"],
        main_bm25_pair["fully_generated_prefix_n48"]["left_only"],
        main_bm25_pair["fully_generated_prefix_n48"]["right_only"],
    ),
    (17, 3, 19, 5),
)
fails += check(
    "N49 route-dollar thresholds",
    tuple(round(main_sensitivity["route_cost_utility"][method]["route_dollar_cost_per_net_additional_correct_answer"], 3) for method in ("text_decompose_qwen36", "bm25_qwen36")),
    (0.940, 1.052),
)
fails += check(
    "Released main labels stopped-prefix and same-budget limits",
    "attempted-$N{=}49$ endpoint stopped score-blind" in main_source
    and "Prospective equal-cap reversal" in main_source
    and (
        "common 20-decision/1,200-second caps" in main_source
        or "matched decision/time caps" in main_source
    )
    and (
        "recursion is not isolated from inference budget" in main_source
        or "We do not vary recursion depth" in main_source
        or "recursion depth is fixed" in main_source
    ),
    True,
)
fails += check(
    "Released main contains timeout-cost enforcement boundary",
    "Seven repeat RLM calls exceed the cap and score incorrect" in main_source
    and "provider/runtime reconciliation" in main_source,
    True,
)
fails += check(
    "Released main discloses ethics scope and AI assistance",
    "\\paragraph{Ethics and AI assistance.}" in main_source
    and "no human-subject data" in main_source
    and "AI tools assisted coding, orchestration and editing" in main_source
    and "analyses, citations, figures and text were human-verified" in main_source,
    True,
)
vc_manifest = json.loads((ROOT / "results/oolong_validation_corpus_disjoint_n45_manifest_20260721_summary.json").read_text())
vc = json.loads((ROOT / "results/oolong_validation_corpus_disjoint_n45_threeway_20260721.json").read_text())
vc_qp = json.loads((ROOT / "results/oolong_validation_corpus_disjoint_n45_slm_labeler_question_parsed_typed_20260721_summary.json").read_text())
vc_result_memo = (ROOT / "results/oolong_validation_corpus_disjoint_n45_threeway_20260721.md").read_text()
vc_route_summaries = [
    json.loads((ROOT / f"results/oolong_validation_corpus_disjoint_n45_standard_rlm_{group}_20260721_summary.json").read_text())
    for group in ("counting", "timeline", "user")
]
fails += check("VC-45 manifest N/clusters/max reuse", (vc_manifest["n"], vc_manifest["unique_context_window_ids"], vc_manifest["max_questions_per_context_window_id"]), (45, 20, 3))
fails += check("VC-45 source corpora", vc_manifest["datasets"], {"spam": 27, "trec_coarse": 18})
fails += check("VC-45 overlap audit", tuple(vc_manifest["overlap"][k] for k in ("validation_test_ids", "validation_test_contexts", "validation_test_datasets", "validation_prior_ids", "validation_prior_contexts", "validation_prior_datasets")), (0, 0, 0, 0, 0, 0))
fails += check("VC-45 exact SLM/direct/RLM", tuple(vc["overall"][m]["exact_count"] for m in ("slm_typed", "direct_controller", "standard_rlm")), (35, 23, 28))
fails += check("VC-45 costs SLM/direct/RLM", tuple(round(vc["overall"][m]["cost_usd"], 6) for m in ("slm_typed", "direct_controller", "standard_rlm")), (0.312208, 0.658420, 1.139174))
fails += check("VC-45 SLM-vs-RLM discordance", (vc["paired"]["slm_vs_rlm"]["b_a_right_b_wrong"], vc["paired"]["slm_vs_rlm"]["c_b_right_a_wrong"]), (10, 3))
fails += check("VC-45 cluster exact interval includes zero", vc["cluster_bootstrap"]["slm_minus_rlm_exact"]["lo"], 0.0)
fails += check("VC-45 cluster score interval excludes zero", vc["cluster_bootstrap"]["slm_minus_rlm_score"]["lo"] > 0, True)
fails += check("VC-45 question parser audit", (vc_qp["n"], vc_qp["task_parse_accuracy_vs_metadata"], vc_qp["answer_type_parse_accuracy_vs_metadata"]), (45, 1.0, 1.0))
fails += check(
    "VC-45 trace rows/code blocks from release-safe summary",
    (
        vc["trace_integrity"]["slm_rows"],
        vc["trace_integrity"]["rlm_rows"],
        vc["trace_integrity"]["rlm_code_blocks"],
    ),
    (45, 45, 205),
)
fails += check(
    "VC-45 release chronology is exact",
    "pre-output locked after one outcome-blind no-call parser grammar repair" in vc_result_memo
    and "prospectively frozen" not in vc_result_memo.lower()
    and all(
        "pre-output-locked" in row["contract"].lower()
        and "outcome-blind no-call parser grammar repair" in row["contract"].lower()
        and "prospectively frozen" not in json.dumps(row).lower()
        for row in vc_route_summaries
    ),
    True,
)
fails += check(
    "VC-45 source boundary in manuscript",
    "pre-output-locked VC-45" in main_source
    and "parser repair applied only to rows returning no call" in main_source
    and "pre-output locked after one outcome-blind no-call parser repair" in supplement_source
    and "subgroup differences are therefore descriptive, not source-independent" in supplement_source,
    True,
)
fails += check(
    "Released prose excludes stale revision seams",
    all(
        token not in main_source + supplement_source
        for token in [
            "prospective source-corpus transfer",
            "\\section{Prospective BrowseComp-Plus Positive-Regime Audit}",
            "stopped at the user's request",
            "proves active protocol diligence",
            "Comparator publication-status guard",
            "sample-size optics",
        ]
    )
    and "RLM completes 41/45 with 50.1/628.8-second median/p95 latency" in main_source
    and all(
        token in main_source
        for token in ["\\$9.873", "\\$1.710", "\\$1.400", "\\$0.296"]
    ),
    True,
)
tstruct_rlm = load_jsonl("results/raw_results_official_rlm_oolong_pairs_30_20260630.jsonl")
tstruct_sml = load_jsonl("results/raw_results_20260630T180407Z.jsonl")
tstruct_summary = json.loads((ROOT / "results/summary_metrics_official_rlm_oolong_pairs_30_20260630.json").read_text())
fails += check("T-STRUCT raw rows", (len(tstruct_rlm), len(tstruct_sml)), (30, 30))
fails += check("T-STRUCT raw exact", (sum(1 for r in tstruct_rlm if r.get("answer_correct")), sum(1 for r in tstruct_sml if r.get("answer_correct"))), (29, 30))
fails += check("T-STRUCT summary cost", round(tstruct_summary["official_rlm_depth1"]["estimated_api_cost_usd"], 6), 0.594778)
slm = load_csv("results/oolong_standard_multilength_n120_slm_labeler_question_parsed_typed_20260713.csv")
rlm = load_csv("results/oolong_standard_multilength_n120_rlm_20260712.csv")
direct = load_csv("results/oolong_standard_multilength_n120_direct_controller_gemini25flash_20260713.csv")
fails += check("Oolong N120 rows", (len(slm), len(rlm), len(direct)), (120, 120, 120))
fails += check("Oolong N120 exact", (exact(slm), exact(rlm), exact(direct)), (80, 53, 54))
threeway = json.loads((ROOT / "results/oolong_standard_multilength_n120_threeway_controller_analysis_20260713.json").read_text())
paired_n120 = threeway["paired"]
fails += check("Oolong N120 SLM-vs-RLM discordance", (paired_n120["slm_qparsed_typed_vs_standard_rlm"]["b_a_right_b_wrong"], paired_n120["slm_qparsed_typed_vs_standard_rlm"]["c_b_right_a_wrong"]), (37, 10))
fails += check("Oolong N120 direct-vs-RLM discordance", (paired_n120["direct_controller_vs_standard_rlm"]["b_a_right_b_wrong"], paired_n120["direct_controller_vs_standard_rlm"]["c_b_right_a_wrong"]), (26, 25))
valid = json.loads((ROOT / "results/oolong_standard_validation_n45_threeway_analysis_20260713.json").read_text())
fails += check("Oolong N45 exact", (valid["overall"]["slm_qparsed_typed"]["exact_count"], valid["overall"]["direct_controller"]["exact_count"], valid["overall"]["standard_rlm"]["exact_count"]), (30, 18, 17))
n150_slm = load_csv("results/oolong_standard_validation_n150_slm_labeler_question_parsed_typed_20260714.csv")
n150_direct = load_csv("results/oolong_standard_validation_n150_direct_controller_gemini25flash_20260714.csv")
n150_rlm = load_csv("results/oolong_standard_validation_n150_rlm_20260714.csv")
fails += check("Oolong N150 row alignment", (len(n150_slm), len(n150_direct), len(n150_rlm), paired(n150_slm, n150_rlm)[0], paired(n150_direct, n150_rlm)[0]), (150, 150, 150, 150, 150))
fails += check("Oolong N150 exact from case rows", (exact(n150_slm), exact(n150_direct), exact(n150_rlm)), (98, 65, 68))
fails += check("Oolong N150 costs from case rows", (cost(n150_slm), cost(n150_direct), cost(n150_rlm)), (0.838777, 1.93877, 4.144901))
fails += check("Oolong N150 SLM-vs-RLM discordance from case rows", paired(n150_slm, n150_rlm)[1:], (44, 14))
fails += check("Oolong N150 direct-vs-RLM discordance from case rows", paired(n150_direct, n150_rlm)[1:], (26, 29))
n150_qp = json.loads((ROOT / "results/oolong_standard_validation_n150_slm_labeler_question_parsed_typed_20260714_summary.json").read_text())
fails += check("Oolong N150 question-parser audit", (n150_qp["n"], n150_qp["exact_count"], n150_qp["task_parse_accuracy_vs_metadata"], n150_qp["answer_type_parse_accuracy_vs_metadata"]), (150, 98, 1.0, 1.0))
n150_overlap = json.loads((ROOT / "results/oolong_standard_validation_n150_split_overlap_audit_20260714.json").read_text())
fails += check("Oolong N150 split-overlap audit", (n150_overlap["union_target_id_overlap"], n150_overlap["union_target_context_window_overlap"], n150_overlap["union_target_rows_on_overlapping_context_windows"], n150_overlap["union_target_rows_on_new_context_windows"]), (20, 73, 150, 0))
cd45_summary = json.loads((ROOT / "results/oolong_context_disjoint_n45_manifest_20260715_summary.json").read_text())
fails += check("Oolong context-disjoint N45 manifest", (cd45_summary["n"], cd45_summary["unique_context_window_ids"], cd45_summary["max_questions_per_context_window_id"], cd45_summary["prior_overlap_check"]["selected_prior_id_overlap"], cd45_summary["prior_overlap_check"]["selected_prior_context_window_overlap"]), (45, 32, 2, 0, 0))
cd45_slm = load_csv("results/oolong_context_disjoint_n45_slm_labeler_question_parsed_typed_20260715.csv")
cd45_direct = load_csv("results/oolong_context_disjoint_n45_direct_controller_gemini25flash_20260715.csv")
cd45_rlm = load_csv("results/oolong_context_disjoint_n45_rlm_20260715.csv")
cd45_rlm_repeat = load_csv("results/oolong_context_disjoint_n45_rlm_repeat1_20260716.csv")
fails += check("Oolong context-disjoint N45 row alignment", (len(cd45_slm), len(cd45_direct), len(cd45_rlm), len(cd45_rlm_repeat), paired(cd45_slm, cd45_rlm)[0], paired(cd45_direct, cd45_rlm)[0]), (45, 45, 45, 45, 45, 45))
fails += check("Oolong context-disjoint N45 exact from case rows", (exact(cd45_slm), exact(cd45_direct), exact(cd45_rlm)), (36, 21, 27))
fails += check("Oolong context-disjoint N45 costs from case rows", (cost(cd45_slm), cost(cd45_direct), cost(cd45_rlm)), (0.416415, 1.02459, 1.001014))
fails += check("Oolong context-disjoint N45 SLM-vs-RLM discordance", paired(cd45_slm, cd45_rlm)[1:], (11, 2))
cd45_rlm_repeatability = json.loads((ROOT / "results/oolong_context_disjoint_n45_rlm_repeatability_20260716_summary.json").read_text())
fails += check("Oolong context-disjoint N45 RLM repeatability", (exact(cd45_rlm_repeat), cd45_rlm_repeatability["overall"]["standard_rlm_repeat1"]["exact_count"], cd45_rlm_repeatability["overall"]["standard_rlm_repeat1"]["errors"], cd45_rlm_repeatability["paired_exact"]["original_rlm_vs_repeat_rlm"]["a_only"], cd45_rlm_repeatability["paired_exact"]["original_rlm_vs_repeat_rlm"]["b_only"], cd45_rlm_repeatability["paired_exact"]["slm_vs_repeat_rlm"]["a_only"], cd45_rlm_repeatability["paired_exact"]["slm_vs_repeat_rlm"]["b_only"]), (21, 21, 2, 12, 6, 17, 2))
fails += check("Oolong context-disjoint N45 RLM repeatability cost", cd45_rlm_repeatability["overall"]["standard_rlm_repeat1"]["cost_usd"], 0.969986)
cd45_qp = json.loads((ROOT / "results/oolong_context_disjoint_n45_slm_labeler_question_parsed_typed_20260715_summary.json").read_text())
fails += check("Oolong context-disjoint N45 question-parser audit", (cd45_qp["n"], cd45_qp["exact_count"], cd45_qp["task_parse_accuracy_vs_metadata"], cd45_qp["answer_type_parse_accuracy_vs_metadata"]), (45, 36, 1.0, 1.0))
cd45_gpt5 = json.loads((ROOT / "results/oolong_context_disjoint_n45_gpt5_controller_freshness_analysis_20260715.json").read_text())
fails += check("Oolong context-disjoint N45 GPT-5 exact/errors", (cd45_gpt5["overall"]["standard_rlm_gpt5"]["exact_count"], cd45_gpt5["overall"]["standard_rlm_gpt5"]["errors"]), (23, 15))
fails += check("Oolong context-disjoint N45 SLM-vs-GPT5 discordance", (cd45_gpt5["paired_vs_gpt5"]["slm_qparsed_typed_vs_standard_rlm_gpt5"]["b_a_right_b_wrong"], cd45_gpt5["paired_vs_gpt5"]["slm_qparsed_typed_vs_standard_rlm_gpt5"]["c_b_right_a_wrong"]), (15, 2))
cd45_gpt56_canary = json.loads((ROOT / "results/oolong_context_disjoint_n45_gpt56_terra_rlm_canary3_20260715_summary.json").read_text())
cd45_gpt56_aborted = json.loads((ROOT / "results/oolong_context_disjoint_n45_gpt56_terra_rlm_aborted_credit_20260715_summary.json").read_text())
cd45_gpt56_interrupted = json.loads((ROOT / "results/oolong_context_disjoint_n45_gpt56_terra_rlm_interrupted_budget_20260715_summary.json").read_text())
cd45_gpt56_luna = json.loads((ROOT / "results/oolong_context_disjoint_n45_gpt56_luna_controller_freshness_analysis_20260718.json").read_text())
fails += check("Oolong context-disjoint N45 GPT-5.6 canary", (cd45_gpt56_canary["overall"]["rlm"]["n"], cd45_gpt56_canary["overall"]["rlm"]["exact_count"]), (3, 2))
fails += check("Oolong context-disjoint N45 GPT-5.6 aborted status", cd45_gpt56_aborted["metadata"]["status"], "aborted_provider_credit_exhaustion_not_benchmark")
fails += check("Oolong context-disjoint N45 GPT-5.6 interrupted", (cd45_gpt56_interrupted["metadata"]["status"], cd45_gpt56_interrupted["recorded_rows"], cd45_gpt56_interrupted["exact_count"], cd45_gpt56_interrupted["error_rows"]), ("interrupted_budget_safety_not_benchmark", 13, 7, 4))
fails += check("Oolong context-disjoint N45 GPT-5.6 provider delta", cd45_gpt56_interrupted["provider_usage_delta_usd"], 10.948003)
fails += check("Oolong context-disjoint N45 GPT-5.6 Luna exact/errors", (cd45_gpt56_luna["overall"]["standard_rlm_gpt56_luna"]["exact_count"], cd45_gpt56_luna["overall"]["standard_rlm_gpt56_luna"]["errors"]), (26, 2))
fails += check("Oolong context-disjoint N45 SLM-vs-GPT5.6 Luna discordance", (cd45_gpt56_luna["paired"]["slm_qparsed_typed_vs_standard_rlm_gpt56_luna"]["b_a_right_b_wrong"], cd45_gpt56_luna["paired"]["slm_qparsed_typed_vs_standard_rlm_gpt56_luna"]["c_b_right_a_wrong"]), (15, 5))
cd45_su150 = json.loads((ROOT / "results/oolong_cd45_vs_su150_selection_difficulty_audit_20260715.json").read_text())
fails += check("Oolong CD45-vs-SU150 selection audit", (cd45_su150["manifests"]["cd45"]["n"], cd45_su150["manifests"]["su150"]["n"], cd45_su150["performance"]["cd45"]["slm_qparsed_typed"]["exact_count"], cd45_su150["performance"]["su150"]["slm_qparsed_typed"]["exact_count"]), (45, 150, 36, 98))
cd15_repeatability = json.loads((ROOT / "results/oolong_context_disjoint_cd15_repeatability_manifest_20260715.json").read_text())
fails += check("Oolong CD15 repeatability manifest", (cd15_repeatability["summary"]["n"], cd15_repeatability["summary"]["groups"]["counting"], cd15_repeatability["summary"]["groups"]["timeline"], cd15_repeatability["summary"]["groups"]["user"], cd15_repeatability["summary"]["logged_exact_counts_on_parent_cd45_outputs"]["slm_qparsed_typed"], cd15_repeatability["summary"]["logged_exact_counts_on_parent_cd45_outputs"]["standard_rlm_gemini25_flash"]), (15, 5, 5, 5, 15, 10))
cd15_rollouts = json.loads((ROOT / "results/oolong_context_disjoint_cd15_rlm_repeatability_20260716_summary.json").read_text())
fails += check("Oolong CD15 RLM repeatability rollouts", (cd15_rollouts["aggregate_over_45_repeat_rows"]["n"], cd15_rollouts["aggregate_over_45_repeat_rows"]["exact_count"], cd15_rollouts["per_repeat"]["repeat1"]["exact_count"], cd15_rollouts["per_repeat"]["repeat2"]["exact_count"], cd15_rollouts["per_repeat"]["repeat3"]["exact_count"], cd15_rollouts["per_example_stability_counts"]["3"]), (45, 30, 13, 11, 6, 3))
fails += check("Oolong CD15 RLM repeatability cost", cd15_rollouts["aggregate_over_45_repeat_rows"]["cost_usd"], 1.252444)
cd15_direct = json.loads((ROOT / "results/oolong_context_disjoint_cd15_direct_gemini25_repeat_20260718_summary.json").read_text())
fails += check("Oolong CD15 direct replay", (cd15_direct["overall"]["slm_direct"]["n"], cd15_direct["overall"]["slm_direct"]["exact_count"], cd15_direct["overall"]["slm_direct"]["errors"]), (15, 8, 0))
fails += check("Oolong CD15 direct replay cost", cd15_direct["overall"]["slm_direct"]["cost_usd"], 0.340761)
cd15_positive = json.loads((ROOT / "results/oolong_context_disjoint_cd15_positive_regime_lock_20260718.json").read_text())
fails += check("Oolong CD15 retrospective exacts", (cd15_positive["overall"]["slm_typed_stored_cd15"]["exact_count"], cd15_positive["overall"]["direct_gemini_replay_cd15"]["exact_count"], cd15_positive["overall"]["standard_rlm_three_repeats_aggregate"]["exact_count"]), (15, 8, 30))
fails += check("Oolong CD15 retrospective clustered summary", (cd15_positive["item_clustered_descriptive"]["n_item_clusters"], cd15_positive["item_clustered_descriptive"]["observed_difference_points"], cd15_positive["item_clustered_descriptive"]["item_cluster_bootstrap_95_points"]), (15, 13.3, [-13.3, 40.0]))
fails += check("Oolong CD15 invalid pseudo-pair inference absent", ("direct_gemini_repeated_denominator" in cd15_positive["overall"], "standard_rlm_three_repeats_aggregate_vs_direct_repeated_denominator" in cd15_positive["paired"]), (False, False))
references_text = (ROOT / "references.bib").read_text(encoding="utf-8")
fails += check("Oolong venue corrected to COLM 2026", ("booktitle = {Conference on Language Modeling}" in references_text, "note      = {COLM 2026 accepted paper}" in references_text), (True, True))
cd45_trace = json.loads((ROOT / "results/oolong_context_disjoint_cd45_trace_examples_20260715.json").read_text())
fails += check("Oolong CD45 trace examples", (cd45_trace["summary"]["case_count"], cd45_trace["summary"]["outcome_pattern_counts"]["rlm_gemini,gpt5_rlm,slm,direct=1111"], cd45_trace["cases"][0]["example_id"]), (5, 14, "912090010"))
cd45_program_trace = json.loads((ROOT / "results/oolong_context_disjoint_cd45_rlm_program_trace_subset_20260716_summary.json").read_text())
fails += check("Oolong CD45 RLM program-trace subset", (cd45_program_trace["n"], cd45_program_trace["exact_count"], cd45_program_trace["errors"], cd45_program_trace["with_trajectory"], cd45_program_trace["code_block_count"], cd45_program_trace["cost_usd"]), (3, 2, 0, 3, 14, 0.015245))
cd45_specialization = json.loads((ROOT / "results/oolong_context_disjoint_cd45_specialization_controls_20260716_summary.json").read_text())
fails += check("Oolong CD45 specialization stress control", (cd45_specialization["n"], cd45_specialization["routes"]["question_parsed"]["exact_count"], cd45_specialization["routes"]["wrong_family_rotated"]["exact_count"], cd45_specialization["routes"]["generic_label_route"]["exact_count"]), (45, 36, 2, 3))
cd45_shared_operator = json.loads((ROOT / "results/oolong_context_disjoint_cd45_shared_operator_controller_20260716_summary.json").read_text())
fails += check("Oolong CD45 shared-operator controller", (cd45_shared_operator["n"], cd45_shared_operator["exact_count"], cd45_shared_operator["task_match_count"], cd45_shared_operator["answer_type_match_count"], cd45_shared_operator["parse_errors"], cd45_shared_operator["execution_errors"], round(cd45_shared_operator["cost_usd"], 6)), (45, 36, 45, 45, 0, 0, 0.008861))
cd45_same_ops = load_csv("results/oolong_cd45_rlm_same_ops_20260716.csv")
cd45_same_ops_summary = json.loads((ROOT / "results/oolong_cd45_rlm_same_ops_20260716_summary.json").read_text())
fails += check("Oolong CD45 same-operator standard rlms row", (len(cd45_same_ops), cd45_same_ops_summary["n"], cd45_same_ops_summary["exact_count"], round(cd45_same_ops_summary["mean_score"] * 100, 1), cd45_same_ops_summary["total_cost_usd"], cd45_same_ops_summary["errors"]), (45, 45, 31, 69.3, 1.31445, 2))
fails += check("Oolong CD45 same-operator standard rlms paired", (paired(cd45_slm, cd45_same_ops)[1:], paired(cd45_rlm, cd45_same_ops)[1:]), ((7, 2), (8, 12)))
fails += check("Oolong CD45 same-operator standard rlms boundary", "not official SRLM/lambda-RLM" in cd45_same_ops_summary["contract"], True)
cd45_atomic_ops = load_csv("results/oolong_cd45_rlm_atomic_ops_20260717.csv")
cd45_atomic_ops_summary = json.loads((ROOT / "results/oolong_cd45_rlm_atomic_ops_20260717_summary.json").read_text())
cd45_atomic_analysis = json.loads((ROOT / "results/oolong_cd45_same_operator_atomic_analysis_20260717.json").read_text())
fails += check("Oolong CD45 atomic same-operator standard rlms row", (len(cd45_atomic_ops), cd45_atomic_ops_summary["n"], cd45_atomic_ops_summary["exact_count"], round(cd45_atomic_ops_summary["mean_score"] * 100, 1), cd45_atomic_ops_summary["total_cost_usd"], cd45_atomic_ops_summary["errors"]), (45, 45, 29, 69.3, 0.958685, 4))
fails += check("Oolong CD45 atomic same-operator standard rlms tool mode", (cd45_atomic_ops_summary["tool_mode"], "solve_oolong_with_tools" in cd45_atomic_ops_summary["tool_names"]), ("atomic", False))
fails += check("Oolong CD45 atomic same-operator standard rlms paired", (paired(cd45_slm, cd45_atomic_ops)[1:], paired(cd45_same_ops, cd45_atomic_ops)[1:]), ((9, 2), (8, 6)))
fails += check("Oolong CD45 atomic same-operator analysis", (cd45_atomic_analysis["overall"]["same_ops_atomic"]["exact_count"], cd45_atomic_analysis["paired_exact"]["slm_qparsed_typed_vs_same_ops_atomic"]["slm_qparsed_typed_only"], cd45_atomic_analysis["paired_exact"]["slm_qparsed_typed_vs_same_ops_atomic"]["same_ops_atomic_only"]), (29, 9, 2))
cd45_same_operator_trace_exhibit = json.loads((ROOT / "results/oolong_cd45_same_operator_program_trace_exhibit_20260718.json").read_text())
fails += check("Oolong CD45 same-operator trace exhibit", (cd45_same_operator_trace_exhibit["metadata"]["case_count"], cd45_same_operator_trace_exhibit["metadata"]["model_calls_made_by_this_script"], cd45_same_operator_trace_exhibit["aggregate"]["same_ops_convenience"]["total_code_blocks"], cd45_same_operator_trace_exhibit["aggregate"]["same_ops_atomic"]["total_code_blocks"]), (10, 0, 348, 337))
tmixed = json.loads((ROOT / "results/tmixed_finalization_probe_combined_n20_20260713_summary.json").read_text())
fails += check("T-MIXED N20 exact", (tmixed["methods"]["direct_gemini"]["correct"], tmixed["methods"]["rlm_original_count_contract"]["correct"], tmixed["methods"]["rlm_content_json_contract"]["correct"]), (20, 0, 13))
tmixed_cc = json.loads((ROOT / "results/tmixed_current_contract_n30_20260714_analysis.json").read_text())
fails += check("T-MIXED current-contract N30 exact", (tmixed_cc["methods"]["direct_gemini"]["correct"], tmixed_cc["methods"]["rlm_content_json_contract"]["correct"]), (28, 18))
fails += check("T-MIXED current-contract N30 paired", (tmixed_cc["paired"]["direct_vs_content_rlm"]["b_a_right_b_wrong"], tmixed_cc["paired"]["direct_vs_content_rlm"]["c_b_right_a_wrong"]), (12, 2))
feas = json.loads((ROOT / "results/stronger_family_feasibility_gate_20260714.json").read_text())
fails += check("Stronger-family feasibility candidates", len(feas["candidates"]), 5)
lambda_official = json.loads((ROOT / "results/lambda_rlm_official_longbench_oolong_smoke_20260714_summary.json").read_text())
fails += check("lambda-RLM official-loader smoke", (lambda_official["n"], lambda_official["completed"], lambda_official["errors"], lambda_official["exact_count"], lambda_official["cost_known"]), (1, 0, 1, 0, False))
official_qwen = json.loads((ROOT / "results/official_rlm_qwen30b_cd15_20260719_analysis.json").read_text())
official_qwen_rows = load_jsonl("results/official_rlm_qwen30b_cd15_20260719_adjudicated.jsonl")
official_qwen_compact = load_jsonl("results/official_rlm_qwen30b_cd15_20260719_compact_trace.jsonl")
fails += check("Official RLM-Qwen3-30B CD15 row", (len(official_qwen_rows), len(official_qwen_compact), official_qwen["official_rlm_qwen30b"]["exact_count"], official_qwen["official_rlm_qwen30b"]["completed"], official_qwen["official_rlm_qwen30b"]["errors"]), (15, 14, 10, 14, 1))
fails += check("Official RLM-Qwen3-30B CD15 score/groups", (round(official_qwen["official_rlm_qwen30b"]["mean_score"], 6), official_qwen["by_group"]["counting"]["exact_count"], official_qwen["by_group"]["timeline"]["exact_count"], official_qwen["by_group"]["user"]["exact_count"]), (0.704167, 3, 4, 3))
fails += check("Official RLM-Qwen3-30B CD15 trace/cost", (official_qwen["latency_and_trace"]["total_code_blocks_completed_rows"], round(official_qwen["cost"]["protocol_accounted_compute_usd"], 6), round(official_qwen["cost"]["actual_runpod_spend_usd"], 6), official_qwen["cost"]["openrouter_spend_usd"]), (70, 1.719219, 12.509850, 0.0))
official_qwen_remaining = json.loads((ROOT / "results/oolong_context_disjoint_cd30_official_qwen_remaining_manifest_20260719.json").read_text())
official_qwen_stop = json.loads((ROOT / "results/official_rlm_qwen30b_cd30_completion_20260719_stoprule_analysis.json").read_text())
official_qwen_stop_rows = load_jsonl("results/official_rlm_qwen30b_cd30_completion_20260719_stoprule_compact_trace.jsonl")
fails += check("Official RLM-Qwen CD45 remainder", (official_qwen_remaining["summary"]["remaining_n"], official_qwen_remaining["summary"]["remaining_reuse_overlap"]), (30, 0))
fails += check("Official RLM-Qwen stopped prefix", (len(official_qwen_stop_rows), official_qwen_stop["returned_prefix"]["completed"], official_qwen_stop["returned_prefix"]["errors"], official_qwen_stop["returned_prefix"]["exact_count"], official_qwen_stop["usage"]["iterations"], official_qwen_stop["usage"]["code_blocks"]), (8, 6, 2, 2, 57, 55))
fails += check("Official RLM-Qwen serving limit", (official_qwen_stop["stop"]["minimum_input_tokens"], official_qwen_stop["stop"]["requested_output_tokens"], official_qwen_stop["stop"]["minimum_total_tokens"], official_qwen_stop["stop"]["max_model_len"]), (12289, 4096, 16385, 16384))
fails += check("Official RLM-Qwen stopped prefix nonclaim", "No pooled CD-45 official-policy accuracy or mean-score row is estimated." in official_qwen_stop["nonclaims"], True)
rollout = json.loads((ROOT / "results/oolong_rollout_variability_microaudit_20260714.json").read_text())
fails += check("Rollout micro-audit stable predictions", (rollout["agreement"]["slm_labeler_typed"]["prediction_stable_examples"], rollout["agreement"]["direct_controller"]["prediction_stable_examples"], rollout["agreement"]["rlm"]["prediction_stable_examples"]), (3, 3, 0))
rollout_stop = json.loads((ROOT / "results/oolong_rollout_variability_n15_stoprule_20260714.json").read_text())
rollout_stop_overall = rollout_stop["overall"]
rollout_stop_cmp = rollout_stop["comparisons"]
fails += check("Rollout stop-rule base exact", (rollout_stop_overall["base_slm"]["exact_count"], rollout_stop_overall["base_direct"]["exact_count"], rollout_stop_overall["base_rlm"]["exact_count"]), (12, 5, 6))
fails += check("Rollout stop-rule repeat exact/errors", (rollout_stop_overall["direct_repeat_full_n15"]["n"], rollout_stop_overall["direct_repeat_full_n15"]["exact_count"], rollout_stop_overall["direct_repeat_full_n15"]["errors"], rollout_stop_overall["rlm_repeat_stoprule_n3"]["n"], rollout_stop_overall["rlm_repeat_stoprule_n3"]["exact_count"], rollout_stop_overall["rlm_repeat_stoprule_n3"]["errors"]), (15, 5, 0, 3, 0, 2))
fails += check("Rollout stop-rule trace rows/stability", (rollout_stop["trace_rows"]["direct_repeat_full_n15"], rollout_stop["trace_rows"]["rlm_repeat_stoprule_n3"], rollout_stop_cmp["direct_base_vs_repeat_n15"]["prediction_stable"], rollout_stop_cmp["direct_base_vs_repeat_n15"]["correctness_stable"], rollout_stop_cmp["rlm_base_vs_stoprule_n3"]["prediction_stable"], rollout_stop_cmp["rlm_base_vs_stoprule_n3"]["correctness_stable"]), (15, 3, 15, 15, 0, 0))
sem = json.loads((ROOT / "results/semantic_boundary_failure_modes_20260713.json").read_text())
fails += check("Semantic-boundary Hotpot support exact", (sem["hotpotqa_support_fact_failure_modes"]["tfidf_top2"]["support_exact"], sem["hotpotqa_support_fact_failure_modes"]["llm_generated_lexical_operator"]["support_exact"], sem["hotpotqa_support_fact_failure_modes"]["llm_direct"]["support_exact"]), (3, 8, 17))
lb2_over = json.loads((ROOT / "results/lb2_over500k_retrieval_rerank_n30_retuned_20260714_analysis.json").read_text())
lb2_methods = lb2_over["methods"]
fails += check("LB2 over500 balanced N", lb2_over["n"], 30)
fails += check("LB2 over500 balanced exact", (lb2_methods["bm25_gemma_vote"]["correct"], lb2_methods["bm25_gemini_vote"]["correct"], lb2_methods["bm25_gemma_rerank_gemini_vote"]["correct"]), (8, 11, 12))
fails += check("LB2 over500 balanced rerank delta/net", (len(lb2_over["rerank_delta_rows"]), lb2_methods["bm25_gemma_rerank_gemini_vote"]["correct"] - lb2_methods["bm25_gemini_vote"]["correct"]), (3, 1))
lb2_smoke = json.loads((ROOT / "results/lb2_over500k_standard_rlm_smoke_n6_20260714_analysis.json").read_text())
lb2_smoke_methods = lb2_smoke["methods"]
fails += check("LB2 over500 standard-RLM smoke N", lb2_smoke["n"], 6)
fails += check("LB2 over500 standard-RLM smoke exact/errors", (lb2_smoke_methods["standard_rlm"]["correct"], lb2_smoke_methods["standard_rlm"]["errors"]), (1, 1))
fails += check("LB2 over500 standard-RLM smoke rerank/cost/no-scale", (lb2_smoke_methods["bm25_gemma_rerank_gemini_vote"]["correct"], round(lb2_smoke_methods["standard_rlm"]["total_cost_usd"], 6), lb2_smoke["decision"]["scale_standard_rlm_to_n30_now"]), (2, 0.469751, False))
if fails:
    sys.exit(1)
print("RELEASE VERIFIER: PASS")
