# Standard `rlms` + Atomic Same Typed Operator Library Diagnostic

This is the atomic same-operator-library diagnostic for standard `rlms`. It preserves free-form RLM program generation while injecting parse, SLM-label, typed-solve, and schema-list tools through `custom_tools`, but withholds the `solve_oolong_with_tools` convenience solver.

## Summary

- Run ID: `oolong_cd45_rlm_atomic_ops_20260717`
- Tool mode: `atomic`
- Rows: 29/45 exact
- Mean score: 0.6928
- Controller cost: `$0.548691`
- Tool cost: `$0.409998`
- Total cost: `$0.958685`
- Errors: 4
- Tool calls: 155
- Generated code blocks: 337

## Contract

Standard rlms v0.1.3 with custom_tools exposing the same typed Oolong operator library. Input is standard context_window_text only; root prompt is the natural-language question. The generated program must choose task/answer_type itself. Atomic mode removes the solve_oolong_with_tools convenience solver, leaving parse, SLM-label, solve_labeled, and schema-list tools only. This is not shared-operator routing and not official SRLM/lambda-RLM.

## Rows

| example | group | len | gold | pred | score | cost | tools | std RLM | SLM+typed | direct | shared-op | error |
|---|---|---:|---|---|---:|---:|---|---|---|---|---|---|
| 210020009 | counting | 1024 | 1 | 1 | 1.000 | $0.011674 | parse_oolong_rows;parse_oolong_rows;parse_oolong_rows;parse_oolong_rows;parse_oolong_rows;parse_oolong_rows;parse_oolong_rows;parse_oolong_rows |  |  |  | 1 |  |
| 710070026 | counting | 1024 | neutral | neutral | 1.000 | $0.020635 | parse_oolong_rows;parse_oolong_rows;parse_oolong_rows;parse_oolong_rows;parse_oolong_rows;parse_oolong_rows;parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm;label_oolong_rows_with_slm |  |  |  | contradiction |  |
| 710070007 | counting | 1024 | 2 | 2 | 1.000 | $0.006051 | parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm;label_oolong_rows_with_slm |  |  |  | 2 |  |
| 210020033 | counting | 1024 | 0 | 0 | 1.000 | $0.006403 | parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm |  |  |  | 0 |  |
| 410040003 | counting | 1024 | 11 | 10 | 0.750 | $0.008940 | parse_oolong_rows;label_oolong_rows_with_slm |  |  |  | 11 |  |
| 412040009 | counting | 4096 | True | True | 1.000 | $0.012862 | parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm;label_oolong_rows_with_slm;label_oolong_rows_with_slm;label_oolong_rows_with_slm |  |  |  | true |  |
| 712070012 | counting | 4096 | less common than | less common than | 1.000 | $0.010756 | parse_oolong_rows |  |  |  | less common than |  |
| 512050034 | counting | 4096 | more common than | more common than | 1.000 | $0.009705 | parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm |  |  |  | more common than |  |
| 912090010 | counting | 4096 | less common than | less common than | 1.000 | $0.015217 | parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm |  |  |  | less common than |  |
| 612060011 | counting | 4096 | 46 | 40 | 0.178 | $0.009092 | parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm |  |  |  | 37 |  |
| 718070027 | counting | 262144 | more common than |  | 0.000 | $0.055790 | parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm |  |  |  | more common than | TimeoutError: RLM+ops run timed out after 360s |
| 618060051 | counting | 262144 | less common than |  | 0.000 | $0.064026 | parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm;solve_labeled_oolong |  |  |  | less common than | TimeoutError: RLM+ops run timed out after 360s |
| 718070049 | counting | 262144 | contradiction | Label: Unable to determine due to tool error. | 0.000 | $0.104970 | parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm;label_oolong_rows_with_slm;solve_labeled_oolong |  |  |  | contradiction |  |
| 218020053 | counting | 262144 | 387 | 396 | 0.075 | $0.044575 | parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm |  |  |  | 393 |  |
| 218020026 | counting | 262144 | more common than | more common than | 1.000 | $0.042289 | parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm |  |  |  | more common than |  |
| 410040043 | timeline | 1024 | False | Label: false | 0.000 | $0.031255 | parse_oolong_rows;parse_oolong_rows;parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm;parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm;parse_oolong_rows;label_oolong_rows_with_slm;parse_oolong_rows;parse_oolong_rows;parse_oolong_rows;parse_oolong_rows |  |  |  | true |  |
| 310030048 | timeline | 1024 | more common | same frequency | 0.000 | $0.010566 | parse_oolong_rows;label_oolong_rows_with_slm |  |  |  | more common |  |
| 210020017 | timeline | 1024 | 2023-06-29 00:00:00 | Jun 29, 2023 | 1.000 | $0.000835 | parse_oolong_rows |  |  |  | Jun 29, 2023 |  |
| 210020029 | timeline | 1024 | 2025-03-03 00:00:00 | 03/03/2025 | 1.000 | $0.002515 | parse_oolong_rows |  |  |  | Mar 03, 2025 |  |
| 910090047 | timeline | 1024 | 1 | 1 | 1.000 | $0.014669 | parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm;label_oolong_rows_with_slm |  |  |  | 1 |  |
| 912090031 | timeline | 4096 | 6 | 9 | 0.422 | $0.022400 | parse_oolong_rows;parse_oolong_rows;parse_oolong_rows;parse_oolong_rows;parse_oolong_rows;label_oolong_rows_with_slm;parse_oolong_rows;parse_oolong_rows;label_oolong_rows_with_slm;parse_oolong_rows;label_oolong_rows_with_slm;parse_oolong_rows;parse_oolong_rows |  |  |  | 4 |  |
| 612060022 | timeline | 4096 | more common | same frequency | 0.000 | $0.022549 | parse_oolong_rows;parse_oolong_rows;parse_oolong_rows;label_oolong_rows_with_slm;parse_oolong_rows |  |  |  | more common |  |
| 612060046 | timeline | 4096 | less common | less common | 1.000 | $0.011890 | parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm;label_oolong_rows_with_slm |  |  |  | less common |  |
| 412040047 | timeline | 4096 | True | False | 0.000 | $0.014288 | parse_oolong_rows |  |  |  | false |  |
| 212020028 | timeline | 4096 | 2 | 2 | 1.000 | $0.020769 | parse_oolong_rows;label_oolong_rows_with_slm |  |  |  | 2 |  |
| 918090044 | timeline | 262144 | 383 |  | 0.000 | $0.000000 | parse_oolong_rows |  |  |  | 375 | TimeoutError: RLM+ops run timed out after 360s |
| 218020038 | timeline | 262144 | 2024-12-06 00:00:00 | 12/06/2024 | 1.000 | $0.002820 | parse_oolong_rows |  |  |  | Dec 06, 2024 |  |
| 418040042 | timeline | 262144 | more common than | more common than | 1.000 | $0.029080 | parse_oolong_rows |  |  |  | more common than |  |
| 718070046 | timeline | 262144 | more common than | same frequency as | 0.000 | $0.081094 | parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm |  |  |  | more common than |  |
| 418040063 | timeline | 262144 | True | True | 1.000 | $0.042539 | parse_oolong_rows |  |  |  | true |  |
| 410040038 | user | 1024 | 91546 | 91546 | 1.000 | $0.013485 | parse_oolong_rows;label_oolong_rows_with_slm |  |  |  | 91546 |  |
| 310030013 | user | 1024 | Business | Business | 1.000 | $0.007284 | parse_oolong_rows |  |  |  | business |  |
| 610060037 | user | 1024 | 1 | 1 | 1.000 | $0.009439 | parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm |  |  |  | 1 |  |
| 710070033 | user | 1024 | 30364 | 30364 | 1.000 | $0.003376 | parse_oolong_rows |  |  |  | 30364 |  |
| 710070014 | user | 1024 | 2 | 3 | 0.750 | $0.024052 | parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm;label_oolong_rows_with_slm;label_oolong_rows_with_slm;label_oolong_rows_with_slm;label_oolong_rows_with_slm;label_oolong_rows_with_slm |  |  |  | 2 |  |
| 312030020 | user | 4096 | 16226 | 16226 | 1.000 | $0.000853 | parse_oolong_rows |  |  |  | 16226 |  |
| 712070048 | user | 4096 | 25844 | 25844 | 1.000 | $0.012751 | parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm;label_oolong_rows_with_slm |  |  |  | 25844 |  |
| 712070018 | user | 4096 | entailment | entailment | 1.000 | $0.006502 | parse_oolong_rows |  |  |  | entailment |  |
| 412040041 | user | 4096 | 28140 | 28140 | 1.000 | $0.021419 | parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm;solve_labeled_oolong;solve_labeled_oolong |  |  |  | 82428 |  |
| 312030051 | user | 4096 | 22165 | 22165 | 1.000 | $0.009594 | parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm;parse_oolong_rows;label_oolong_rows_with_slm |  |  |  | 22165 |  |
| 418040032 | user | 262144 | True | User ID 77373 not found in the dataset. Cannot determine the least common label. | 0.000 | $0.002814 | parse_oolong_rows |  |  |  | true |  |
| 618060211 | user | 262144 | 20 | 20 | 1.000 | $0.018853 | parse_oolong_rows |  |  |  | 20 |  |
| 418040058 | user | 262144 | 12 |  | 0.000 | $0.000000 | parse_oolong_rows |  |  |  | 11 | TimeoutError: RLM+ops run timed out after 360s |
| 218020061 | user | 262144 | 39309 | 39309 | 1.000 | $0.039610 | parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm |  |  |  | 39309 |  |
| 318030064 | user | 262144 | more common than | more common than | 1.000 | $0.058399 | parse_oolong_rows;label_oolong_rows_with_slm;label_oolong_rows_with_slm |  |  |  | more common than |  |

