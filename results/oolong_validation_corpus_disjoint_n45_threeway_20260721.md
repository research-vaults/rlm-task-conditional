# Oolong Validation Corpus-Disjoint N=45 Three-Way Result

This replication was pre-output locked after one outcome-blind no-call parser grammar repair and uses the official Oolong validation split. Its `spam` and `trec_coarse` source corpora do not occur in the official test split or any prior project Oolong artifact. The public schema does not expose source-document identity, so this is corpus-disjoint rather than proven document-disjoint.

| Method | Exact | Mean score | Captured cost | Cost / exact | Errors |
|---|---:|---:|---:|---:|---:|
| SLM+typed | 35/45 (77.8%) | 82.1% | $0.312 | $0.009 | 0 |
| Standard RLM | 28/45 (62.2%) | 65.6% | $1.139 | $0.041 | 0 |
| Direct Gemini | 23/45 (51.1%) | 55.2% | $0.658 | $0.029 | 0 |

## Task families

| Group | SLM+typed | Standard RLM | Direct |
|---|---:|---:|---:|
| counting | 10/15 | 6/15 | 9/15 |
| timeline | 14/15 | 9/15 | 8/15 |
| user | 11/15 | 13/15 | 6/15 |

## Paired and clustered uncertainty

- slm_vs_rlm: b=10, c=3, exact two-sided p=0.0922852, three-pair Holm p=0.18457.
- slm_vs_direct: b=14, c=2, exact two-sided p=0.00418091, three-pair Holm p=0.0125427.
- direct_vs_rlm: b=8, c=13, exact two-sided p=0.38331, three-pair Holm p=0.38331.
- SLM+typed minus RLM exact-rate cluster bootstrap: 0.0% to 31.1% over 20 context windows (100,000 draws).
- Captured-cost ratio: RLM/SLM+typed 3.65x. Account delta $2.304960; retained successful-row costs $2.109802; aborted/partial overhead $0.195158.

## Interpretation

The specialized route transfers to two unseen upstream corpora and remains the best overall accuracy/cost operating point. Standard RLM is not uniformly weak: it reaches 13/15 on user tasks and beats direct prompting overall. The mechanism boundary therefore persists: semantic local interpretation plus deterministic aggregation is strongest when the task family is known, while recursive code execution helps relative to direct prompting on some compositional user-centric questions but does not erase specialization or cost overhead.
