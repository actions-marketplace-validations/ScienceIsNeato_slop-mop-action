# Slop-Mop GitHub Action

Run Slop-Mop in GitHub Actions and get a hull grade for the repo.

This repository is intentionally small. The action installs the `slopmop`
Python package, runs `sm swab` or `sm scour`, writes Slop-Mop's JSON and SARIF
outputs, optionally uploads SARIF to GitHub Code Scanning, surfaces the hull
grade in the job summary, and can enforce a minimum grade. Gate behavior,
SARIF shape, JSON schema, and the grading scale live in the main Slop-Mop
project.

Main project: https://github.com/ScienceIsNeato/slop-mop

## Hull Grades

Every full run grades the repo's hull — a deterministic rating computed by
Slop-Mop from how many gates are failing:

| Grade | Hull | Meaning |
| --- | --- | --- |
| A+ | shipshape | All gates green |
| A | seaworthy | All green, with warnings |
| B | serviceable | 1 gate failing |
| C | weathered | 2 gates failing |
| D | fouled | 3 gates failing |
| F | scuttled | 4+ gates failing |
| N/A | dry-dock | Repo never initialized |

The grade headlines the job summary and is exposed as action outputs
(`grade`, `hull`, `failing`, `warned`, `provisional`). Hull grades require
`slopmop >= 2.5.0`; on older versions the grade outputs are empty and the
action still works.

## Usage

```yaml
name: Slop-Mop

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read
  security-events: write
  actions: read

jobs:
  slop-mop:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5

      - uses: ScienceIsNeato/slop-mop-action@v1
        with:
          command: scour
```

Enforce a minimum hull grade (independent of pass/fail):

```yaml
- uses: ScienceIsNeato/slop-mop-action@v1
  with:
    command: scour
    fail-on-failure: "false"   # advisory on gate failures...
    minimum-grade: "B"          # ...but the hull must be serviceable or better
```

For fully advisory mode:

```yaml
- uses: ScienceIsNeato/slop-mop-action@v1
  with:
    fail-on-failure: "false"
```

To skip Code Scanning upload:

```yaml
- uses: ScienceIsNeato/slop-mop-action@v1
  with:
    upload-sarif: "false"
```

Use the grade downstream:

```yaml
- uses: ScienceIsNeato/slop-mop-action@v1
  id: slopmop

- name: Comment grade
  run: echo "Hull rating ${{ steps.slopmop.outputs.grade }} (${{ steps.slopmop.outputs.hull }})"
```

## Inputs

| Input | Default | Description |
| --- | --- | --- |
| `command` | `scour` | Slop-Mop validation command. Supported values: `swab`, `scour`. |
| `args` | `--no-auto-fix` | Extra arguments passed to `sm` before action-managed output flags. |
| `python-version` | `3.12` | Python version used by `actions/setup-python`. |
| `install-extra` | `all` | PyPI extra installed as `slopmop[extra]`. |
| `slopmop-version` | empty | Optional version specifier, for example `>=2.5.0`. |
| `results-file` | `slopmop-results.json` | JSON results file path. |
| `sarif-file` | `slopmop.sarif` | SARIF file path. |
| `upload-sarif` | `true` | Upload SARIF with `github/codeql-action/upload-sarif`. |
| `sarif-category` | `slopmop` | Code Scanning category. |
| `strict-sarif-upload` | `false` | Fail if SARIF upload fails. |
| `fail-on-failure` | `true` | Fail the action when `sm` exits non-zero. |
| `minimum-grade` | empty | Fail when the hull grade is worse than this letter (`A+`, `A`, `B`, `C`, `D`, `F`). Empty disables enforcement. |

## Outputs

| Output | Description |
| --- | --- |
| `result` | `passed` or `failed`, based on the `sm` exit code. |
| `exit_code` | Raw `sm` exit code. |
| `results_file` | JSON results file path. |
| `sarif_file` | SARIF file path. |
| `grade` | Hull grade letter: `A+`, `A`, `B`, `C`, `D`, `F`, or `N/A`. Empty when not emitted. |
| `hull` | Hull condition: `shipshape`, `seaworthy`, `serviceable`, `weathered`, `fouled`, `scuttled`, `dry-dock`. |
| `failing` | Number of failing gates counted toward the grade. |
| `warned` | Number of warned gates. |
| `provisional` | `true` when operational skips may have hidden failing gates. |
| `hull_grade_json` | Compact `hull_grade` JSON object. |
| `grade_met` | `true`/`false` when `minimum-grade` is set and comparable; empty otherwise. |

## SARIF

When `upload-sarif` is `true`, the action uploads the SARIF file produced by
Slop-Mop. The consuming workflow must grant:

```yaml
permissions:
  contents: read
  security-events: write
  actions: read
```

Set `strict-sarif-upload: "true"` if SARIF upload failures should fail the
action. The default keeps adoption forgiving: Slop-Mop's own verdict still
controls the final pass/fail result.

## Grade Semantics

The action does not compute grades. It reads the `hull_grade` object that
Slop-Mop emits in its JSON results (the v3 envelope's `data` payload) and
surfaces it. Notes:

- `N/A` (dry-dock) means the repo has no Slop-Mop configuration yet. It never
  fails `minimum-grade` — the job summary shows the onboarding command
  instead.
- `provisional: true` means operational skips (missing tool, fail-fast, time
  budget) may have hidden failing gates; the letter is a floor, not a final.
- Partial runs (custom `-g` args) don't emit a grade.

## Marketplace Notes

This repository is designed for GitHub Marketplace publication:

- `action.yml` lives at the repository root.
- The repository contains only action metadata, action plumbing, docs, and a
  license.
- No `.github/workflows` directory is included. Test this action from a
  separate scratch repository before publishing releases.
