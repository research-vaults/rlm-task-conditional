# Stronger-Family Feasibility Gate

This no-call gate decides whether another paid stronger-RLM-family run would materially reduce rejection risk before submission. It complements the protocol-boundary audit by adding an explicit scale/no-scale decision.

## Decision

**Do not scale the current public adapters or strong-controller swaps before submission.** A larger unofficial run would add rows but would not close the official-reproduction criticism. The only spend that should override this is an official or near-official SRLM/lambda-RLM same-contract protocol with valid traces, costs, and stop rules.

## Candidate Gate Scores

| Candidate | Fidelity | Stability | Acceptance value | Cost discipline | Total | Decision | Reason |
|---|---:|---:|---:|---:|---:|---|---|
| Scale public lambda-RLM adapter to full Oolong N=120 standard contract | 1 | 1 | 1 | 2 | 5 | DO_NOT_SCALE_NOW | The public repository is real, but the project adapter is not the lambda-RLM paper protocol. The matched smoke emitted no exact aggregate answers, so a larger run would mostly measure adapter mismatch. |
| Scale public prehend/SRLM-style adapter to full Oolong N=120 standard contract | 1 | 2 | 2 | 2 | 7 | HOLD_UNLESS_REVIEWER_REQUIRES | This is the strongest available public stronger-family pressure row, but it is not an official Apple SRLM reproduction. Scaling it could add useful context, yet would not close the official-reproduction objection. |
| Scale Gemini 3.5 Flash as a current standard-RLM controller | 2 | 0 | 2 | 1 | 5 | DO_NOT_SCALE_NOW | It addresses freshness but not stronger-family protocol fidelity, and the attempted standard-RLM prefix showed early timeout/accounting instability. |
| Scale Sonnet 4.6 inside standard rlms | 2 | 0 | 1 | 0 | 3 | DO_NOT_SCALE_NOW | A stronger controller swap would be expensive and still would not reproduce SRLM or lambda-RLM. The stop-rule probe also showed worse stability than the logged Gemini controller on matched rows. |
| Run only an official or near-official SRLM/lambda-RLM same-contract comparator | 3 | 2 | 3 | 2 | 10 | RUN_IF_PROTOCOL_AVAILABLE | This is the only stronger-family spend that would materially change the rejection-risk profile. It must be faithful enough that reviewers read it as comparator parity rather than adapter debugging. |

## Evidence Used

- Public lambda-RLM adapter: label-provided Oolong 63/150 exact; matched standard-unlabeled smoke 0/15 exact.
- Public prehend/SRLM-style adapter: label-provided Oolong 48/60 exact; matched standard-unlabeled smoke 7/15 exact.
- Gemini 3.5 Flash direct sensitivity: 20/45 exact; Gemini 3.5 standard-RLM prefix 5/8 exact with 3 timeout/error rows.
- Sonnet 4.6 standard-RLM stop-rule probe: 0/3 exact with one timeout/error row.
- Web/source check on 2026-07-14: lambda-RLM has an advertised public implementation; SRLM did not surface an obvious official runnable Apple repository in search results, so prehend remains SRLM-style pressure evidence only.

## Reviewer-Facing Interpretation

This gate should be cited when explaining why the paper does not spend more on weak adapter scaling. It is stronger to show a conservative predeclared scale/no-scale rule than to report a larger unofficial adapter table that reviewers could dismiss as protocol-mismatched.
