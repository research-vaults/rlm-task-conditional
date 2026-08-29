# Oolong Standard-Input Split-Overlap Audit

Target: `results/oolong_standard_validation_n150_manifest_20260714.json`

## Summary

- Target rows: 150
- Target unique IDs: 150
- Target unique context-window IDs: 73
- Union prior ID overlap: 20
- Union prior context-window overlap: 73
- Target rows on prior context windows: 150
- Target rows on new context windows: 0

## Paper Implication

The target manifest is a larger standard-input Oolong replication on new questions/rows under a fixed pipeline, but it is not context-window-disjoint from prior project Oolong work. Paper wording should not call it a disjoint prospective validation unless the claim is explicitly limited to example IDs.

## Prior Inputs

| Prior artifact | Rows | ID overlap | Context-window overlap | Target rows on overlapping contexts |
|---|---:|---:|---:|---:|
| `results/oolong_standard_unlabeled_methods_n30_20260712.csv` | 90 | 0 | 0 | 0 |
| `results/oolong_standard_unlabeled_slm_labeler_typed_n30_20260712.csv` | 30 | 0 | 0 | 0 |
| `results/oolong_standard_multilength_n15_smoke_manifest_20260712.json` | 15 | 0 | 15 | 29 |
| `results/oolong_standard_multilength_n45_5len_manifest_20260712.json` | 45 | 0 | 36 | 65 |
| `results/oolong_standard_multilength_n120_5len_manifest_20260712.json` | 120 | 0 | 69 | 143 |
| `results/oolong_standard_multilength_n120_missing75_manifest_20260712.json` | 75 | 0 | 50 | 106 |
| `results/oolong_standard_validation_n45_manifest_20260713.json` | 45 | 5 | 32 | 68 |
| `results/oolong_rollout_variability_n15_manifest_20260714.json` | 15 | 0 | 12 | 25 |
| `results/oolong_standard_multilength_frozen_manifest_20260712.json` | 126 | 15 | 43 | 90 |