## First Generated Code Block Per Completed Row

### 210020009

```python
parsed_rows = parse_oolong_rows(context)
labels, cost = label_oolong_rows_with_slm(parsed_rows)
negative_count = labels.count('negative')
print(f"Number of negative labels: {negative_count}")
answer["content"] = f"Answer: {negative_count}"
answer["ready"] = True
```

### 710070026

```python
parsed_rows = parse_oolong_rows(context)
labels, cost = label_oolong_rows_with_slm(parsed_rows)

label_counts = {}
for label in labels:
    label_counts[label] = label_counts.get(label, 0) + 1

print(label_counts)
```

### 710070007

```python
parsed_rows = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_rows)}")
# print first 3 rows to inspect
print(parsed_rows[:3])
```

### 210020033

```python
print(context[:500])
```

### 410040003

```python
parsed_rows = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_rows)}")
print(f"First 3 parsed rows: {parsed_rows[:3]}")
```

### 412040009

```python
parsed_rows = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_rows)}")
```

### 712070012

```python
parsed_rows = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_rows)}")
print(f"First 3 parsed rows: {parsed_rows[:3]}")
```

### 512050034

```python
parsed_rows = parse_oolong_rows(context)
print(f"Parsed {len(parsed_rows)} rows.")
```

### 912090010

