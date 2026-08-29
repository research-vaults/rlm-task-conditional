# BrowseComp+ Positive-Regime Protocol v1.4: Transparent N=80 Resumption

Status: **FROZEN BEFORE RESUMED MODEL OUTPUTS**  
Frozen: 2026-07-20 07:46 BST  
Study ID: `browsecomp_plus_positive_regime_v1_4_resumption`  
Parent: `BROWSECOMP_PLUS_PROSPECTIVE_POSITIVE_REGIME_20260720_v1_3_STAGEB_STORAGE.md`

## Why a resumption amendment is necessary

The parent protocol fixed an N=80 manifest, row order, three matched-controller
routes, prompts, model revision, decoding settings, scoring plan, and
non-directional completion rule. The first execution was nevertheless stopped
at the user's request after ranks 1--37 were fully paired and rank 38 was
partial. That stop occurred outside the protocol's hard stops. Semantic scoring
was performed after the stop, so resuming now cannot retroactively make the
N=37 endpoint prospectively locked.

This amendment preserves the N=37 analysis as a protocol-deviating,
user-truncated paired-prefix result and separately completes the *originally
planned* N=80 endpoint. The interruption, post-stop scoring, and resumption are
disclosed. The N=80 result may be described as completion of a previously
frozen manifest after an operational interruption, but not as an uninterrupted
preregistered or prospectively locked run.

## Frozen continuation contract

1. Run all three parent-protocol methods on ranks 38--80:
   `standard_rlm_qwen36`, `bm25_qwen36`, and `text_decompose_qwen36`.
2. Re-run all three methods at rank 38. The earlier partial rank-38 BM25 output
   remains in the interruption archive and is excluded from the completed N=80
   endpoint. This prevents a mixed-deployment row.
3. Combine parent Stage A ranks 1--12, parent Stage B ranks 13--37, and resumed
   ranks 38--80. Failed generations remain incorrect. No output from ranks
   38--80 may be inspected or scored before all methods finish or a parent hard
   safety stop fires.
4. Continue regardless of whether the final direction favors RLM, textual
   decomposition, or BM25. No accuracy-based stop, sample-size change, method
   change, or row exclusion is permitted.
5. Preserve the parent scorer and semantic-judge contract. Judge the completed
   N=80 only after generation closes. Any project-side case audit must have a
   row-level artifact and must not be called independent human validation.
6. Preserve all parent generation parameters, prompts, timeouts, document
   pools, corpus, manifest order, `rlms` commit, and Qwen model revision.
7. The only runner change is replacing mutable
   `vllm/vllm-openai:latest` with its immutable current multi-architecture
   digest `sha256:e4f88a835143cd22aee2397a26ec6bb80b3a4a6fe0c882bcbc63822904766089`.
   Its amd64 child image was created 2026-07-12, before the original July 20
   execution, and reports vLLM version `0.25.1` and revision
   `752a3a504485790a2e8491cacbb35c137339ad34`. This is an infrastructure
   reproducibility repair, not a model or method change.
8. Keep the parent RunPod hard ceiling of `$300`, 8 GiB local-disk floor, pod
   ownership rule, watchdog, row timeout, and cleanup requirements.

## Frozen identities

- Restricted manifest SHA-256:
  `42acf2e988276be931946539f96f3e2b7026acae4c99612390e946223e20e0c9`.
- Qwen repository/revision:
  `Qwen/Qwen3.6-35B-A3B-FP8@95a723d08a9490559dae23d0cff1d9466213d989`.
- Official `rlms` commit:
  `72d6940142ddfb84ee6be573dc999a37e633e671`.
- Parent Stage-A gzip SHA-256:
  `6cf62a7542b878bb10ff62099b9b616965e96a99a6e16fa1633f2ccc6f1ca563`.
- Parent interrupted Stage-B gzip SHA-256:
  `608abb1a60b6ada9dc5f1b6b98e9e7e013a69ed060f132b08e9799fb96731c96`.
- Amended runner SHA-256:
  `eb32dd628e86f3237680a063bce04d954faafe90e4824d8fc7563131430880cd`.

## Interpretation

The completed endpoint improves precision and closes the planned public-task
sample. It does not erase the interruption or post-stop visibility of ranks
1--37. The paper must report both facts and retain the earlier N=37 artifact.
Any inference at N=80 is conditional on the fixed manifest and two execution
episodes, with deployment episode available as a sensitivity factor.
