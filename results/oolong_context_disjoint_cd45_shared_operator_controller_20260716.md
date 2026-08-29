# Oolong CD-45 Shared-Operator Controller Diagnostic

Run id: `oolong_context_disjoint_cd45_shared_operator_controller_20260716`
Model: `google/gemini-2.5-flash`

LLM controller selects task/answer_type from question only; existing typed Oolong operator library executes over stored CD-45 Gemma row-label predictions. This is a shared-operator controller diagnostic, not standard rlms or official SRLM/lambda-RLM.

## Headline

- Exact: 36/45 (80.0%).
- Mean score: 83.7%.
- Controller API cost: `$0.008861`.
- Task matches metadata: 45/45.
- Answer-type matches metadata: 45/45.
- Parse errors: 0; execution errors: 0.

## By Group

| Group | Exact | Mean score | Cost | Parse err. | Exec. err. |
|---|---:|---:|---:|---:|---:|
| counting | 12/15 | 81.7% | $0.002912 | 0 | 0 |
| timeline | 11/15 | 77.8% | $0.003026 | 0 | 0 |
| user | 13/15 | 91.7% | $0.002923 | 0 | 0 |

## Paper Use

Use this as a fairness/control diagnostic only. It shows what happens when a large controller receives the same typed operator menu as the SLM+typed route and chooses the route from the natural-language question. It does not reproduce standard `rlms`, does not provide generated Python traces, and does not close the official SRLM/lambda-RLM comparator gap.
