# BrowseComp-Plus N=80 Independent Second-Model Blind Audit

Date: 2026-07-20  
Status: completed sensitivity audit  
Evidence role: independent second-model validation, not human validation

## Question

Does the primary method-blinded Gemma 4 semantic judge's N=80 route ordering
survive a separate frontier-model adjudication that cannot see route identity,
primary labels, selection-stratum labels, or aggregate outcomes?

## Frozen Selection

The audit packet was generated deterministically before second-model labels
were observed:

- all 25 cells where primary semantic correctness differed from normalized
  answer containment;
- all three cells with malformed primary-judge outputs;
- three deterministic agreement examples per method and primary semantic class
  where available, yielding 18 agreement-sample cells;
- 46 unique cells total.

The raw N=80 study contains 240 cells. The selected set intentionally
oversamples difficult cases, so raw audit agreement is diagnostic rather than a
population agreement estimate.

## Blinding And Input

The adjudicator received one JSON object per case with exactly:

```json
{
  "case_id": "opaque identifier",
  "question": "restricted benchmark question",
  "reference_answer": "restricted benchmark reference",
  "candidate_response": "one route prediction"
}
```

It did not receive route/method, rank, episode, primary-judge label,
containment label, selection stratum, other route outputs, aggregate scores, or
paper claims. The restricted packet is
`results/browsecomp_plus_positive_regime/bcp_n80_second_model_blind_packet_20260720_restricted.jsonl`.
Its SHA-256 is
`5da1c4aea8ad39b0364245874a0e553700d610a0f0a8bba97d337d47df0c1ebf`.

## Adjudicator And Decision Rule

- Model: GPT-5.6 Sol
- Reasoning effort: high
- Service: independent second-model evaluation process, separate from the primary OpenRouter generation pipeline
- OpenRouter spend: `$0.00`
- Temperature/sampling controls: not exposed by the internal agent service
- Retries: none for correctness

For each case, the adjudicator decided whether the candidate response
semantically answered the question with the reference answer. Alias,
diacritic, formatting, and noncontradictory explanatory differences could be
accepted. A different entity/value, contradiction, refusal, unsupported
alternative, or empty/non-answer was incorrect.

Required output schema:

```json
{
  "case_id": "same opaque identifier",
  "correct": true,
  "confidence": "low|medium|high",
  "rationale_code": "short categorical code",
  "rationale": "brief case-specific explanation"
}
```

All 46 rows were returned once and validated for exact case-ID coverage,
boolean labels, confidence enum, and nonempty rationale fields. Restricted
adjudication rows and rationales remain local.

## Reconciliation Rule

The sensitivity analysis replaces the primary semantic label only for the 46
preselected audited cells and retains the primary label for the other 194
cells. It does not select cases after seeing second-model labels and does not
replace failures with completions.

## Results

- Agreement with primary judge: 43/46 (93.5%).
- Disagreement-set agreement: 23/25.
- Malformed-primary set agreement: 3/3.
- Stratified agreement-sample agreement: 17/18.
- Primary RLM/text/BM25 totals: 54/48/39.
- Sensitivity totals: 55/47/38.
- Sensitivity RLM--BM25: `b=26,c=9,p=0.005988`; Holm-adjusted
  `p=0.017964` over all three route pairs.
- Sensitivity RLM--text: `b=20,c=12,p=0.215327`.

The second-model sensitivity therefore preserves the primary conclusions:
RLM is supported over BM25 on this endpoint, while RLM versus text
decomposition remains uncertain.

## Release Boundary

Release-safe files:

- `bcp_n80_privacy_safe_cell_ledger_20260720.jsonl` and summary;
- `bcp_n80_second_model_blind_audit_aggregate_20260720.json` and Markdown;
- deterministic build/reconciliation scripts.

The release-safe ledger contains rank, method, episode, completion,
score booleans, judge parse state, error category, execution metadata, and
provenance hashes. It excludes question, reference, prediction, query ID,
opaque case ID, and rationale. Restricted packet, mapping, adjudication rows,
and rationales remain local because BrowseComp-Plus query/corpus material is
restricted.
