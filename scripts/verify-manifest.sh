#!/usr/bin/env bash
#
# Drift guard for the committed dependency manifest.
#
# The committed required-deps.json can silently fall out of sync with the repo's
# actual gate config (someone toggles a gate but forgets to regenerate). This
# emits the live manifest from the installed slop-mop and compares it to the
# committed file; a mismatch fails the run with a regenerate hint.
#
# Compared canonically (jq -S, sorted keys) so formatting/key-order differences
# never cause a false mismatch — only a genuine content drift fails.
#
# Inputs (environment):
#   MANIFEST_FILE  path to the committed required-deps.json (required)
#   DRY_RUN        when "1", report drift but exit 0 (for local testing)
#
set -uo pipefail

MANIFEST_FILE="${MANIFEST_FILE:-.slopmop/required-deps.json}"
DRY_RUN="${DRY_RUN:-0}"

fail() {
  echo "::error::$*" >&2
  exit 1
}

command -v jq >/dev/null 2>&1 || fail "jq is required to compare manifests."
command -v sm >/dev/null 2>&1 || fail "sm not on PATH — cannot emit the live manifest."
[[ -f "$MANIFEST_FILE" ]] || fail "Committed manifest not found: ${MANIFEST_FILE}. Generate it with 'sm doctor --required-deps > ${MANIFEST_FILE}' and commit it."

live="$(mktemp)"
trap 'rm -f "$live"' EXIT
sm doctor --required-deps >"$live" 2>/dev/null || fail "sm doctor --required-deps failed — is slop-mop new enough to support it?"

if diff -u <(jq -S . "$MANIFEST_FILE") <(jq -S . "$live"); then
  echo "Committed manifest is in sync with the repo's gate config."
  exit 0
fi

echo "::error::Committed manifest ${MANIFEST_FILE} is stale (differs from the live gate config above)."
echo "::error::Regenerate it:  sm doctor --required-deps > ${MANIFEST_FILE}  and commit the result."
[[ "$DRY_RUN" == "1" ]] && exit 0
exit 1
