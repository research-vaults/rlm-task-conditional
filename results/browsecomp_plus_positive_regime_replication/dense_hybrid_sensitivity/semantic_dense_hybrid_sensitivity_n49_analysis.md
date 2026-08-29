# BrowseComp N=49 Learned-Retrieval Sensitivity

**Evidence tier:** post-hoc sensitivity only. The original N=49 outcomes and scores were visible before this protocol was written. Rank 1 was a bounded preflight; ranks 2--49 used the unchanged protocol and runner hashes.

| Route | Semantic accuracy (Wilson 95%) | Complete | Median wall time | Route-attributed cost |
|---|---:|---:|---:|---:|
| BM25-64 + Qwen3-Embedding-8B rerank | 20/49 = 40.8% (28.2--54.8) | 43 | 3.4s | $0.516 |
| BM25 replay | 22/49 = 44.9% (31.9--58.7) | 47 | 4.9s | $0.509 |
| Standard RLM (original N=49) | 35/49 = 71.4% (57.6--82.2) | 43 | 69.9s | $15.046 |
| BM25 (original N=49) | 21/49 = 42.9% (30.0--56.7) | 46 | 4.0s | $0.321 |
| Text decomposition (original N=49) | 21/49 = 42.9% (30.0--56.7) | 48 | 29.2s | $1.884 |

## Paired descriptive comparisons

| Comparison | Difference | Left/right only | Bootstrap 95% | McNemar p |
|---|---:|---:|---:|---:|
| BM25-64 + Qwen3-Embedding-8B rerank vs BM25 replay | -4.1 pp | 4/6 | -16.3 to +8.2 pp | 0.7539 |
| BM25-64 + Qwen3-Embedding-8B rerank vs Standard RLM (original N=49) | -30.6 pp | 4/19 | -46.9 to -14.3 pp | 0.0026 |
| BM25-64 + Qwen3-Embedding-8B rerank vs BM25 (original N=49) | -2.0 pp | 4/5 | -14.3 to +10.2 pp | 1.0000 |
| BM25-64 + Qwen3-Embedding-8B rerank vs Text decomposition (original N=49) | -2.0 pp | 5/6 | -14.3 to +10.2 pp | 1.0000 |
| BM25 replay vs BM25 (original N=49) | +2.0 pp | 1/0 | +0.0 to +6.1 pp | 1.0000 |

Required-document recall is an outcome-aware diagnostic computed after the run; it is not a selection criterion or a confirmatory endpoint.

The learned-retriever row is not promoted into the primary evidence. Its role is to test whether the paper's decision boundary survives a stronger, reproducible, nonrecursive retrieval alternative under the same answer model and context fitter.
