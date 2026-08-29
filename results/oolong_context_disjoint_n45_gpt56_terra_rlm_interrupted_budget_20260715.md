# GPT-5.6 Terra CD-45 Restart Attempt After Credit Replenishment

Status: interrupted by budget-safety stop, not a benchmark result.

- Date: 2026-07-15.
- Model/backend: `openai/gpt-5.6-terra` via OpenRouter.
- Manifest: `results/oolong_context_disjoint_n45_manifest_20260715.json`.
- Run ID: `oolong_context_disjoint_n45_gpt56_terra_rlm_complete_20260715`.
- Output CSV: `results/oolong_context_disjoint_n45_gpt56_terra_rlm_complete_20260715.csv`.
- Runner log: `results/oolong_context_disjoint_n45_gpt56_terra_rlm_complete_20260715_run.log`.
- Stop rule: 240 seconds per row; standard `rlms` scaffold budget left unchanged.

## Credit Context

Before the restart, OpenRouter reported:

```json
{"data":{"total_credits":240,"total_usage":220.120380919}}
```

During the run, after row 13 and while row 14 was beginning, OpenRouter reported:

```json
{"data":{"total_credits":240,"total_usage":231.068384169}}
```

This means the restart consumed about `$10.95` of actual provider credit before reaching the timeline/user groups. Because failed `rlms` subprocess attempts often do not return a normal usage summary, the CSV's captured successful-row cost undercounts the provider-side spend.

## Recorded Prefix

Recorded rows: 13/45.

- Exact: 7/13.
- Score sum: 7.2373.
- Captured successful-row cost in CSV: `$0.580884`.
- Strict timeout/error rows: 4/13.
- Actual OpenRouter usage increase during the attempted run: about `$10.95`.

Rows 11--13 repeatedly hit `BudgetExceededError` inside the standard `rlms` scaffold before the outer 240-second row timeout. The run was stopped manually to avoid burning the remaining account balance on repeated failed scaffold attempts.

## Interpretation

This is now a real current-controller scaffold-instability artifact, not the earlier provider-credit-exhaustion artifact. It shows that GPT-5.6 Terra is reachable and can solve several short CD-45 rows, but under the unchanged standard `rlms` protocol it can also trigger expensive internal budget failures and strict timeouts. It should not be reported as a complete accuracy benchmark.

For the paper, the cleaner reviewer-facing hierarchy is:

1. A completed same-manifest GPT-5.6 Sol run would be the strongest frontier-controller sensitivity if sufficient budget is available.
2. A completed GPT-5.6 Terra run would be an acceptable balanced-tier sensitivity if it can complete under the same strict stop rule.
3. Luna/Luna Pro are useful cheaper current-model probes but do not answer the strongest-controller objection as well as Sol.

Given the observed Terra burn rate and remaining credit after this attempt, the next paid run should not be a blind full CD-45 Sol/Terra run unless more budget is added or the protocol is deliberately narrowed to the frozen CD-15 repeatability subset.
