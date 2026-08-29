# T-MIXED Current-Contract N=30 Extension

- Manifest: `./results/tmixed_current_contract_n30_manifest_20260714.json`.
- Run CSV: `./results/tmixed_current_contract_n30_20260714.csv`.
- N: 30 deterministic examples; domain counts {'clinician_burnout_reduction': 15, 'diagnostic_error_reduction': 15}.
- Contract: direct Gemini versus RLM with repaired `answer['content']` JSON finalization.
- Boundary: this uses a stable generator extension, not the historical salted Round 22 generator.

| Method | Correct/N | Accuracy | Cost USD | Errors | Finalized |
|---|---:|---:|---:|---:|---:|
| direct_gemini | 28/30 | 93.3% | $0.022309 | 0 | 30/30 |
| rlm_content_json_contract | 18/30 | 60.0% | $0.108923 | 2 | 28/30 |

Paired direct-vs-content-RLM exact: b=12, c=2, two-sided exact p=0.0129395.
Cost ratio content-RLM/direct: 4.88x.
