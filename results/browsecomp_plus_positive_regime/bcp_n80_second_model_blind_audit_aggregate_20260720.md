# BrowseComp-Plus N=80 Independent Second-Model Blind Audit

This release-safe aggregate summarizes a GPT-5.6 Sol high-reasoning adjudication. The adjudicator saw only question, reference answer, candidate response, and opaque case ID; method and primary labels were hidden. This is independent second-model validation, not human validation.

- Audited: 46/240 cells.
- Agreement with the primary Gemma 4 judge: 43/46 (93.5%).
- Primary totals (RLM/text/BM25): 54/48/39.
- Sensitivity totals (RLM/text/BM25): 55/47/38.

## Sensitivity Pairwise Results

| Pair | Difference (points) | b/c | Exact p | Holm p (3 pairs) |
|---|---:|---:|---:|---:|
| rlm vs text | 10.0 | 20/12 | 0.2153 | 0.2155 |
| rlm vs bm25 | 21.2 | 26/9 | 0.0060 | 0.0180 |
| text vs bm25 | 11.2 | 17/8 | 0.1078 | 0.2155 |

The sensitivity analysis changes only the preselected audited cells. Because the audit deliberately oversamples disagreements and malformed outputs, its raw agreement rate is diagnostic rather than a population estimate.
