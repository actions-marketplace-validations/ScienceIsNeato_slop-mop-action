#!/usr/bin/env bash
#
# Install the external tools a repo's slop-mop gates need, read from a
# committed dependency manifest (`sm doctor --required-deps`).
#
# Why a committed manifest instead of `pipx install slopmop[all]`?
#   - Deterministic: every tool is installed by exact pin, only the tools THIS
#     repo's config actually uses — not the whole `[all]` extra.
#   - Auditable: the manifest is in the repo, so what CI installs is reviewable.
#
# Install strategy is keyed on the requirement's `kind` (install channel) only;
# the `probe` (how presence is detected) is deliberately ignored here:
#   - python: injected into slop-mop's own pipx venv with --include-apps, which
#     BOTH exposes the tool's console scripts on PATH (binary-probed gates) AND
#     makes the package importable from slop-mop's env (import-probed gates).
#     One channel covers both probe kinds, so this script never branches on it.
#   - npm: installed global under a local --prefix (no runner npm-config mutation).
#   - system: cannot be pip/npm-installed (node, dart, flutter, actionlint) —
#     verified-present-or-warned; the caller provides them via setup-* actions.
#   - env: not an installable tool — skipped.
#
# Inputs (environment):
#   MANIFEST_FILE  path to the committed required-deps.json (required)
#   PIPX_VENV      pipx venv name slop-mop was installed as (default: slopmop)
#   NPM_PREFIX     --prefix for global npm installs (required for npm deps)
#   DRY_RUN        when "1", print the resolved commands instead of running them
#
set -uo pipefail

MANIFEST_FILE="${MANIFEST_FILE:-.slopmop/required-deps.json}"
PIPX_VENV="${PIPX_VENV:-slopmop}"
NPM_PREFIX="${NPM_PREFIX:-}"
DRY_RUN="${DRY_RUN:-0}"

fail() {
  echo "::error::$*" >&2
  exit 1
}

command -v jq >/dev/null 2>&1 || fail "jq is required to parse the manifest."
[[ -f "$MANIFEST_FILE" ]] || fail "Manifest not found: ${MANIFEST_FILE}. Generate it with 'sm doctor --required-deps > ${MANIFEST_FILE}'."

schema="$(jq -r '.schema_version // empty' "$MANIFEST_FILE")"
[[ -n "$schema" ]] || fail "Manifest ${MANIFEST_FILE} has no schema_version — is it a valid required-deps document?"
if [[ "$schema" != "1" ]]; then
  echo "::warning::Manifest schema_version ${schema} is newer than this action understands (1). Installing best-effort."
fi

run() {
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "+ $*"
  else
    echo "+ $*"
    "$@" || fail "Command failed: $*"
  fi
}

# --- python tools: one batched pipx inject (exact pins) -------------------
# `<name>` or `<name>==<version>` when a pin is declared. Batching keeps it to a
# single resolver run for the whole set.
mapfile -t py_specs < <(
  jq -r '
    .requirements[]
    | select(.kind == "python")
    | if (.version // "") == "" then .name else "\(.name)==\(.version)" end
  ' "$MANIFEST_FILE"
)

if [[ "${#py_specs[@]}" -gt 0 ]]; then
  run pipx inject "$PIPX_VENV" --include-apps "${py_specs[@]}"
else
  echo "No python tools in manifest."
fi

# --- npm tools: global install under a local prefix -----------------------
mapfile -t npm_specs < <(
  jq -r '
    .requirements[]
    | select(.kind == "npm")
    | if (.version // "") == "" then .name else "\(.name)@\(.version)" end
  ' "$MANIFEST_FILE"
)

if [[ "${#npm_specs[@]}" -gt 0 ]]; then
  [[ -n "$NPM_PREFIX" ]] || fail "Manifest declares npm tools but NPM_PREFIX is unset."
  run npm install --global --prefix "$NPM_PREFIX" "${npm_specs[@]}"
else
  echo "No npm tools in manifest."
fi

# --- system tools: verify present, warn (cannot install generically) ------
missing_system=()
while IFS= read -r tool; do
  [[ -n "$tool" ]] || continue
  if command -v "$tool" >/dev/null 2>&1; then
    echo "system tool present: ${tool}"
  else
    missing_system+=("$tool")
  fi
done < <(jq -r '.requirements[] | select(.kind == "system") | .name' "$MANIFEST_FILE")

if [[ "${#missing_system[@]}" -gt 0 ]]; then
  echo "::warning::System tools not on PATH: ${missing_system[*]}. Provide them via a setup-* step (e.g. setup-node) or the corresponding gate will warn-and-skip."
fi

echo "Dependency install complete."
