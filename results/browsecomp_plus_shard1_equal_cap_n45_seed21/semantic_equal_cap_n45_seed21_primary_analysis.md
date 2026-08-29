# BrowseComp-Plus Equal-Cap N45 Seed-21 Rollout Repeat

This is a post-hoc same-row rollout-variance sensitivity. It is not an independent endpoint and is not pooled with the prospective seed-20 result.

| Route | Cap-valid complete | Correct / 45 | Active-runtime cost | Median / p95 wall time |
|---|---:|---:|---:|---:|
| Standard RLM | 36/45 | 30/45 (66.7%) | $18.170 | 64.2s / 1219.4s |
| Iterative search | 45/45 | 31/45 (68.9%) | $1.145 | 7.9s / 68.3s |
| Text decomposition | 45/45 | 29/45 (64.4%) | $1.498 | 26.0s / 44.8s |
| BM25 + same model | 42/45 | 22/45 (48.9%) | $0.356 | 3.2s / 21.0s |

## Declared RLM contrasts

| Contrast | RLM only / other only | Difference | Paired 95% interval | Raw p | Holm p |
|---|---:|---:|---:|---:|---:|
| rlm_vs_iterative | 8 / 9 | -2.2 points | [-20.0, 15.6] | 1.000000 | 1.000000 |
| rlm_vs_text | 10 / 9 | 2.2 points | [-15.6, 20.0] | 1.000000 | 1.000000 |
| rlm_vs_bm25 | 14 / 6 | 17.8 points | [-2.2, 35.6] | 0.115318 | 0.345955 |

## Interpretation

The non-significant RLM contrast set repeats: the minimum Holm-adjusted p-value is 0.345955. The route ordering changes across the two rollouts, driven chiefly by textual decomposition changing from 37/45 to 29/45. This establishes seed sensitivity for this same-row endpoint, not equivalence and not independent replication.

RLM active-runtime cost is 12.1x textual decomposition and 15.9x iterative search. Seven RLM rows exceed the nominal 1,200-second wrapper wall time; six are failures and the sole late nonempty output is judged incorrect, so strict fail-closed scoring leaves the 30/45 result unchanged.

Common cap-valid completion is a post-treatment sensitivity over N=34; the fixed 45-row denominator remains primary.
