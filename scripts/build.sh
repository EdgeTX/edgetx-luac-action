#!/usr/bin/env bash
# Build edgetx-luac from an EdgeTX source tree and copy it to <out-dir>.
# Usage: build.sh <edgetx-src> <out-dir> [extra cmake args...]
set -euo pipefail

src=$1
out=$2
shift 2

build=$(mktemp -d)
args=(-DCMAKE_BUILD_TYPE=Release)

case "$(uname -s)" in
  MINGW* | MSYS* | CYGWIN*)
    # older EdgeTX refs only declare alloca() for GCC/clang
    args+=("-DCMAKE_C_FLAGS=/FImalloc.h /Dalloca=_alloca")
    ;;
esac

cmake -S "$src/radio/src/thirdparty/Lua" -B "$build" "${args[@]}" "$@"
cmake --build "$build" --config Release

bin=$(find "$build" -type f \( -name edgetx-luac -o -name edgetx-luac.exe \) | head -1)
if [ -z "$bin" ]; then
  echo "::error::edgetx-luac binary not found after build" >&2
  exit 1
fi

mkdir -p "$out"
cp "$bin" "$out/"
rm -rf "$build"
