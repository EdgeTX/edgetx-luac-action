#!/usr/bin/env bash
# Compile (or syntax-check) Lua scripts with edgetx-luac.
#
# Environment:
#   LUAC        path to the edgetx-luac binary
#   FILES       newline-separated glob patterns
#   STRIP       "true" to strip debug information
#   CHECK_ONLY  "true" to only check syntax, writing nothing
#   OUTPUT_DIR  directory for .luac files (default: next to each source)
#   EXCLUDE     directory to leave out of the matches
set -uo pipefail

if ((BASH_VERSINFO[0] < 4)); then
  echo "::error::bash 4 or later is required (found $BASH_VERSION)"
  exit 1
fi
shopt -s globstar nullglob

: "${LUAC:?}" "${FILES:?}"
STRIP=${STRIP:-true}
CHECK_ONLY=${CHECK_ONLY:-false}
OUTPUT_DIR=${OUTPUT_DIR:-}
EXCLUDE=${EXCLUDE:-}

# escape a workflow command message
escape() {
  local s=${1//'%'/'%25'}
  s=${s//$'\r'/'%0D'}
  s=${s//$'\n'/'%0A'}
  printf '%s' "$s"
}

declare -A seen=()
scripts=()
while IFS= read -r pattern; do
  pattern=${pattern#"${pattern%%[![:space:]]*}"}
  pattern=${pattern%"${pattern##*[![:space:]]}"}
  [ -z "$pattern" ] && continue

  # split on newlines only, so patterns may contain spaces
  IFS=$'\n'
  # shellcheck disable=SC2206
  matches=($pattern)
  unset IFS

  for f in "${matches[@]}"; do
    f=${f#./}
    [ -f "$f" ] || continue
    [[ $f == *.lua ]] || continue
    [ -n "$EXCLUDE" ] && [[ $f == "$EXCLUDE"/* ]] && continue
    [ -n "${seen[$f]:-}" ] && continue
    seen[$f]=1
    scripts+=("$f")
  done
done <<< "$FILES"

if [ ${#scripts[@]} -eq 0 ]; then
  echo "::error::No .lua files matched: $(escape "$FILES")"
  exit 1
fi

failed=0
outputs=()
for f in "${scripts[@]}"; do
  if [ "$CHECK_ONLY" = true ]; then
    args=(-p "$f")
  else
    if [ -n "$OUTPUT_DIR" ]; then
      out="${OUTPUT_DIR%/}/${f%.lua}.luac"
      mkdir -p "$(dirname "$out")"
    else
      out="${f%.lua}.luac"
    fi
    args=(-o "$out" "$f")
    [ "$STRIP" = true ] && args=(-s "${args[@]}")
  fi

  if err=$("$LUAC" "${args[@]}" 2>&1); then
    if [ "$CHECK_ONLY" = true ]; then
      echo "ok  $f"
    else
      echo "ok  $f -> $out"
      outputs+=("$out")
    fi
    continue
  fi

  failed=$((failed + 1))
  # "<progname>: <chunk>:<line>: <message>"
  msg=${err#*: }
  if [[ $msg =~ ^[^:]*:([0-9]+):\ (.*)$ ]]; then
    echo "::error file=$f,line=${BASH_REMATCH[1]}::$(escape "${BASH_REMATCH[2]}")"
  else
    echo "::error file=$f::$(escape "$msg")"
  fi
done

if [ -n "${GITHUB_OUTPUT:-}" ]; then
  {
    echo "files<<EDGETX_LUAC_EOF"
    [ ${#outputs[@]} -gt 0 ] && printf '%s\n' "${outputs[@]}"
    echo "EDGETX_LUAC_EOF"
  } >> "$GITHUB_OUTPUT"
fi

verb=$([ "$CHECK_ONLY" = true ] && echo checked || echo compiled)
summary="edgetx-luac: $verb $((${#scripts[@]} - failed)) of ${#scripts[@]} scripts"
[ $failed -gt 0 ] && summary+=", $failed failed"
echo "$summary"
[ -n "${GITHUB_STEP_SUMMARY:-}" ] && echo "$summary" >> "$GITHUB_STEP_SUMMARY"

[ $failed -eq 0 ]
