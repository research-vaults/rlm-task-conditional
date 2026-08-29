# Standard `rlms` + Same Typed Operator Library Diagnostic

This is the same-operator-library diagnostic for standard `rlms`. It preserves free-form RLM program generation while injecting the typed Oolong operator library through `custom_tools`.

## Summary

- Run ID: `oolong_cd45_rlm_same_ops_20260716`
- Rows: 31/45 exact
- Mean score: 0.6928
- Controller cost: `$0.494506`
- Tool cost: `$0.819945`
- Total cost: `$1.314450`
- Errors: 2
- Tool calls: 173
- Generated code blocks: 348

## Contract

Standard rlms v0.1.3 with custom_tools exposing the same typed Oolong operator library. Input is standard context_window_text only; root prompt is the natural-language question. The generated program must choose task/answer_type itself. This is not shared-operator routing and not official SRLM/lambda-RLM.

## Rows

| example | group | len | gold | pred | score | cost | tools | std RLM | SLM+typed | direct | shared-op | error |
|---|---|---:|---|---|---:|---:|---|---|---|---|---|---|
| 210020009 | counting | 1024 | 1 | 1 | 1.000 | $0.008646 | label_oolong_rows_with_slm;solve_labeled_oolong;solve_oolong_with_tools;parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm;solve_labeled_oolong;solve_oolong_with_tools |  |  |  | 1 |  |
| 710070026 | counting | 1024 | neutral | contradiction | 0.000 | $0.006279 | parse_oolong_rows;label_oolong_rows_with_slm;solve_labeled_oolong;solve_oolong_with_tools |  |  |  | contradiction |  |
| 710070007 | counting | 1024 | 2 | 2 | 1.000 | $0.003695 | label_oolong_rows_with_slm |  |  |  | 2 |  |
| 210020033 | counting | 1024 | 0 | 0 | 1.000 | $0.018753 | label_oolong_rows_with_slm;solve_labeled_oolong;solve_oolong_with_tools;parse_oolong_rows;label_oolong_rows_with_slm;solve_labeled_oolong;solve_oolong_with_tools;label_oolong_rows_with_slm;solve_labeled_oolong;solve_oolong_with_tools;label_oolong_rows_with_slm |  |  |  | 0 |  |
| 410040003 | counting | 1024 | 11 | 11 | 1.000 | $0.008002 | label_oolong_rows_with_slm;label_oolong_rows_with_slm |  |  |  | 11 |  |
| 412040009 | counting | 4096 | True | true | 1.000 | $0.008089 | parse_oolong_rows;label_oolong_rows_with_slm;solve_labeled_oolong;solve_oolong_with_tools |  |  |  | true |  |
| 712070012 | counting | 4096 | less common than | contradiction is unknown neutral | 0.000 | $0.021815 | parse_oolong_rows;parse_oolong_rows;parse_oolong_rows;parse_oolong_rows;parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm;label_oolong_rows_with_slm;solve_labeled_oolong;solve_oolong_with_tools |  |  |  | less common than |  |
| 512050034 | counting | 4096 | more common than | more common than | 1.000 | $0.004257 | label_oolong_rows_with_slm |  |  |  | more common than |  |
| 912090010 | counting | 4096 | less common than | less common than | 1.000 | $0.016334 | label_oolong_rows_with_slm;solve_labeled_oolong;solve_oolong_with_tools;label_oolong_rows_with_slm;solve_labeled_oolong;solve_oolong_with_tools;label_oolong_rows_with_slm;solve_labeled_oolong;solve_oolong_with_tools;parse_oolong_rows;parse_oolong_rows |  |  |  | less common than |  |
| 612060011 | counting | 4096 | 46 | {informal_count}" | 0.000 | $0.015397 | label_oolong_rows_with_slm;solve_labeled_oolong;solve_oolong_with_tools;parse_oolong_rows;label_oolong_rows_with_slm;solve_labeled_oolong;solve_oolong_with_tools |  |  |  | 37 |  |
| 718070027 | counting | 262144 | more common than | more common than | 1.000 | $0.065303 | parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm |  |  |  | more common than |  |
| 618060051 | counting | 262144 | less common than | less common than | 1.000 | $0.175599 | label_oolong_rows_with_slm;solve_labeled_oolong;solve_oolong_with_tools;label_oolong_rows_with_slm;solve_labeled_oolong;solve_oolong_with_tools;parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm;solve_labeled_oolong;solve_oolong_with_tools;label_oolong_rows_with_slm |  |  |  | less common than |  |
| 718070049 | counting | 262144 | contradiction | contradiction | 1.000 | $0.035699 | parse_oolong_rows;label_oolong_rows_with_slm;solve_labeled_oolong;solve_oolong_with_tools |  |  |  | contradiction |  |
| 218020053 | counting | 262144 | 387 | 393 | 0.178 | $0.099922 | parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm;solve_labeled_oolong;solve_oolong_with_tools;label_oolong_rows_with_slm;label_oolong_rows_with_slm;label_oolong_rows_with_slm |  |  |  | 393 |  |
| 218020026 | counting | 262144 | more common than | more common than | 1.000 | $0.037068 | label_oolong_rows_with_slm;label_oolong_rows_with_slm |  |  |  | more common than |  |
| 410040043 | timeline | 1024 | False | False | 1.000 | $0.012275 | parse_oolong_rows;parse_oolong_rows;parse_oolong_rows |  |  |  | true |  |
| 310030048 | timeline | 1024 | more common | more common | 1.000 | $0.014742 | parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm;label_oolong_rows_with_slm |  |  |  | more common |  |
| 210020017 | timeline | 1024 | 2023-06-29 00:00:00 | Jun 29, 2023 | 1.000 | $0.000857 | parse_oolong_rows |  |  |  | Jun 29, 2023 |  |
| 210020029 | timeline | 1024 | 2025-03-03 00:00:00 | 03/03/2025 | 1.000 | $0.002063 | parse_oolong_rows |  |  |  | Mar 03, 2025 |  |
| 910090047 | timeline | 1024 | 1 |  | 0.000 | $0.013390 | parse_oolong_rows;label_oolong_rows_with_slm;solve_labeled_oolong;solve_oolong_with_tools |  |  |  | 1 |  |
| 912090031 | timeline | 4096 | 6 | {'answer': '', 'prediction': '', 'task': 'TASK_TYPE.NUMERIC_ONE_CLASS', 'answer_type': 'ANSWER_TYPE.NUMERIC', 'typed_ops': 'unsupported', 'typed_status': 'unsupported', 'row_count': 71, 'label_cost_usd': 0.00046452, 'label_input_tokens': 4222, 'label_output_tokens': 640, 'allowed_labels': 'positive', 'negative'} | 0.000 | $0.016694 | parse_oolong_rows;parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm;solve_labeled_oolong;solve_oolong_with_tools |  |  |  | 4 |  |
| 612060022 | timeline | 4096 | more common | more common | 1.000 | $0.012055 | parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm |  |  |  | more common |  |
| 612060046 | timeline | 4096 | less common | less common | 1.000 | $0.011927 | parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm |  |  |  | less common |  |
| 412040047 | timeline | 4096 | True | false | 0.000 | $0.011175 | parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm;solve_labeled_oolong;solve_oolong_with_tools |  |  |  | false |  |
| 212020028 | timeline | 4096 | 2 | 2 | 1.000 | $0.010080 | parse_oolong_rows |  |  |  | 2 |  |
| 918090044 | timeline | 262144 | 383 |  | 0.000 | $0.000000 | parse_oolong_rows |  |  |  | 375 | TimeoutError: RLM+ops run timed out after 360s |
| 218020038 | timeline | 262144 | 2024-12-06 00:00:00 | 12/06/2024 | 1.000 | $0.002629 | parse_oolong_rows |  |  |  | Dec 06, 2024 |  |
| 418040042 | timeline | 262144 | more common than |  | 0.000 | $0.055779 | parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm;label_oolong_rows_with_slm |  |  |  | more common than |  |
| 718070046 | timeline | 262144 | more common than |  | 0.000 | $0.145530 | parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm;label_oolong_rows_with_slm;label_oolong_rows_with_slm;label_oolong_rows_with_slm;label_oolong_rows_with_slm;label_oolong_rows_with_slm |  |  |  | more common than | TimeoutError: RLM+ops run timed out after 360s |
| 418040063 | timeline | 262144 | True | True | 1.000 | $0.152464 | parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm;label_oolong_rows_with_slm;label_oolong_rows_with_slm;parse_oolong_rows |  |  |  | true |  |
| 410040038 | user | 1024 | 91546 | Both users have the same number of False instances. | 0.000 | $0.010266 | parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm;label_oolong_rows_with_slm |  |  |  | 91546 |  |
| 310030013 | user | 1024 | Business | Business | 1.000 | $0.010092 | parse_oolong_rows |  |  |  | business |  |
| 610060037 | user | 1024 | 1 | 1 | 1.000 | $0.014041 | parse_oolong_rows |  |  |  | 1 |  |
| 710070033 | user | 1024 | 30364 | 30364 | 1.000 | $0.008009 | label_oolong_rows_with_slm;solve_labeled_oolong;solve_oolong_with_tools |  |  |  | 30364 |  |
| 710070014 | user | 1024 | 2 | 2 | 1.000 | $0.006351 | parse_oolong_rows |  |  |  | 2 |  |
| 312030020 | user | 4096 | 16226 | 16226 | 1.000 | $0.000867 | parse_oolong_rows |  |  |  | 16226 |  |
| 712070048 | user | 4096 | 25844 | 24944 | 0.000 | $0.010766 | parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm;solve_labeled_oolong;solve_oolong_with_tools |  |  |  | 25844 |  |
| 712070018 | user | 4096 | entailment | entailment | 1.000 | $0.009142 | parse_oolong_rows |  |  |  | entailment |  |
| 412040041 | user | 4096 | 28140 | 28140 | 1.000 | $0.013174 | parse_oolong_rows;label_oolong_rows_with_slm;solve_labeled_oolong;solve_oolong_with_tools |  |  |  | 82428 |  |
| 312030051 | user | 4096 | 22165 | 22165 | 1.000 | $0.010725 | parse_oolong_rows |  |  |  | 22165 |  |
| 418040032 | user | 262144 | True | I am unable to determine the least common label due to persistent errors when attempting to use the `label_oolong_rows_with_slm` and `solve_oolong_with_tools` functions. The tools' expected input format for parsed rows and context strings remains unclear despite multiple attempts to adapt. | 0.000 | $0.055994 | parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm |  |  |  | true |  |
| 618060211 | user | 262144 | 20 | 20 | 1.000 | $0.011886 | parse_oolong_rows |  |  |  | 20 |  |
| 418040058 | user | 262144 | 12 | number'. | 0.000 | $0.101104 | parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm;label_oolong_rows_with_slm |  |  |  | 11 |  |
| 218020061 | user | 262144 | 39309 | 39309 | 1.000 | $0.046265 | parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm |  |  |  | 39309 |  |
| 318030064 | user | 262144 | more common than | more common than | 1.000 | $0.019250 | parse_oolong_rows |  |  |  | more common than |  |

