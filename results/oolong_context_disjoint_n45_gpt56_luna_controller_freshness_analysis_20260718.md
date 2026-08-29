# Oolong CD-45 GPT-5.6 Luna Controller-Freshness Analysis

This is a complete strict-stop standard-`rlms` run on the frozen context-window-disjoint Oolong CD-45 manifest. It uses `openai/gpt-5.6-luna` through OpenRouter with the same standard/unlabeled input contract and 360-second row cap used for the central controller-freshness family. It is not an official SRLM/lambda-RLM/RAH reproduction.

## Overall

| Method | Exact | Mean score | Cost | Errors | Cost/exact |
|---|---:|---:|---:|---:|---:|
| SLM+typed | 36/45 (80.0%) | 83.7% | $0.416415 | 0 | $0.011567 |
| Direct Gemini 2.5 Flash | 21/45 (46.7%) | 54.9% | $1.024590 | 0 | $0.048790 |
| Standard RLM / Gemini 2.5 Flash | 27/45 (60.0%) | 62.3% | $1.001014 | 0 | $0.037075 |
| Standard RLM / GPT-5 | 23/45 (51.1%) | 58.1% | $2.442035 | 15 | $0.106175 |
| Standard RLM / GPT-5.6 Luna | 26/45 (57.8%) | 62.9% | $3.965806 | 2 | $0.152531 |

## Paired Exact Comparisons

| Comparison | Exact diff | b | c | two-sided p | Cluster CI |
|---|---:|---:|---:|---:|---|
| `slm_qparsed_typed_vs_standard_rlm_gpt56_luna` | 22.2 pp | 15 | 5 | 0.0413895 | [2.3, 40.9] pp |
| `standard_rlm_gpt56_luna_vs_standard_rlm_gemini25` | -2.2 pp | 10 | 11 | 1 | [-22.2, 18.2] pp |
| `standard_rlm_gpt56_luna_vs_standard_rlm_gpt5` | 6.7 pp | 12 | 9 | 0.663624 | [-13.6, 26.2] pp |
| `standard_rlm_gpt56_luna_vs_direct_gemini25` | 11.1 pp | 12 | 7 | 0.359283 | [-8.7, 31.1] pp |

## Interpretation

- GPT-5.6 Luna standard RLM is complete on CD-45: 26/45 exact, mean score 62.9%, 2 timeout/error rows, and $3.965806 captured cost.
- It does not overturn the central SLM+typed result: SLM+typed remains 36/45 exact at $0.416415.
- It is essentially tied with the older Gemini 2.5 Flash standard-RLM row on exact count (26 vs 27) and slightly above GPT-5 strict-stop exact count (26 vs 23).
- The paper-facing value is model-freshness/fairness: a complete current GPT-5.6 controller run no longer leaves the result dependent on stale partial GPT-5.6 credit-aborted prefixes.
- This is still standard `rlms`, not stronger-family SRLM/lambda-RLM/RAH parity; keep the official-family non-claim.
