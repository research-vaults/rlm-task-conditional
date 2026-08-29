# BrowseComp+ Positive-Regime Protocol v1.3: Stage-B Storage Amendment

Status: **FROZEN BEFORE STAGE-B MODEL OUTPUTS**  
Frozen: 2026-07-20 05:37 BST  
Study ID: `browsecomp_plus_positive_regime_v1_3_stageb`  
Parent: `BROWSECOMP_PLUS_PROSPECTIVE_POSITIVE_REGIME_20260720_v1_2_STABILITY_AMENDMENT.md`

Stage A completed 34/36 method cells: standard RLM 10/12, BM25 12/12,
and textual decomposition 12/12. It therefore passed the predeclared
completion gate. Creation-to-cleanup time was 5,287.6 seconds and the listed
rate estimate was `$6.4479`; projected full-study cost is below `$50`, well
under the `$300` ceiling. The decision to continue is based only on these
stability and cost facts.

The uncompressed restricted Stage-A log was 846MB because complete prompt I/O
is retained. To keep Stage B above the 8GiB disk safety threshold, ranks 13--80
are written as concatenated lossless gzip JSONL members. This changes only the
storage container. Decompressed JSON records, model, prompts, methods,
generation settings, timeouts, rows, document pools, and interpretation are
identical to v1.2. The runner still flushes and closes each record before the
next method call so interrupted runs remain recoverable.

No Stage-A accuracy result is used to alter or stop Stage B. Stage-A semantic
scoring may proceed in parallel for analysis, but ranks 13--80 must continue
unless a parent-protocol hard safety stop occurs.
