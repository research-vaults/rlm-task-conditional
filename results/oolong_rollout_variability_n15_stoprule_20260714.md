# Oolong N=15 Rollout Repeat Stop-Rule Artifact (2026-07-14)

Scope: bounded repeatability/stop-rule artifact over the frozen 15-row validation manifest. This is not a benchmark-scale variance estimate.

## Overall

| Source | N | Exact | Mean score | Cost | Errors | Latency s |
|---|---:|---:|---:|---:|---:|---:|
| base_slm | 15 | 12/15 | 0.866 | $0.082004 | 0 | 0.0 |
| base_direct | 15 | 5/15 | 0.429 | $0.191340 | 0 | 26.6 |
| base_rlm | 15 | 6/15 | 0.578 | $0.934455 | 0 | 0.0 |
| direct_repeat_full_n15 | 15 | 5/15 | 0.429 | $0.191340 | 0 | 34.1 |
| rlm_repeat_stoprule_n3 | 3 | 0/3 | 0.000 | $0.000880 | 2 | 4.8 |

## Stability Checks

- Direct Gemini base vs full N=15 replay: 15/15 predictions stable and 15/15 correctness labels stable.
- Standard RLM base vs stop-rule N=3 replay: 0/3 predictions stable and 0/3 correctness labels stable.

## RLM Stop-Rule Rows

| Example | Group | Length | Base correct | Repeat prediction | Gold | Repeat correct | Repeat error |
|---|---|---:|---:|---|---|---:|---|
| 513050058 | counting | 8192 | 1.000 | same frequency as | less common than | 0.000 |  |
| 613060055 | timeline | 8192 | 1.000 | (none) | 4 | 0.000 | TimeoutError: rlm timed out after 360s on example 613060055 |
| 213020016 | user | 8192 | 1.000 | (none) | positive | 0.000 | TimeoutError: rlm timed out after 360s on example 213020016 |

## Interpretation

- The full direct-controller N=15 replay exactly reproduces the original direct-controller correctness pattern: 5/15 exact, mean score 0.429, no errors.
- The standard-RLM repeat was intentionally stopped after the first three 8k rows: the original N45 run solved all three, but the repeat produced one wrong fast answer and two 360-second timeouts.
- This is stronger repeatability evidence than the original N=3 micro-audit because it also shows the full N=15 direct baseline is stable while the attempted RLM extension fails the stop rule immediately.
- The right paper-facing use is conservative: do not claim an RLM-family benchmark-scale variance estimate; use it to justify not spending on a larger standard-rlms repeat before submission without a more stable harness.
