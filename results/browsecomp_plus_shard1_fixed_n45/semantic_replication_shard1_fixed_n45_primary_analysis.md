# BrowseComp-Plus Shard-1 Fixed-N45 Replication

This endpoint was prospectively frozen on a disjoint official query shard. All 45 rows and all three routes were attempted before semantic scoring; generation failures remain incorrect.

| Method | Complete | Semantic accuracy (Wilson 95%) | Calls | Input/output tokens | Median / p95 / max wall | Active-runtime cost |
|---|---:|---:|---:|---:|---:|---:|
| Standard RLM | 42/45 | 33/45 = 73.3% (59.0--84.0) | 607 | 6,133,671/188,943 | 44.6s / 425.7s / 1289.4s | $6.746 |
| BM25 + same model | 42/45 | 21/45 = 46.7% (32.9--60.9) | 42 | 2,222,961/23,064 | 3.2s / 19.6s / 21.2s | $0.294 |
| Text decomposition + same model | 45/45 | 29/45 = 64.4% (49.8--76.8) | 314 | 7,236,374/205,696 | 29.6s / 44.9s / 62.5s | $1.610 |

## Paired comparisons

| Comparison | Difference | Left/right-only | Bootstrap 95% | McNemar p | Holm p (primary family) |
|---|---:|---:|---:|---:|---:|
| Standard RLM vs BM25 + same model | +26.7 pp | 15/3 | +11.1 to +44.4 pp | 0.0075 | 0.0151 |
| Standard RLM vs Text decomposition + same model | +8.9 pp | 9/5 | -6.7 to +24.4 pp | 0.4240 | 0.4240 |
| BM25 + same model vs Text decomposition + same model | -17.8 pp | 1/9 | -31.1 to -4.4 pp | 0.0215 | -- |

## Common-completion sensitivity

This post-treatment sensitivity retains only rows with successful nonblank generation from all three routes. It does not replace the fixed-N45 failure-as-incorrect primary endpoint.

| Method | Semantic accuracy (Wilson 95%) |
|---|---:|
| Standard RLM | 30/39 = 76.9% (61.7--87.4) |
| BM25 + same model | 19/39 = 48.7% (33.9--63.8) |
| Text decomposition + same model | 23/39 = 59.0% (43.4--72.9) |

| Comparison | Difference | Left/right-only | Bootstrap 95% | McNemar p |
|---|---:|---:|---:|---:|
| Standard RLM vs BM25 + same model | +28.2 pp | 12/1 | +12.8 to +43.6 pp | 0.0034 |
| Standard RLM vs Text decomposition + same model | +17.9 pp | 9/2 | +2.6 to +33.3 pp | 0.0654 |
| BM25 + same model vs Text decomposition + same model | -10.3 pp | 1/5 | -23.1 to +0.0 pp | 0.2188 |

## Cost and provenance

Latency summaries include all 45 attempted rows per route, including failed attempts. The p95 uses the linear empirical percentile (Hyndman-Fan type 7).

Generation used two disclosed infrastructure episodes after a local-driver interruption: the original 107 cells were retained and only 28 missing cells were resumed on the same pod. Generation plus semantic judging cost $10.459 at listed rates; OpenRouter cost was $0.00.

The prior shard-0 attempted-N49 result is retained only as chronological context. It is not pooled into this primary fixed-N45 endpoint.
