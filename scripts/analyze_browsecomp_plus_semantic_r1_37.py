#!/usr/bin/env python3
"""Primary paired semantic analysis for complete BrowseComp+ ranks 1--37."""

from __future__ import annotations

import json
import hashlib
import math
import random
import statistics
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
COMPACT=ROOT/"results/browsecomp_plus_positive_regime/truncated_r1_38_deterministic_compact_restricted.json"
JUDGES=ROOT/"results/browsecomp_plus_positive_regime/bcp_gemma4_judge_r1_38_20260720_restricted.jsonl"
CASE_AUDIT=ROOT/"results/browsecomp_plus_positive_regime/bcp_semantic_disagreement_case_audit_r1_37_20260720.json"
POD_SUMMARY=ROOT/"results/browsecomp_plus_positive_regime/bcp_qwen36_stageA_20260720_summary.json"
OUT=ROOT/"results/browsecomp_plus_positive_regime/semantic_r1_37_primary_analysis.json"
REPORT=ROOT/"results/browsecomp_plus_positive_regime/semantic_r1_37_primary_analysis.md"
METHODS=("standard_rlm_qwen36","bm25_qwen36","text_decompose_qwen36")
LABELS={"standard_rlm_qwen36":"Standard RLM","bm25_qwen36":"BM25 + same model","text_decompose_qwen36":"Text decomposition + same model"}

def wilson(k:int,n:int,z:float=1.959963984540054)->list[float]:
    p=k/n; den=1+z*z/n; c=(p+z*z/(2*n))/den
    h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [c-h,c+h]

def exact_mcnemar(b:int,c:int)->float:
    n=b+c
    if not n:return 1.0
    tail=sum(math.comb(n,k) for k in range(0,min(b,c)+1))/(2**n)
    return min(1.0,2*tail)

def bootstrap_diff(left:list[bool],right:list[bool],seed:int=20260720,reps:int=20000)->list[float]:
    rng=random.Random(seed);n=len(left);vals=[]
    for _ in range(reps):
        ids=[rng.randrange(n) for _ in range(n)]
        vals.append(sum(int(left[i])-int(right[i]) for i in ids)/n)
    vals.sort();return [vals[int(.025*reps)],vals[min(reps-1,int(.975*reps))]]

