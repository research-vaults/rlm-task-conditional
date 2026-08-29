# Typed-Route Released Implementation-Surface Audit

Generated: `2026-07-19T17:37:34.200927+00:00`

| Role | Released file | Physical lines | Nonblank lines | Top-level functions | SHA-256 prefix |
|---|---|---:|---:|---:|---|
| `typed_aggregation_kernel_and_audit` | `scripts/probe_typed_oolong_proxy.py` | 592 | 507 | 16 | `59f104753308` |
| `question_schema_parser_and_audit` | `scripts/analyze_oolong_question_parsed_typed.py` | 294 | 264 | 6 | `7d727d278d2d` |
| `slm_labeling_execution_and_audit` | `scripts/eval_oolong_standard_slm_labeler_typed.py` | 835 | 754 | 19 | `bbdb4d8f5454` |
| `standard_rlm_tool_wrappers` | `scripts/oolong_operator_library.py` | 296 | 268 | 5 | `314f900d221e` |
| **Total** | **4 files** | **2017** | **1793** | **46** | -- |

## Declared Typed Surface

- Task families: **6**.
- Answer types: **5**.
- Standard-RLM custom-tool exposure: **5 atomic/schema tools** plus **1 optional convenience solver**.

## Interpretation Boundary

Counts cover the complete released source files used by the typed route, including CLI, tracing, caching, analysis, and reporting support. They are not minimal runtime LOC.

**Non-claim:** Source size does not measure human engineering hours, maintenance burden, or total cost of ownership; no such quantities were logged prospectively.
