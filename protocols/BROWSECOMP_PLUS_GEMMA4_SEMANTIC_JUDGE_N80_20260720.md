# BrowseComp+ N=80 Gemma 4 Semantic-Judge Protocol

Status: **FROZEN BEFORE N=80 JUDGE OUTPUTS**  
Frozen: 2026-07-20 after generation and integrity closure, before judging

Apply the parent semantic criterion and exact prompt from
`BROWSECOMP_PLUS_GEMMA4_SEMANTIC_JUDGE_20260720.md` to every successful
prediction in
`results/browsecomp_plus_positive_regime/bcp_qwen36_n80_deterministic_compact_restricted.json`.
Generation failures remain semantically incorrect and are not sent to the
judge. Judge order is the existing deterministic hash order; methods remain
hidden in the prompt. No interim judge results may alter coverage or scoring.

Frozen judge:

- model: `google/gemma-4-26B-A4B-it`;
- revision: `01e5b3ee840d3a9e0b0b493c593e85398a30ef75`;
- temperature: 0; seed: 20; thinking disabled;
- immutable vLLM image:
  `sha256:e4f88a835143cd22aee2397a26ec6bb80b3a4a6fe0c882bcbc63822904766089`;
- input coverage: 240 attempted cells, with only successful non-empty
  predictions judged;
- failures: incorrect in the final denominator;
- interpretation: the judge is independent of the generation model and method
  blinded at inference, but it is an automated model judge, not human
  validation.
