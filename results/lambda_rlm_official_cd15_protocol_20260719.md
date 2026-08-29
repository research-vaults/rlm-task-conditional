# Official lambda-RLM CD-15 Cross-Task Protocol

Status: preregistered before model calls on 2026-07-19 (Europe/London).

## Scientific purpose

Test whether the unmodified public lambda-RLM implementation changes the paper's
same-contract conclusion on a frozen, context-disjoint Oolong-synth slice. This
is an **official-code cross-task evaluation**, not a reproduction of the
lambda-RLM paper's original benchmark protocol: the implementation and one of
its evaluated controller models are official, while CD-15 is this project's
frozen Oolong-synth contract.

## Immutable inputs and implementation

- Frozen manifest: `results/oolong_context_disjoint_cd15_repeatability_manifest_20260715.json`
- Manifest SHA-256: `6b16c98cd8a4cbb4261768e0334e5354e47f247d2f9f09788e99ac58bf15ec84`
- Standard input: Oolong `context_window_text` (no labels or task-family metadata)
- Output contract and scorer: identical to the existing CD-15/CD-45 exact scorer
- Official repository: `https://github.com/lambda-calculus-LLM/lambda-RLM`
- Commit: `3874d393483dc4299101918cf8e9af670194bd88`
- `rlm/lambda_rlm.py` SHA-256: `3f0e0521f92e1e124e76aa4f717a7bf29c95386ff42b3faf6057d4fa320f42e6`
- `benchmarks/benchmark.py` SHA-256: `903d8f42a5d6ab512cdc126db54429aee278021841ef07b9e9732afcb034727a`
- Tracked official-repository files must be clean at execution time.

## Controller and settings

- Provider route: OpenRouter OpenAI-compatible endpoint
- Model: `qwen/qwen3-8b` (Qwen3-8B is an exact controller tier evaluated by the official repository)
- Live model-catalog check on 2026-07-19: 131,072-token context, 8,192 maximum completion tokens
- Temperature: `0.6`
- Top-p: `0.7`
- Maximum output tokens per call: `4096`
- Lambda context window: `100000` characters
- Streaming: enabled, matching the official benchmark configuration.
- Per-row wall-clock cap: `1,800` seconds after the documented amendment below (`900` seconds in attempts 1-2)

## Prompt and logging

Every row uses the public implementation's documented generic API contract:

```text
Context:
{standard unlabeled context}

Question: {Oolong question}

Answer:
```

The JSONL trace stores the full prompt, raw final output, parsed prediction,
gold answer, score, all reported input/output tokens, call count, cost, latency,
the implementation's printed detected task and deterministic plan, source
hashes, and errors. Provider-hidden internal request bodies are not available;
the public implementation source plus plan trace defines their generation.

## Canary and expansion rule

Run these three frozen rows first, selected before calls to span all task groups
and all context lengths:

- `210020009`: counting, 1,024
- `212020028`: timeline, 4,096
- `218020061`: user, 262,144

Expand to all 15 frozen rows only if all three produce a non-empty final output,
at least two have no execution error, the long row completes within the cap,
and no source/config drift is detected. Accuracy is not an expansion criterion.

## Stop and interpretation rules

- Stop after two total errors, two consecutive errors, or observed OpenRouter
  cost above USD 5.00. Timeout calls can incur provider cost that the killed
  child process cannot report; record this attempted-cost limitation.
- Do not tune prompts, decoding, context size, or model after seeing accuracy.
- Primary endpoint: exact answer count over completed frozen rows, with failures
  scored incorrect under intention-to-evaluate.
- Report task-group and length breakdowns, cost, error count, and paired outcomes
  against the already-logged CD-15 methods.
- A weak result is still reported and cannot be used as a method-level claim
  about lambda-RLM's original tasks. A strong result must not be described as an
  original-paper reproduction.

## Execution amendment after zero-evidence and failed canaries

The first OpenRouter attempt made no model calls because the account could not
reserve 4,096 output tokens; spend was USD 0.00. The first RunPod canary used
non-streaming transport solely to recover token usage. Its 262k row exposed a
provider/runtime interoperability failure: a null `message.content` reached the
official filter's `.strip()` call. This is not an answer-quality observation.
Before any rerun, transport is restored to the official benchmark's
`stream=True` setting. The model, prompts, rows, scorer, decoding parameters,
context limit, timeout, expansion rule, and accuracy-independent gate remain
unchanged. RunPod wall-clock GPU cost replaces unavailable streaming token cost.

The official-stream attempt then completed the short and medium rows but reached
the 900-second wall-clock cap on the 262k row. Before a third attempt, the row
cap is prospectively increased to 1,800 seconds for all rows. This does not alter
the algorithm or favor correct outputs; it tests whether the official bounded
pipeline can finish and makes latency/cost an observed outcome. The identical
three-row canary and accuracy-independent expansion rule remain in force. The
original 900-second attempt is retained as deployability evidence and is not
discarded or overwritten.

The 1,800-second attempt on a 50-GB-class GPU also reached its cap on the same
262k row. Before a fourth attempt, hardware is changed to an H100/A100 80-GB
class GPU while every scientific parameter and the 1,800-second cap remains
fixed. This is a throughput correction, not model or prompt tuning. All prior
attempts and creation-to-cleanup costs remain part of the accounting.

The first H100 attempt completed the long execution path quickly enough, but
the provider pod disappeared during the row. The official runtime converted
downstream HTTP 404 responses into a non-empty final string (`Error: Error code:
404`), so the initial gate implementation incorrectly accepted it and expansion
immediately stopped after two further 404s. This attempt is infrastructure
evidence only. Before the next run, the gate is corrected to reject error-text
outputs and the pod is requested from RunPod secure cloud. Scientific settings
remain unchanged.

RunPod secure-cloud creation then failed before resource allocation because the
account balance was below the rental threshold (zero spend). Hugging Face's live
provider mapping for the exact `Qwen/Qwen3-8B` checkpoint lists Nscale and
Featherless AI. A 64-token connectivity probe showed both routes working but
exhausting that deliberately tiny cap during reasoning, confirming that the
4,096-token official setting must not be reduced. The next identical canary is
routed through Hugging Face/Nscale with official streaming and the same
1,800-second row cap. Provider choice is logged; no result is pooled across
providers.
