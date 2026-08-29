# BrowseComp-Plus Equal-Cap N45 No-Context Parametric Probe

## Status

- Protocol ID: `BCP-EQUAL-CAP-N45-NOCONTEXT-v1`
- Frozen: 2026-07-27 before any probe output
- Chronology: `POST_HOC_EXPLORATORY`
- Purpose: measure answer signal available from the matched Qwen checkpoint
  without the BrowseComp document corpus, retrieval or tools.
- This probe is not a fifth route in the prospective equal-cap comparison and
  cannot change the four-route primary ordering.

## Population

Use exactly the 45 ranks in
`results/browsecomp_plus_shard1_equal_cap_n45/manifest_n45_restricted.json`.
Questions and reference answers are read from the already frozen restricted
compact ledger. The runner must verify one unique question and answer per rank.

## Generation

- Model: `qwen/qwen3.6-35b-a3b`
- Required canonical slug:
  `qwen/qwen3.6-35b-a3b-20260415`
- Input: question only.
- No BrowseComp documents, retrieval results, search, external context, tools
  or inter-model calls.
- Temperature: 0.
- Seed: 20.
- Maximum output: 128 tokens.
- Reasoning: disabled.
- Output instruction: concise final answer only; make a best attempt if
  uncertain and do not explain.

Every rank is attempted. Transport or parse failures count incorrect. Raw
request bodies, provider response IDs, returned model/provider, token usage,
reported cost, latency and output are retained in a restricted ledger.

## Semantic Scoring

Apply the same semantic contract used for the equal-cap endpoint:

1. `google/gemma-4-26b-a4b-it`, canonical slug
   `google/gemma-4-26b-a4b-it-20260403`, temperature 0, seed 20 and reasoning
   disabled.
2. `openai/gpt-5.6-sol`, canonical slug
   `openai/gpt-5.6-sol-20260709`, blinded batch sensitivity with high
   reasoning.

Judges see the question, candidate response and reference answer but no method
identity. Generation failures remain incorrect and are not sent to a judge.

## Admission And Reporting

- Primary diagnostic statistic: Gemma semantic correct / 45.
- Sensitivity: GPT-5.6 semantic correct / 45 and cross-judge agreement on
  successful outputs.
- Also report strict exact and normalized-contains rates from the raw probe
  outputs.
- The result may be described only as a parametric-knowledge diagnostic. It
  must not be used to claim contamination, memorization, retrieval quality or
  equal-cap route superiority.
- Raw questions, answers and outputs remain restricted. Only aggregate counts,
  settings, model identities, hashes and costs are release-safe.

## Run Gate

- OpenRouter hard cap: USD 2.00 account-usage delta.
- RunPod spend: USD 0.00.
- Abort promotion if the generation or either judge resolves to a different
  canonical model, if any judge output remains unparsed after one retry or if
  the aggregate cannot be recomputed from retained raw ledgers.

