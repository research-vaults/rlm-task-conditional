# BrowseComp-Plus N=49 RLM No-Subcall Ablation

Retrospective matched-row, matched-cap component ablation. This is not official SRLM or exact realized-dollar matching.

| Route | Complete | Semantic accuracy | Wilson 95% | Median / max wall | Active-runtime cost |
|---|---:|---:|---:|---:|---:|
| RLM no subcalls | 24/49 | 20/49 = 40.8% (83.3% completed-row) | 28.2--54.8% | 20.1s / 1200.4s | $4.327 |
| Standard RLM | 43/49 | 35/49 = 71.4% (81.4% completed-row) | 57.6--82.2% | 69.9s / 2694.4s | $15.046 |

Predeclared N=49 failure-policy endpoint, no-subcall minus standard: -30.6 points; paired bootstrap 95% -44.9 to -16.3; discordances 1/16; exact McNemar p=0.0003. This endpoint counts ranks 31--49 incorrect after the stability stop and is a conservative route bound, not a clean mechanism estimate.

On the actually attempted N=30 prefix, no-subcall is 20/30 and standard RLM is 24/30: -13.3 points, paired bootstrap 95% -30.0 to +0.0, discordances 1/5, exact McNemar p=0.2188.

Among the 23 rows completed by both routes, no-subcall is 19/23 and standard RLM is 21/23. The fixed-denominator difference is therefore primarily a completion/reach effect under the matched cap.

The no-subcall arm logged 0 attempted disabled calls across 318 root iterations. Failures remain incorrect.
