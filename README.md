# Slop-Mop GitHub Action

Run Slop-Mop in GitHub Actions.

This repository is intentionally small. The action installs the `slopmop`
Python package, runs `sm swab` or `sm scour`, writes Slop-Mop's JSON and SARIF
outputs, optionally uploads SARIF to GitHub Code Scanning, and reports the
result in the job summary. Gate behavior, SARIF shape, JSON schema, and posture
labels live in the main Slop-Mop project.

Main project: https://github.com/ScienceIsNeato/slop-mop

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
      - uses: actions/checkout@v4

      - uses: ScienceIsNeato/slop-mop-action@v1
        with:
          command: scour
```

For advisory mode:

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

## Inputs

| Input | Default | Description |
| --- | --- | --- |
| `command` | `scour` | Slop-Mop validation command. Supported values: `swab`, `scour`. |
| `args` | `--no-auto-fix` | Extra arguments passed to `sm` before action-managed output flags. |
| `python-version` | `3.12` | Python version used by `actions/setup-python`. |
| `install-extra` | `all` | PyPI extra installed as `slopmop[extra]`. |
| `slopmop-version` | empty | Optional version specifier, for example `==1.2.3`. |
| `results-file` | `slopmop-results.json` | JSON results file path. |
| `sarif-file` | `slopmop.sarif` | SARIF file path. |
| `upload-sarif` | `true` | Upload SARIF with `github/codeql-action/upload-sarif`. |
| `sarif-category` | `slopmop` | Code Scanning category. |
| `strict-sarif-upload` | `false` | Fail if SARIF upload fails. |
| `fail-on-failure` | `true` | Fail the action when `sm` exits non-zero. |

## Outputs

| Output | Description |
| --- | --- |
| `result` | `passed` or `failed`, based on the `sm` exit code. |
| `exit_code` | Raw `sm` exit code. |
| `results_file` | JSON results file path. |
| `sarif_file` | SARIF file path. |
| `myopia` | Slop-Mop posture label for myopia, when emitted by Slop-Mop. |
| `deceptiveness` | Slop-Mop posture label for deceptiveness, when emitted by Slop-Mop. |
| `laziness` | Slop-Mop posture label for laziness, when emitted by Slop-Mop. |
| `overconfidence` | Slop-Mop posture label for overconfidence, when emitted by Slop-Mop. |
| `posture_json` | Compact posture JSON, when emitted by Slop-Mop. |

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

## Posture Labels

The action does not compute Slop-Mop posture labels. It only displays labels
when Slop-Mop includes a top-level `posture` object in its JSON output. This
keeps the Marketplace wrapper stable while the rubric evolves in Slop-Mop
proper.

## Marketplace Notes

This repository is designed for GitHub Marketplace publication:

- `action.yml` lives at the repository root.
- The repository contains only action metadata, action plumbing, docs, and a
  license.
- No `.github/workflows` directory is included. Test this action from a
  separate scratch repository before publishing releases.
