# Protocol: Standard `rlms` + Same Typed Operator Library on CD-15

Created: 2026-07-16

## Purpose

This is the predeclared protocol for the remaining fairness falsifier in the RLM audit paper: give the deployed standard `rlms` scaffold access to the same Oolong typed operator library used by the SLM+typed route, while preserving free-form RLM program generation and the standard-unlabeled input contract.

This is not the completed shared-operator controller diagnostic. In that diagnostic, an LLM selected task and answer type, then deterministic typed execution ran over stored SLM labels. Here, the standard `rlms` scaffold can write Python in the REPL and decide whether/how to call the injected tools.

## Contract

- Scaffold: `from rlm import RLM`, standard inference-time `rlms` v0.1.3.
- Backend: OpenRouter, `google/gemini-2.5-flash`.
- Environment: `local`.
- Max depth: 1.
- Max iterations: 15.
- Max budget: `$0.50` per row.
- Wall-clock row cap: 360 seconds.
- Input field: standard `context_window_text` only.
- Root prompt: natural-language question only.
- Tool mechanism: `custom_tools` in the standard `RLM(...)` constructor.
- No gold local labels, no `context_window_text_with_labels`, no benchmark task metadata, and no pre-parsed answer type are passed to the prompt.

## Tools

The injected tools are thin wrappers around existing project code:

- `parse_oolong_rows(context)`: parse the standard Oolong text rows.
- `label_oolong_rows_with_slm(context, question)`: run the same Gemma SLM row-labeling path used by SLM+typed.
- `solve_labeled_oolong(context, question, labels, task, answer_type)`: execute typed aggregation over supplied predicted labels. The generated RLM code must supply `task` and `answer_type`.
- `solve_oolong_with_tools(context, question, task, answer_type)`: convenience wrapper that labels rows with the SLM helper and then executes the typed solver. The generated RLM code must still supply `task` and `answer_type`.
- `available_oolong_tasks`: task enum strings.
- `available_oolong_answer_types`: answer-type enum strings.

Every tool call writes a JSONL tool trace record with tool name, arguments summary, row count, labels/cost/tokens when applicable, prediction/status when applicable, errors, and latency.

## Slice and Stop Rules

1. Smoke: 1 to 3 CD-15 rows.
   - Stop/fix if custom tools cannot be called, trajectory logging fails, or the model never sees usable tools.
   - No paper claim from smoke alone.

2. Pilot: frozen CD-15 manifest.
   - Stop if at least 50% of rows timeout/error/tool-unusable or if spend exceeds roughly `$3--5` before completion.
   - Analyze only if stable enough to interpret.

3. Scale: full CD-45.
   - Run only if CD-15 is stable and the interpretation is clean.
   - Use identical settings and explicit spend/stability rules.

## Required Comparators

For the same row IDs, compare against:

- SLM+typed.
- Standard RLM without tools, including original and repeat rows where available.
- Direct Gemini.
- Shared-operator controller, labeled route-selection only.
- The new RLM+ops row.

## Allowed Claims

- "When the same typed library is available inside standard `rlms`, free-form control [matches / loses to / beats] SLM+typed on this frozen pilot, at [cost/error rate]."
- "This is a same-operator-library diagnostic for standard `rlms`, not official SRLM or `lambda`-RLM."

## Forbidden Claims

- Do not call this official SRLM, official `lambda`-RLM, or RAH.
- Do not claim it proves all RLM-family variants would behave the same.
- Do not treat CD-15 as a full Oolong leaderboard.
- Do not imply the previous shared-operator controller already closed this falsifier.

