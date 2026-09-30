# LCFM 2026 Manuscript Snapshot

This directory stores the canonical anonymous manuscript for the NeurIPS 2026
Long-Context Foundation Models workshop.

## PDFs

- `RLM_TaskConditional_LCFM_NeurIPS2026_Full.pdf` is the exact 31-page
  submission artifact. SHA-256:
  `f29762df1b7b8b2a47e669f52f94a7967e30d9c963879d12a1cbf73f293040d6`.
- `RLM_TaskConditional_LCFM_NeurIPS2026_Main_and_References.pdf` is a derived
  storage copy of pages 1–11: eight technical pages followed by references.
- `RLM_TaskConditional_LCFM_NeurIPS2026_Supplement_and_Checklist.pdf` is a
  derived storage copy of pages 12–31: the appendix and reproducibility
  checklist.

The two split PDFs are provided for convenient storage and reading. The full
PDF is the canonical submission artifact.

## LaTeX Source

`source/` is the complete source tree used for the canonical PDF, including:

- `main.tex` (SHA-256
  `3bfb1c27a25fa23f8402e527dc947d7818ae42b247931dbd117fc626fcc42602`);
- `appendix.tex` (SHA-256
  `5b6791414d31e1f7cd05d4962afcedb6406d942260e1b2672c83168fb0a53138`);
- the bibliography, answered checklist, workshop style and all referenced
  figure files.

Build from `source/` with a standard LaTeX installation:

```bash
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

The snapshot is anonymous and intentionally excludes project reviews, planning
documents, build directories and submission-platform metadata.

The official workshop style is retained unchanged. Any venue-maintainer contact
text inside that style file is not project-author metadata.
