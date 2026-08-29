# BrowseComp+ Positive-Regime Protocol v1.1: RunPod Infrastructure Amendment

Status: **FROZEN BEFORE ANY SUCCESSFUL MODEL OUTPUT**  
Frozen: 2026-07-20 03:24 BST  
Study ID: `browsecomp_plus_positive_regime_v1_1_runpod`  
Parent protocol: `BROWSECOMP_PLUS_PROSPECTIVE_POSITIVE_REGIME_20260720.md`

## Why this amendment is admissible

The first rank-1 infrastructure attempt under v1 returned HTTP 402 before any
model output. OpenRouter reported that the configured key could not fund the
requested output allowance. The attempt produced no prediction, no judge
outcome, no correctness signal, and a provider-usage delta of `$0.00`. Its full
error record remains in `results/browsecomp_plus_positive_regime/`; it is not
deleted or rewritten.

Vertex credentials are not present in the local authorized environment.
Continuing to retry OpenRouter would therefore be neither executable nor a
scientific decision. This one permitted infrastructure-only repair moves every
generative method to a temporary self-hosted RunPod endpoint. The frozen 80
queries, 1,000-document pools, order, answer target, scorer contract, two-stage
stability rule, and direction-independent interpretation are unchanged.

No successful model output or correctness label was inspected before freezing
this amendment.

## Current model and immutable revisions

All compared generation routes use the same current open-weight controller:

- model: `Qwen/Qwen3.6-35B-A3B-FP8`;
- Hugging Face revision:
  `95a723d08a9490559dae23d0cff1d9466213d989`;
- architecture: 35B total parameters, approximately 3B activated per token;
- native context: 262,144 tokens;
- serving: official-model-card-compatible vLLM OpenAI endpoint on a temporary
  RunPod pod;
- official source model card also declares vLLM compatibility;
- the non-FP8 reference revision is
  `995ad96eacd98c81ed38be0c5b274b04031597b0`.

Model selection was checked against the current OpenRouter catalogue and the
official Qwen Hugging Face release on 2026-07-20. Qwen3.6 supersedes the Qwen3.5
fallback considered after the OpenRouter failure. The endpoint model-list and
readiness probe must be stored before benchmark calls.

## Frozen methods

All methods receive the identical frozen question and 1,000-document pool.

1. `standard_rlm_qwen36`
   - official `rlms==0.1.3`, source commit
     `72d6940142ddfb84ee6be573dc999a37e633e671`;
   - Qwen3.6 is both root controller and `llm_query` worker;
   - local REPL, `max_depth=1`, `max_iterations=20`;
   - no hand-supplied task operator library;
   - 1,200-second row timeout.

2. `bm25_qwen36`
   - deterministic BM25 over all 1,000 documents;
   - original question only, top 12 documents under a 120k-token approximate
     input allowance;
   - Qwen3.6 answers once from the retrieved text;
   - no generated code or controller program.
   - ranking uses full documents; prompt construction deterministically clips
     any selected document above 120,000 characters by retaining equal head and
     tail spans, and caps selected text at 420,000 characters.

3. `text_decompose_qwen36`
   - Qwen3.6 produces up to four textual retrieval queries;
   - deterministic BM25 retrieves a fixed union of up to 20 documents;
   - Qwen3.6 evidence workers read fixed batches and a Qwen3.6 finalizer answers
     from textual notes;
   - no generated or executed preprocessing code.
   - worker batches use the same full-document ranking and deterministically
     clip each presented document to 90,000 head/tail-preserving characters.

Using one model across routes is intentional: it estimates the contribution of
the dynamic programmatic scaffold rather than confounding scaffold and model
strength. Because the model is a sparse 35B-total/3B-active MoE, the paper must
describe it with both numbers and must not call it simply a 3B model.

## Generation contract

- Qwen model-card instruct settings: temperature 0.7, top-p 0.8, top-k 20,
  presence penalty 1.5; fixed random seed 20 where the server accepts it.
- Standard RLM root maximum output: 8,192 tokens; subcalls: 4,096 tokens.
- Retrieval/decomposition calls: task-specific fixed maxima recorded in the
  runner and every request.
- Every request body, prompt hash, plaintext restricted input/output, usage,
  latency, endpoint/model revision, error, and method trace is stored.
- Console progress remains accuracy-blind through Stage A.

## Scoring amendment

The original `qwen/qwen3-32b` OpenRouter judge is unavailable under the exhausted
key. Predictions are first scored by normalized exact/substring match. After
all Stage-A predictions are frozen, semantic scoring uses a separately declared
self-hosted judge run; the judge model/revision, complete prompts, outputs, and
manual audit sample are recorded before semantic results enter the manuscript.
The generation stage may not be rerun based on judge direction.

## RunPod accounting and isolation

- Project pod names begin `rlm-audit-bcp-qwen36-`.
- The runner may delete only the pod ID it created and records that ID before
  model loading.
- A detached watchdog deletes that same ID if the driver dies.
- Existing pods with any other name or ID are unrelated and must not be
  modified.
- Report listed hourly price, creation-to-cleanup wall time, protocol-attributed
  active time, and provider billing when it becomes available.
- OpenRouter spend for v1.1 is fixed at `$0.00`.

## Stage A and Stage B

Stage A remains the first 12 frozen ranks. Continue only if each method
completes at least 10/12 rows, data hashes remain exact, and no infrastructure
or scorer parse failure exceeds the parent thresholds. The continuation decision
uses completion, integrity, and projected RunPod cost only, never accuracy.

If Stage A passes, continue to all 80 frozen ranks without directional stopping.
Hard stops remain provider-wide failure, less than 8 GiB local disk, or a total
RunPod cost projection above `$300`. All attempted rows remain reportable.

## Interpretation

This is a prospective positive-regime test, not an official SRLM or lambda-RLM
checkpoint comparison. An RLM win would strengthen the paper by validating a
natural regime where dynamic programs justify their cost. A retrieval or textual
route win would show that the original RLM-favorable task does not by itself
establish a scaffold advantage under a current matched controller. Either result
is admissible and must be reported.
