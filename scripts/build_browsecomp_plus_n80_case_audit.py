#!/usr/bin/env python3
"""Build the row-level project audit for all N=80 semantic disagreements."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULT_DIR = ROOT / "results/browsecomp_plus_positive_regime"
COMPACT = RESULT_DIR / "bcp_qwen36_n80_deterministic_compact_restricted.json"
ANALYSIS = RESULT_DIR / "semantic_n80_resumed_primary_analysis.json"
OLD_AUDIT = RESULT_DIR / "bcp_semantic_disagreement_case_audit_r1_37_20260720.json"
OUT = RESULT_DIR / "bcp_semantic_disagreement_case_audit_n80_20260720.json"

NEW_DECISIONS = {
    (38, "bm25_qwen36"): (True, "equivalent_name_and_title", "Marie of Romania with her queen-consort title identifies Queen Marie of Romania."),
    (40, "bm25_qwen36"): (False, "reference_only_in_rejected_reasoning", "The response mentions Vera Nunning only while arguing that no person satisfies the clues, so it does not answer with her."),
    (46, "bm25_qwen36"): (False, "wrong_final_entity", "The response selects Chris Benoit rather than the reference Chris Jericho."),
    (58, "bm25_qwen36"): (True, "same_paper_title_variant", "The title variant and author list identify the same Blackwell, Trzesniewski, and Dweck intervention paper."),
    (58, "text_decompose_qwen36"): (True, "same_paper_title_variant", "The shortened title identifies the same longitudinal intelligence intervention paper."),
    (59, "text_decompose_qwen36"): (False, "candidate_mentioned_but_rejected", "The response discusses Taj-ul-Masajid but concludes that no mosque can be identified."),
    (67, "text_decompose_qwen36"): (False, "answer_only_in_rejected_reasoning", "Jim Hibbert appears only as part of a rejected candidate chain and the final answer says the husband cannot be determined."),
    (75, "text_decompose_qwen36"): (False, "incomplete_legal_name", "The question asks for the real full name, but the response gives only the shorter publication name and omits multiple names in the reference."),
    (77, "standard_rlm_qwen36"): (True, "equivalent_order_and_wording", "The response contains both the 2300-year age and Sara Beatriz Maldonado in an acceptable sentence form."),
    (77, "text_decompose_qwen36"): (True, "equivalent_order_and_wording", "The semicolon-delimited reference and the comma-delimited response contain the same name and age."),
}


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    compact = json.loads(COMPACT.read_text(encoding="utf-8"))
    source = {(int(row["rank"]), str(row["method"])): row for row in compact}
    analysis = json.loads(ANALYSIS.read_text(encoding="utf-8"))
    disagreements = {
        (int(row["rank"]), str(row["method"])): row
        for row in analysis["semantic_vs_containment_disagreements"]
    }
    old = json.loads(OLD_AUDIT.read_text(encoding="utf-8"))
    old_rows = {(int(row["rank"]), str(row["method"])): row for row in old["cases"]}
    if set(old_rows) | set(NEW_DECISIONS) != set(disagreements):
        raise ValueError("old plus new decisions do not exactly cover N=80 disagreements")
    if set(old_rows) & set(NEW_DECISIONS):
        raise ValueError("old/new audit overlap")

    cases = []
    for key in sorted(disagreements):
        row = source[key]
        semantic = bool(disagreements[key]["semantic_correct"])
        contains = bool(disagreements[key]["normalized_contains"])
        hashes = {
            "question_sha256": sha256_text(str(row["question"])),
            "reference_sha256": sha256_text(str(row["answer"])),
            "prediction_sha256": sha256_text(str(row["prediction"])),
        }
        if key in old_rows:
            prior = old_rows[key]
            if any(prior[field] != value for field, value in hashes.items()):
                raise ValueError(f"old source hash mismatch for {key}")
            audit_correct = bool(prior["case_audit_correct"])
            rationale_code = str(prior["rationale_code"])
            rationale = str(prior["rationale"])
            provenance = "carried_forward_from_r1_37_audit"
        else:
            audit_correct, rationale_code, rationale = NEW_DECISIONS[key]
            provenance = "new_project_side_n80_audit"
        cases.append(
            {
                "rank": key[0],
                "method": key[1],
                **hashes,
                "normalized_contains": contains,
                "semantic_judge_correct": semantic,
                "case_audit_correct": audit_correct,
                "agrees_with_semantic_judge": audit_correct == semantic,
                "rationale_code": rationale_code,
                "rationale": rationale,
                "provenance": provenance,
            }
        )

    payload = {
        "study_id": "browsecomp_plus_positive_regime_v1_4_resumption",
        "audit_contract": {
            "scope": "all semantic-judge versus normalized-containment disagreements on the completed N=80 endpoint",
            "audit_type": "post_hoc_project_case_inspection",
            "reference_answer_visible": True,
            "semantic_judge_label_visible": True,
            "method_identity_visible": True,
            "independent_human_validation": False,
            "inter_annotator_agreement_study": False,
            "primary_score_changed": False,
            "sensitivity_role": "replace semantic-judge labels with project-audit labels only as a disclosed sensitivity",
        },
        "sources": {
            "compact": str(COMPACT.relative_to(ROOT)),
            "compact_sha256": sha256_file(COMPACT),
            "semantic_analysis": str(ANALYSIS.relative_to(ROOT)),
            "prior_r1_37_audit": str(OLD_AUDIT.relative_to(ROOT)),
            "prior_r1_37_audit_sha256": sha256_file(OLD_AUDIT),
        },
        "n_disagreements": len(cases),
        "agreement_with_semantic_judge": sum(int(row["agrees_with_semantic_judge"]) for row in cases),
        "cases": cases,
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT.relative_to(ROOT)), "n": len(cases), "agreement": payload["agreement_with_semantic_judge"], "sha256": sha256_file(OUT)}, indent=2))


if __name__ == "__main__":
    main()
