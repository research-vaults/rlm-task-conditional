# LCFM 2026 Manuscript Snapshot

This directory stores the canonical anonymous manuscript for the NeurIPS 2026
Long-Context Foundation Models workshop.

## PDFs

- `RLM_TaskConditional_LCFM_NeurIPS2026_Full.pdf` is the exact 30-page
  submission artifact. SHA-256:
  `dca778cba6b4b703c2330fc5b6008f73b40098041ed15b1d58b14730a4cae040`.
- `RLM_TaskConditional_LCFM_NeurIPS2026_Main_and_References.pdf` is a derived
  storage copy of pages 1–11: eight technical pages followed by references.
- `RLM_TaskConditional_LCFM_NeurIPS2026_Supplement_and_Checklist.pdf` is a
  derived storage copy of pages 12–30: the appendix and reproducibility
  checklist.

The two split PDFs are provided for convenient storage and reading. The full
PDF is the canonical submission artifact.

## LaTeX Source

`source/` is the complete source tree used for the canonical PDF, including:

- `main.tex` (SHA-256
  `0a9bfe79f407b1bdf57c1e79d8caccd06f7d19c1d795b90c7350641674eae94f`);
- `appendix.tex` (SHA-256
  `20da866341d7912fb5379d3086cdf66733912f87429668f51b382b405bf26e34`);
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
