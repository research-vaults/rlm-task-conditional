# Official lambda-RLM CD-15 RunPod Full-Run Protocol

Status: frozen before model/GPU calls on 2026-07-19 (Europe/London).

## Purpose and evidence role

Run a provider-consistent full-CD-15 official-code lambda-RLM cross-task
diagnostic after both routed-provider paths remained credit-limited. This row
is separate from the Hugging Face/Nscale prefix and zero-output OpenRouter
canary. It evaluates the unmodified lambda-RLM implementation and its Qwen3-8B
controller tier on this project's frozen same-input/same-scorer contract; it is
not an original-task reproduction of the lambda-RLM paper.

## Immutable implementation and data

- Manifest:
  `results/oolong_context_disjoint_cd15_repeatability_manifest_20260715.json`
- Manifest SHA-256:
  `6b16c98cd8a4cbb4261768e0334e5354e47f247d2f9f09788e99ac58bf15ec84`
- Input: standard unlabeled `context_window_text`
- Prompt: public `Context / Question / Answer` adapter contract
- Output parser/scorer: unchanged CD-15 exact scorer
- Official repository commit:
  `3874d393483dc4299101918cf8e9af670194bd88`
- `rlm/lambda_rlm.py` SHA-256:
  `3f0e0521f92e1e124e76aa4f717a7bf29c95386ff42b3faf6057d4fa320f42e6`
- `benchmarks/benchmark.py` SHA-256:
  `903d8f42a5d6ab512cdc126db54429aee278021841ef07b9e9732afcb034727a`
- Official tracked files must remain clean.

## Frozen model and serving environment

- Model: `Qwen/Qwen3-8B`
- Weight revision:
  `b968826d9c46dd6066d109eabc6255188de91218`
- Serving image: `vllm/vllm-openai:v0.21.0`
- GPU request: one secure-cloud H100 80GB, H100 NVL, A100 SXM4 80GB, or
  A100 PCIe 80GB, in that preference list
- vLLM model context: 32,768 tokens
- Reasoning parser: `qwen3`
- Maximum concurrent sequences: one
- Temperature/top-p/max output: `0.6` / `0.7` / `4096`
- Lambda context window: `100000` characters
- Streaming: enabled
- Per-row cap: `1800` seconds
- Stop rules: two total errors, two consecutive errors, or USD 5.00 in
  returned model usage. RunPod creation-to-cleanup cost is reported separately.

The weight and image pins improve serving reproducibility; they do not tune the
controller after observing benchmark accuracy.

## Accuracy-blind canary and expansion

Run the previously frozen cross-group/length canary:

- `210020009`: counting, 1,024
- `212020028`: timeline, 4,096
- `218020061`: user, 262,144

Expand only if all three produce non-empty final outputs, at least two have no
execution error, the long row completes within the cap, no error string is
mistaken for a model output, and all source/configuration pins match. Accuracy
is not inspected. If the gate passes, append the remaining 12 rows without
rerunning the canary.

## Reporting and stop rules

- If all 15 rows are attempted, report intention-to-evaluate exact and mean
  score, errors/completions, group/length breakdowns, calls/tokens, latency,
  protocol cost, actual provider cost, and full prompt/output traces.
- Compute paired same-row comparisons with SLM+typed, direct Gemini, standard
  RLM/Gemini, standard RLM/GPT-5, and official trained RLM-Qwen.
- Preserve every failure and all infrastructure attempts. Never pool results
  across RunPod, Nscale, and OpenRouter.
- If the canary or full stop rule fires, report deployability evidence only and
  do not infer a full-CD-15 ranking.
- Always delete the temporary pod and record the cleanup response.

## Budget

- RunPod pre-run balance: USD 9.8437418642; pre-run active spend: USD 0/hour.
- Expected cost from prior H100 timing: below USD 5, but actual
  creation-to-cleanup billing is authoritative.
- OpenRouter spend for this route: USD 0.00.

