# BrowseComp+ Untouched-Slice Replication Protocol

Status: **FROZEN BEFORE ANY REPLICATION MODEL OUTPUT**  
Frozen: 2026-07-20 17:40 BST  
Study ID: `browsecomp_plus_untouched_replication_n59_v1`  
Parent execution contract: `BROWSECOMP_PLUS_PROSPECTIVE_POSITIVE_REGIME_20260720_v1_1_RUNPOD.md`

## Purpose

Replicate the completed BrowseComp+ N=80 finding on every untouched query in
the same pinned public query shard. This run removes the original study's
two-episode execution and post-stop score-visibility limitation. It is an
independent frozen-manifest replication, not an extension selected after
examining which remaining rows favor a method.

## Immutable sample

- Query dataset: `Tevatron/browsecomp-plus`, commit
  `144cff8e35b5eaef7e526346aa60774a9deb941f`.
- Corpus: `Tevatron/browsecomp-plus-corpus`, commit
  `b27b02bc3e45511b8b82a13e6f90ce761df726f6`.
- Candidate pool: the 139 rows in pinned shard
  `data/test-00000-of-00006.parquet`.
- Ordering: sort all 139 rows by
  `SHA256("RLM-AUDIT-BCP-v1|" + query_id)`, exactly as in the first study.
- Original-study exclusion: remove the first 80 ordered rows before any model
  call or replication score is observed.
- Replication sample: all remaining 59 rows, in their fixed order. There is no
  sampling, substitution, or direction-based stopping.
- Each row uses the same deterministic 1,000-document construction and
  presentation-order seeds as the original study. Required gold/evidence
  documents are included; distractors are selected without query text,
  answer, prediction, or score.
- The manifest generator must verify zero query-ID overlap with the original
  N=80 manifest and exact 59-row coverage.

## Methods and generation

All methods receive the identical question and 1,000-document pool. The
methods, prompts, request limits, decoding, controller, and official RLM source
are exactly those in the parent RunPod amendment:

1. `standard_rlm_qwen36`: official `rlms==0.1.3`, commit
   `72d6940142ddfb84ee6be573dc999a37e633e671`, local REPL,
   `max_depth=1`, `max_iterations=20`, 1,200-second row timeout.
2. `bm25_qwen36`: deterministic BM25, top-12 text budget, one Qwen answer.
3. `text_decompose_qwen36`: Qwen textual query planning, deterministic BM25,
   textual evidence workers, and Qwen finalization, with no generated or
   executed preprocessing program.

Matched controller: `Qwen/Qwen3.6-35B-A3B-FP8`, revision
`95a723d08a9490559dae23d0cff1d9466213d989`, served with the immutable vLLM
image digest and fixed model-card decoding settings in the parent protocol.
The official Qwen Hugging Face repository was rechecked on 2026-07-20 before
freezing; the exact pinned revision is retained for replication rather than
switching models.

## Execution and stop rule

- Run all 59 rows and all three methods in rank-major order.
- Do not score, inspect semantic correctness, or change the protocol while
  generation is active.
- Failed and timed-out cells remain in the denominator and count incorrect.
- The only permissible early stops are: three consecutive method execution
  errors, provider-wide failure, less than 8 GiB free local storage, or a
  projected RunPod cost above $300.
- A detached watchdog must delete only the pod created by this run. The driver
  must verify cleanup and report any remaining project pod.
- No implementation repair is allowed after a successful replication output.
  An infrastructure-only repair before any successful output must be frozen as
  a numbered amendment.

## Scoring and analysis

- Primary: the same method-blinded Gemma 4 semantic judge contract used for
  the completed N=80 study, with failures scored incorrect.
- Secondary: normalized exact/substring match.
- Report Wilson 95% intervals, paired differences with paired-bootstrap 95%
  intervals, exact two-sided McNemar tests, completion, latency, official-RLM
  trace counts, route-attributed active runtime, and total attempted cost.
- Analyze the 59-row replication on its own before any pooled N=139 analysis.
- A pooled N=139 estimate may be reported only as a secondary synthesis with
  study/episode labels and without erasing the original N=80 chronology.
- Report the result regardless of direction. RLM superiority over BM25 would
  independently confirm the natural positive regime; failure to replicate
  would narrow or reverse that claim.

## Cost and provenance

Before launch, save a sanitized provider snapshot, the manifest, protocol,
runner, and execution-lock hashes. Every request body, prompt/input hash,
output, usage field, error, latency, RLM trace, pod event, and cleanup action
must be retained locally. After cleanup and after billing finalization, append
actual or conservatively estimated spend to `COST_LEDGER.md`.
