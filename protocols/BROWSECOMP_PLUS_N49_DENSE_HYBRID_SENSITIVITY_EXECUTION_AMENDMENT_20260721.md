# Execution Amendment: Parallel Embedding Scheduling

## Scope and chronology

This amendment applies only to the post-hoc BrowseComp-Plus N=49 learned-
retrieval sensitivity defined in
`BROWSECOMP_PLUS_N49_DENSE_HYBRID_SENSITIVITY_20260721.md`.

The original runner completed a bounded rank-1 generation preflight and wrote
retrieval plans for ranks 1--4. Before semantic judging and before promoting any
result into the manuscript, the rank-5 embedding preparation was interrupted.
OpenRouter embedding latency made the serial scheduler unnecessarily slow.
The existing plans and completed generation cells remain immutable.

## Permitted change

The remaining independent embedding requests may be scheduled concurrently:

- at most two query ranks are prepared concurrently;
- within a rank, the one query request and four 16-document requests may run
  concurrently;
- each request retains the same model, inputs, character clipping, batch size,
  query instruction, and float encoding;
- each successful response retains its provider response ID, usage, latency,
  input hashes, dimensions, and request hash;
- transient request failures may be retried up to three times and every failed
  attempt is recorded in the plan audit.

The scheduler does **not** change BM25 candidate generation, cosine scoring,
tie breaking, selected-document fitting, answer prompts, generation model,
generation settings, judge, denominator, or evidence tier.

## Evidence boundary

This remains a post-hoc sensitivity designed after the original N=49 outcomes
and scores were visible. Scheduler parallelism cannot promote it to
confirmatory evidence. Rank 1 is a preflight generation episode; the resumed
answer-generation episode must preserve all rows and failures. The analysis
must disclose the interrupted serial preparation and this amendment.

