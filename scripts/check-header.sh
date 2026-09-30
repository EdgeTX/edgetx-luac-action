#!/usr/bin/env bash
# Check that a .luac file has the bytecode header EdgeTX radios expect.
# Usage: check-header.sh <file.luac>...
set -euo pipefail

# signature, version 5.3, format, LUAC_DATA, then sizeof(int),
# sizeof(size_t) (written as int for the radio), Instruction,
# lua_Integer and lua_Number, all 4 bytes
expected=1b4c7561530019930d0a1a0a0404040404

status=0
for f in "$@"; do
  actual=$(od -An -tx1 -N17 "$f" | tr -d ' \n')
  if [ "$actual" != "$expected" ]; then
    echo "::error file=$f::Unexpected bytecode header: $actual (expected $expected)"
    status=1
  fi
done
exit $status
