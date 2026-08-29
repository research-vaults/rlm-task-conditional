# Official RLM-Qwen CD-45 Completion Stop-Rule Audit

## Outcome

The remaining 30 examples were frozen before calls by subtracting the prior CD-15
manifest from the parent context-window-disjoint CD-45 manifest. The three-row
preflight completed without errors (2/3 exact), so the predeclared gate expanded.
The run returned eight rows: six completed and two consecutive serving errors.
The predeclared stability stop then fired. **This is not a completed CD-45 accuracy
row, and the 2/8 descriptive prefix accuracy is not used for method ranking.**

| Quantity | Value |
|---|---:|
| Frozen remaining manifest | 30 rows |
| Overlap with prior CD-15 | 0 rows |
| Returned prefix | 8 rows |
| Completed / errors | 6 / 2 |
| Generated iterations / code blocks | 57 / 55 |
| Stability trigger | 2 consecutive errors |

## Failure mechanism

Both errors came from the official serving configuration: the model advertises a
16,384-token maximum, while each failing internal request contained at least
12,289 input tokens and requested 4,096 output tokens, totaling at least 16,385.
The two failures occurred on examples 912090010, 612060011.
Because the model-card settings and stop rule were fixed before the run, we did
not reduce the completion cap, raise the model context limit, reorder rows, or
resume the prefix after observing this failure.

## Cost and cleanup

The pod existed for 754.15 seconds from provider creation to
successful deletion (HTTP 204). At the listed $2.99/hour rate, this is a
provider-rate estimate of $0.6264; the billing-history
endpoint had not yet populated an itemized charge. The detached watchdog was
cancelled after normal cleanup. OpenRouter spend was $0.00.

## Interpretation boundary

This result strengthens the audit's deployability evidence: a prospectively
locked official-policy scale attempt encountered a deterministic serving-contract
boundary under published settings. It does not strengthen or weaken the CD-15
accuracy ranking, does not estimate full-CD-45 performance, and does not establish
parity with SRLM, lambda-RLM, or RAH.
