# Oolong CD-45 Standard-RLM Full Repeatability Diagnostic

This artifact compares the original CD-45 standard-RLM/Gemini rollout with a full independent repeat on the same frozen context-window-ID-disjoint Oolong manifest. Both runs use `context_window_text`, Gemini 2.5 Flash through OpenRouter, and a 360-second row cap. The diagnostic targets execution variability, not source-document independence.

## Headline

- Original standard RLM: 27/45 exact (60.0%), mean score 62.3%, cost $1.001, errors 0.
- Repeat standard RLM: 21/45 exact (46.7%), mean score 55.8%, cost $0.970, errors 2.
- SLM+typed reference row: 36/45 exact (80.0%).
- Original-vs-repeat exact stability: {'00': 12, '01': 6, '10': 12, '11': 15}. Discordance original-only/repeat-only = 12/6 (13.3 points original minus repeat).
- SLM+typed versus repeat RLM discordance: 17/2 (33.3 points SLM minus repeat).

## Per-Group RLM Summary

| Group | Original exact | Repeat exact | Original mean | Repeat mean |
|---|---:|---:|---:|---:|
| counting | 6/15 | 5/15 | 40.3% | 47.1% |
| timeline | 8/15 | 6/15 | 59.2% | 48.8% |
| user | 13/15 | 10/15 | 87.6% | 71.7% |

## Interpretation

The result should be used as rollout-aware uncertainty evidence for the central CD-45 row. If the repeat stays near the original aggregate, it strengthens the finding that the SLM+typed advantage is not a one-run artifact; if it swings substantially, it supports the manuscript's narrower claim that standard RLM is stochastic enough that small frozen slices need explicit execution-variance disclosure. In either case, the paper should describe CD-45 bootstrap intervals as conditional on the observed RLM executions rather than as total uncertainty over both examples and scaffold rollouts.
