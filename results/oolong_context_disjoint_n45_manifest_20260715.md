# Context-Disjoint Oolong Standard-Input Freeze

Manifest: `results/oolong_context_disjoint_n45_manifest_20260715.json`

## Summary

- N: 45
- Groups: `{'counting': 15, 'timeline': 15, 'user': 15}`
- Lengths: `{'1024': 15, '4096': 15, '262144': 15}`
- Unique context-window IDs: 32
- Max questions per new context window: 2
- Prior ID overlap after freeze: 0
- Prior context-window overlap after freeze: 0

## Paper Interpretation

This is a standard-unlabeled Oolong-synth slice frozen before new model calls. It is example-ID-disjoint and context-window-disjoint from all prior project Oolong artifacts discoverable under `results/`. It should still be described as context-window-disjoint, not source-document-disjoint, because Oolong exposes `context_window_id` as the enforceable source-window unit.

## Candidate Availability After Prior-Context Exclusion

| Cell | Candidate rows | Candidate context windows |
|---|---:|---:|
| `counting/1024` | 144 | 21 |
| `counting/262144` | 125 | 14 |
| `counting/4096` | 116 | 15 |
| `timeline/1024` | 107 | 18 |
| `timeline/262144` | 100 | 11 |
| `timeline/4096` | 106 | 12 |
| `user/1024` | 59 | 10 |
| `user/262144` | 125 | 12 |
| `user/4096` | 80 | 11 |