## First Generated Code Block Per Completed Row

### 210020009

```python
print(available_oolong_tasks)
print(available_oolong_answer_types)
```

### 710070026

```python
parsed_rows = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_rows)}")
```

### 710070007

```python
print(available_oolong_tasks)
print(available_oolong_answer_types)
```

### 210020033

```python
print(available_oolong_tasks)
print(available_oolong_answer_types)
```

### 410040003

```python
print(context[:500])
print(len(context))
```

### 412040009

```python
print(context[:500]) # Print the first 500 characters to understand the context format
```

### 712070012

```python
print(available_oolong_tasks)
print(available_oolong_answer_types)
```

### 512050034

```python
print(available_oolong_tasks)
print(available_oolong_answer_types)
```

### 912090010

```python
print(available_oolong_tasks)
print(available_oolong_answer_types)
```

### 612060011

```python
print(context[:500])
print(len(context))
```

### 718070027

```python
parsed_rows = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_rows)}")
print(f"First 3 parsed rows: {parsed_rows[:3]}")
```

### 618060051

```python
print(available_oolong_tasks)
print(available_oolong_answer_types)
```

### 718070049

```python
parsed_rows = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_rows)}")
print(f"First 3 parsed rows: {parsed_rows[:3]}")
```

### 218020053

```python
print(context[:1000])
```

