# BrowseComp-Plus Equal-Cap N45 Seed-21 Second-Model Audit

GPT-5.6 Sol (high reasoning) adjudicated all 169 raw successful route generations under method and primary-label blinding. Outputs beyond the 1,200-second row cap and generation failures remain incorrect. This is independent second-model sensitivity for a post-hoc same-row rollout repeat, not human validation or an independent endpoint.

- Successful-output agreement: 166/169 (98.2%), Cohen's kappa 0.961.
- Positive/negative agreement: 98.6% / 97.4%.
- Judge disagreements: 3/169.
- Returned per-call cost sum: $0.811596; account delta: $0.718489.

| Method | Primary correct | Sol correct | Successful-output agreement | Primary no / Sol yes | Primary yes / Sol no |
|---|---:|---:|---:|---:|---:|
| Standard RLM | 30/45 | 29/45 | 36/37 (97.3%) | 0 | 1 |
| Iterative search agent | 31/45 | 30/45 | 44/45 (97.8%) | 0 | 1 |
| Text decomposition + same model | 29/45 | 28/45 | 44/45 (97.8%) | 0 | 1 |
| BM25 + same model | 22/45 | 22/45 | 42/42 (100.0%) | 0 | 0 |

## Sol-label paired sensitivity

| Pair | Difference | Left/right only | Bootstrap 95% | Exact p | Holm p (three RLM contrasts) |
|---|---:|---:|---:|---:|---:|
| rlm vs iterative | -2.2 pp | 7/8 | -20.0 to +15.6 pp | 1.0000 | 1.0000 |
| rlm vs text | +2.2 pp | 9/8 | -15.6 to +20.0 pp | 1.0000 | 1.0000 |
| rlm vs bm25 | +15.6 pp | 13/6 | -2.2 to +33.3 pp | 0.1671 | 0.5012 |
| iterative vs text | +4.4 pp | 7/5 | -11.1 to +20.0 pp | 0.7744 | -- |
| iterative vs bm25 | +17.8 pp | 13/5 | +0.0 to +35.6 pp | 0.0963 | -- |
| text vs bm25 | +13.3 pp | 11/5 | -4.4 to +31.1 pp | 0.2101 | -- |

Case text, opaque IDs, rationales and the disagreement ledger are restricted. The release surface contains only this aggregate and cryptographic hashes.
