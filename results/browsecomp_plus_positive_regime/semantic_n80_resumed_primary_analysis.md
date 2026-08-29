# BrowseComp+ N=80 Interrupted-Then-Resumed Semantic Analysis

The originally frozen N=80 manifest is complete across two execution episodes. Ranks 1--37 were scored before resumption; this is disclosed and the result is not described as an uninterrupted preregistered run. Failed generations count incorrect.

| Method | Complete | Semantic accuracy (Wilson 95%) | Median / max wall time | Active-runtime listed-rate cost |
|---|---:|---:|---:|---:|
| Standard RLM | 70/80 | 54/80 = 67.5% (56.6--76.8) | 50.2s / 1279.5s | $23.482 |
| BM25 + same model | 75/80 | 39/80 = 48.8% (38.1--59.5) | 3.1s / 21.2s | $0.469 |
| Text decomposition + same model | 80/80 | 48/80 = 60.0% (49.0--70.0) | 23.5s / 65.0s | $2.440 |

## Paired comparisons

| Comparison | Difference | Left/right-only | Paired bootstrap 95% | McNemar p |
|---|---:|---:|---:|---:|
| Standard RLM vs BM25 + same model | +18.8 pp | 25/10 | +5.0 to +32.5 pp | 0.0167 |
| Standard RLM vs Text decomposition + same model | +7.5 pp | 19/13 | -6.2 to +21.2 pp | 0.3771 |
| BM25 + same model vs Text decomposition + same model | -11.2 pp | 8/17 | -23.8 to +1.2 pp | 0.1078 |

## Episode sensitivity

- `pre_interruption_r1_37`: Standard RLM 24/37, BM25 + same model 21/37, Text decomposition + same model 22/37.
- `resumed_r38_80`: Standard RLM 30/43, BM25 + same model 18/43, Text decomposition + same model 26/43.

## Cost and interpretation

Conservative listed-rate generation cost across both execution episodes is $29.378; the N=80 semantic judge adds $0.416, for $29.794. Route-attributed active-runtime costs exclude startup/idle and judging.

The semantic judge differs from normalized containment on 25 cells. Three judge responses violated the required prefix but began with an unambiguous `no`; they are conservatively scored incorrect without a rerun. A hash-linked project-side audit agrees on 24/25 disagreements; it was not method-blinded or independent human validation. Replacing those disagreement labels by the audit labels changes only text decomposition from 48/80 to 47/80 and does not change the ranking.
