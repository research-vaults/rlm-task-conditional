# Cost Sensitivity Audit

This deterministic audit reads stored result files only. It reconciles the Oolong N=30 Gemma repricing and marks T-STRUCT cost as a deployed-configuration ratio, not a matched-model scaffold-overhead estimate.

| Family | Scenario | Baseline | Comparator | Ratio | Interpretation |
|---|---|---:|---:|---:|---|
| T-STRUCT | reported deployed configuration | standard_rlm $0.019826 | Gemma extraction + fixed aggregation $0.000200 | 99.13x | This is the paper-facing deployed-configuration ratio, not a matched-model scaffold-overhead estimate. |
| T-STRUCT | Gemma alternative cost x10 | standard_rlm $0.019826 | Gemma extraction + fixed aggregation $0.002000 | 9.91x | Even if the Gemma extraction path were ten times more expensive than logged, it remains cheaper on the stored run. |
| T-STRUCT | RLM cost /2 and Gemma alternative cost x2 | standard_rlm $0.009913 | Gemma extraction + fixed aggregation $0.000400 | 24.78x | A conservative two-sided price perturbation still leaves a large cost gap; it should still be described as deployed-configuration cost. |
| Oolong N=30 standard-unlabeled | corrected token-trace price | standard_rlm $0.255676 | SLM-labeler + typed $0.007257 | 35.23x | Paper-facing corrected price after adding the exact Gemma 4 26B-A4B OpenRouter entry. |
| Oolong N=30 standard-unlabeled | old raw pre-patch SLM estimate | standard_rlm $0.255676 | SLM-labeler + typed $0.103732 | 2.46x | The old raw SLM estimate is retained for audit; even under it, the SLM route is cheaper than standard RLM on this pilot. |
| Oolong N=120 standard-unlabeled | reported logged price | standard_rlm $2.688340 | SLM-labeler + typed $0.658995 | 4.08x | Main public-contract cost ratio from fully traced stored outputs. |
| Oolong N=120 standard-unlabeled | SLM route x2 | standard_rlm $2.688340 | SLM-labeler + typed $1.317990 | 2.04x | A doubled SLM price still leaves the SLM route cheaper than standard RLM. |
| Oolong N=120 standard-unlabeled | direct Gemini comparator | standard_rlm $2.688340 | direct Gemini $1.546563 | 1.74x | Direct Gemini ties standard RLM on accuracy and is cheaper; this is a matched-controller scaffold diagnostic. |
| Oolong N=45 method-locked checkpoint | reported logged price | standard_rlm $1.799692 | SLM-labeler + typed $0.248136 | 7.25x | Method-locked checkpoint cost ratio under the same standard-input contract; example IDs are prior-excluded but context-window overlap is disclosed separately. |
| Oolong N=45 method-locked checkpoint | Gemini 3.5 direct vs SLM | Gemini 3.5 direct $2.942868 | SLM-labeler + typed $0.248136 | 11.86x | Current-model direct controller remains substantially more expensive than the SLM route on the method-locked checkpoint slice. |

Conclusion: the exact ratios move under price perturbations, but the main cost claims do not depend on hiding the Oolong N=30 pre-patch estimate. The strongest caveat is interpretive: T-STRUCT's ratio is a deployed-configuration comparison and should not be described as a pure matched-model scaffold overhead.
