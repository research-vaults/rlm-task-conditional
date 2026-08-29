# BrowseComp+ Positive-Regime Protocol v1.2: Stage-A Stability Amendment

Status: **FROZEN BEFORE ANY CORRECTNESS OUTCOME**  
Frozen: 2026-07-20 03:58 BST  
Study ID: `browsecomp_plus_positive_regime_v1_2_runpod`  
Parent: `BROWSECOMP_PLUS_PROSPECTIVE_POSITIVE_REGIME_20260720_v1_1_RUNPOD.md`

The v1.1 rank-1 Stage-A attempt generated no final prediction for any method.
The standard-RLM request caused the one-GPU H100 service to disappear after the
readiness probe; the two later methods therefore received proxy 404 errors. No
answer correctness or judge output exists. Listed-rate cost was `$0.5554`.

This is the one Stage-A implementation-only stability amendment:

1. require an H200/H200-NVL pod rather than allowing an H100;
2. reduce the served maximum sequence from 131,072 to 65,536 tokens;
3. reduce non-RLM prompt text ceilings to 220,000 aggregate characters for
   BM25 and 50,000 characters per document in four-document worker batches;
4. preserve full-document BM25 ranking and deterministic head/tail clipping;
5. hash and head/tail-bound any REPL stdout field above 20,000 characters in
   the stored RLM trajectory, because full context remains reconstructable from
   the immutable manifest and corpus; and
6. never duplicate the full externalized context in trajectory metadata.

The frozen rows, 1,000-document pools, method definitions, prompts, generation
settings, correctness-blind continuation rule, and interpretation contract do
not change. The failed v1.1 raw artifact was hashed as
`66ec64823cb501aa6a22af9e666f2280813f8efd1b6290914938ed88c590093e`;
a compact failure record and the summary preserve the evidentiary facts. The
unbounded 3.1GB duplicate log is not a public/release artifact.

No further prompt, model, row, or infrastructure amendment is allowed based on
Stage-A performance direction. If v1.2 cannot complete stably, this prospective
cell is reported as an execution-boundary result rather than repeatedly tuned.
