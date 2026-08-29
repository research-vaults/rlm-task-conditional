# Official RLM-Qwen3-30B-A3B CD-15 Same-Contract Diagnostic

## Result

| Method | Exact | Mean Oolong score | Cost role |
|---|---:|---:|---|
| Official RLM-Qwen3-30B-A3B | 10/15 (66.7%) | 70.4% | $1.719 protocol-accounted RunPod compute |
| Standard RLM/Gemini stored CD-15 | 10/15 | 70.4% | Stored same-row baseline |
| Direct Gemini stored CD-15 | 9/15 | 65.0% | Stored same-row baseline |
| SLM+typed stored CD-15 | 15/15 | 100.0% | Stored same-row baseline |

The official policy completed 14/15 rows and generated 70
code blocks across 70 iterations. The final 262k-token-window
row is scored as a timeout under the predeclared 1,500-second outer cap.

## Paired exact tests

| Comparison (official first) | Official-only | Comparator-only | Two-sided exact p |
|---|---:|---:|---:|
| vs SLM+typed | 0 | 5 | 0.0625 |
| vs direct Gemini | 5 | 4 | 1.0000 |
| vs standard RLM/Gemini | 4 | 4 | 1.0000 |

## Interpretation

This closes the narrowest version of the official-policy omission: the model is an official post-trained
RLM policy and was run through the authors' current canonical harness and published Oolong settings on the
same frozen input/scorer contract. It does not establish parity with SRLM, lambda-RLM, or RAH. On this
diagnostic it improves numerically over direct Gemini but remains below SLM+typed and does not reverse the
task-conditional deployment recommendation.

## Cost and incident boundary

Protocol-accounted compute, including cold start and the final timeout cap, is $1.719.
Actual RunPod billing was $12.510; the difference is an infrastructure teardown overrun after
the local process died, not model inference required by the protocol. OpenRouter spend was $0.00.
