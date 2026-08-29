# Oolong CD-45 vs SU-150 Selection and Difficulty Audit

This no-call audit documents why CD-45 should be read as a cleaner split-validity check, not as a difficulty-matched replacement for SU-150.

| Slice | N | Lengths | Context clusters | Prior overlap status | SLM exact | RLM exact | Direct exact |
|---|---:|---|---:|---|---:|---:|---:|
| N120 | 120 | 8192:24, 16384:24, 32768:24, 65536:24, 131072:24 | 72 | development-era replication | 80/120 | 53/120 | 54/120 |
| SU-150 | 150 | 8192:30, 16384:30, 32768:30, 65536:30, 131072:30 | 73 | not context-window-disjoint after audit | 98/150 | 68/150 | 65/150 |
| CD-45 | 45 | 1024:15, 4096:15, 262144:15 | 32 | 0 example / 0 context-window overlap | 36/45 | 27/45 | 21/45 |

## Interpretation

- CD-45 is the cleanest overlap-controlled standard-input Oolong slice in this project.
- CD-45 is not source-document-disjoint because the local Oolong metadata exposes `context_window_id`, not a stronger source-document key.
- CD-45 is not difficulty-matched to SU-150: it uses 1k/4k/262k contexts rather than 8k--131k, and all methods score higher.
- The paper should therefore pair the two rows: SU-150 for larger scale/method-lock evidence and CD-45 for split-validity evidence.
