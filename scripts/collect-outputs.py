#!/usr/bin/env python3
"""Collect Slop-Mop action outputs and render a GitHub step summary.

Reads the JSON artifact written by ``sm <command> --json-file`` — the v3
response envelope (``{schema, command, status, exit_code, data: {...}}``)
— and surfaces the validation payload as action outputs plus a job
summary. The headline is the hull grade: the deterministic A+..F rating
(with its boat-condition name) that full swab/scour runs emit.

Tolerates older slopmop versions: if the file is a bare payload (no
``data`` key) it is read directly, and missing ``hull_grade`` simply
leaves the grade outputs empty.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

#: Grade order, best first. Used for minimum-grade enforcement.
GRADE_ORDER = ("A+", "A", "B", "C", "D", "F")

#: Emoji per hull level for the job-summary headline.
HULL_EMOJI = {
    "shipshape": "✨",
    "seaworthy": "⛵",
    "serviceable": "🔧",
    "weathered": "🌊",
    "fouled": "🦪",
    "scuttled": "🪣",
    "dry-dock": "🏗️",
}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _payload(document: dict[str, Any]) -> dict[str, Any]:
    """Unwrap the v3 envelope; fall back to treating the doc as the payload."""
    data = document.get("data")
    if isinstance(data, dict):
        return data
    return document


def _write_output(name: str, value: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with Path(output_path).open("a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


def _summary_counts(payload: dict[str, Any]) -> dict[str, int]:
    raw = payload.get("summary")
    if not isinstance(raw, dict):
        return {}
    counts: dict[str, int] = {}
    for key in ("passed", "failed", "errors", "warned", "skipped", "not_applicable"):
        value = raw.get(key)
        if isinstance(value, (int, float)):
            counts[key] = int(value)
    return counts


def _hull_grade(payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("hull_grade")
    return raw if isinstance(raw, dict) else {}


def _grade_meets_minimum(grade: str, minimum: str) -> bool | None:
    """True/False when comparable; None when enforcement doesn't apply.

    N/A (dry-dock) and absent grades are not comparable — a repo that
    was never initialized shouldn't fail a grade threshold, it should
    show up loudly in the summary instead.
    """
    if not minimum or grade not in GRADE_ORDER or minimum not in GRADE_ORDER:
        return None
    return GRADE_ORDER.index(grade) <= GRADE_ORDER.index(minimum)


def _top_actionable(payload: dict[str, Any], limit: int = 8) -> list[str]:
    raw = payload.get("results")
    if not isinstance(raw, list):
        return []

    names: list[str] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        if item.get("status") not in {"failed", "error"}:
            continue
        name = item.get("name")
        if isinstance(name, str):
            names.append(name)
        if len(names) >= limit:
            break
    return names


def _grade_headline(grade: dict[str, Any]) -> str:
    letter = str(grade.get("grade", ""))
    level = str(grade.get("level", ""))
    emoji = HULL_EMOJI.get(level, "⚓")
    suffix = " *(provisional)*" if grade.get("provisional") else ""
    return f"{emoji} Hull rating: **{letter} — {level}**{suffix}"


def _render_summary(
    *,
    exit_code: int,
    results_file: Path,
    sarif_file: Path,
    payload: dict[str, Any],
    grade: dict[str, Any],
    minimum_grade: str,
    grade_met: bool | None,
) -> str:
    result = "passed" if exit_code == 0 else "failed"
    lines = ["## Slop-Mop", ""]

    if grade:
        lines.extend([_grade_headline(grade), ""])
        if grade.get("level") == "dry-dock":
            lines.extend(
                [
                    "This repo has no slop-mop configuration yet. "
                    "Run `sm init && sm refit --start` to activate grading.",
                    "",
                ]
            )
        if grade_met is False:
            lines.extend(
                [
                    f"❌ Grade is below the configured minimum (`{minimum_grade}`).",
                    "",
                ]
            )

    lines.extend(
        [
            f"Result: **{result}**",
            f"Exit code: `{exit_code}`",
            f"JSON results: `{results_file}`",
            f"SARIF: `{sarif_file}`",
            "",
        ]
    )

    counts = _summary_counts(payload)
    if counts:
        lines.extend(["### Gate Counts", "", "| Status | Count |", "| --- | ---: |"])
        for key in ("passed", "failed", "errors", "warned", "skipped", "not_applicable"):
            if key in counts:
                lines.append(f"| {key.replace('_', ' ')} | {counts[key]} |")
        lines.append("")

    actionable = _top_actionable(payload)
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
    parser.add_argument("--minimum-grade", default="")
    args = parser.parse_args()

    results_file = Path(args.results_file)
    sarif_file = Path(args.sarif_file)
    payload = _payload(_load_json(results_file))
    grade = _hull_grade(payload)
    result = "passed" if args.exit_code == 0 else "failed"

    grade_letter = str(grade.get("grade", ""))
    minimum = args.minimum_grade.strip()
    grade_met = _grade_meets_minimum(grade_letter, minimum)

    _write_output("exit_code", str(args.exit_code))
    _write_output("result", result)
    _write_output("results_file", str(results_file))
    _write_output("sarif_file", str(sarif_file))
    _write_output("sarif_exists", "true" if sarif_file.exists() else "false")

    _write_output("grade", grade_letter)
    _write_output("hull", str(grade.get("level", "")))
    _write_output("failing", str(grade.get("failing", "")))
    _write_output("warned", str(grade.get("warned", "")))
    provisional = grade.get("provisional")
    _write_output(
        "provisional", "" if provisional is None else str(bool(provisional)).lower()
    )
    grade_json = (
        json.dumps(grade, separators=(",", ":"), sort_keys=True) if grade else ""
    )
    _write_output("hull_grade_json", grade_json)
    _write_output("grade_met", "" if grade_met is None else str(grade_met).lower())

    summary = _render_summary(
        exit_code=args.exit_code,
        results_file=results_file,
        sarif_file=sarif_file,
        payload=payload,
        grade=grade,
        minimum_grade=minimum,
        grade_met=grade_met,
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
