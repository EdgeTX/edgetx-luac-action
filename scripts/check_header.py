"""Check that .luac files have the bytecode header EdgeTX radios expect.

Usage: check_header.py <file.luac>...
"""

import sys

# signature, version 5.3, format, LUAC_DATA, then sizeof(int),
# sizeof(size_t) (written as int for the radio), Instruction,
# lua_Integer and lua_Number, all 4 bytes
EXPECTED = bytes.fromhex("1b4c7561530019930d0a1a0a0404040404")


def main(paths: list[str]) -> int:
    status = 0
    for path in paths:
        try:
            with open(path, "rb") as f:
                actual = f.read(len(EXPECTED))
        except OSError as e:
            print(f"::error file={path}::{e.strerror}")
            status = 1
            continue
        if actual != EXPECTED:
            print(
                f"::error file={path}::Unexpected bytecode header: "
                f"{actual.hex()} (expected {EXPECTED.hex()})"
            )
            status = 1
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
