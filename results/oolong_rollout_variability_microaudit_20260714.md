# Oolong Rollout-Variability Micro-Audit (2026-07-14)

Scope: three 8k standard-input Oolong examples, one each for counting, timeline, and user filtering. SLM+typed and direct Gemini have the original N45 run plus two trace-replay repeats; standard RLM has the original N45 run plus one trace-replay repeat.

This is not a benchmark-scale variance estimate. It is a low-cost rejection-risk probe for whether the central method ordering instantly collapses under repeated calls on matched prompts.

## Overall

| Rollout | Method | N | Exact | Mean score | Cost | Errors | Latency s |
|---|---|---:|---:|---:|---:|---:|---:|
| base_n45 | direct_controller | 3 | 1/3 | 0.393 | $0.005376 | 0 | 4.3 |
| base_n45 | rlm | 3 | 3/3 | 1.000 | $0.153225 | 0 | 0.0 |
| base_n45 | slm_labeler_typed | 3 | 3/3 | 1.000 | $0.002086 | 0 | 0.0 |
| replay_rollout1 | direct_controller | 3 | 1/3 | 0.393 | $0.005376 | 0 | 4.3 |
| replay_rollout1 | rlm | 3 | 0/3 | 0.188 | $0.057816 | 0 | 128.8 |
| replay_rollout1 | slm_labeler_typed | 3 | 3/3 | 1.000 | $0.002086 | 0 | 83.7 |
| replay_rollout2 | direct_controller | 3 | 1/3 | 0.393 | $0.005376 | 0 | 2.1 |
| replay_rollout2 | slm_labeler_typed | 3 | 3/3 | 1.000 | $0.002086 | 0 | 76.1 |

## Stability

| Method | Examples | Prediction-stable | Correctness-stable | Notes |
|---|---:|---:|---:|---|
| slm_labeler_typed | 3 | 3 | 3 | no flips |
| direct_controller | 3 | 3 | 3 | no flips |
| rlm | 3 | 0 | 0 | [{"example_id": "213020016", "task_group": "user", "predictions": ["positive", "Error: Unable to parse the original context string due to persistent environment state issues (the 'context' variable was overwritten and could not be restored to its original string content). Therefore, cannot accurately determine the least common label."], "scores": [1.0, 0.0], "rollouts": ["base_n45", "replay_rollout1"]}, {"example_id": "513050058", "task_group": "counting", "predictions": ["less common than", "I am unable to determine the frequencies of 'Health' and 'Family & Relationships' labels because the `llm_query` and `llm_query_batched` functions are not callable, returning a `TypeError: 'NoneType' object is not callable`. These functions are essential for classifying the questions and extracting the labels needed to answer the query."], "scores": [1.0, 0.0], "rollouts": ["base_n45", "replay_rollout1"]}, {"example_id": "613060055", "task_group": "timeline", "predictions": ["4", "6"], "scores": [1.0, 0.5625], "rollouts": ["base_n45", "replay_rollout1"]}] |

## Interpretation

- SLM+typed is stable and exact on all three 8k examples across the original run and two repeats.
- Direct Gemini is stable on these prompts but weaker: it repeats the same counting error, the same timeline numeric near miss, and the same user success.
- Standard RLM is less stable/useful on this tiny repeat: the original N45 run solved all three selected examples, while the repeat solves none and emits scaffold/environment-style failure messages on counting and user rows. Because N=3, this should stay in supporting reliability evidence, not a headline benchmark result.
- A partial 16k replay also completed one counting row for SLM+typed/direct before the next long SLM call was manually interrupted; it is retained in the raw rollout1 CSV/trace as latency evidence but excluded from this clean N=3 micro-audit summary.
