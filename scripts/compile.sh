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
# Written for bash 3.2, which is what macOS runners provide: no globstar,
# associative arrays or mapfile.

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

# Convert a glob to an anchored extended regex, following bash's globstar
# rules: '*' and '?' stay within a path component, '**/' matches any
# number of directories and a trailing '**' matches everything below.
glob_to_regex() {
  local glob=$1 re='' c i=0 n=${#1}
  while ((i < n)); do
    c=${glob:i:1}
    case "$c" in
      '*')
        if [ "${glob:i:3}" = '**/' ]; then
          re+='(.*/)?'
          i=$((i + 2))
        elif [ "${glob:i:2}" = '**' ]; then
          re+='.*'
          i=$((i + 1))
        else
          re+='[^/]*'
        fi
        ;;
      '?') re+='[^/]' ;;
      '[')
        # copy a bracket expression through, turning '[!' into '[^'
        local j=$((i + 1)) class='['
        [ "${glob:j:1}" = '!' ] && class+='^' && j=$((j + 1))
        [ "${glob:j:1}" = ']' ] && class+=']' && j=$((j + 1))
        while ((j < n)) && [ "${glob:j:1}" != ']' ]; do
          class+=${glob:j:1}
          j=$((j + 1))
        done
        if ((j < n)); then
          re+="$class]"
          i=$j
        else
          re+='\['
        fi
        ;;
      '.' | '+' | '(' | ')' | '{' | '}' | '|' | '^' | '$' | "\\")
        re+="\\$c"
        ;;
      *) re+=$c ;;
    esac
    i=$((i + 1))
  done
  printf '^%s$' "$re"
}

# print the files matching a glob, one per line, sorted
expand_glob() {
  local glob=${1#./} root re hidden=false dot='(^|/)\.'
  re=$(glob_to_regex "$glob")

  # start from the directory part before the first wildcard
  root=${glob%%[*?[]*}
  case "$root" in
    */*) root=${root%/*} ;;
    *) root=. ;;
  esac

  # like bash globs, skip hidden files and directories unless asked for
  [[ $glob =~ $dot ]] && hidden=true

  find "$root" -type f 2>/dev/null | sed 's|^\./||' | LC_ALL=C sort |
    while IFS= read -r f; do
      [ $hidden = false ] && [[ $f =~ $dot ]] && continue
      [[ $f =~ $re ]] && printf '%s\n' "$f"
    done
}

seen=$'\n'
scripts=()
while IFS= read -r pattern; do
  pattern=${pattern#"${pattern%%[![:space:]]*}"}
  pattern=${pattern%"${pattern##*[![:space:]]}"}
  [ -z "$pattern" ] && continue

  while IFS= read -r f; do
    [[ $f == *.lua ]] || continue
    [ -n "$EXCLUDE" ] && [[ $f == "$EXCLUDE"/* ]] && continue
    case "$seen" in *$'\n'"$f"$'\n'*) continue ;; esac
    seen+="$f"$'\n'
    scripts+=("$f")
  done < <(expand_glob "$pattern")
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
