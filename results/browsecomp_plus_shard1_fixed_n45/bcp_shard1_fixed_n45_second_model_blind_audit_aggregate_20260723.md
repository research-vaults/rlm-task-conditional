# BrowseComp-Plus Shard-1 N45 Independent Second-Model Audit

GPT-5.6 Sol (high reasoning) adjudicated all 129 successful route generations under method and primary-label blinding. Generation failures remain incorrect. This is independent second-model sensitivity, not human validation.

- Successful-output agreement: 128/129 (99.2%), Cohen's kappa 0.983.
- Positive/negative agreement: 99.4% / 98.9%.
- Judge disagreements: 1/129.
- Returned per-call cost sum: $0.590893; account delta: $0.496861.

| Method | Primary correct | Sol correct | Successful-output agreement | Primary no / Sol yes | Primary yes / Sol no |
|---|---:|---:|---:|---:|---:|
| Standard RLM | 33/45 | 33/45 | 42/42 (100.0%) | 0 | 0 |
| Text decomposition + same model | 29/45 | 28/45 | 44/45 (97.8%) | 0 | 1 |
| BM25 + same model | 21/45 | 21/45 | 42/42 (100.0%) | 0 | 0 |

## Sol-label paired sensitivity

| Pair | Difference | Left/right only | Bootstrap 95% | Exact p | Holm p (two RLM contrasts) |
|---|---:|---:|---:|---:|---:|
| rlm vs text | +11.1 pp | 10/5 | -6.7 to +26.7 pp | 0.3018 | 0.3018 |
| rlm vs bm25 | +26.7 pp | 15/3 | +8.9 to +42.2 pp | 0.0075 | 0.0151 |
| text vs bm25 | +15.6 pp | 9/2 | +2.2 to +28.9 pp | 0.0654 | -- |

Case text, opaque IDs, rationales and the disagreement ledger are restricted. The release surface contains only this aggregate and cryptographic hashes.
