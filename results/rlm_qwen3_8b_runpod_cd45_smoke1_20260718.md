# RLM-Qwen3-8B Official-Checkpoint RunPod Smoke

Date: 2026-07-18

## Purpose

This smoke test directly probes the remaining paid-run gate: can an official RLM-family checkpoint be run under the same Oolong CD contract, rather than leaving "official/near-official stronger-family row" as a purely documented future item?

The tested path is official RLM-Qwen, not SRLM, lambda-RLM, or RAH:

- Checkpoint: `mit-oasys/rlm-qwen3-8b-v0.1`
- Hugging Face status checked before launch: public, ungated, revision `171c96639865d559206cd7ef78c4d8188a91992a`
- Serving: temporary RunPod serverless vLLM endpoint using `runpod/worker-v1-vllm:v2.22.5`
- Scaffold: installed official `rlm.RLM`
- Contract: frozen Oolong CD manifest, standard/unlabeled `context_window_text`, natural-language question as `root_prompt`, same local scorer
- No custom typed tools and no label-provided context

## Endpoint Creation

Artifact: `results/runpod_rlm_qwen_endpoint_attempt_20260718.json`

- First serverless template attempt failed with HTTP 500 because RunPod serverless templates do not support `volumeInGb`.
- Retried with a serverless-compatible template and created:
  - Template: `3ac6y9532c`
  - Endpoint: `kl68voh8ttlb0q`
  - Worker policy: `workersMin=0`, `workersMax=1`, `idleTimeout=5`
- Cleanup completed after the smoke:
  - Endpoint delete: HTTP 204
  - Template delete: HTTP 204
  - Post-cleanup `/endpoints`, `/pods`, and `/templates`: empty lists

## OpenAI-Compatible Endpoint Smoke

Artifact: `results/runpod_rlm_qwen_openai_smoke_20260718.json`

- `/models` returned `mit-oasys/rlm-qwen3-8b-v0.1` after a 136.44 second cold start.
- A tiny chat-completion probe returned a scoreable response in 1.19 seconds:
  - Prompt: `Return exactly: READY`
  - Response: `You responded with:\n[Answer]\nREADY`
  - Usage: 12 prompt tokens, 9 completion tokens, 21 total tokens

This proves that the checkpoint was served and reachable through an OpenAI-compatible API.

## Same-Contract RLM Scaffold Smoke

Artifacts:

- `results/rlm_qwen3_8b_runpod_cd45_smoke1_20260718.jsonl`
- `results/rlm_qwen3_8b_runpod_cd45_smoke1_20260718_summary.json`

Row:

- Example ID: `912090010`
- Task group: `counting`
- Context length: 10,257 characters
- Question: `In the above data, is label 'negative' more common, less common, or the same frequency as label 'positive'? Give your final answer in the form 'Answer: negative is [X] positive', where [X] is 'more common than', 'less common than', or 'same frequency as'.`
- Gold: `less common than`

Outcome:

- Outer row cap: 420 seconds
- Result: timeout
- Exact: 0/1
- Prediction: empty
- Raw response: empty
- Captured code blocks: 0
- Captured usage/cost from OpenAI-compatible response: none

## Interpretation

This is not evidence that official RLM-Qwen is weak. It is evidence that the official-checkpoint path is not currently a cheap, stable, same-contract comparator under the local RunPod/vLLM plus installed-`rlm` scaffold setup.

The result should be used as a protocol-boundary artifact:

1. We did not merely document the stronger-family gate; we tried the most concrete official-checkpoint path available.
2. The endpoint itself worked, so the blocker is not Hugging Face access or RunPod authentication.
3. The blocker is RLM scaffold stability/latency under the same Oolong CD contract when using the served RLM-Qwen checkpoint.
4. Scaling this path to CD-15/CD-45 before submission would be irresponsible unless a shorter preflight can first complete reliably and return generated-program traces.

## Cost Note

OpenRouter spend for this run: `$0.00`.

RunPod REST billing endpoints showed no endpoint billing rows immediately after cleanup. The API did not return a dollar cost for the temporary serverless worker in the response. Treat any RunPod charge as account-side compute billing rather than model API usage; the local artifact records endpoint lifetime, cold-start time, row timeout, and cleanup proof.

