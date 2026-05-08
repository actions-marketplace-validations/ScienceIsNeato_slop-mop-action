#!/usr/bin/env python3
"""Collect Slop-Mop action outputs and render a GitHub step summary."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


DIMENSIONS = ("myopia", "deceptiveness", "laziness", "overconfidence")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_output(name: str, value: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with Path(output_path).open("a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


def _summary_counts(results: dict[str, Any]) -> dict[str, int]:
    raw = results.get("summary")
    if not isinstance(raw, dict):
        return {}
    counts: dict[str, int] = {}
    for key in ("passed", "failed", "errors", "warned", "skipped", "not_applicable"):
        value = raw.get(key)
        if isinstance(value, (int, float)):
            counts[key] = int(value)
    return counts


def _posture(results: dict[str, Any]) -> dict[str, Any]:
    raw = results.get("posture")
    return raw if isinstance(raw, dict) else {}


def _label_for(posture: dict[str, Any], dimension: str) -> str:
    raw = posture.get(dimension)
    if isinstance(raw, dict):
        label = raw.get("label")
        if isinstance(label, str):
            return label
    return ""


def _top_actionable(results: dict[str, Any], limit: int = 8) -> list[str]:
    raw = results.get("results")
    if not isinstance(raw, list):
        return []

    names: list[str] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        status = item.get("status")
        if status not in {"failed", "error"}:
            continue
        name = item.get("name")
        if isinstance(name, str):
            names.append(name)
        if len(names) >= limit:
            break
    return names


def _render_summary(
    *,
    exit_code: int,
    results_file: Path,
    sarif_file: Path,
    results: dict[str, Any],
    posture: dict[str, Any],
) -> str:
    result = "passed" if exit_code == 0 else "failed"
    lines = [
        "## Slop-Mop",
        "",
        f"Result: **{result}**",
        f"Exit code: `{exit_code}`",
        f"JSON results: `{results_file}`",
        f"SARIF: `{sarif_file}`",
        "",
    ]

    if posture:
        lines.extend(["### Posture", "", "| Dimension | Label |", "| --- | --- |"])
        for dimension in DIMENSIONS:
            lines.append(f"| {dimension} | {_label_for(posture, dimension) or 'Not assessed'} |")
        lines.append("")
    else:
        lines.extend(
            [
                "### Posture",
                "",
                "Slop-Mop did not emit posture metadata for this run.",
                "",
            ]
        )

    counts = _summary_counts(results)
    if counts:
        lines.extend(["### Gate Counts", "", "| Status | Count |", "| --- | ---: |"])
        for key in ("passed", "failed", "errors", "warned", "skipped", "not_applicable"):
            if key in counts:
                lines.append(f"| {key.replace('_', ' ')} | {counts[key]} |")
        lines.append("")

    actionable = _top_actionable(results)
    if actionable:
        lines.extend(["### First Failing Gates", ""])
        lines.extend(f"- `{name}`" for name in actionable)
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exit-code", required=True, type=int)
    parser.add_argument("--results-file", required=True)
    parser.add_argument("--sarif-file", required=True)
    args = parser.parse_args()

    results_file = Path(args.results_file)
    sarif_file = Path(args.sarif_file)
    results = _load_json(results_file)
    posture = _posture(results)
    result = "passed" if args.exit_code == 0 else "failed"

    _write_output("exit_code", str(args.exit_code))
    _write_output("result", result)
    _write_output("results_file", str(results_file))
    _write_output("sarif_file", str(sarif_file))
    _write_output("sarif_exists", "true" if sarif_file.exists() else "false")

    for dimension in DIMENSIONS:
        _write_output(dimension, _label_for(posture, dimension))

    posture_json = json.dumps(posture, separators=(",", ":"), sort_keys=True) if posture else ""
    _write_output("posture_json", posture_json)

    summary = _render_summary(
        exit_code=args.exit_code,
        results_file=results_file,
        sarif_file=sarif_file,
        results=results,
        posture=posture,
    )
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with Path(summary_path).open("a", encoding="utf-8") as handle:
            handle.write(summary)
            handle.write("\n")
    else:
        print(summary)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
