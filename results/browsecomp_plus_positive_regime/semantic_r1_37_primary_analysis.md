# BrowseComp+ Prospective Positive-Regime Analysis

Primary paired set: frozen ranks 1--37 (`N=37`); failed generations count incorrect. Rank 38 is excluded because the user-requested stop occurred before all three methods were attempted.

| Method | Complete | Semantic accuracy (Wilson 95%) | Median / max wall time | Active-runtime listed-rate cost |
|---|---:|---:|---:|---:|
| Standard RLM | 32/37 | 24/37 = 64.9% (48.8--78.2) | 50.2s / 1279.5s | $7.390 |
| BM25 + same model | 34/37 | 21/37 = 56.8% (40.9--71.3) | 3.0s / 21.2s | $0.115 |
| Text decomposition + same model | 37/37 | 22/37 = 59.5% (43.5--73.7) | 23.9s / 65.0s | $0.787 |

## Paired comparisons

| Comparison | Difference | Discordant left/right | Paired bootstrap 95% | McNemar p |
|---|---:|---:|---:|---:|
| Standard RLM vs BM25 + same model | +8.1 pp | 10/7 | -13.5 to +29.7 pp | 0.629 |
| Standard RLM vs Text decomposition + same model | +5.4 pp | 9/7 | -16.2 to +27.0 pp | 0.804 |
| BM25 + same model vs Text decomposition + same model | -2.7 pp | 4/5 | -18.9 to +13.5 pp | 1.000 |

## Interpretation

Standard RLM has the highest semantic point estimate, but all paired intervals include zero and exact McNemar tests are non-significant. These are the first 37 fully paired ranks of a prospectively frozen N=80 manifest, user-truncated for time outside the planned hard-stop rules before scoring; they are not a locked endpoint or evidence of universal superiority. The result also exposes the price of the point estimate: standard RLM has lower completion and an extreme latency tail, while the same-model alternatives are much faster.

At the generation pod's listed $2.99/hour rate, route-attributed active row time is $7.390 for standard RLM, $0.787 for textual decomposition, and $0.115 for BM25. These allocations exclude shared startup/idle time, the failed H100 attempt, and judging; the conservative creation-to-stop generation total remains $14.558.

A row-level post-hoc project case audit covers all 15 semantic-versus-containment disagreements and agrees with Gemma on 15/15. The audit records source hashes, labels, rationale codes, and short rationales in `results/browsecomp_plus_positive_regime/bcp_semantic_disagreement_case_audit_r1_37_20260720.json`. Judge labels and method identity were visible, so this is an auditable case inspection, not independent human validation or an inter-annotator agreement study.
