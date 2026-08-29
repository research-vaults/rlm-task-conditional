# BrowseComp-Plus Shard-1 Equal-Cap N45 Study

This endpoint was prospectively frozen on outcome-unseen shard-1 ranks 46--90. All 45 rows and all four routes were attempted before semantic scoring; generation failures remain incorrect.

| Method | Complete | Semantic accuracy (Wilson 95%) | Calls | Input/output tokens | Median / p95 / max wall | Active-runtime cost |
|---|---:|---:|---:|---:|---:|---:|
| Standard RLM | 41/45 | 31/45 = 68.9% (54.3--80.5) | 476 | 3,853,035/174,599 | 50.1s / 628.8s / 1502.2s | $9.873 |
| Iterative search agent | 45/45 | 33/45 = 73.3% (59.0--84.0) | 426 | 8,421,368/110,999 | 14.1s / 90.2s / 147.4s | $1.710 |
| Text decomposition + same model | 45/45 | 37/45 = 82.2% (68.7--90.7) | 311 | 7,019,276/174,328 | 22.1s / 47.6s / 53.1s | $1.400 |
| BM25 + same model | 42/45 | 25/45 = 55.6% (41.2--69.1) | 42 | 2,222,815/25,591 | 3.0s / 20.0s / 22.7s | $0.296 |

## Paired comparisons

| Comparison | Difference | Left/right-only | Bootstrap 95% | McNemar p | Holm p (primary family) |
|---|---:|---:|---:|---:|---:|
| Standard RLM vs Iterative search agent | -4.4 pp | 6/8 | -20.0 to +11.1 pp | 0.7905 | 0.7905 |
| Standard RLM vs Text decomposition + same model | -13.3 pp | 5/11 | -31.1 to +4.4 pp | 0.2101 | 0.5387 |
| Standard RLM vs BM25 + same model | +13.3 pp | 10/4 | -2.2 to +28.9 pp | 0.1796 | 0.5387 |
| Iterative search agent vs Text decomposition + same model | -8.9 pp | 5/9 | -24.4 to +6.7 pp | 0.4240 | -- |
| Iterative search agent vs BM25 + same model | +17.8 pp | 12/4 | +2.2 to +33.3 pp | 0.0768 | -- |
| Text decomposition + same model vs BM25 + same model | +26.7 pp | 14/2 | +11.1 to +42.2 pp | 0.0042 | -- |

## Common-completion sensitivity

On the 39 rows completed by every route, standard RLM / iterative search / text decomposition / BM25 score 30/28/31/22. This conditioning is post-treatment; the all-attempted fixed-N endpoint remains primary.

| RLM comparison | Difference | Left/right-only | Bootstrap 95% | Exact p |
|---|---:|---:|---:|---:|
| Iterative search agent | +5.1 pp | 5/3 | -7.7 to +20.5 pp | 0.7266 |
| Text decomposition + same model | -2.6 pp | 5/6 | -20.5 to +12.8 pp | 1.0000 |
| BM25 + same model | +20.5 pp | 9/1 | +7.7 to +35.9 pp | 0.0215 |

## Cost and provenance

Latency summaries include all 45 attempted rows per route, including failed attempts. The p95 uses the linear empirical percentile (Hyndman-Fan type 7).

Generation used a one-row exact-runner qualification, an interrupted immutable ranks 2--19 episode and a pre-score ranks 20--45 recovery under the same runner. Generation plus semantic judging cost $15.015 at listed rates using a lower bound for the interrupted pod; OpenRouter cost was $0.00.
