# BrowseComp+ Prospective Positive-Regime Protocol

Status: **FROZEN BEFORE ANY MODEL OUTCOME**  
Frozen: 2026-07-20 02:01 BST  
Study ID: `browsecomp_plus_positive_regime_v1`  
Purpose: add a natural, RLM-favorable, multi-document reasoning regime to the
focused evaluation-science audit. Results are reported regardless of direction.

## Scientific question

On a public task selected by the original RLM paper as strongly favorable to
standard RLM, does a current official `rlms` scaffold remain worth its cost
relative to retrieval plus a small language model and a non-programmatic
LLM+SLM decomposition route?

This is not a reproduction of the original paper's hidden random 150 IDs. It is
a new prospectively frozen evaluation using the same public benchmark, the same
1,000-document input scale, and the same semantic answer-correctness target.

## Immutable data contract

- Query dataset: `Tevatron/browsecomp-plus`, commit
  `144cff8e35b5eaef7e526346aa60774a9deb941f`.
- Corpus: `Tevatron/browsecomp-plus-corpus`, commit
  `b27b02bc3e45511b8b82a13e6f90ce761df726f6`.
- Candidate rows: first immutable parquet shard,
  `data/test-00000-of-00006.parquet`.
- Selection: sort candidates by
  `SHA256("RLM-AUDIT-BCP-v1|" + query_id)` and take the first 80 rows.
- Required documents: union of each row's gold and evidence documents.
- Distractors: corpus documents ranked independently per query by
  `SHA256("RLM-AUDIT-BCP-DOC-v1|" + query_id + "|" + docid)`; take the first
  non-required documents needed to produce exactly 1,000 unique documents.
- Presentation order: independently sorted by
  `SHA256("RLM-AUDIT-BCP-ORDER-v1|" + query_id + "|" + docid)`.
- No query text, answer, model outcome, or judge outcome may affect row or
  document selection.
- Local restricted logs may contain decrypted inputs for reproducibility. The
  anonymous/public release must contain only encrypted IDs, hashes, aggregate
  lengths, predictions, and permitted traces, respecting the benchmark's
  anti-contamination request.

## Frozen methods

All methods receive the identical 1,000-document pool and question.

1. `standard_rlm_terra_luna`
   - implementation: official `rlms==0.1.3`, source commit
     `72d6940142ddfb84ee6be573dc999a37e633e671`;
   - root: `openai/gpt-5.6-terra` via OpenRouter;
   - recursive/sub-call worker: `openai/gpt-5.6-luna` via OpenRouter;
   - `environment=local`, `max_depth=1`, `max_iterations=20`, temperature 0;
   - per-row wall timeout 1,200 seconds and maximum attempted model cost $3.00.

2. `bm25_gemma4_a4b`
   - deterministic BM25 over the 1,000 full documents using the original
     question;
   - top 12 documents, truncated only as needed to the declared 240k-token
     prompt budget;
   - answer model: `google/gemma-4-26b-a4b-it` (26B total, approximately 4B
     active parameters), temperature 0;
   - no generated code, operator program, or strong-LLM controller.

3. `bm25_terra`
   - identical BM25 rankings and top-document budget as method 2;
   - answer model: `openai/gpt-5.6-terra`, temperature 0;
   - isolates final-model strength from retrieval/preprocessing.

4. `terra_plan_gemma_workers_terra_final`
   - Terra produces up to four textual retrieval queries from the question;
   - deterministic BM25 retrieves a union of candidates;
   - Gemma 4 A4B reads fixed candidate batches and returns textual evidence
     notes; Terra finalizes from those notes and the question;
   - no generated/executed preprocessing code and no deterministic operator
     program. This is the paper's LLM+SLM alternative.

The exact prompt templates, input hashes, outputs, usage, provider, latency,
errors, and attempted cost must be recorded for every call.

## Current-model selection record

OpenRouter's model catalogue was downloaded before freezing to
`results/model_catalogs/openrouter_models_20260720T004848Z.json`. It listed:

- `openai/gpt-5.6-terra`, 1,050,000-token context;
- `openai/gpt-5.6-luna`, 1,050,000-token context;
- `google/gemma-4-26b-a4b-it`, 262,144-token context;
- `qwen/qwen3-32b`, 131,072-token context.

This avoids adding a stale Gemini 2.5 controller to the new experiment. The
existing Gemini 2.5 results remain historical evidence and are not rewritten.

## Scoring and uncertainty

- Primary: semantic correctness under the official BrowseComp+ grader prompt,
  using `qwen/qwen3-32b` at temperature 0.
- Secondary: normalized exact/substring match after punctuation and article
  normalization.
- Audit: every primary judge input/output is logged; parse failures are scored
  incorrect, not silently retried under a different prompt.
- Report method accuracy with Wilson 95% intervals, paired differences with
  paired bootstrap intervals, exact McNemar tests, completion rate, successful
  and attempted cost, latency, and accuracy/cost Pareto status.
- Method-vs-method scoring uses identical predictions and the same frozen judge.

## Two-stage execution and stop rules

### Stage A: accuracy-blind stability smoke

- First 12 selected IDs, all four methods.
- Continuation gate is based only on execution stability and cost, not
  correctness: each method must complete at least 10/12 rows; no unresolved
  input/document mismatch; no scorer parse failure above 1/12; and projected
  total OpenRouter spend must be at most $300.
- One implementation-only repair is allowed if it does not inspect correctness,
  does not alter selected IDs/documents/scorer, and is documented as protocol
  version 1.1 before rerunning the smoke.

### Stage B: powered evaluation

- Continue to all 80 frozen IDs once Stage A passes.
- No interim direction-based stopping, method dropping, prompt selection, or
  row substitution.
- Hard safety stop only if cumulative spend reaches $300, provider-wide failure
  exceeds 20 consecutive calls, or local storage falls below 8 GiB.
- If a safety stop occurs, all attempted rows and costs remain reportable and
  the result is labeled truncated rather than complete.

## Interpretation contract

- RLM winning supports a task-conditional deployment policy and supplies the
  prospectively locked positive regime requested by reviewers.
- A retrieval/SLM route matching or beating RLM supports the paper's claim that
  dynamic programmatic preprocessing is not generally necessary even on an
  RLM-favorable natural task.
- Either outcome is admissible. No task, row, prompt, model, or scorer will be
  changed to improve the preferred narrative.

## Billing baseline

OpenRouter key snapshot before paid calls: lifetime usage `$300.199385939`,
daily usage `$0.00` (2026-07-20 UTC). The key has no explicit per-key limit.
Every run records before/after snapshots and the run-level usage delta.
