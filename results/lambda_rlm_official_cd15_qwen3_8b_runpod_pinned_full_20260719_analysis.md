# Official lambda-RLM CD-15 cross-task analysis

- Evidence role: official lambda-RLM implementation cross-task same-contract evaluation; not original-paper benchmark reproduction
- Rankable full CD-15 row: **True**
- Integrity gate: **True**; errors: `[]`
- Rows attempted: 15; valid model outputs: 15; valid strict exact: 8
- Failure modes: `{"latent_gold_output_contract_failure": 2, "semantic_or_aggregation_error": 3, "strict_exact": 8, "timeout_or_runtime_failure": 2}`
- Listed RunPod runtime cost: `$5.450228`; OpenRouter: `$0.00`

## Paired same-row results

| Comparator | N | lambda exact | comparator exact | b/c | exact McNemar p |
|---|---:|---:|---:|---:|---:|
| slm_qparsed_typed | 15 | 8 | 15 | 0/7 | 0.0156 |
| direct_gemini25_flash | 15 | 8 | 9 | 2/3 | 1.0000 |
| standard_rlm_gemini25_flash | 15 | 8 | 10 | 1/3 | 0.6250 |
| standard_rlm_gpt5 | 15 | 8 | 10 | 2/4 | 0.6875 |
| official_trained_qwen30b | 15 | 8 | 10 | 2/4 | 0.6875 |

## Row diagnostics

- `210020009` (counting, 1024): strict_exact; task=qa; exact=True; calls=2; time=28.0s; error=''.
- `212020028` (timeline, 4096): latent_gold_output_contract_failure; task=classification; exact=False; calls=2; time=15.7s; error=''.
- `218020061` (user, 262144): semantic_or_aggregation_error; task=qa; exact=False; calls=60; time=417.9s; error=''.
- `210020033` (counting, 1024): strict_exact; task=qa; exact=True; calls=2; time=42.7s; error=''.
- `412040009` (counting, 4096): semantic_or_aggregation_error; task=qa; exact=False; calls=2; time=37.5s; error=''.
- `512050034` (counting, 4096): strict_exact; task=qa; exact=True; calls=2; time=38.0s; error=''.
- `218020026` (counting, 262144): strict_exact; task=qa; exact=True; calls=157; time=1259.2s; error=''.
- `210020017` (timeline, 1024): strict_exact; task=qa; exact=True; calls=2; time=20.6s; error=''.
- `210020029` (timeline, 1024): strict_exact; task=qa; exact=True; calls=2; time=13.8s; error=''.
- `218020038` (timeline, 262144): timeout_or_runtime_failure; task=None; exact=False; calls=0; time=0.0s; error='TimeoutError: lambda_rlm timed out after 1800s on example 218020038'.
- `418040042` (timeline, 262144): semantic_or_aggregation_error; task=classification; exact=False; calls=44; time=446.5s; error=''.
- `310030013` (user, 1024): latent_gold_output_contract_failure; task=extraction; exact=False; calls=2; time=34.3s; error=''.
- `312030051` (user, 4096): strict_exact; task=qa; exact=True; calls=2; time=46.1s; error=''.
- `312030020` (user, 4096): strict_exact; task=qa; exact=True; calls=2; time=48.9s; error=''.
- `318030064` (user, 262144): timeout_or_runtime_failure; task=None; exact=False; calls=0; time=0.0s; error='TimeoutError: lambda_rlm timed out after 1800s on example 318030064'.
