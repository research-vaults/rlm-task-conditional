# BrowseComp+ Replication Semantic-Judge Protocol

Status: **FROZEN AFTER GENERATION AND BEFORE SEMANTIC-JUDGE OUTPUTS**  
Frozen: 2026-07-20 21:53 BST  
Study: `browsecomp_plus_untouched_replication_n59_v1`

The generation run reached its predeclared three-consecutive-error stability
stop at rank 49. The score-blind attempted endpoint is therefore ranks 1--49:
147 attempted cells, 137 successful predictions, and every generation failure
retained as incorrect. No correctness result was inspected before this judge
contract was frozen; only completion/error status and deterministic
exact/containment diagnostics were available.

Judge every successful prediction exactly once with the same method-blinded
contract used for the completed N=80 study:

- model: `google/gemma-4-26B-A4B-it`;
- revision: `01e5b3ee840d3a9e0b0b493c593e85398a30ef75`;
- temperature 0, seed 20, thinking disabled;
- input: question, candidate prediction, and reference answer only;
- no method label, trace, latency, cost, completion pattern, or other method
  prediction is shown to the judge;
- required output prefix: `correct: yes|no`, followed by one short reason;
- parse failures count incorrect and are not silently reprompted.

The generation compact input SHA-256 is
`abae16fb8a9dfbbce3f8c69c127112fc046dd19ebe101d74299e6de41142a2a4`.
Judge order is a fixed hash of rank and method. After judging, analyze all 49
attempted rows per method, counting ungenerated cells incorrect. The semantic
result must be reported regardless of direction and before any pooled N=139
synthesis.
