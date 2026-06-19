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
| `slopmop-version` | `==2.5.0` | Version specifier. Pinned by default for deterministic install caching; the Slop-Mop release workflow bumps it on each release. Override (e.g. `>=2.5.0`) to track a range. See [Gate tools & caching](#gate-tools--caching). |
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

## Gate tools & caching

Several gates wrap off-the-shelf tools — `flake8`, `black`, `vulture`, `radon`
(Python), and `find-duplicate-strings` (Node). The action installs them so the
gates actually run instead of warning and passing:

- Slop-Mop is installed with `pipx install --include-deps`, which exposes the
  Python tools' console scripts on `PATH` (plain `pipx install` only exposes
  `sm`).
- Node is set up and `find-duplicate-strings` is installed globally for the
  `myopia:string-duplication` gate.
- The whole install (pipx venv + Node tool) is cached with `actions/cache`,
  keyed on OS + resolved Python version + extra + `slopmop-version`, so a
  cache hit skips reinstallation entirely.

`slopmop-version` is **pinned by default** (and part of the cache key), so the
cache refreshes exactly when the pin changes. The Slop-Mop release workflow
opens a PR here to bump the pin on every release, so it tracks the latest
release without manual edits. Override the input to track a range (e.g.
`>=2.5.0`) — note that a range reintroduces cache staleness, since the key
then stays constant while the resolved version drifts.

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
