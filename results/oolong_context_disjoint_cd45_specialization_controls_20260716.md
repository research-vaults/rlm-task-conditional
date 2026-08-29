# Oolong CD-45 Specialization Controls

Run id: `oolong_context_disjoint_cd45_specialization_controls_20260716`

No new model/API calls. Reuses stored Gemma SLM row-label predictions from CD-45 and changes only the typed operation family before scoring against the original Oolong gold answer.

wrong_family_rotated and generic_label_route are stress tests, not fair baselines. They show whether the SLM+typed result depends on correct operation-family specialization.

| Route | Exact | Exact rate | Mean score | Errors | Interpretation |
|---|---:|---:|---:|---:|---|
| `metadata_oracle` | 36/45 | 80.0% | 83.7% | 0 | Uses benchmark task/answer_type metadata. |
| `question_parsed` | 36/45 | 80.0% | 83.7% | 0 | Infers task/answer_type from the question; main CD-45 typed route. |
| `wrong_family_rotated` | 2/45 | 4.4% | 5.9% | 0 | Intentionally rotates to a wrong task family; stress test only. |
| `generic_label_route` | 3/45 | 6.7% | 6.7% | 0 | Naive fixed most-frequent-label route; stress test only. |

Exact-rate drop from question-parsed to wrong-family route: 75.6 points.
Exact-rate drop from question-parsed to generic-label route: 73.3 points.

Paper use: this artifact should be cited as a specialization stress test, not as a competing method. It supports the claim that SLM+typed success depends on correct deployment prior knowledge about the operation family.
