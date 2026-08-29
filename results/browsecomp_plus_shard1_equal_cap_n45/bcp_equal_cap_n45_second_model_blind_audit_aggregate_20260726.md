# BrowseComp-Plus Shard-1 Equal-Cap N45 Second-Model Audit

GPT-5.6 Sol (high reasoning) adjudicated all 173 successful route generations under method and primary-label blinding. Generation failures remain incorrect. This is independent second-model sensitivity, not human validation.

- Successful-output agreement: 172/173 (99.4%), Cohen's kappa 0.985.
- Positive/negative agreement: 99.6% / 98.9%.
- Judge disagreements: 1/173.
- Returned per-call cost sum: $0.757387; account delta: $0.631188.

| Method | Primary correct | Sol correct | Successful-output agreement | Primary no / Sol yes | Primary yes / Sol no |
|---|---:|---:|---:|---:|---:|
| Standard RLM | 31/45 | 31/45 | 41/41 (100.0%) | 0 | 0 |
| Iterative search agent | 33/45 | 33/45 | 45/45 (100.0%) | 0 | 0 |
| Text decomposition + same model | 37/45 | 37/45 | 45/45 (100.0%) | 0 | 0 |
| BM25 + same model | 25/45 | 24/45 | 41/42 (97.6%) | 0 | 1 |

## Sol-label paired sensitivity

| Pair | Difference | Left/right only | Bootstrap 95% | Exact p | Holm p (three RLM contrasts) |
|---|---:|---:|---:|---:|---:|
| rlm vs iterative | -4.4 pp | 6/8 | -20.0 to +11.1 pp | 0.7905 | 0.7905 |
| rlm vs text | -13.3 pp | 5/11 | -31.1 to +4.4 pp | 0.2101 | 0.4202 |
| rlm vs bm25 | +15.6 pp | 11/4 | +0.0 to +31.1 pp | 0.1185 | 0.3554 |
| iterative vs text | -8.9 pp | 5/9 | -24.4 to +6.7 pp | 0.4240 | -- |
| iterative vs bm25 | +20.0 pp | 13/4 | +2.2 to +37.8 pp | 0.0490 | -- |
| text vs bm25 | +28.9 pp | 14/1 | +15.6 to +44.4 pp | 0.0010 | -- |

Case text, opaque IDs, rationales and the disagreement ledger are restricted. The release surface contains only this aggregate and cryptographic hashes.
