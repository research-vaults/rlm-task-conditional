# BrowseComp-Plus Shard-1 Fixed-N45 Infrastructure Amendment 1

Status: **FROZEN BEFORE RESUMED MODEL OUTPUT**  
Frozen: 2026-07-23 21:13 BST  
Parent protocol: `BROWSECOMP_PLUS_SHARD1_FIXED_N45_REPLICATION_20260723.md`

## Trigger

The local execution session was interrupted while the score-blind
generation driver was processing rank 36. The driver process and its detached
local watchdog ended without entering the runner's cleanup block. The isolated
RunPod pod remained healthy and running. The partial summary contained 107
attempted cells: 102 successful and five route failures. The last locked cell
was rank 36 BM25; rank 36 textual decomposition and all routes for ranks 37--45
were unattempted.

No deterministic answer score, semantic-judge output, paired statistic or
route accuracy was computed or inspected. Diagnostic inspection was limited to
cell completion/error status and error strings needed to distinguish route
failures from a provider-wide infrastructure fault.

## Allowed Repair

1. Preserve the interrupted gzip byte-for-byte and record its SHA-256.
2. Recover only complete JSONL records from that stream into a separate sealed
   provenance artifact; never overwrite the interrupted bytes.
3. Verify exactly 107 unique frozen rank-route cells and identify the 28
   missing cells from the original 135-cell endpoint.
4. Reuse the same still-running pod, endpoint, pinned Qwen revision, immutable
   vLLM image, official-RLM commit, manifest, prompts, route functions,
   generation settings, row timeout and failure policy.
5. Launch a replacement pod-specific watchdog before the first resumed model
   call.
6. Write resumed cells to a new restricted gzip. Never rerun an already
   attempted cell.
7. Delete the pod after the 28 missing cells close. Record the full original
   pod creation-to-final-cleanup lifecycle cost, both episode hashes and the
   absence of any remaining project pod.
8. Build the deterministic compact endpoint only from the 107 recovered
   episode-1 cells plus 28 episode-2 cells. Require exactly 135 unique cells.

This amendment repairs infrastructure continuity only. It does not change the
population, estimand, method, budget, timeout, failure treatment or analysis.
The result remains one fixed endpoint with two disclosed execution episodes.
It may be promoted only if every cell is attempted and all integrity, cleanup
and judge gates pass.
