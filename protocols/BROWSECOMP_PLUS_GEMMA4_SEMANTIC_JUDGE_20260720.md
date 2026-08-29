# BrowseComp+ Independent Semantic-Judge Protocol

Status: **FROZEN BEFORE JUDGE OUTPUTS**  
Frozen: 2026-07-20 07:14 BST  
Study: completed Qwen3.6 generations on frozen BrowseComp+ ranks 1--38

Generation is immutable. The independent judge is the current official
`google/gemma-4-26B-A4B-it` revision
`01e5b3ee840d3a9e0b0b493c593e85398a30ef75` (25.2B total/3.8B active,
Apache-2.0). Google identifies Gemma 4 as its latest family and recommends the
26B A4B variant as the lower-resource general model. It is served on an isolated
RunPod pod with an 8,192-token context because grader inputs are short.

Each successful generation is judged once using the official BrowseComp-style
semantic-equivalence prompt containing only question, gold answer, and
prediction; method identity is withheld and order is SHA-256 shuffled. Failed
or absent generations score incorrect without a judge call. Temperature is 0,
thinking is disabled, no correctness-based retry is allowed, and parse failures
score incorrect. All judge requests, outputs, usage, latency, model revision,
pod events, and billing are retained in restricted artifacts.

Primary accuracy for this new cell is semantic judge correctness over attempted
rows. Normalized exact and containment remain transparent secondary checks.
Judge disagreements with normalized containment are manually audited before
manuscript integration; generation is never rerun based on judging.
