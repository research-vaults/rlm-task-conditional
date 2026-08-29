# Parameterized Engineering-Cost Break-Even Audit

This deterministic analysis converts frozen per-case API-cost differences into the number of cases needed to amortize an assumed one-time engineering budget. The budgets are sensitivity parameters, not measured labor or total cost of ownership.

Formula: `ceil(budget / unrounded observed API savings per case)`. Displayed savings are rounded only for presentation.

| Evidence row | API savings/case | $100 budget | $1,000 budget | $10,000 budget |
|---|---:|---:|---:|---:|
| SU-150 method-lock replication | $0.022041 | 4,538 | 45,371 | 453,704 |
| VC-45 unseen-corpus replication | $0.018377 | 5,442 | 54,416 | 544,158 |

Interpretation: observed API savings alone amortize even a modest implementation budget only at nontrivial deployment volume. This qualifies the marginal-cost comparison rather than estimating engineering labor.

Boundaries: successful-completion costs only; no failed-call billing, latency valuation, maintenance, reliability valuation, or human labor estimate. SU-150 is method-lock evidence with reused windows. VC-45 is source-corpus transfer without document-level independence.
