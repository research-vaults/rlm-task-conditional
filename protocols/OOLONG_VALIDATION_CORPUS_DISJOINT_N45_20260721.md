# Oolong Validation Corpus-Disjoint N=45 Prospective Protocol

## Status and purpose

This protocol was frozen on 2026-07-21 before any paid method output on this
slice. It tests whether the established standard-unlabeled Oolong ordering
survives on the official validation split, whose upstream corpora (`spam` and
`trec_coarse`) do not occur in the official test split or in any prior project
Oolong artifact. It is an external-validity replication under a new source-
corpus boundary, not a claim of source-document disjointness: the public schema
does not expose a source-document identifier.

## Frozen data

- Dataset: `oolongbench/oolong-synth`, pinned snapshot
  `f0d59eaf0febf130664cfceb710436c8e3216b2b`.
- Split: `validation` only.
- Manifest:
  `results/oolong_validation_corpus_disjoint_n45_manifest_20260721.json`.
- Manifest SHA-256:
  `b1db482b7df676fbf3599a9eb788df56b590617b019441199a355e25a4f3b28c`.
- Frozen ID-set SHA-256:
  `eb47cd5f91a4d66ed266c28a8c549395adce60513b86a63aafc6c7bf0469fb7b`.
- Design: 45 rows; 15 each counting/timeline/user; 9 each at 8k, 16k,
  32k, 65k, and 131k declared context length; 20 context-window clusters;
  maximum three questions per context.
- Disjointness: zero row-ID, context-window-ID, and `dataset`/source-corpus
  overlap with both the official test split and all prior project Oolong
  artifacts found by the freezer. Individual source-document identity is
  `UNIDENTIFIABLE` from the official schema and must not be claimed.
- Input contract: standard unlabeled `context_window_text` plus the benchmark
  question. Gold local labels are unavailable to every evaluated method.

## Frozen methods

1. **SLM+typed**: one Gemma 4 26B-A4B semantic-labeling worker over each
   example's rows, followed by the already fixed typed deterministic operators.
   Declared Oolong task/answer-family metadata remains part of this specialized
   deployment route, exactly as in the existing SU-150/CD-45 evidence.
2. **Direct controller**: one direct Gemini 2.5 Flash call over the same
   standard context and question, no code execution or recursion.
3. **Standard RLM**: `rlms==0.1.3`, local environment, Gemini 2.5 Flash
   controller, maximum depth 1, maximum 15 iterations, per-row RLM budget 0.50,
   and 360-second wall-clock cap. Full available trajectory metadata is logged.

Gemini 2.5 Flash is retained for the primary three-way replication because it
is the controller used in SU-150 and CD-45; changing controller generation at
the same time as source corpus would confound the replication. Model freshness
is handled separately by existing Gemini 3.5 Flash and GPT-5.6 sensitivities.
Google's current official model page lists `gemini-3.5-flash` as the stable
current Flash model, and OpenRouter's live catalog on 2026-07-21 still lists
both `google/gemini-2.5-flash` and `google/gemini-3.5-flash`. A new current-
controller sensitivity may be run only after the primary replication is
complete and only if it is fully matched and budget-safe; it cannot replace or
be pooled with the primary row.

## Frozen runtime and logging

- Worker endpoint: `google/gemma-4-26b-a4b-it`; OpenRouter live-catalog context
  262,144; 2026-07-21 listed prices $0.07/M prompt and $0.34/M completion.
- Controller endpoint: `google/gemini-2.5-flash`; live-catalog context
  1,048,576; listed prices $0.30/M prompt and $2.50/M completion.
- Current-model reference: `google/gemini-3.5-flash`; stable model code
  confirmed in Google documentation; not part of the primary replication.
- Runtime packages: `rlms==0.1.3`, `openai==2.45.0`, `pyarrow==22.0.0`.
- OpenRouter account baseline immediately before calls: total purchased credits
  $390.000000; total usage $383.317258824; remaining $6.682741176.
- Every route must preserve its frozen manifest, prompt/input, raw output,
  parsed prediction, gold/scorer output, token usage where exposed, latency,
  retry/error/timeout state, model ID, run ID, and cost. Standard-RLM rows also
  preserve available generated programs and REPL outputs through the trajectory
  logger.
- Failed and timed-out rows remain in the denominator with score zero. No row
  may be replaced. Resume is allowed only for missing rows after an execution
  interruption; completed outputs are immutable.
- Paid-run order: SLM+typed, direct controller, standard RLM. Query account
  usage after each route. Stop before the next route if remaining credit cannot
  support the historical route-cost envelope plus a $0.50 reserve.

## Preflight result

The exact manifest was hydrated from the validation parquet shards. A no-call
SLM+typed dry run initially exposed four failures in the allowed-label parser
for the phrase `spam or ham (i.e., not spam)`. The grammar was narrowly repaired
to admit a parenthesis after the second declared label. The complete repeated
dry run then processed 45/45 rows with zero parser errors. This repair occurred
before any paid output and must be disclosed with the final results.

## Analysis and claim rules

- Primary endpoints: exact accuracy, mean benchmark score, captured successful-
  completion API cost, attempted rows, and errors for all three methods.
- Report by task family and context length.
- Paired exact comparisons use exact two-sided McNemar tests. Uncertainty over
  examples sharing a context uses a context-window cluster bootstrap over the
  20 frozen clusters. No subgroup p-value is promoted as confirmatory.
- The result must be integrated regardless of direction. If the prior ordering
  reverses, the paper must headline the boundary failure. If it replicates, the
  claim is limited to these two new upstream corpora and this known Oolong task
  family.
- This run does not establish natural-document prevalence, human validity,
  official SRLM/RAH parity, source-document disjointness, or a broad Oolong
  leaderboard.

