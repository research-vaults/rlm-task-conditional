# CD-15 Retrospective Positive-Side Rollout Diagnostic

The subset was frozen for repeatability after the parent CD-45 outcomes were known. The positive-side interpretation was formulated only after the RLM repeats. This is therefore a retrospective descriptive diagnostic, not a prospectively selected positive regime.

## Overall

| Method | N | Exact | Mean score | Cost | Errors |
|---|---:|---:|---:|---:|---:|
| slm_typed_stored_cd15 | 15 | 15/15 (100.0%) | 100.0% | $0.107011 | 0 |
| direct_gemini_original_cd15 | 15 | 9/15 (60.0%) | 65.0% | $0.335770 | 0 |
| standard_rlm_original_cd15 | 15 | 10/15 (66.7%) | 70.4% | $0.308485 | 0 |
| direct_gemini_replay_cd15 | 15 | 8/15 (53.3%) | 53.3% | $0.340761 | 0 |
| standard_rlm_three_repeats_aggregate | 45 | 30/45 (66.7%) | 71.2% | $1.252444 | 0 |

## Item-Clustered Descriptive Summary

- Mean observed RLM-repeat accuracy minus the one observed direct replay: 13.3 percentage points.
- Item-cluster bootstrap (15 unique items; conditional on three observed RLM rollouts and one observed direct rollout): -13.3 to 40.0 points.
- No aggregate McNemar test is reported: the 45 RLM repeat rows are nested within 15 items and the direct comparator was observed once, so duplicating it would create pseudoreplication.
- Interpretation: the observed average is RLM-favorable relative to this direct replay, but uncertainty is wide and SLM+typed remains 15/15 exact and cheaper.

## Per Repeat

| Repeat | RLM exact | Direct exact | RLM-only | Direct-only | p |
|---|---:|---:|---:|---:|---:|
| standard_rlm_repeat1 | 13/15 | 8/15 | 6 | 1 | 0.125 |
| standard_rlm_repeat2 | 11/15 | 8/15 | 5 | 2 | 0.453125 |
| standard_rlm_repeat3 | 6/15 | 8/15 | 2 | 4 | 0.6875 |

## Evidence Tier

- Positive-side RLM evidence: retrospective and descriptive only; not a powered RLM-over-direct result.
- Default-route evidence: no, because SLM+typed remains stronger and cheaper.
- Stronger-family evidence: no, because this is standard `rlms` with Gemini 2.5 Flash.

New OpenRouter spend for this pass: `$0.340761`.
A three-run direct cost of `$1.022283` would be a counterfactual linear projection, not observed spend.
