# Claim-to-Command Map

This map separates deterministic verification from analyses that require
restricted benchmark inputs, credentials or temporary model-serving
infrastructure. `PUBLIC_RERUN` commands run from the repository root
and write only under `_reproduced/`, outside the immutable reference manifest.
`PUBLIC_SKIP` commands terminate successfully with an explicit withheld-input
message and direct the reviewer to the root verifier. `LOCAL_ONLY` commands
document the full-data reconstruction path but cannot run from this release
because their raw inputs are intentionally excluded.

## One-command release verification

```bash
python3 verify_release.py
```

This no-call command verifies `SHA256SUMS.json`, parses every released
JSON/JSONL/CSV file, compiles every released Python file and checks the
claim-bearing counts, costs, intervals and frozen manuscript surfaces used by the
paper. It makes no network, API, model or GPU calls.

## Claim-bearing evidence map

| Paper surface | Status | Analysis or verification command | Released evidence and boundary |
|---|---|---|---|
| All claim-bearing release surfaces | `PUBLIC_RERUN` | `python3 verify_release.py` | Verifies the repository manifest, every structured file and script, and the released claim ledger without model, network or GPU calls. |
| Oolong LP-80/LP-150 and standard-unlabeled SU-30/SU-120/SU-150 | `PUBLIC_RERUN` through root verifier | `python3 verify_release.py` | `results/oolong_*` aggregates, tables and traces are checked. Raw restricted Oolong text is excluded. |
| Oolong VC-45 transfer | `LOCAL_ONLY` analysis; public aggregate verification | `python3 scripts/analyze_oolong_validation_corpus_disjoint_n45.py` | The full-data command needs restricted route rows. The repository ships release-safe route summaries/traces and checks them through `verify_release.py`. |
| Oolong CD-45 repeatability | `PUBLIC_RERUN` | `python3 scripts/analyze_oolong_cd45_rlm_repeatability.py --output-dir _reproduced/oolong_cd45_repeatability` | Recomputes the repeatability summary from released rows without changing immutable reference evidence. Fresh generation still requires benchmark access and provider credentials. |
| Official-policy RLM-Qwen CD-15 | `LOCAL_ONLY` analysis; public aggregate verification | `python3 scripts/analyze_official_rlm_qwen30b_cd15.py` | The 105 MB raw trajectory repeats restricted context and is excluded. Compact trajectories, adjudicated summaries, source hashes and result checks are released. |
| Official-code lambda-RLM CD-15 | `LOCAL_ONLY` analysis; public aggregate verification | `python3 scripts/analyze_lambda_rlm_official_cd15.py --help` | The analyzer requires the full frozen manifest/events/balance/billing arguments documented by the protocol. Released compact outputs and aggregates are checked by the root verifier. |
| BrowseComp-Plus N=80 and score-blind N=49 replication | `LOCAL_ONLY` reconstruction; public aggregate verification | `python3 scripts/analyze_browsecomp_plus_n80.py`; `python3 scripts/analyze_browsecomp_plus_replication_n49.py` | Restricted compact generations and 1,000-document pools are excluded. Public manifests, hashes, aggregates and judge summaries are released and root-verified. |
| BrowseComp-Plus fixed-N45 and equal-cap seed-20 endpoint | `PUBLIC_SKIP` plus public aggregate verification | `python3 scripts/verify_browsecomp_plus_shard1_fixed_n45.py`; `python3 scripts/verify_browsecomp_plus_shard1_equal_cap_n45.py` | Both endpoint verifiers exit 0, name withheld row-level inputs and direct reviewers to `verify_release.py`, which checks the released aggregates and claims. |
| Equal-cap seed-21 same-row sensitivity | `LOCAL_ONLY` reconstruction; public aggregate verification | `python3 scripts/analyze_browsecomp_equal_cap_n45_seed21.py` | Restricted compact generations are excluded; release-safe analysis and judge aggregates are root-verified. |
| Dense-hybrid and no-subcall sensitivities | `LOCAL_ONLY` reconstruction; public aggregate verification | `python3 scripts/analyze_browsecomp_n49_dense_hybrid_sensitivity.py`; `python3 scripts/analyze_browsecomp_rlm_no_subcall_n49.py` | Restricted row outputs and document pools are excluded. Public aggregates, protocols and central counts are root-verified. |
| HotpotQA and semantic-boundary diagnostics | `LOCAL_ONLY` reconstruction; public aggregate verification | `python3 scripts/analyze_hotpotqa_public_semantic_slice.py`; `python3 scripts/analyze_semantic_boundary_failure_modes.py` | Upstream corpus rows are not redistributed. Released result summaries, tables and figure source values are root-verified. |
| LongBench-v2 over-500k diagnostics | `LOCAL_ONLY` reconstruction; public aggregate verification | `python3 scripts/analyze_lb2_over500k_retrieval_rerank.py --output-dir _reproduced/lb2_retrieval`; `python3 scripts/analyze_lb2_over500k_standard_rlm_smoke.py --output-dir _reproduced/lb2_rlm_smoke` | Source-document-scale trace/context inputs are excluded. When release-safe row inputs are present, generated analyses are isolated under `_reproduced/` and never overwrite manifested reference evidence. Released aggregates, tables and plots are checked by `verify_release.py`. |
| Attempted-cost audit | `LOCAL_ONLY` reconstruction; public aggregate verification | `python3 scripts/audit_attempted_costs.py --output _reproduced/attempted_cost_audit_latest.json` | Source model-call logs are excluded. The script fails closed rather than writing a zero audit when those inputs are absent; the promoted stored aggregate is checked by `verify_release.py`. |
| Engineering break-even sensitivity | `PUBLIC_RERUN` | `python3 scripts/analyze_engineering_break_even.py --output-dir _reproduced/engineering_break_even` | Deterministic no-call sensitivity over released aggregate records; writes only to the generated-output directory. |

## Environment and execution boundaries

Install the recorded Python environment with:

```bash
python3 -m pip install -r requirements.txt
```

Some scripts are execution drivers rather than no-call reproduction commands.
They require credentials, licensed or restricted benchmark inputs and the
external model/repository revisions named in their protocol files. The repository
does not include credentials or restricted corpora and does not claim that
fresh model generations can be reproduced offline. The root verifier is the
authoritative release-local check for the submitted immutable result package.
It ignores only the user-generated `_reproduced/` subtree and continues to
reject any other unmanifested or modified member.
