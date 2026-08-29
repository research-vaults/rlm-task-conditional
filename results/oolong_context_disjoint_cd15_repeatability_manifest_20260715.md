# Oolong CD-15 Repeatability Manifest

No model calls were made. This artifact freezes a balanced 15-row subset from CD-45 so later repeatability runs are predeclared.

## Summary

- N: 15
- Groups: {'counting': 5, 'timeline': 5, 'user': 5}
- Lengths: {'1024': 5, '4096': 5, '262144': 5}
- Unique context windows: 14
- Max questions per context window: 2
- Parent CD-45 exact counts: {'slm_qparsed_typed': 15, 'direct_gemini25_flash': 9, 'standard_rlm_gemini25_flash': 10, 'standard_rlm_gpt5': 10}
- Parent CD-45 captured costs: {'slm_qparsed_typed': 0.107011, 'direct_gemini25_flash': 0.33577, 'standard_rlm_gemini25_flash': 0.308485, 'standard_rlm_gpt5': 0.561897}
- Parent CD-45 error counts: {'slm_qparsed_typed': 0, 'direct_gemini25_flash': 0, 'standard_rlm_gemini25_flash': 0, 'standard_rlm_gpt5': 4}

## Future Stop Rule

Run three independent standard-RLM repeats only after provider credits are available. Charge all completed and failed rows, keep the same 360-second row cap, and report exact agreement, errors/timeouts, cost, and latency. Do not replace this subset after seeing outcomes.

## Selected IDs

| example_id | group | context_len | context_window_id | SLM | RLM/Gemini | RLM/GPT-5 | direct |
|---|---|---:|---|---:|---:|---:|---:|
| 210020009 | counting | 1024 | 20001 | 1 | 1 | 1 | 1 |
| 210020033 | counting | 1024 | 20005 | 1 | 1 | 1 | 1 |
| 412040009 | counting | 4096 | 40008 | 1 | 0 | 0 | 1 |
| 512050034 | counting | 4096 | 50006 | 1 | 0 | 0 | 0 |
| 218020026 | counting | 262144 | 20024 | 1 | 1 | 0 | 1 |
| 210020017 | timeline | 1024 | 20002 | 1 | 1 | 1 | 1 |
| 210020029 | timeline | 1024 | 20004 | 1 | 1 | 1 | 1 |
| 212020028 | timeline | 4096 | 20008 | 1 | 1 | 1 | 1 |
| 218020038 | timeline | 262144 | 20024 | 1 | 0 | 1 | 0 |
| 418040042 | timeline | 262144 | 40024 | 1 | 1 | 0 | 1 |
| 310030013 | user | 1024 | 30000 | 1 | 1 | 1 | 1 |
| 312030051 | user | 4096 | 30006 | 1 | 1 | 1 | 1 |
| 312030020 | user | 4096 | 30008 | 1 | 1 | 1 | 0 |
| 218020061 | user | 262144 | 20025 | 1 | 0 | 0 | 0 |
| 318030064 | user | 262144 | 30025 | 1 | 1 | 1 | 0 |