```python
parsed_rows = parse_oolong_rows(context)
print(f"Parsed {len(parsed_rows)} rows.")
```

### 612060011

```python
parsed_rows = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_rows)}")
```

### 718070049

```python
parsed_rows = parse_oolong_rows(context)
print(f"Parsed {len(parsed_rows)} rows.")
```

### 218020053

```python
parsed_rows = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_rows)}")
```

### 218020026

```python
parsed_rows = parse_oolong_rows(context)
print(f"Parsed {len(parsed_rows)} rows.")
```

### 410040043

```python
parsed_rows = parse_oolong_rows(context)
february_rows = [row for row in parsed_rows if row['date'].month == 2]
print(f"Number of rows in February: {len(february_rows)}")
```

### 310030048

```python
parsed_rows = parse_oolong_rows(context)
print(f"Parsed {len(parsed_rows)} rows.")
print(f"First 3 parsed rows: {parsed_rows[:3]}")
```

### 210020017

```python
parsed_data = parse_oolong_rows(context)
dates = [row['date'] for row in parsed_data]
from collections import Counter
date_counts = Counter(dates)
most_common_date = date_counts.most_common(1)[0][0]
answer["content"] = f"Date: {most_common_date}"
answer["ready"] = True
print(answer["content"])
```

### 210020029

```python
print(context[:500])
```

### 910090047

```python
parsed_rows = parse_oolong_rows(context)
print(f"Total rows parsed: {len(parsed_rows)}")
print("First 3 parsed rows:")
for i in range(min(3, len(parsed_rows))):
    print(parsed_rows[i])
```

### 912090031

