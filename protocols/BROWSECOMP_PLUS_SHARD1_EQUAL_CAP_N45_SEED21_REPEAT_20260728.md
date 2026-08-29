# BrowseComp-Plus Shard-1 Equal-Cap N=45 — Seed-21 Rollout Repeat

## Status

- Freeze date: 2026-07-28
- Study ID: `browsecomp_plus_shard1_equal_cap_n45_seed21_v1`
- Chronology: `POST_HOC_EXPLORATORY`. The seed-20 equal-cap results were already
  observed and reported before this repeat was designed. This study therefore
  cannot claim, and does not claim, the prospective status of the seed-20 run.
- Evidence role: rollout-variance sensitivity. It is a replication of the
  generation step only, not an independent endpoint.
- Parent study: `browsecomp_plus_shard1_equal_cap_n45_v1`, protocol
  `protocols/BROWSECOMP_PLUS_SHARD1_EQUAL_CAP_N45_20260726.md`.

## Question

Does the equal-cap route ordering, and specifically the non-significant RLM
contrast set, survive a second rollout drawn under the same sampling
distribution but a different random seed?

This is the only quantity at issue. A rerun at the parent seed would measure
vLLM/FP8 batching nondeterminism rather than rollout variance, because the
parent run already pins `seed: 20`.

## What changes from the parent protocol

Exactly one generation parameter:

| Field | Parent | This repeat |
|---|---|---|
| `seed` | 20 | **21** |

## What is held identical

Everything else is inherited unchanged from the parent protocol and enforced by
hash or constant in the runner:

- Rows: the same frozen 45-row manifest,
  `results/browsecomp_plus_shard1_equal_cap_n45/manifest_n45_restricted.json`,
  SHA-256 `c74487ed2cb53640c107c352ab3ba6569f5aa09a16eb74978700e791658ae816`.
- Routes: all four — `standard_rlm_qwen36`, `iterative_search_qwen36`,
  `textual_decomposition_qwen36`, `bm25_qwen36`.
- Model: `Qwen/Qwen3.6-35B-A3B-FP8`, revision
  `95a723d08a9490559dae23d0cff1d9466213d989`.
- Serving image: `vllm/vllm-openai@sha256:e4f88a835143cd22aee2397a26ec6bb80b3a4a6fe0c882bcbc63822904766089`.
- Official RLM commit: `72d6940142ddfb84ee6be573dc999a37e633e671`.
- Sampling: temperature 0.7, top-p 0.8, top-k 20, presence penalty 1.5,
  thinking disabled.
- Budgets and stopping rules: 20 maximum controller decisions, 1,200-second row
  timeout, 8 search documents per decision, 12,000 search-document characters,
  12,000 search-state characters.
- Query shard, answer contract and concise-answer instruction.

## Scoring

- Primary judge: the same method-blinded Gemma 4 judge contract used for the
  parent study, at temperature 0 with correctness retries disabled.
- Second judge: the same blinded GPT-5.6 Sol audit contract.
- Judges are frozen before any seed-21 score is inspected.

## Analysis, frozen before scoring

- Paired exact McNemar with `b`, `c` reported for RLM versus each of BM25,
  textual decomposition and iterative search.
- Fixed-seed percentile bootstrap, 50,000 paired-row draws, for difference
  intervals.
- Holm adjustment over the same three RLM contrasts.
- Failed or invalid executions score zero, as in the parent study.

## Pooling rule

Seed-20 and seed-21 results are **not** pooled. Seed 20 remains the primary
prospective endpoint. Seed 21 is reported separately as a rollout-variance
sensitivity.

## Reporting rule

The repeat is reported regardless of direction.

- If seed 21 reproduces the seed-20 ordering and the non-significant contrast
  set, it is reported as strengthening the route-selection conclusion.
- If seed 21 diverges, it is reported as a rollout-instability result, and the
  seed-20 conclusion is qualified accordingly in the main paper.

No stopping rule depends on an observed accuracy direction. Permitted stops are
limited to those inherited from the parent protocol: harness errors, model
endpoint instability, manifest/source/model/runner hash mismatch, or watchdog
and budget hard stops.

## Logging

Per cell: request parameters, full output, failure class, token usage, latency,
model-call count, and active-runtime dollar cost. Pod lifecycle events and
creation-to-cleanup cost are recorded. The runner deletes only pods it created.
