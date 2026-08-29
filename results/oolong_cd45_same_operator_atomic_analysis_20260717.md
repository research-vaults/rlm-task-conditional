# Oolong CD-45 Same-Operator Atomic Analysis

No model calls were made by this analysis script. It summarizes completed CD-45 rows.

## Overall

| Method | Exact | Mean score |
|---|---:|---:|
| `slm_qparsed_typed` | 36/45 (80.0%) | 83.7% |
| `standard_rlm` | 27/45 (60.0%) | 62.3% |
| `direct_gemini25` | 21/45 (46.7%) | 54.9% |
| `gpt5_standard_rlm` | 23/45 (51.1%) | 58.1% |
| `same_ops_convenience` | 31/45 (68.9%) | 69.3% |
| `same_ops_atomic` | 29/45 (64.4%) | 69.3% |
| `shared_operator_controller` | 36/45 (80.0%) | 83.7% |

## Atomic Same-Operator Cost and Failure Profile

- Exact: 29/45 (64.4%).
- Mean score: 69.3%.
- Cost: $0.958685 total ($0.548691 controller, $0.409998 tools).
- Errors/timeouts: 4.
- Tool calls: 155 ({'parse_oolong_rows': 79, 'label_oolong_rows_with_slm': 72, 'solve_labeled_oolong': 4}).

## Paired Exact Counts

| Pair | Both | First only | Atomic only | Neither |
|---|---:|---:|---:|---:|
| `slm_qparsed_typed_vs_same_ops_atomic` | 27 | 9 | 2 | 7 |
| `same_ops_convenience_vs_same_ops_atomic` | 23 | 8 | 6 | 8 |
| `standard_rlm_vs_same_ops_atomic` | 23 | 4 | 6 | 12 |
| `direct_gemini25_vs_same_ops_atomic` | 20 | 1 | 9 | 15 |
| `gpt5_standard_rlm_vs_same_ops_atomic` | 19 | 4 | 10 | 12 |
| `shared_operator_controller_vs_same_ops_atomic` | 27 | 9 | 2 | 7 |

## Interpretation

- Atomic-only standard rlms reaches 29/45, below SLM+typed and shared-operator controller at 36/45.
- Withholding the convenience solver lowers the same-operator diagnostic from 31/45 to 29/45 and reduces total cost from $1.31445 to $0.958685.
- The atomic row is still above the original standard-RLM row and direct Gemini on exact count, so access to typed tools helps, but free-form orchestration remains less reliable than the specialized route.
- The result is a bounded diagnostic, not an official SRLM/lambda-RLM result and not a replacement benchmark row.
