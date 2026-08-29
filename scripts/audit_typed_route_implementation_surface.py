#!/usr/bin/env python3
"""Audit the released implementation surface of the Oolong typed route.

This is a source-accounting artifact, not an estimate of engineering time or
total cost of ownership. It deliberately reports the full released files used
for the typed route, including CLI, tracing, and evaluation support, so the
line counts are an auditable upper bound on the implementation surface rather
than a minimal runtime-kernel count.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

FILES = {
    "typed_aggregation_kernel_and_audit": ROOT / "scripts" / "probe_typed_oolong_proxy.py",
    "question_schema_parser_and_audit": ROOT / "scripts" / "analyze_oolong_question_parsed_typed.py",
    "slm_labeling_execution_and_audit": ROOT / "scripts" / "eval_oolong_standard_slm_labeler_typed.py",
    "standard_rlm_tool_wrappers": ROOT / "scripts" / "oolong_operator_library.py",
}


def file_metrics(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    lines = text.splitlines()
    tree = ast.parse(text, filename=str(path))
    top_functions = [node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    top_classes = [node.name for node in tree.body if isinstance(node, ast.ClassDef)]
    all_functions = [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "physical_lines": len(lines),
        "nonblank_lines": sum(bool(line.strip()) for line in lines),
        "comment_only_lines": sum(line.lstrip().startswith("#") for line in lines),
        "top_level_function_count": len(top_functions),
        "nested_and_top_level_function_count": len(all_functions),
        "top_level_class_count": len(top_classes),
        "top_level_functions": top_functions,
        "top_level_classes": top_classes,
    }


def build_report() -> dict[str, Any]:
    by_role = {role: file_metrics(path) for role, path in FILES.items()}
    operator_module = ast.parse(FILES["standard_rlm_tool_wrappers"].read_text(encoding="utf-8"))
    constants: dict[str, list[str]] = {}
    for node in operator_module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {"TASKS", "ANSWER_TYPES"}:
                    constants[target.id] = ast.literal_eval(node.value)

    totals = {
        key: sum(int(metrics[key]) for metrics in by_role.values())
        for key in (
            "bytes",
            "physical_lines",
            "nonblank_lines",
            "comment_only_lines",
            "top_level_function_count",
            "nested_and_top_level_function_count",
            "top_level_class_count",
        )
    }
    return {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "measurement_type": "released_implementation_surface_upper_bound",
        "files": by_role,
        "totals": totals,
        "declared_schema": {
            "task_family_count": len(constants.get("TASKS", [])),
            "task_families": constants.get("TASKS", []),
            "answer_type_count": len(constants.get("ANSWER_TYPES", [])),
            "answer_types": constants.get("ANSWER_TYPES", []),
            "atomic_tool_count": 5,
            "convenience_tool_count": 1,
            "all_tool_count": 6,
        },
        "scope_note": (
            "Counts cover the complete released source files used by the typed route, including CLI, "
            "tracing, caching, analysis, and reporting support. They are not minimal runtime LOC."
        ),
        "nonclaim": (
            "Source size does not measure human engineering hours, maintenance burden, or total cost "
            "of ownership; no such quantities were logged prospectively."
        ),
    }


def render_markdown(report: dict[str, Any]) -> str:
    rows = []
    for role, metrics in report["files"].items():
        rows.append(
            f"| `{role}` | `{metrics['path']}` | {metrics['physical_lines']} | "
            f"{metrics['nonblank_lines']} | {metrics['top_level_function_count']} | "
            f"`{metrics['sha256'][:12]}` |"
        )
    totals = report["totals"]
    schema = report["declared_schema"]
    return "\n".join(
        [
            "# Typed-Route Released Implementation-Surface Audit",
            "",
            f"Generated: `{report['created_utc']}`",
            "",
            "| Role | Released file | Physical lines | Nonblank lines | Top-level functions | SHA-256 prefix |",
            "|---|---|---:|---:|---:|---|",
            *rows,
            f"| **Total** | **4 files** | **{totals['physical_lines']}** | "
            f"**{totals['nonblank_lines']}** | **{totals['top_level_function_count']}** | -- |",
            "",
            "## Declared Typed Surface",
            "",
            f"- Task families: **{schema['task_family_count']}**.",
            f"- Answer types: **{schema['answer_type_count']}**.",
            f"- Standard-RLM custom-tool exposure: **{schema['atomic_tool_count']} atomic/schema tools** "
            f"plus **{schema['convenience_tool_count']} optional convenience solver**.",
            "",
            "## Interpretation Boundary",
            "",
            report["scope_note"],
            "",
            f"**Non-claim:** {report['nonclaim']}",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--json-out",
        type=Path,
        default=ROOT / "results" / "typed_route_implementation_surface_20260719.json",
    )
    parser.add_argument(
        "--md-out",
        type=Path,
        default=ROOT / "results" / "typed_route_implementation_surface_20260719.md",
    )
    args = parser.parse_args()
    report = build_report()
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.md_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.md_out.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"json": str(args.json_out), "markdown": str(args.md_out), **report["totals"]}, indent=2))


if __name__ == "__main__":
    main()
