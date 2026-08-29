# GPT-5.6 Terra RLM CD-45 Attempt

Status: aborted provider-credit run, not a benchmark result.

- Model/backend: `openai/gpt-5.6-terra` via OpenRouter.
- Stop rule: 240 seconds per row.
- Recorded rows before manual stop: 20.
- Valid rows before provider-credit errors: 11.
- Valid-prefix exact/mean: 8/11 exact, 74.3% mean score.
- Valid-prefix captured cost: $0.764031.
- First provider-credit error row: 618060051.

Interpretation: this attempt confirms that the current GPT-5.6 Terra controller is reachable through the harness and can process short rows, but the full CD-45 run is not usable as accuracy evidence because provider-credit/max-token errors began before completion. Use the clean `canary3` result and the completed GPT-5 strict-stop run for paper-facing model-freshness discussion unless credits are replenished and the full GPT-5.6 run is restarted from scratch.
