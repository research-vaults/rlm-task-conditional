# Oolong CD-15 Standard-RLM Repeatability Stop-Rule

Three independent standard-RLM repeats were run on the frozen context-disjoint CD-15 manifest with the same standard/unlabeled context and 360-second row cap. This is a bounded variance check, not a replacement for the main CD-45 or SU-150 estimates.

## Headline

- Across 45 repeat rows, exact accuracy was 30/45 (66.7%), score-sum was 32.0625/45, and total OpenRouter cost was $1.252.
- Per-repeat exact counts were: repeat1 13/15 (86.7%), repeat2 11/15 (73.3%), repeat3 6/15 (40.0%).
- Stability over the 15 frozen examples: 3 correct in all three repeats, 10 correct in two repeats, 1 correct in one repeat, and 1 correct in none.
- Harness-level error rows: 0; internal error-string predictions: 1; free-form non-answer failures: 2.

## Per-Repeat Summary

| Repeat | Exact | Score sum | Cost | Counting exact | Timeline exact | User exact |
|---|---:|---:|---:|---:|---:|---:|
| repeat1 | 13/15 | 13/15 | $0.513 | 4/5 | 5/5 | 4/5 |
| repeat2 | 11/15 | 11.75/15 | $0.324 | 2/5 | 4/5 | 5/5 |
| repeat3 | 6/15 | 7.312/15 | $0.415 | 1/5 | 3/5 | 2/5 |

## Unstable Examples

| Example | Group | Length | Task | Exact pattern | Gold | Predictions |
|---|---|---:|---|---|---|---|
| 210020009 | counting | 1024 | TASK_TYPE.NUMERIC_ONE_CLASS | 110 | 1 | 1 / 1 / 0 |
| 210020033 | counting | 1024 | TASK_TYPE.NUMERIC_ONE_CLASS | 100 | 0 | 0 / 1 / 2 |
| 412040009 | counting | 4096 | TASK_TYPE.LEAST_FREQ | 110 | True | True / True / False |
| 512050034 | counting | 4096 | TASK_TYPE.RELATIVE_FREQ | 000 | more common than | same frequency as / same frequency as / same frequency as |
| 218020026 | counting | 262144 | TASK_TYPE.RELATIVE_FREQ | 101 | more common than | more common than / same frequency as / more common than |
| 210020029 | timeline | 1024 | TASK_TYPE.MOST_FREQ | 101 | 2025-03-03 00:00:00 | 03/03/2025 / 09/30/2024 / 03/03/2025 |
| 212020028 | timeline | 4096 | TASK_TYPE.NUMERIC_ONE_CLASS | 110 | 2 | 2 / 2 / Here's an analysis of the provided data based on the given date range and sentiment: |
| 218020038 | timeline | 262144 | TASK_TYPE.MOST_FREQ | 110 | 2024-12-06 00:00:00 | 12/06/2024 / 12/06/2024 / No dates found in the context. |
| 310030013 | user | 1024 | TASK_TYPE.LEAST_FREQ | 011 | Business | Error: llm() call failed - Connection error. / Business / Business |
| 312030051 | user | 4096 | TASK_TYPE.RELATIVE_FREQ | 110 | 22165 | 22165 / 22165 / Both users have an equal number of Sports instances. |
| 218020061 | user | 262144 | TASK_TYPE.MOST_FREQ | 110 | 39309 | 39309 / 39309 / 23861 |
| 318030064 | user | 262144 | TASK_TYPE.RELATIVE_FREQ | 110 | more common than | more common than / more common than / same frequency as |

## Interpretation

The stop-rule supports the manuscript's claim that standard RLM is not simply a deterministic preprocessing scaffold in this setting. On a fixed, balanced, context-disjoint subset, the same controller/protocol ranges from 13/15 to 6/15 exact. The instability is concentrated in relative-frequency, extraction-format, and user/timeline rows where the generated operator plan or final answer normalization can drift into wrong labels, prose non-answers, or internally surfaced connection-error strings. This strengthens the case for reporting task-conditional regimes and for treating RLM as a fallback when task type is unknown, not as a uniformly dominant default.
