# Oolong CD-45 Trace Examples

No model calls were made. This artifact summarizes paired CD-45 outputs and available traces. Standard-RLM generated program text is not available for CD-45; the stored RLM artifacts contain prediction, cost, and error rows.

## Outcome Pattern Counts

Pattern order: standard RLM/Gemini, standard RLM/GPT-5, SLM+typed, direct Gemini.

- `rlm_gemini,gpt5_rlm,slm,direct=0000`: 5
- `rlm_gemini,gpt5_rlm,slm,direct=0010`: 6
- `rlm_gemini,gpt5_rlm,slm,direct=0011`: 1
- `rlm_gemini,gpt5_rlm,slm,direct=0100`: 2
- `rlm_gemini,gpt5_rlm,slm,direct=0110`: 3
- `rlm_gemini,gpt5_rlm,slm,direct=0111`: 1
- `rlm_gemini,gpt5_rlm,slm,direct=1000`: 1
- `rlm_gemini,gpt5_rlm,slm,direct=1001`: 1
- `rlm_gemini,gpt5_rlm,slm,direct=1010`: 4
- `rlm_gemini,gpt5_rlm,slm,direct=1011`: 4
- `rlm_gemini,gpt5_rlm,slm,direct=1110`: 3
- `rlm_gemini,gpt5_rlm,slm,direct=1111`: 14

## Representative Cases

| case | example | group | len | gold | RLM/Gemini | RLM/GPT-5 | SLM+typed | direct |
|---|---|---|---:|---|---|---|---|---|
| slm_and_direct_fix_standard_rlm | 912090010 | counting | 4096 | less common than | same frequency as (0) | less common than (1) | less common than (1) | less common than (1) |
| slm_and_direct_fix_standard_and_gpt5_rlm | 412040009 | counting | 4096 | True | False (0) | ERR (0) | true (1) | True (1) |
| structured_routes_fix_direct | 312030020 | user | 4096 | 16226 | 16226 (1) | 16226 (1) | 16226 (1) | 72294 (0) |
| rlm_and_direct_fix_slm | 710070026 | counting | 1024 | neutral | neutral (1) | ERR (0) | contradiction (0) | neutral (1) |
| long_context_gpt5_scaffold_timeout | 218020026 | counting | 262144 | more common than | more common than (1) | ERR (0) | more common than (1) | more common than (1) |

### slm_and_direct_fix_standard_rlm (`912090010`)

SLM+typed, direct Gemini, and GPT-5 RLM all answer the comparison correctly; standard RLM/Gemini collapses to a tie.

- Question: In the above data, is label 'negative' more common, less common, or the same frequency as label 'positive'? Give your final answer in the form 'Answer: negative is [X] positive', where [X] is 'more common than', 'less common than', or 'same frequency as'.
- SLM worker: rows=71, blocks=1, typed_ops=['count_label', 'compare'], typed_status=label_compare, row_label_accuracy=0.9577464788732394
- Direct controller trace: input_tokens=3469, output_tokens=8, latency_s=0.533

### slm_and_direct_fix_standard_and_gpt5_rlm (`412040009`)

SLM+typed and direct Gemini answer a least-label question correctly; standard RLM/Gemini chooses the wrong label and GPT-5 RLM times out.

- Question: In the above data, which of the labels is the least common? Give your final answer in the form 'Label: answer' where answer is one of the labels: True, False.
- SLM worker: rows=77, blocks=1, typed_ops=['count_label', 'argmin'], typed_status=label_least, row_label_accuracy=0.8311688311688312
- Direct controller trace: input_tokens=3494, output_tokens=3, latency_s=0.626

### structured_routes_fix_direct (`312030020`)

Both RLM controllers and SLM+typed recover the most frequent user; direct whole-context Gemini selects a different user.

- Question: In the above data, which user is represented most often? Give your final answer in the form 'User: [X]', where [X] is the user ID.
- SLM worker: rows=38, blocks=1, typed_ops=['count_user', 'argmax'], typed_status=user_most, row_label_accuracy=0.9473684210526315
- Direct controller trace: input_tokens=3203, output_tokens=8, latency_s=0.708

### rlm_and_direct_fix_slm (`710070026`)

The SLM row labels are locally exact, but a tie/normalization edge in typed aggregation returns the wrong least label; standard RLM and direct Gemini answer correctly.

- Question: In the above data, which of the labels is the least common? Give your final answer in the form 'Label: answer' where answer is one of the labels: neutral, entailment, contradiction.
- SLM worker: rows=7, blocks=1, typed_ops=['count_label', 'argmin'], typed_status=label_least, row_label_accuracy=1.0
- Direct controller trace: input_tokens=804, output_tokens=3, latency_s=0.542

### long_context_gpt5_scaffold_timeout (`218020026`)

At 262k context, SLM+typed, standard RLM/Gemini, and direct Gemini agree; GPT-5 standard RLM times out under the strict row cap.

- Question: In the above data, is label 'negative' more common, less common, or the same frequency as label 'positive'? Give your final answer in the form 'Answer: negative is [X] positive', where [X] is 'more common than', 'less common than', or 'same frequency as'.
- SLM worker: rows=661, blocks=9, typed_ops=['count_label', 'compare'], typed_status=label_compare, row_label_accuracy=0.962178517397882
- Direct controller trace: input_tokens=214817, output_tokens=8, latency_s=3.401
