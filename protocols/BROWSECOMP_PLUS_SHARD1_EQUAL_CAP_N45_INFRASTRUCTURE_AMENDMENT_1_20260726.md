# BrowseComp-Plus Equal-Cap N=45 Infrastructure Amendment 1

## Status

- Frozen: 2026-07-26
- Parent protocol:
  `protocols/BROWSECOMP_PLUS_SHARD1_EQUAL_CAP_N45_20260726.md`
- Study ID: `browsecomp_plus_shard1_equal_cap_n45_v1`
- Amendment role: pre-score recovery of missing route cells only

## Interruption

The main generation episode requested ranks 2--45 under the exact frozen
runner. The local execution session was cancelled while rank 20 was active.
The driver process ended and the RunPod pod was deleted. Its `finally` block
did not finish writing cleanup and aggregate-cost fields to the episode
summary.

Before this amendment:

- no semantic judge was run;
- no deterministic or semantic correctness value was inspected;
- no prediction text was inspected;
- operational progress alone was read;
- the immutable compressed raw ledger contains exactly 72 unique cells:
  all four routes for ranks 2--19;
- 69 cells are terminal successes and three are retained terminal route
  errors;
- raw ledger SHA-256:
  `f2904f602e9467ca402793f8b58df292e96b9113c7f39fe51fa464a146126d10`;
- the provider API reports no surviving project pod.

## Authorized Recovery

Run exactly ranks 20--45 for all four frozen routes with:

- the same restricted manifest and protocol hashes;
- the same runner source and hash;
- the same Qwen repository, revision, vLLM image and generation settings;
- the same route implementations, controller caps, row timeout, answer
  contract and logging;
- no score, judge output or route-dependent retry decision.

This produces exactly 104 missing cells. The final endpoint is reconstructed
from:

1. qualification episode, rank 1, four cells;
2. interrupted main episode, ranks 2--19, 72 immutable cells;
3. recovery episode, ranks 20--45, 104 cells.

The compactor must reject duplicate cells, missing cells, query-ID mismatches,
raw-hash mismatches, incomplete recovery or a surviving project pod. All
terminal route errors remain incorrect. The two complete pods and the
interrupted pod's provider-billed amount must be reported separately where
available; if the provider does not expose the deleted pod's final billed
amount, its cost is recorded as a bounded estimate from creation and last
terminal event rather than silently omitted.

No partial episode can be promoted. Primary judging and inference remain
blocked until all 180 cells are terminal.

