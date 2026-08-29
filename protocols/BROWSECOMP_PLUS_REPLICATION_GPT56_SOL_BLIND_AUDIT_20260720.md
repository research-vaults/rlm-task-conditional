# BrowseComp+ Replication GPT-5.6 Sol Blind Audit

Status: **FROZEN BEFORE SECOND-MODEL OUTPUTS**  
Frozen: 2026-07-20 22:05 BST  
Evidence role: independent second-model sensitivity, not human validation

Audit all 137 successful predictions from the attempted-N=49 untouched-slice
replication. Selection is exhaustive over successful generations and therefore
does not depend on the primary Gemma 4 label, containment score, method, or
aggregate result. The ten failed generation cells remain incorrect under both
judges.

## Model and blinding

- Model: `openai/gpt-5.6-sol` through OpenRouter.
- Reasoning effort: high.
- Live model-catalogue record:
  `results/browsecomp_plus_positive_regime_replication/openrouter_gpt56_sol_catalog_pre_second_judge.json`.
- The model was verified against OpenAI's official model documentation on
  2026-07-20 as the flagship GPT-5.6 tier.
- Each case contains only an opaque case ID, question, reference answer, and
  one candidate response. It excludes method, rank, primary label,
  containment label, other predictions, cost, latency, and paper claims.
- Cases are deterministically hash-ordered and processed in fixed batches of
  16. Transport failures may retry the identical request once; parse or label
  failures are not correctness-reprompted and count incorrect.

The semantic rule matches the primary judge: accept harmless wording, aliases,
and additional noncontradictory detail; reject a different entity/value,
contradiction, ambiguity, refusal, or non-answer. Every call stores its exact
request, request hash, raw output, response hash, usage, provider metadata,
latency, parsed labels, and estimated provider cost. Report full-case agreement,
method totals under each judge, paired sensitivity, and all disagreements.