### 218020026

```python
result = solve_oolong_with_tools(task='count_labels', answer_type='label_counts')
print(result)
```

### 410040043

```python
parsed_rows = parse_oolong_rows(context)
february_rows = [row for row in parsed_rows if row['date'].month == 2]
print(f"Number of parsed rows: {len(parsed_rows)}")
print(f"Number of February rows: {len(february_rows)}")
```

### 310030048

```python
parsed_rows = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_rows)}")
print(f"First 3 parsed rows: {parsed_rows[:3]}")
```

### 210020017

```python
rows = parse_oolong_rows(context)
dates = [row['date'] for row in rows]
from collections import Counter
date_counts = Counter(dates)
most_common_date = date_counts.most_common(1)[0][0]
print(f"Most common date: {most_common_date}")
answer["content"] = f"Date: {most_common_date}"
answer["ready"] = True
```

### 210020029

```python
parsed_data = parse_oolong_rows(context)
date_counts = {}
for row in parsed_data:
    date = row['date']
    date_counts[date] = date_counts.get(date, 0) + 1

most_frequent_date = None
max_count = 0
for date, count in date_counts.items():
    if count > max_count:
        max_count = count
        most_frequent_date = date

print(f"Most frequent date: {most_frequent_date}")
```

### 910090047

```python
parsed_rows = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_rows)}")
print(f"First 3 parsed rows: {parsed_rows[:3]}")
```

