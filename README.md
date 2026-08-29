# When Are Recursive Language Models Useful?

This private, anonymized repository contains the release-ready code and
release-safe evidence for **When Are Recursive Language Models Useful? A
Cost-Aware, Task-Conditional Evaluation**.

The project evaluates standard Recursive Language Model (RLM) scaffolds under
matched information, scoring and budget contracts. It compares them with
operation-matched deterministic, retrieval, semantic-worker and direct routes
across controlled aggregation and open multi-document search settings.

## Repository Contents

- `scripts/`: deterministic analyzers, integrity checks and experiment drivers.
- `protocols/`: frozen execution contracts and amendments for the reported studies.
- `results/`: release-safe rows, aggregates, compact traces and statistical
  summaries. Restricted source documents are excluded.
- `paper/`: frozen anonymized source snapshots used only by the claim verifier.
- `CLAIM_TO_COMMAND_MAP.md`: maps evidence to commands and states whether each
  command is public, needs withheld inputs or requires fresh provider calls.
- `CONFIGURATION.md`: environment variables, external inputs and execution boundaries.
- `RELEASE_RIGHTS_AND_DATA_BOUNDARIES.md`: third-party data, licensing and
  correction boundaries.
- `SHA256SUMS.json`: size and SHA-256 manifest for every release member.
- `verify_release.py`: deterministic, no-network release verifier.

## Quick Start

The main verifier uses only the Python standard library:

```bash
python3 verify_release.py
```

Expected final line:

```text
RELEASE VERIFIER: PASS
```

For the recorded analysis environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
python3 verify_release.py
```

## Deterministic Reproduction Examples

These commands use released inputs, make no model calls and write only below
the ignored `_reproduced/` directory:

```bash
python3 scripts/analyze_engineering_break_even.py \
  --output-dir _reproduced/engineering_break_even

python3 scripts/analyze_oolong_cd45_rlm_repeatability.py \
  --output-dir _reproduced/oolong_cd45_repeatability
```

The complete evidence-to-command mapping is in `CLAIM_TO_COMMAND_MAP.md`.
Some generation and analysis drivers require restricted benchmark inputs or
paid model endpoints. They are retained to document the exact experimental
surface, but the repository does not claim those runs can execute without
obtaining the upstream data and configuring the named providers.

## Required Inputs

No external input is required for `verify_release.py` or the deterministic
examples above. Fresh generation may require:

- the upstream Oolong/Oolong-synth data;
- BrowseComp-Plus document pools and evaluation labels;
- HotpotQA or LongBench-v2 source data;
- public RLM-family repositories and model revisions named in the protocols;
- provider credentials supplied through environment variables.

The repository never loads credentials from committed files. See
`CONFIGURATION.md` for supported variable names.

## Expected Outputs

- `verify_release.py` prints one `PASS` or `FAIL` line per invariant and exits
  nonzero on any mismatch.
- Deterministic analyses write regenerated JSON, CSV, Markdown or figures under
  the selected `_reproduced/` subdirectory.
- Fresh model drivers write outputs specified by their command-line arguments
  or protocol and should run only after reviewing cost and stopping rules.

## Included and Excluded Material

Included:

- release-relevant Python code and pinned Python dependencies;
- frozen protocols and configuration boundaries;
- reasonably sized, release-safe result rows and compact traces;
- aggregate statistics, manifests and deterministic verification code;
- anonymized source snapshots needed to verify claim-bearing wording.

Intentionally excluded:

- API keys, tokens, `.env` files and cloud-account configuration;
- author identities, affiliations and machine-specific paths;
- internal review and project-management material;
- caches, temporary renders, build products and model checkpoints;
- restricted or source-document-scale benchmark text;
- raw trajectories that reproduce restricted source contexts;
- unrelated project files and full working-directory history.

## Data, Rights and Anonymity

Released records contain only material needed to inspect and verify the
reported analyses. Upstream datasets and third-party model code remain under
their original terms. This private repository does not grant an additional
license for third-party data and does not redistribute restricted benchmark
content.

The repository is intentionally anonymous. Author and affiliation metadata can
be added after the applicable review process permits de-anonymization.
