# LB2 >500k Standard-RLM Same-Row Smoke Analysis

This analysis compares the bounded standard-`rlms` smoke against the existing retrieval/rerank outputs on the exact same six rows from the balanced LongBench-v2 `>500k` manifest.

## Summary

| Method | N | Correct | Accuracy | Total cost | Cost/example | Errors |
|---|---:|---:|---:|---:|---:|---:|
| Standard RLM | 6 | 1 | 16.7% | `$0.469751` | `$0.078292` | 1 |
| BM25+Gemma vote | 6 | 1 | 16.7% | `$0.006484` | `$0.001081` | 0 |
| BM25+Gemini vote | 6 | 2 | 33.3% | `$0.028368` | `$0.004728` | 0 |
| BM25+Gemma rerank+Gemini | 6 | 2 | 33.3% | `$0.032598` | `$0.005433` | 0 |

## Paired Rows

| Domain | Gold | RLM | BM25+Gemma | BM25+Gemini | Rerank+Gemini |
|---|---:|---|---|---|---|
| Code Repository Understanding | D | C (MISS) | C (MISS) | B (MISS) | B (MISS) |
| Long In-context Learning | C | ? (MISS timeout) | A (MISS) | D (MISS) | D (MISS) |
| Long Structured Data Understanding | B | A (MISS) | ? (MISS) | B (OK) | B (OK) |
| Long-dialogue History Understanding | B | D (MISS) | A (MISS) | D (MISS) | D (MISS) |
| Multi-Document QA | C | A (MISS) | C (OK) | D (MISS) | D (MISS) |
| Single-Document QA | C | C (OK) | A (MISS) | C (OK) | C (OK) |

## Decision

- Scale standard RLM to N=30 now: `False`.
- Reason: The bounded same-row smoke solved 1/6 with one 480s timeout. The best retrieval route on the same six rows is bm25_gemini_vote with 2/6 at $0.028368, versus standard RLM 1/6 at $0.469751. This does not justify a blind N=30 standard-RLM scale-up before submission.
- Paper role: Supplement-level feasibility/stop-rule evidence for the over-window positive-regime section; not a full LongBench-v2 ranking and not an SRLM/lambda-RLM reproduction.