### 912090031

```python
parsed_rows = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_rows)}")
print(f"First 3 parsed rows: {parsed_rows[:3]}")
```

### 612060022

```python
print(available_oolong_tasks)
print(available_oolong_answer_types)
```

### 612060046

```python
print(context[:500])
```

### 412040047

```python
parsed_rows = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_rows)}")
print(f"First 3 parsed rows: {parsed_rows[:3]}")
```

### 212020028

```python
parsed_rows = parse_oolong_rows(context)
print(f"Total rows parsed: {len(parsed_rows)}")
print("First 3 rows:")
for i in range(min(3, len(parsed_rows))):
    print(parsed_rows[i])
```

### 218020038

```python
parsed_rows = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_rows)}")
print(f"First 5 parsed rows: {parsed_rows[:5]}")
```

### 418040042

```python
parsed_rows = parse_oolong_rows(context)
print(f"Total rows parsed: {len(parsed_rows)}")
print("First 5 parsed rows:")
for i, row in enumerate(parsed_rows[:5]):
    print(row)
```

### 418040063

```python
print(context[:1000])
```

### 410040038

```python
parsed_rows = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_rows)}")
print(f"First 3 parsed rows: {parsed_rows[:3]}")
```

### 310030013

```python
print(context[:500])
print(len(context))
```

### 610060037

```python
parsed_rows = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_rows)}")
print(f"First 3 parsed rows: {parsed_rows[:3]}")
```

### 710070033

```python
print(available_oolong_tasks)
print(available_oolong_answer_types)
```

### 710070014

```python
print(context[:500])
```

### 312030020

```python
parsed_rows = parse_oolong_rows(context)
user_ids = [row['user'] for row in parsed_rows]

from collections import Counter
user_counts = Counter(user_ids)

most_common_user = user_counts.most_common(1)[0][0]

print(f"User: {most_common_user}")
answer["content"] = f"User: {most_common_user}"
answer["ready"] = True
```

### 712070048

```python
parsed_rows = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_rows)}")
print(f"First 3 parsed rows: {parsed_rows[:3]}")
```

### 712070018

```python
print(context[:1000])
```

### 412040041

```python
print(context[:500])
```

### 312030051

```python
print(available_oolong_tasks)
print(available_oolong_answer_types)
```

### 418040032

```python
parsed_rows = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_rows)}")
print(f"First 3 parsed rows: {parsed_rows[:3]}")
```

### 618060211

```python
parsed_rows = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_rows)}")
print(f"First 3 parsed rows: {parsed_rows[:3]}")
```

### 418040058

```python
parsed_rows = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_rows)}")
print(f"First 3 parsed rows: {parsed_rows[:3]}")
```

### 218020061

```python
parsed_rows = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_rows)}")
print(f"First 3 parsed rows: {parsed_rows[:3]}")
```

### 318030064

```python
parsed_rows = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_rows)}")
print(f"First 3 parsed rows: {parsed_rows[:3]}")
```

