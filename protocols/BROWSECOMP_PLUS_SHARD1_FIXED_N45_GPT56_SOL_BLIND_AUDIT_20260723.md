# BrowseComp-Plus Shard-1 Fixed-N45 GPT-5.6 Sol Blind Audit

Status: **FROZEN BEFORE SEMANTIC-JUDGE OUTPUT**  
Frozen: 2026-07-23 20:10 BST  
Parent study: `browsecomp_plus_shard1_fixed_n45_v1`

## Purpose

Measure sensitivity of the fixed-N45 semantic endpoint to a second independent
model judge. This is not human validation and cannot close the human-authority
ceiling. The primary judge remains the separately pinned Gemma 4 contract.

## Population And Blinding

- Input is the deterministic compact endpoint generated only after all 135
  parent generation cells close.
- Audit every successful nonempty prediction. Parent route failures remain
  incorrect and are not sent to the judge.
- Each case contains only question, reference answer and candidate response.
  It excludes route, rank, cost, latency, completion status, trace, primary
  judgment and deterministic score.
- Stable blind order:
  `SHA256("BCP-SHARD1-N45-GPT56-SOL-v1|" + rank + "|" + method)`.
- Stable anonymous case ID:
  first 24 hex characters of
  `SHA256("BCP-SHARD1-N45-GPT56-SOL-CASE-v1|" + rank + "|" + method)`.

## Judge

- Provider/model: OpenRouter `openai/gpt-5.6-sol`.
- Reasoning: `{"effort": "high"}`.
- Batch size: 16.
- Maximum output tokens: 6,000.
- Seed: 20.
- Structured output: JSON object with a complete `labels` array.
- The exact model must appear in the live OpenRouter catalog at execution.
  The full catalog record, request/response, usage, provider response ID,
  transport attempts, latency and cost are retained.
- Live web checks on 2026-07-23 identified GPT-5.6 Sol as the flagship GPT-5.6
  tier, released 2026-07-09 with a 1M context window. The stronger Sol tier is
  used here rather than Luna because this is a small authority-sensitivity
  audit, not a high-volume production route.

## Frozen Rubric

For each case, decide whether the candidate response correctly answers the
question given the reference answer:

- accept aliases, harmless wording variation and additional
  noncontradictory detail;
- reject a different entity/value, contradiction, material ambiguity,
  refusal, empty answer or non-answer;
- do not infer route identity or solve using external evidence;
- return one Boolean label and one short rationale.

Every expected case ID must appear exactly once. A missing, duplicated,
non-Boolean or rationale-free label is a judge-format failure and is scored
incorrect for sensitivity reporting. Infrastructure failures must be retried
only under the frozen two-attempt transport policy and remain fully logged.

## Analysis

- Report per-route correctness over the parent fixed N=45 denominator.
- Report agreement with primary Gemma 4 over mutually judged successful
  outputs: raw agreement, positive/negative agreement and Cohen's kappa.
- Recompute paired route differences, 50,000 paired-row bootstrap intervals,
  exact McNemar tests and Holm adjustment over the two standard-RLM contrasts.
- Keep the primary Gemma result and this sensitivity separate. No adjudicator
  may select labels after comparing route outcomes.
- Report all costs from request usage and before/after OpenRouter account
  snapshots. The account may be shared; distinguish request-reported cost from
  account-level deltas.

## Privacy And Promotion

Restricted case payloads, predictions, references and rationales remain local
with mode 0600. Release only privacy-safe aggregates and hashes. The main paper
may cite agreement or sensitivity only after complete case coverage,
independent verification and exact source binding.