```python
print(context[:500]) # Print the first 500 characters to understand the context format
parsed_rows = parse_oolong_rows(context)
print(f"Total parsed rows: {len(parsed_rows)}")

# Define the date range
from datetime import datetime
start_date = datetime(2023, 7, 18)
end_date = datetime(2024, 5, 5)

# Filter rows by date
filtered_rows = [
    row for row in parsed_rows
    if start_date <= row['date'] <= end_date
]
print(f"Rows after date filtering: {len(filtered_rows)}")

# Label the filtered rows
labeled_rows, cost = label_oolong_rows_with_slm(filtered_rows)
print(f"Cost of labeling: {cost}")

# Count 'negative' labels
negative_count = sum(1 for label in labeled_rows if label == 'negative')
print(f"Number of 'negative' labels: {negative_count}")

answer["content"] = f"Answer: {negative_count}"
answer["ready"] = True
```

### 612060022

```python
from datetime import datetime

parsed_rows = parse_oolong_rows(context)
print(f"Parsed {len(parsed_rows)} rows.")

labeled_rows, cost = label_oolong_rows_with_slm(parsed_rows)
print(f"Labeled {len(labeled_rows)} rows with cost {cost}.")
print(f"Sample labeled row: {labeled_rows[0]}")

date_threshold = datetime.fromisoformat('2024-04-29')

before_threshold = [row for row in labeled_rows if row['date'] < date_threshold]
after_threshold = [row for row in labeled_rows if row['date'] >= date_threshold]

formal_before = sum(1 for row in before_threshold if row['label'] == 'formal')
formal_after = sum(1 for row in after_threshold if row['label'] == 'formal')

print(f"Formal labels before {date_threshold}: {formal_before}")
print(f"Formal labels after {date_threshold}: {formal_after}")

if formal_before > formal_after:
    result = "more common"
elif formal_before < formal_after:
    result = "less common"
else:
    result = "the same frequency"

answer["content"] = f"Answer: formal is {result} before 2024-04-29"
answer["ready"] = True
```

### 612060046

```python
parsed_rows = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_rows)}")
print(f"First 3 parsed rows: {parsed_rows[:3]}")
```

### 412040047

```python
parsed_rows = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_rows)}")
print("First 3 parsed rows:")
for i in range(min(3, len(parsed_rows))):
    print(parsed_rows[i])
```

### 212020028

```python
parsed_data = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_data)}")
print(f"First 3 parsed rows: {parsed_data[:3]}")
```

### 218020038

```python
parsed_rows = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_rows)}")
print("First 5 parsed rows:")
for i in range(min(5, len(parsed_rows))):
    print(parsed_rows[i])
```

### 418040042

```python
parsed_rows = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_rows)}")
print(f"First 3 parsed rows: {parsed_rows[:3]}")
```

### 718070046

```python
parsed_rows = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_rows)}")
print(f"First 3 parsed rows: {parsed_rows[:3]}")
```

### 418040063

```python
parsed_data = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_data)}")
print(f"First 3 parsed rows: {parsed_data[:3]}")
```

### 410040038

```python
parsed_rows = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_rows)}")
print(f"First 3 parsed rows: {parsed_rows[:3]}")
```

### 310030013

```python
parsed_rows = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_rows)}")
print(f"First 3 parsed rows: {parsed_rows[:3]}")
```

### 610060037

```python
parsed_rows = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_rows)}")
print(f"First 3 parsed rows: {parsed_rows[:3]}")
```

### 710070033

```python
print(context[:500])
```

### 710070014

```python
parsed_rows = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_rows)}")
print(f"First 3 parsed rows: {parsed_rows[:3]}")
```

### 312030020

```python
parsed_data = parse_oolong_rows(context)
user_ids = [row['user'] for row in parsed_data]

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
parsed_rows = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_rows)}")
print(f"First 3 parsed rows: {parsed_rows[:3]}")
```

### 412040041

```python
parsed_rows = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_rows)}")
print(f"First 3 parsed rows: {parsed_rows[:3]}")
```

### 312030051

```python
parsed_rows = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_rows)}")
print(f"First 3 parsed rows: {parsed_rows[:3]}")
```

### 418040032

```python
parsed_rows = parse_oolong_rows(context)
print(f"Number of parsed rows: {len(parsed_rows)}")
```

### 618060211

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

