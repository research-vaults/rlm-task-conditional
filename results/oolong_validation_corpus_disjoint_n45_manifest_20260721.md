# Oolong Validation Corpus-Disjoint N=45 Freeze

- Manifest: `results/oolong_validation_corpus_disjoint_n45_manifest_20260721.json`
- Pinned revision: `f0d59eaf0febf130664cfceb710436c8e3216b2b`
- N: **45**
- Groups: `{'counting': 15, 'timeline': 15, 'user': 15}`
- Lengths: `{'131072': 9, '16384': 9, '32768': 9, '65536': 9, '8192': 9}`
- Source corpora: `{'spam': 27, 'trec_coarse': 18}`
- Unique context windows: **20**
- Maximum questions per context: **3**

## Disjointness

The official validation split uses only `spam` and `trec_coarse`; the test split and every prior project Oolong manifest with an explicit corpus field use different corpora. Validation and test IDs and context-window IDs are also disjoint, and no validation ID/window/corpus appears in prior project Oolong artifacts. This supports a **source-corpus-disjoint** claim.

The official schema has no source-document identifier. This artifact therefore does **not** claim independently verified source-document disjointness within a corpus.

## Cell Availability and Selection

| Cell | Candidate rows | Candidate contexts | Selected |
|---|---:|---:|---:|
| `counting/8192` | 52 | 4 | 3 |
| `counting/16384` | 42 | 4 | 3 |
| `counting/32768` | 49 | 4 | 3 |
| `counting/65536` | 52 | 4 | 3 |
| `counting/131072` | 43 | 4 | 3 |
| `timeline/8192` | 22 | 2 | 3 |
| `timeline/16384` | 23 | 2 | 3 |
| `timeline/32768` | 22 | 2 | 3 |
| `timeline/65536` | 25 | 2 | 3 |
| `timeline/131072` | 23 | 2 | 3 |
| `user/8192` | 26 | 4 | 3 |
| `user/16384` | 35 | 4 | 3 |
| `user/32768` | 29 | 4 | 3 |
| `user/65536` | 23 | 4 | 3 |
| `user/131072` | 34 | 4 | 3 |

## Execution Boundary

This manifest was frozen before any method output on these rows. Model execution may begin only after hashes and overlap checks pass. All attempted rows, failures, costs, and stop events must remain in the denominator.
