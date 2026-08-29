# BrowseComp N=49 Main-Paper Sensitivities

This deterministic audit uses the frozen compact execution ledger, the complete primary-judge ledger and the canonical route-cost analysis. It makes no model calls.

## Terminal-rank sensitivity

| Comparison | Attempted N=49 | Fully generated prefix N=48 |
|---|---|---|
| Standard RLM vs Text decomposition | 28.6 pp; b/c=17/3; p=0.0026 | 29.2 pp; b/c=17/3; p=0.0026 |
| Standard RLM vs BM25 | 28.6 pp; b/c=19/5; p=0.0066 | 29.2 pp; b/c=19/5; p=0.0066 |

The terminal rank is incorrect for all routes. Removing it leaves every paired discordance and exact McNemar p-value unchanged. This is a descriptive stability check, not stopping-adjusted population inference.

## Route-dollar utility sensitivity

| Alternative | Net extra RLM correct | Incremental RLM route cost | Dollars per net extra correct |
|---|---:|---:|---:|
| Text decomposition | 14 | $13.161 | $0.940 |
| BM25 | 14 | $14.725 | $1.052 |

These thresholds value only route-attributed active-runtime dollars. They omit latency value, engineering, maintenance, reliability and uncaptured failed-call billing. No same-budget nonrecursive route is present, so they describe the observed tradeoff rather than attributing it uniquely to recursion.
