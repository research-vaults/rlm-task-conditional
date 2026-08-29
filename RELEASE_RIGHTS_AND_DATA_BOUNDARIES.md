# Release Rights, Data Boundaries And Corrections

## Release status

This private repository is supplied for reproducibility inspection. No license
to redistribute, republish or create derivative works from the project-authored
manuscript, code or evidence files is granted unless a separate repository
license states otherwise.

## Third-party data and software

The repository does not grant rights to any third-party benchmark, model, API,
paper, template or software dependency. Users must obtain those resources
from their official sources and comply with the applicable licenses, dataset
terms and provider policies.

Source-document-scale benchmark content is excluded. The repository contains
release-safe manifests, aggregates, hashes, protocols and compact generated
traces needed to verify reported results without redistributing the underlying
BrowseComp-Plus, Oolong, LongBench-v2 or HotpotQA corpora. Commands requiring
those excluded source payloads are marked `LOCAL_ONLY`. Frozen manuscript
sources, the official workshop style and compiled manuscript PDFs are retained
for claim verification, reproducibility and private archival storage. The venue
style remains governed by its original terms.

Selected files can contain short task statements, answers or generated
responses needed to audit a row, but not source-document-scale benchmark
contexts or prompts. The release builder rejects oversized structured
source-payload fields and redacts email-like strings from text artifacts before
packaging. Unredacted local evidence remains outside the repository and this
release grants no additional rights to the underlying public-corpus text.

Python and LaTeX dependencies are not vendored or relicensed. Installations
remain governed by their upstream licenses.

## Corrections and versions

The repository contains a `SHA256SUMS.json` manifest covering every release
file except the manifest itself and explicitly ignored development outputs.
`verify_release.py` verifies that manifest, parses every structured data file,
compiles every Python file and checks the claim-bearing released evidence
without model, network or GPU calls. A corrected release should regenerate the
manifest and identify affected claims or artifacts. During anonymous review,
correction notices should be communicated through the venue's official
submission channel.

Absence of a file from the release repository does not imply that it was
unused. Restricted and privacy-sensitive inputs remain outside the package
and are represented only through documented hashes, counts and aggregate
verification surfaces.
