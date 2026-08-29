# BrowseComp-Plus Shard-1 Fixed-N45 Replication

Status: **FROZEN BEFORE ANY MODEL OUTPUT OR SEMANTIC SCORE**  
Frozen: 2026-07-23 19:27 BST  
Study ID: `browsecomp_plus_shard1_fixed_n45_v1`

## Purpose

Test whether the standard-RLM positive regime replicates on a genuinely new,
fixed population without resuming the score-visible residual rows from the
stopped shard-0 N=59 study. This is a separate replication, not a continuation
or pooled extension of the attempted-N=49 endpoint.

## Frozen Population

- Query dataset: `Tevatron/browsecomp-plus`, revision
  `144cff8e35b5eaef7e526346aa60774a9deb941f`.
- Query shard: `data/test-00001-of-00006.parquet`, 139 encrypted rows,
  SHA-256
  `70cc3a6781693bb013c6855f231d15159222dddf826eb19947f6f85fcabccd4e`.
- Official source URL:
  `https://huggingface.co/datasets/Tevatron/browsecomp-plus/resolve/144cff8e35b5eaef7e526346aa60774a9deb941f/data/test-00001-of-00006.parquet`.
- Corpus: `Tevatron/browsecomp-plus-corpus`, revision
  `b27b02bc3e45511b8b82a13e6f90ce761df726f6`, 100,195 documents.
- Fixed N: 45.
- Selection order:
  `SHA256("RLM-AUDIT-BCP-SHARD1-FIXED-N45-v1|" + query_id)`.
- Select the first 45 rows in that order without inspecting plaintext
  questions, answers, model outputs or correctness.
- The manifest builder must prove zero query-ID and query-ID-hash overlap
  against the frozen shard-0 N=80 and N=59 manifests.
- Every row contains exactly 1,000 documents. Required gold/evidence documents
  are included. Remaining documents and presentation order use the same
  answer-blind deterministic functions as the previous replication.

The encrypted shard may be deleted after manifest and execution completion,
but the revision, URL, SHA-256, row count, restricted/public manifest hashes and
all corpus-shard hashes must remain recorded.

## Frozen Methods

All methods receive the identical question and 1,000-document pool:

1. `standard_rlm_qwen36`: official `rlms==0.1.3`, official repository commit
   `72d6940142ddfb84ee6be573dc999a37e633e671`, local REPL,
   `max_depth=1`, `max_iterations=20`, 1,200-second row timeout.
2. `bm25_qwen36`: deterministic BM25 followed by one Qwen answer call.
3. `text_decompose_qwen36`: one Qwen textual query planner, deterministic
   BM25, textual evidence workers and one Qwen finalizer; it generates and
   executes no preprocessing program.

Matched model: `Qwen/Qwen3.6-35B-A3B-FP8`, pinned revision
`95a723d08a9490559dae23d0cff1d9466213d989`, served as
`qwen36-35b-a3b-fp8` with the immutable vLLM image digest already used by the
shard-0 replication. Live checks on 2026-07-23 confirmed that the official
Hugging Face repository and OpenRouter catalog still expose this model. The
pin is retained for protocol equivalence rather than switched to another
controller.

Generation settings remain:

```text
temperature=0.7
top_p=0.8
top_k=20
presence_penalty=1.5
seed=20
enable_thinking=false
```

Base runner:
`scripts/run_browsecomp_plus_qwen36_replication_runpod.py`, pre-execution
SHA-256
`ef2cf760cf0b41d707a4feca089efe33051db6b261ab450dac4df6cd8ee6be0c`.
The shard-1 wrapper must be hash-locked after the manifest freeze and before
the first model output.

## Endpoint And Execution

- Target endpoint: all 45 rows and all three routes, 135 attempted cells.
- Execution is rank-major. Correctness, reference-answer matching and judge
  outputs remain hidden until all generation cells are locked.
- Generation failures and timeouts remain in the denominator and count
  incorrect.
- Three consecutive method errors are an infrastructure stop, not a
  statistical stop. If it fires, do not inspect scores. Repair only a proven
  infrastructure defect under a numbered amendment and resume the remaining
  frozen cells. If the endpoint cannot be completed, report attempted N and do
  not promote the run as fixed-N evidence.
- Other admissible infrastructure stops: provider-wide failure, less than
  6 GiB free local storage, orphaned-pod risk or projected new RunPod spend
  above $150. These do not permit substituting rows.
- A detached watchdog must delete only the pod created by this run. The driver
  must verify cleanup and list any remaining project pod.

## Scoring And Analysis

- Primary semantic judge: the same method-blinded Gemma 4 contract used for
  shard-0 N=49. The judge receives question, reference answer and candidate
  response, but no route name, rank, latency, cost or trace.
- Secondary: normalized exact/accepted-substring score.
- Required reporting: attempted/completed/failed counts, per-route semantic
  accuracy over fixed N=45, Wilson intervals, paired differences with 50,000
  paired-row bootstrap replicates, exact two-sided McNemar tests, Holm
  sensitivity for the two RLM contrasts, latency distributions, call/token
  counts, route-attributed active runtime and total generation-plus-judging
  cost.
- An independent second-model audit may be added only after the primary
  endpoint is frozen. It remains model sensitivity, not human validation.
- Analyze shard 1 independently. Do not pool with shard-0 N=80 or attempted
  N=49 in the primary result. Any synthesis must retain study labels and
  chronology.
- Report the result regardless of direction.

## Same-Budget Control Boundary

This protocol does not claim a same-realized-dollar nonrecursive control. Such
an arm requires a separately frozen adaptive route and paired dynamic-budget
rule that pass a no-score smoke before execution. Adding an improvised arm
after observing these outputs is prohibited.

## Provenance, Privacy And Cost

- Restricted outputs contain benchmark plaintext and remain local with mode
  0600. They must not enter the anonymous release.
- Preserve encrypted-shard, protocol, manifest, builder, wrapper, base-runner,
  official-RLM commit, model revision, image digest and corpus-shard hashes.
- Log every request, response, usage field, error, latency, official-RLM trace,
  pod event, watchdog event and cleanup action.
- Save provider/account snapshots before launch and after cleanup. Append
  listed-rate and finalized provider spend to `COST_LEDGER.md`.
- Do not print plaintext benchmark questions, answers or predictions to the
  console or any public document.

