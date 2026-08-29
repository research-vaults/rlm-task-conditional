# CD-45 Standard-RLM Program Trace Subset

This is a small qualitative mechanism artifact. It reruns selected CD-45 rows with the standard `rlms` scaffold and trajectory logger so generated code blocks are inspectable. It is not a new aggregate benchmark row.

## Summary

- Run ID: `oolong_context_disjoint_cd45_rlm_program_trace_subset_20260716`
- Model: `google/gemini-2.5-flash`
- Rows: 3
- Exact: 2/3
- Total cost: `$0.015245`
- Rows with trajectories: 3/3
- Code blocks captured: 14

## Rows

| example | group | len | gold | pred | score | iterations | code blocks | cost | error |
|---|---|---:|---|---|---:|---:|---:|---:|---|
| 710070026 | counting | 1024 | neutral | neutral | 1.000 | 6 | 6 | $0.006186 |  |
| 912090010 | counting | 4096 | less common than | more common than | 0.000 | 5 | 5 | $0.006600 |  |
| 312030020 | user | 4096 | 16226 | 16226 | 1.000 | 3 | 3 | $0.002459 |  |

## First Generated Code Block Per Completed Row

### 710070026

```python
print(context[:500])
```

### 912090010

```python
print(context[:1000])
```

### 312030020

```python
print(context[:1000])
```