def main()->None:
    compact=json.loads(COMPACT.read_text(encoding="utf-8"))
    case_audit=json.loads(CASE_AUDIT.read_text(encoding="utf-8"))
    pod_summary=json.loads(POD_SUMMARY.read_text(encoding="utf-8"))
    generation_rate=float(pod_summary["pod"]["cost_per_hr"])
    judge={}
    for line in JUDGES.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row=json.loads(line);judge[(int(row["rank"]),str(row["method"]))]=bool(row["judge"]["correct"])
    source={(int(r["rank"]),str(r["method"])):r for r in compact}
    ranks=list(range(1,38))
    disagreements=[]
    for key,row in sorted(source.items()):
        rank,method=key
        if rank in ranks and key in judge and bool(row["normalized_contains"]) != bool(judge[key]):
            disagreements.append(key)
    audit_rows={(int(r["rank"]),str(r["method"])):r for r in case_audit["cases"]}
    if set(audit_rows) != set(disagreements):
        raise ValueError(f"case-audit keys do not match semantic/containment disagreements: {set(audit_rows) ^ set(disagreements)}")
    for key,audit in audit_rows.items():
        row=source[key]
        expected={
            "question_sha256":hashlib.sha256(str(row["question"]).encode()).hexdigest(),
            "reference_sha256":hashlib.sha256(str(row["answer"]).encode()).hexdigest(),
            "prediction_sha256":hashlib.sha256(str(row["prediction"]).encode()).hexdigest(),
        }
        if any(audit[field] != value for field,value in expected.items()):
            raise ValueError(f"case-audit source hash mismatch for {key}")
        if bool(audit["normalized_contains"]) != bool(row["normalized_contains"]):
            raise ValueError(f"case-audit containment mismatch for {key}")
        if bool(audit["semantic_judge_correct"]) != bool(judge[key]):
            raise ValueError(f"case-audit judge mismatch for {key}")
    audit_agreement=sum(bool(r["case_audit_correct"]) == bool(r["semantic_judge_correct"]) for r in audit_rows.values())
    out:dict[str,Any]={
        "analysis_contract":"paired complete prospective ranks 1-37; generation failures count incorrect",
        "n":37,"semantic_judge":"google/gemma-4-26B-A4B-it","judge_revision":"01e5b3ee840d3a9e0b0b493c593e85398a30ef75",
        "case_audit":{
            "scope":"all semantic-vs-normalized-containment disagreements on paired ranks 1-37",
            "audited":len(audit_rows),
            "agreement_with_gemma":audit_agreement,
            "artifact":str(CASE_AUDIT.relative_to(ROOT)),
            "audit_type":case_audit["audit_contract"]["audit_type"],
            "judge_label_visible_during_case_audit":case_audit["audit_contract"]["judge_label_visible_during_case_audit"],
            "independent_human_validation":case_audit["audit_contract"]["independent_human_validation"],
        },
        "methods":{},"paired":{},
        "cost":{
            "openrouter_usd":0.0,"failed_h100_provider_billing_usd":0.4054053651634604,
            "stage_a_h200_provider_billing_usd_current_export":6.471934544155374,
            "stage_b_h200_provider_billing_usd_current_export":5.2756499404786155,
            "generation_current_provider_export_usd":12.15298984979745,
            "generation_listed_rate_estimate_through_user_stop_usd":14.558426469635,
            "judge_listed_rate_estimate_usd":0.33433934999981324,
            "note":"Stage-B provider billing was still populating; listed-rate creation-to-stop is the conservative attempted-cost estimate."
        }
    }
    correctness={}
    for method in METHODS:
        vals=[judge.get((rank,method),False) for rank in ranks]
        rows=[source[(rank,method)] for rank in ranks]
        correctness[method]=vals;k=sum(vals);completed=sum(int(r["ok"]) for r in rows)
        lat=[float(r["wall_seconds"]) for r in rows]
        out["methods"][method]={"attempted":37,"completed":completed,"completion_rate":completed/37,
            "semantic_correct":k,"semantic_accuracy":k/37,"wilson_95":wilson(k,37),
            "strict_exact":sum(int(r["strict_exact"]) for r in rows),
            "normalized_contains":sum(int(r["normalized_contains"]) for r in rows),
            "wall_seconds_total":sum(lat),"wall_seconds_median":statistics.median(lat),"wall_seconds_max":max(lat),
            "active_runtime_listed_rate_usd":sum(lat)/3600*generation_rate,
            "rlm_iterations":sum(int(r["iterations"]) for r in rows),"rlm_code_blocks":sum(int(r["code_blocks"]) for r in rows)}
    out["cost"]["generation_pod_listed_rate_usd_per_hour"]=generation_rate
    out["cost"]["route_attribution_scope"]="active row wall time multiplied by the listed generation-pod hourly rate; excludes shared startup, idle time, failed H100 attempt, and semantic judge"
    out["cost"]["active_runtime_routes_total_usd"]=sum(x["active_runtime_listed_rate_usd"] for x in out["methods"].values())
    for i,left in enumerate(METHODS):
        for right in METHODS[i+1:]:
            l,r=correctness[left],correctness[right];b=sum(x and not y for x,y in zip(l,r));c=sum(y and not x for x,y in zip(l,r))
            out["paired"][f"{left}__vs__{right}"]={"left_only":b,"right_only":c,"difference":sum(l)/37-sum(r)/37,
                "paired_bootstrap_95":bootstrap_diff(l,r,20260720+i),"mcnemar_exact_two_sided_p":exact_mcnemar(b,c)}
    OUT.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    lines=["# BrowseComp+ Prospective Positive-Regime Analysis","", "Primary paired set: frozen ranks 1--37 (`N=37`); failed generations count incorrect. Rank 38 is excluded because the user-requested stop occurred before all three methods were attempted.","", "| Method | Complete | Semantic accuracy (Wilson 95%) | Median / max wall time | Active-runtime listed-rate cost |", "|---|---:|---:|---:|---:|"]
    for m in METHODS:
        x=out["methods"][m];lo,hi=x["wilson_95"]
        lines.append(f"| {LABELS[m]} | {x['completed']}/37 | {x['semantic_correct']}/37 = {100*x['semantic_accuracy']:.1f}% ({100*lo:.1f}--{100*hi:.1f}) | {x['wall_seconds_median']:.1f}s / {x['wall_seconds_max']:.1f}s | ${x['active_runtime_listed_rate_usd']:.3f} |")
    lines += ["", "## Paired comparisons", "", "| Comparison | Difference | Discordant left/right | Paired bootstrap 95% | McNemar p |", "|---|---:|---:|---:|---:|"]
    for key,x in out["paired"].items():
        a,b=key.split("__vs__");lo,hi=x["paired_bootstrap_95"]
        lines.append(f"| {LABELS[a]} vs {LABELS[b]} | {100*x['difference']:+.1f} pp | {x['left_only']}/{x['right_only']} | {100*lo:+.1f} to {100*hi:+.1f} pp | {x['mcnemar_exact_two_sided_p']:.3f} |")
    lines += ["", "## Interpretation", "", "Standard RLM has the highest semantic point estimate, but all paired intervals include zero and exact McNemar tests are non-significant. These are the first 37 fully paired ranks of a prospectively frozen N=80 manifest, user-truncated for time outside the planned hard-stop rules before scoring; they are not a locked endpoint or evidence of universal superiority. The result also exposes the price of the point estimate: standard RLM has lower completion and an extreme latency tail, while the same-model alternatives are much faster.", "", f"At the generation pod's listed ${generation_rate:.2f}/hour rate, route-attributed active row time is ${out['methods']['standard_rlm_qwen36']['active_runtime_listed_rate_usd']:.3f} for standard RLM, ${out['methods']['text_decompose_qwen36']['active_runtime_listed_rate_usd']:.3f} for textual decomposition, and ${out['methods']['bm25_qwen36']['active_runtime_listed_rate_usd']:.3f} for BM25. These allocations exclude shared startup/idle time, the failed H100 attempt, and judging; the conservative creation-to-stop generation total remains ${out['cost']['generation_listed_rate_estimate_through_user_stop_usd']:.3f}.","", f"A row-level post-hoc project case audit covers all {len(audit_rows)} semantic-versus-containment disagreements and agrees with Gemma on {audit_agreement}/{len(audit_rows)}. The audit records source hashes, labels, rationale codes, and short rationales in `{CASE_AUDIT.relative_to(ROOT)}`. Judge labels and method identity were visible, so this is an auditable case inspection, not independent human validation or an inter-annotator agreement study."]
    REPORT.write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(json.dumps(out,indent=2,sort_keys=True))

if __name__=="__main__":main()
