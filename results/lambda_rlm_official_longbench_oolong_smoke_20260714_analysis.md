# lambda-RLM Official LongBench-v2 Oolong Smoke

This is a protocol-diligence artifact, not a headline same-contract benchmark row.

- Model: `google/gemini-2.5-flash`
- Implementation: public `external_repos/lambda-RLM` using `benchmarks/benchmark.py`'s `load_oolong` and `rlm.LambdaRLM`.
- Dataset/loader: `THUDM/LongBench-v2`, domain filter `Single-Document QA`.
- Contract warning: this is not the main paper's Oolong-synth aggregation contract.
- Rows: 1 loaded, 0 completed, 1 errors.
- Exact: 0/1; mean F1: 0.000; contains: 0/1.
- Captured cost: not returned

| Row | Bin | LB2 idx | Context chars | F1 | Exact | Error |
|---:|---|---:|---:|---:|---:|---|
| 1 | 8k | 1 | 163347 | 0.000 | 0 | ProcessTimeout: row exceeded 180s |

Interpretation: if this smoke is useful, it supports only the claim that the released lambda-RLM code path was inspected and exercised on its own official-style LongBench-v2 task. It cannot establish that lambda-RLM fails or wins on the paper's standard-unlabeled Oolong-synth aggregation benchmark.
