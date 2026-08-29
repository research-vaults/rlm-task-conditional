# Sonnet 4.6 Standard-RLM Compatibility Probe

This paid smoke tested whether the standard `rlms` scaffold could be cleanly swapped from the logged Gemini controller to OpenRouter Sonnet 4.6 on the same standard-unlabeled Oolong contract.

## Result

- Sonnet 4.6 standard-RLM probe: 0/3 exact, mean score 0.000, cost $0.049605, errors 1.
- Matched SLM-labeler+typed on the same IDs: 3/3 exact.
- Matched Gemini 2.5 standard RLM on the same IDs: 1/3 exact.

## Stop-Rule Decision

Do not scale this Sonnet 4.6 standard-RLM run now. The 3-row compatibility probe solved no examples, timed out on one short counting row, and was wrong on the two completed rows. Scaling would not close the official SRLM/lambda-RLM comparator-fidelity objection because this is still standard `rlms`, not a contemporary RLM-family method reproduction.

## Artifact Caveat

The historical runner stored final prediction/error/cost rows, not raw RLM trajectories. The reconstructed trace JSONL records the full input context, question, gold answer, prediction/error, and cost for every row, but raw intermediate RLM trajectory text is unavailable for this probe.
