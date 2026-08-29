# BrowseComp+ Untouched-Slice Replication (Attempted N=49)

All 59 untouched rows were frozen before model output. Score-blind generation reached the predeclared stability stop at rank 49; all attempted rows and failures remain in the denominator. Semantic judging occurred only after generation closed.

| Method | Complete | Semantic accuracy (Wilson 95%) | Median / max wall | Active-runtime cost |
|---|---:|---:|---:|---:|
| Standard RLM | 43/49 | 35/49 = 71.4% (57.6--82.2) | 69.9s / 2694.4s | $15.046 |
| BM25 + same model | 46/49 | 21/49 = 42.9% (30.0--56.7) | 4.0s / 22.0s | $0.321 |
| Text decomposition + same model | 48/49 | 21/49 = 42.9% (30.0--56.7) | 29.2s / 65.5s | $1.884 |

## Paired comparisons

| Comparison | Difference | Left/right-only | Bootstrap 95% | McNemar p |
|---|---:|---:|---:|---:|
| Standard RLM vs BM25 + same model | +28.6 pp | 19/5 | +10.2 to +46.9 pp | 0.0066 |
| Standard RLM vs Text decomposition + same model | +28.6 pp | 17/3 | +12.2 to +44.9 pp | 0.0026 |
| BM25 + same model vs Text decomposition + same model | +0.0 pp | 4/4 | -12.2 to +12.2 pp | 1.0000 |

## Cost and synthesis

Generation plus semantic judging cost $18.580 at listed rates; OpenRouter cost was $0.00.

The separately labeled N=129 synthesis combines the original N=80 and this N=49 attempted endpoint descriptively; it does not erase the original two-episode provenance.
