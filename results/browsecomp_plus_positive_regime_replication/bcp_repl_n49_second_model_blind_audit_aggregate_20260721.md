# BrowseComp+ N=49 Exhaustive Independent Second-Model Audit

GPT-5.6 Luna (high reasoning) adjudicated all 137 successful route generations under method and primary-label blinding. The ten generation failures remain incorrect. This is independent second-model sensitivity, not human validation.

- Successful-output agreement: 132/137 (96.4%), Cohen's kappa 0.927.
- Judge disagreements: 5/137.
- Returned per-call cost sum: $0.112735; concurrent provider-account delta: $0.496674.

| Method | Primary correct | Luna correct | Successful-output agreement | Primary no / Luna yes | Primary yes / Luna no |
|---|---:|---:|---:|---:|---:|
| Standard RLM | 35/49 | 33/49 | 41/43 (95.3%) | 0 | 2 |
| Text decomposition + same model | 21/49 | 20/49 | 47/48 (97.9%) | 0 | 1 |
| BM25 + same model | 21/49 | 19/49 | 44/46 (95.7%) | 0 | 2 |

## Luna-label paired sensitivity

| Pair | Difference | Left/right only | Bootstrap 95% | Exact p | Holm p |
|---|---:|---:|---:|---:|---:|
| rlm vs text | +26.5 pp | 16/3 | +10.2 to +42.9 pp | 0.0044 | 0.0130 |
| rlm vs bm25 | +28.6 pp | 18/4 | +12.2 to +44.9 pp | 0.0043 | 0.0130 |
| text vs bm25 | +2.0 pp | 4/3 | -8.2 to +12.2 pp | 1.0000 | 1.0000 |

Case text, opaque IDs, rationales, and the disagreement ledger are restricted. The release surface contains only this aggregate and cryptographic hashes.
