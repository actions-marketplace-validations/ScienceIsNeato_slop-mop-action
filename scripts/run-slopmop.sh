#!/usr/bin/env bash
set -uo pipefail
set -f

command_name="${SLOPMOP_COMMAND:-scour}"
extra_args="${SLOPMOP_ARGS:-}"
results_file="${SLOPMOP_RESULTS_FILE:-slopmop-results.json}"
sarif_file="${SLOPMOP_SARIF_FILE:-slopmop.sarif}"
exit_code=0

case "$command_name" in
  swab | scour)
    ;;
  *)
    echo "::error::Unsupported Slop-Mop command '${command_name}'. Use 'swab' or 'scour'."
    exit_code=2
    ;;
esac

mkdir -p "$(dirname "$results_file")" "$(dirname "$sarif_file")"

if [[ "$exit_code" == "0" ]]; then
  if ! command -v sm >/dev/null 2>&1; then
    echo "::error::sm was not found on PATH after installation."
    exit_code=127
  else
    cmd=(sm "$command_name")
    if [[ -n "$extra_args" ]]; then
      # This action is intentionally thin. Keep complex Slop-Mop settings in
      # .sb_config.json; this split supports the simple CLI flags used in CI.
      read -r -a user_args <<< "$extra_args"
      cmd+=("${user_args[@]}")
    fi
    cmd+=(
      --sarif
      --output-file "$sarif_file"
      --json-file "$results_file"
      --no-json
    )

    echo "::group::Run Slop-Mop"
    set +e
    "${cmd[@]}"
    exit_code=$?
    set -e
    echo "::endgroup::"
  fi
fi

python "$GITHUB_ACTION_PATH/scripts/collect-outputs.py" \
  --exit-code "$exit_code" \
  --results-file "$results_file" \
  --sarif-file "$sarif_file" \
  --minimum-grade "${SLOPMOP_MINIMUM_GRADE:-}"

exit 0
