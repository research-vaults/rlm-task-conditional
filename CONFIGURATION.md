# Configuration

## Baseline Environment

- Python 3.11.8 was used for the recorded release-verification environment.
- Exact Python package versions are pinned in `requirements.txt`.
- `verify_release.py` itself uses only the standard library.

## Optional Provider Variables

Fresh model or infrastructure runs may read these variables:

| Variable | Purpose |
|---|---|
| `OPENROUTER_API_KEY` | OpenRouter model calls used by selected routes and judges |
| `RUNPOD_API_KEY` | RunPod lifecycle operations for GPU-backed runs |
| `HF_TOKEN` | Access to artifacts governed by upstream terms |
| `RLM_ENV_PATH` | Optional path to a local, untracked environment file |

Do not commit environment files or credential values. Export variables in the
shell or point `RLM_ENV_PATH` at a file outside the repository.

## External Inputs

Raw benchmark corpora are deliberately absent. Obtain them from their original
providers and follow the exact selection, split, model, budget, timeout and
stopping contract in the corresponding file under `protocols/`.

Analysis scripts accept paths through command-line arguments where the released
surface supports public reconstruction. Scripts marked `LOCAL_ONLY` or
`PUBLIC_SKIP` in `CLAIM_TO_COMMAND_MAP.md` require inputs that cannot be
redistributed; their release-safe aggregates are still checked by
`verify_release.py`.

## Generated Files

Use `_reproduced/` for local regenerated outputs. This directory is ignored by
Git and excluded from the immutable release manifest.

