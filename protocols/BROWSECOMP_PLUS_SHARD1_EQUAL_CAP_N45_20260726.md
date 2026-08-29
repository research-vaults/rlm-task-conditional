# BrowseComp-Plus Shard-1 Equal-Cap N=45 Protocol

## Status

- Freeze date: 2026-07-26
- Study ID: `browsecomp_plus_shard1_equal_cap_n45_v1`
- Chronology: frozen before manifest construction, route generation, judging or
  score inspection for the selected rows
- Role: prospective confirmatory baseline-strengthening study

This study tests whether the positive BrowseComp-Plus result survives a strong
adaptive but nonrecursive search baseline. It is not a rerun selected after
seeing model outcomes.

## Population And Selection

- Query source: encrypted
  `Tevatron/browsecomp-plus` shard `test-00001-of-00006.parquet`, revision
  `144cff8e35b5eaef7e526346aa60774a9deb941f`.
- Corpus source: `Tevatron/browsecomp-plus-corpus`, revision
  `b27b02bc3e45511b8b82a13e6f90ce761df726f6`.
- Candidate shard size: 139 queries.
- Row ordering: ascending SHA-256 under
  `RLM-AUDIT-BCP-SHARD1-FIXED-N45-v1|<query_id>`.
- Prior shard-1 study: ranks 1--45 in this deterministic ordering.
- This study: ranks 46--90 in the same ordering, yielding exactly 45 new rows.
- Required evidence documents are included in each deterministic 1,000-document
  pool. Remaining documents are deterministic distractors under the existing
  document and ordering seeds.
- The manifest builder may read encrypted benchmark fields only to construct
  hashes, required-document sets and pools. It must not read model outputs,
  judge outputs or scores.

The restricted manifest stores benchmark plaintext identifiers and must not
enter the anonymous release. The public manifest stores only hashes and
aggregate lengths.

## Routes

All four routes receive the same question, ordered 1,000-document pool and
concise-answer contract. All generation uses the same pinned answer/controller
model:

- repository: `Qwen/Qwen3.6-35B-A3B-FP8`
- revision: `95a723d08a9490559dae23d0cff1d9466213d989`
- vLLM image:
  `vllm/vllm-openai@sha256:e4f88a835143cd22aee2397a26ec6bb80b3a4a6fe0c882bcbc63822904766089`
- temperature 0.7, top-p 0.8, top-k 20, presence penalty 1.5,
  seed 20 and thinking disabled

The routes are:

1. **Standard RLM.** The pinned `rlms` v0.1.3 implementation at commit
   `72d6940142ddfb84ee6be573dc999a37e633e671`, local REPL, depth 1,
   maximum 20 root iterations and a 1,200-second row cap.
2. **Iterative lexical search agent.** A nonrecursive controller alternates
   between model-generated lexical searches over the fixed 1,000-document pool
   and returned evidence. It has at most 20 controller decisions and the same
   1,200-second row cap. Each search returns at most eight BM25-ranked documents
   after deterministic clipping. The controller can revise searches using prior
   evidence but cannot invoke a recursive or subordinate language model.
3. **Textual decomposition.** The previously frozen planner, BM25 retrieval,
   evidence-worker and finalizer implementation.
4. **BM25.** The previously frozen one-pass BM25 retrieval and answer route.

The primary resource match is between standard RLM and the iterative search
agent: same model and hardware, identical row timeout and identical maximum
controller-decision count. Their realized calls, wall time and active-runtime
cost remain outcomes and must be reported rather than forced to equality.

## Endpoints

### Primary

Model-judged semantic accuracy over all 45 rows under failure-as-incorrect:

`standard RLM - iterative lexical search agent`.

Report both directions without a one-sided superiority assumption.

### Secondary

- standard RLM versus textual decomposition;
- standard RLM versus BM25;
- route completion;
- model-call count;
- attempted-row median, p95 and maximum wall time;
- active-runtime cost and creation-to-cleanup cost;
- evidence-document recall when reconstructable from the frozen manifest;
- representative route traces chosen without changing quantitative claims.

## Judging And Inference

- Primary judge: the same method-blinded Gemma 4 semantic judging contract used
  for the completed fixed-N45 study.
- Sensitivity judge: the same method-blinded GPT-5.6 Sol contract, run only
  after all route outputs are frozen.
- Every route output is judged independently of route identity.
- Invalid, timed-out or missing route outputs score incorrect.
- Report route counts and exact rates.
- Report paired row-bootstrap 95% intervals for accuracy differences.
- Report exact two-sided McNemar tests.
- Apply Holm correction across the three declared RLM route contrasts.
- Report judge agreement and Cohen's kappa over jointly parseable successful
  outputs. Model-model agreement is a sensitivity analysis, not human criterion
  validation.

## Execution And Stop Rules

- Generate all four routes for every selected row.
- The runner logs complete request bodies, responses, hashes, usage, latency,
  model identities, revisions, errors, RLM traces, iterative-search actions,
  pod events and cleanup.
- Correctness and judge outputs remain unavailable to the generation driver.
- Permitted execution stops are operational only:
  1. three consecutive route errors;
  2. model endpoint instability;
  3. manifest, source, model or runner hash mismatch;
  4. watchdog or budget hard stop.
- No route or study may stop because of an observed accuracy direction.
- A pre-score infrastructure amendment may repair missing cells only if it
  preserves the frozen inputs, route implementation, model revision,
  generation settings and scoring contract. It must be documented before any
  score inspection.
- Partial prefixes are execution evidence only and cannot become the primary
  endpoint.

## Promotion Rule

Promote the study to the main paper only after all 180 route cells are terminal,
both judging passes are complete, all declared analyses are reproduced and the
result is interpreted regardless of direction. A null or reversal is
scientifically admissible. If the iterative route matches or exceeds RLM under
lower realized resources, the paper must narrow its positive-regime claim.

