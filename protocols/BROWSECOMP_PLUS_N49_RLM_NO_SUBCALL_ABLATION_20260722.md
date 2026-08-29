# BrowseComp-Plus N=49 RLM No-Subcall Ablation Protocol

Status: frozen before any output from this route  
Freeze date: 2026-07-22 05:28 BST  
Study ID: `browsecomp_plus_n49_rlm_no_subcall_ablation_v1`

## Question

On the exact attempted-N=49 BrowseComp-Plus replication rows, how much of the
released standard RLM route's result remains when the root controller retains
its programmatic REPL interaction but cannot issue any submodel call?

This is a matched-scaffold component ablation. It is not official SRLM, not an
implementation of SRLM's uncertainty-guided trajectory selection and not a
prospective dataset replication. The row outcomes for the existing methods
were already known when this control was designed. Inference for this new arm
is therefore descriptive and paired on the same rows.

## Frozen Inputs

- Restricted manifest:
  `results/browsecomp_plus_positive_regime_replication/manifest_n59_restricted.json`
- Manifest SHA-256:
  `3aa19bb692f37d567a8983396ae950a11aca5b6ba5664e9b2c05160a0df6fea2`
- Rows: ranks 1--49 inclusive, preserving the prior attempted-prefix
  denominator and terminal all-route failure.
- Documents: the same ordered 1,000-document pool per row.
- Questions and reference answers: the same pinned BrowseComp-Plus records.
- Existing comparator arm: `standard_rlm_qwen36` from the frozen replication.

## Frozen Controller and Runtime

- Model: `Qwen/Qwen3.6-35B-A3B-FP8`
- Revision: `95a723d08a9490559dae23d0cff1d9466213d989`
- Served name: `qwen36-35b-a3b-fp8`
- Pinned vLLM image:
  `vllm/vllm-openai@sha256:e4f88a835143cd22aee2397a26ec6bb80b3a4a6fe0c882bcbc63822904766089`
- Pinned released RLM commit:
  `72d6940142ddfb84ee6be573dc999a37e633e671`
- Root sampling: temperature 0.7, top-p 0.8, top-k 20, presence penalty
  1.5, seed 20 and thinking disabled.
- Maximum root completion tokens: 8,192 per turn.
- Maximum root iterations: 20.
- Per-row wall-clock cap: 1,200 seconds.
- REPL: released local environment with identical context formatting and root
  answer contract.

The model was checked against the live official Qwen model card before this
run. The pinned Qwen3.6 revision is retained because controller matching is the
estimand; substituting a newer or larger model would confound the ablation.

## Intervention

The released RLM root loop and local REPL remain active. `llm_query`,
`llm_query_batched`, `rlm_query` and `rlm_query_batched` are replaced inside
the per-row REPL by fail-closed functions that record the attempted call and
return an explicit disabled-tool error without issuing a model request. The
system and root prompts truthfully state that submodel calls are unavailable.
All other Python/REPL operations remain available.

This intervention changes only the subcall affordance and the prompt clauses
needed to describe that affordance. It does not claim exact realized-cost
matching. It matches the standard arm's controller, rows, corpus, root-turn
cap, iteration cap and row-time cap. Realized active runtime, completion and
all attempted disabled calls must be reported.

## Execution and Failure Rules

1. Generation is correctness-blind. The runner does not compute or print
   correctness while the route is executing.
2. Every rank 1--49 is attempted exactly once unless an infrastructure failure
   prevents continuation.
3. A timeout, exception, empty answer or parse failure counts as incorrect.
4. Disabled subcall attempts are not infrastructure failures. They are logged
   and the root controller may recover using Python/REPL operations.
5. Three consecutive infrastructure-level row failures trigger a stability
   stop. Any unattempted rows remain incorrect in the attempted-N=49 analysis.
6. The pod must be deleted in a `finally` block and a watchdog must independently
   delete it if the driver disappears.

## Scoring and Analysis

- Primary judge: the same pinned method-blinded Gemma 4 26B-A4B judge prompt,
  model revision and semantic criterion used for the existing N=49 arms.
- Denominator: attempted N=49, with failures incorrect.
- Primary contrast: no-subcall arm versus frozen standard RLM on the same 49
  rows.
- Report: exact counts, Wilson intervals, paired row-bootstrap difference
  interval with 50,000 fixed-seed draws, exact McNemar discordances and p-value,
  completion, latency distribution, active-runtime cost, root iterations,
  disabled-subcall attempts and trace examples.
- Sensitivity: the existing blinded GPT-5.6 judge may be applied only after the
  primary Gemma judgment and must remain labeled a second-model sensitivity.

## Claim Gate

- If no-subcall matches or exceeds standard RLM, the paper may state that
  programmatic search rather than submodel calls explains the observed route
  utility on this retrospective slice.
- If standard RLM wins, the paper may state that submodel calls are associated
  with the gain under matched caps. It must not claim recursion-only causality
  because realized inference spend can differ.
- Any result must retain the retrospective-design limitation and may not be
  called an official SRLM comparison, a prospective replication or an exact
  same-dollar test.
