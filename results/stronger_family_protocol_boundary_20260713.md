# Stronger-Family Protocol Boundary Audit

This no-call audit records which stronger-RLM-family rows are official-target evidence, public-implementation adapter evidence, or small pressure smokes. It is intended to prevent overclaiming in the paper.

## Repository State

- `lambda_rlm`: `external_repos/lambda-RLM` status `present`, commit `3874d393483d`, date `2026-04-24T14:06:08+01:00`, subject `Update README.md`.
- `prehend`: `external_repos/lm-repl` status `present`, commit `c467bb1c2d03`, date `2026-07-08T17:03:36-06:00`, subject `fix: bounce guard-rejection echoes as final answers`.

## Boundary Table

| Family | Status | Protocol level | Largest current contract | Result | What it can support | What it cannot support |
|---|---|---|---|---:|---|---|
| standard_rlm | official audited target | target_method | N=120 standard-unlabeled | 53/120 exact, mean 0.489, $2.688340 | Paper's primary claims about deployed standard rlms v0.1.3 behavior and cost under the evaluated contracts. | Claims about all RLM-family methods, official SRLM, official lambda-RLM, or training/native recursive models. |
| lambda_rlm | official public repository, project-side frozen-manifest adapter | public_implementation_adapter_not_paper_protocol | N=150 label-provided ablation; N=15 standard-unlabeled smoke | 63/150 exact, mean 0.431, $0.283037 | A bounded pressure check showing our project-side adapter did not show a reversal on frozen Oolong rows. | A method-level loss for lambda-RLM, formal guarantee comparison, or reproduction of its four-task/nine-model paper protocol. |
| lambda_rlm_standard_smoke | official public repository, project-side standard-contract adapter | smoke_adapter_not_method_comparison | N=15 standard-unlabeled smoke | 0/15 exact, mean 0.000, $0.062246 | Explains why this adapter was not scaled: zero exact answers and malformed/narrative outputs under our required aggregate-answer contract. | Evidence that the full lambda-RLM method fails on Oolong or on its own tasks. |
| srlm_prehend | public SRLM-style fork, not official Apple repository | unofficial_style_adapter | N=60 label-provided ablation; N=15 standard-unlabeled smoke | 48/60 exact, mean 0.830, $0.214733 | A stronger-family pressure check showing uncertainty-guided selection can approach standard RLM on label-provided Oolong. | Official Apple SRLM reproduction, official SRLM benchmark parity, or claim that SRLM cannot beat our SLM route. |
| srlm_prehend_standard_smoke | public SRLM-style fork, project-side standard-contract adapter | small_smoke_not_official | N=15 standard-unlabeled smoke | 7/15 exact, mean 0.467, $0.075803 | A budgeted standard-contract pressure check; it tied standard RLM on exact count but did not beat SLM+typed or direct Gemini on the smoke subset. | A final ranking of SRLM versus SLM+typed at N=120 or across SRLM's benchmark suite. |

## Decision

- Do not scale the current public adapters solely to improve optics: a larger unofficial adapter run would not close the official-reproduction limitation/criticism.
- Keep the main-paper claim scoped to standard `rlms` v0.1.3 and operation-matched alternatives.
- Keep lambda-RLM and prehend/SRLM-style rows in the supplement as pressure checks and source them to this audit.
- The only expensive run that would materially change the acceptance-risk profile is a faithful official or near-official SRLM/lambda-RLM run under the same standard-unlabeled Oolong contract.
