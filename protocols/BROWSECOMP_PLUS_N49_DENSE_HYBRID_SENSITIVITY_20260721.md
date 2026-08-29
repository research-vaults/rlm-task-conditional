# BrowseComp+ Attempted-N=49 Learned-Retrieval Sensitivity

## Evidence role and chronology

This is a **post-hoc sensitivity**, not a prospective or confirmatory endpoint.
The attempted-N=49 BrowseComp+ route outputs and primary semantic labels were
already visible before this protocol was written. The frozen 49-row endpoint,
questions, 1,000-document pools, answers, scorer, and failure-as-incorrect rule
remain unchanged. The purpose is narrow: test whether the reported RLM
advantage over BM25 and textual decomposition is explained by the absence of a
learned nonrecursive retriever.

The runner, retrieval settings, controller settings, stop rules, and analysis
below must be hash-bound before the first embedding or answer-model call. No
retrieval parameter may be selected from answer correctness or required-document
IDs. Results are integrated regardless of direction and remain sensitivity
evidence because the target rows and prior route scores are already known.

## Fixed rows and contracts

- Restricted source manifest:
  `results/browsecomp_plus_positive_regime_replication/manifest_n59_restricted.json`.
- Source manifest SHA-256:
  `3aa19bb692f37d567a8983396ae950a11aca5b6ba5664e9b2c05160a0df6fea2`.
- Endpoint: ranks 1--49, matching the valid score-blind attempted endpoint.
- Input: the same question and exactly the same ordered pool of 1,000 supplied
  documents for each rank.
- Output: one concise answer string.
- Failure handling: every attempted row remains in the denominator; generation,
  retrieval, timeout, or parsing failures score incorrect.
- Gold answers and required-document IDs are retained for later scoring/audit
  but are not passed to retrieval or generation and may not tune this run.

## Fixed methods

### Learned hybrid retrieval

1. Generate a candidate set with the project's existing deterministic BM25
   implementation using the unmodified question; retain the top 64 document
   indices.
2. Encode the question with `qwen/qwen3-embedding-8b` and the retrieval
   instruction `Given a web research question, retrieve documents that contain
   evidence needed to answer it.`
3. Encode each candidate document independently. For embedding only, represent
   a document by a deterministic 12,000-character head/tail clip: 6,000 leading
   and 6,000 trailing characters with an explicit clipping marker. This keeps
   each input well inside the model's 32,000-token catalog limit.
4. L2-normalize vectors and rank candidates by cosine similarity to the query.
5. Feed documents to the answer controller in dense-rank order through the
   existing answer-context fitter: at most 12 documents, at most 220,000 total
   characters, and at most 80,000 characters per selected document using the
   same deterministic head/tail clipping rule as the released BM25 route.

The embedding endpoint is OpenRouter's live
`qwen/qwen3-embedding-8b`. The catalog was checked on 2026-07-21: 32,000-token
context and `$0.01` per million input tokens. Qwen's public model documentation
identifies the Qwen3 embedding family as instruction-aware dual encoders with
32K sequence length. The model is chosen as an established, reproducible open
retriever, not claimed to be the newest embedding model; Google's newer Gemini
Embedding 2 was also verified in the live catalog but is not needed for this
single controlled sensitivity.

### Matched BM25 replay

Replay the released deterministic BM25 selection and answer prompt on the same
new Qwen3.6 deployment. This is a deployment-drift control. It does not replace
the original score-blind BM25 route.

## Fixed answer controller

- Repository: `Qwen/Qwen3.6-35B-A3B-FP8`.
- Revision: `95a723d08a9490559dae23d0cff1d9466213d989`.
- Served model name: `qwen36-35b-a3b-fp8`.
- Runtime image:
  `vllm/vllm-openai@sha256:e4f88a835143cd22aee2397a26ec6bb80b3a4a6fe0c882bcbc63822904766089`.
- Generation: temperature 0.7, top-p 0.8, top-k 20, presence penalty 1.5,
  seed 20, thinking disabled, maximum 4,096 output tokens.
- Answer prompt and context formatting are exactly the released BM25 route's
  `answer_prompt` and `format_context` helpers.

## Stop rules and logging

- Preflight: endpoint readiness plus rank 1 for both methods. Continue only if
  both produce parseable answer strings and all embedding responses have the
  expected dimension.
- Per-method row timeout: 900 seconds. Three consecutive method failures trigger
  a stability stop. Completed cells are immutable; a resume may fill only
  missing cells using the same runner hash and protocol hash.
- Pod watchdog: 21,600 seconds. The driver deletes only the pod it creates.
- Preserve every query, answer, document-pool hash, selected document ID,
  retrieval score, embedding request hash, answer request/response, usage,
  latency, error, model/revision, runner/protocol hash, provider snapshot,
  creation/cleanup event, and protocol/listed cost.
- Capture OpenRouter usage immediately before and after embeddings and capture
  RunPod creation-to-cleanup listed cost plus a later billing export.

## Evaluation and allowed claims

- Use the same blinded Gemma 4 semantic-judge prompt and parsing contract as the
  N=49 primary analysis. A later second-judge sensitivity may be added but is
  not human validation.
- Report attempted N, completed N, semantic correctness, route cost, latency,
  retrieval coverage of required documents as a **post-output diagnostic**, and
  paired discordance against the stored RLM/BM25/text routes.
- Paired intervals and exact tests may be shown as descriptive sensitivities;
  they are not promoted as new confirmatory tests because this baseline was
  motivated after seeing the N=49 results.
- Allowed conclusion: whether a fixed learned hybrid retriever materially
  narrows, closes, or reverses the observed RLM advantage on these 49 rows.
- Forbidden conclusions: prospective validation, benchmark-wide dense-retrieval
  superiority, family-wide RLM parity, or human validation.

