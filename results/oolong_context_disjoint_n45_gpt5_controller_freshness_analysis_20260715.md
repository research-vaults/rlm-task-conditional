# GPT-5 Controller Freshness Analysis on Oolong CD-45

This is a complete strict-stop standard-`rlms` run on the context-window-disjoint Oolong CD-45 manifest. It uses `openai/gpt-5` through OpenRouter with a 240-second per-row timeout.

| Method | Exact | Mean score | Cost | Errors |
|---|---:|---:|---:|---:|
| Q-parsed SLM+typed | 36/45 (80.0%) | 83.7% | $0.416415 | 0 |
| Direct Gemini 2.5 Flash | 21/45 (46.7%) | 54.9% | $1.024590 | 0 |
| Standard RLM / Gemini 2.5 Flash | 27/45 (60.0%) | 62.3% | $1.001014 | 0 |
| Standard RLM / GPT-5 | 23/45 (51.1%) | 58.1% | $2.442035 | 15 |

## Interpretation

- GPT-5 does not close the central CD-45 gap: SLM+typed remains higher on exact accuracy and mean score.
- GPT-5 introduces substantial strict-stop instability on this scaffold: 15/45 rows timed out or errored under the 240-second row cap.
- This result should be reported as a controller-freshness sensitivity and stability check, not as a new RLM-family leaderboard.
