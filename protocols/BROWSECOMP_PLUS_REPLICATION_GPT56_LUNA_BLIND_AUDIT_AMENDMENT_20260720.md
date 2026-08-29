# BrowseComp+ Replication Blind-Audit Infrastructure Amendment

Status: **FROZEN BEFORE ANY SECOND-MODEL LABEL**  
Frozen: 2026-07-20 22:07 BST

The first GPT-5.6 Sol request returned OpenRouter HTTP 402 before any model
output, label, usage, or cost. The empty output is preserved as
`bcp_repl_gpt56_sol_402_preoutput_empty.jsonl`. This amendment changes only the
model tier to `openai/gpt-5.6-luna`, OpenAI's current cost-efficient GPT-5.6
tier. High reasoning, all 137 cases, deterministic order, batch size, prompt,
blinding, parsing, no correctness retries, and analysis remain unchanged.

The live Luna catalogue record is
`openrouter_gpt56_luna_catalog_pre_second_judge.json`. Results must be labeled
GPT-5.6 Luna, not Sol, and the failed Sol attempt must remain in the cost and
provenance record.
