# Official lambda-RLM CD-15 cross-task analysis

- Evidence role: official lambda-RLM implementation cross-task same-contract evaluation; not original-paper benchmark reproduction
- Rankable full CD-15 row: **False**
- Rows attempted: 14; valid model outputs: 9; valid strict exact: 4
- Failure modes: `{"latent_gold_output_contract_failure": 2, "provider_credit_failure": 5, "semantic_or_aggregation_error": 3, "strict_exact": 4}`
- Listed RunPod runtime cost: `$0.000000`; OpenRouter: `$0.00`

## Paired same-row results

| Comparator | N | lambda exact | comparator exact | b/c | exact McNemar p |
|---|---:|---:|---:|---:|---:|
| slm_qparsed_typed | 9 | 4 | 9 | 0/5 | 0.0625 |
| direct_gemini25_flash | 9 | 4 | 5 | 1/2 | 1.0000 |
| standard_rlm_gemini25_flash | 9 | 4 | 4 | 1/1 | 1.0000 |
| standard_rlm_gpt5 | 9 | 4 | 6 | 1/3 | 0.6250 |

## Row diagnostics

- `210020009` (counting, 1024): strict_exact; task=qa; exact=True; calls=2; time=8.1s; error=''.
- `212020028` (timeline, 4096): latent_gold_output_contract_failure; task=classification; exact=False; calls=2; time=11.1s; error=''.
- `218020061` (user, 262144): semantic_or_aggregation_error; task=qa; exact=False; calls=37; time=371.8s; error=''.
- `210020033` (counting, 1024): latent_gold_output_contract_failure; task=classification; exact=False; calls=2; time=60.2s; error=''.
- `412040009` (counting, 4096): semantic_or_aggregation_error; task=qa; exact=False; calls=2; time=23.9s; error=''.
- `512050034` (counting, 4096): strict_exact; task=qa; exact=True; calls=2; time=21.7s; error=''.
- `218020026` (counting, 262144): provider_credit_failure; task=qa; exact=False; calls=9; time=71.1s; error=''.
- `210020017` (timeline, 1024): provider_credit_failure; task=None; exact=False; calls=0; time=0.0s; error="RuntimeError: APIStatusError: Error code: 402 - {'error': 'You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Providers. Alternatively, subscribe to PRO to get 20x more included usage.'}".
- `210020029` (timeline, 1024): strict_exact; task=qa; exact=True; calls=2; time=15.0s; error=''.
- `218020038` (timeline, 262144): semantic_or_aggregation_error; task=qa; exact=False; calls=51; time=742.6s; error=''.
- `418040042` (timeline, 262144): provider_credit_failure; task=classification; exact=False; calls=5; time=75.6s; error=''.
- `310030013` (user, 1024): strict_exact; task=qa; exact=True; calls=2; time=17.3s; error=''.
- `312030051` (user, 4096): provider_credit_failure; task=qa; exact=False; calls=1; time=4.4s; error=''.
- `312030020` (user, 4096): provider_credit_failure; task=None; exact=False; calls=0; time=0.0s; error="RuntimeError: APIStatusError: Error code: 402 - {'error': 'You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Providers. Alternatively, subscribe to PRO to get 20x more included usage.'}".
