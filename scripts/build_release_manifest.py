#!/usr/bin/env python3
"""Build the deterministic release member manifest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "SHA256SUMS.json"
EXCLUDED_PARTS = {".git", ".venv", "__pycache__", "_reproduced"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def included(path: Path) -> bool:
    return (
        path.is_file()
        and path != MANIFEST
        and not EXCLUDED_PARTS.intersection(path.relative_to(ROOT).parts)
    )


def main() -> int:
    entries = []
    for path in sorted(ROOT.rglob("*")):
        if not included(path):
            continue
        entries.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    MANIFEST.write_text(
        json.dumps({"schema_version": 1, "files": entries}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(entries)} entries to {MANIFEST.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

