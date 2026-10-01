"""Build edgetx-luac from an EdgeTX source tree and copy it to an output directory.

Usage: build.py <edgetx-src> <out-dir> [extra cmake args...]
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

NAMES = {"edgetx-luac", "edgetx-luac.exe"}


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    src, out, extra = Path(argv[0]), Path(argv[1]), argv[2:]
    lua = src / "radio" / "src" / "thirdparty" / "Lua"

    # MSBuild can hold files open briefly after a build, so don't fail on cleanup
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        build = Path(tmp)
        try:
            subprocess.run(
                ["cmake", "-S", lua, "-B", build, "-DCMAKE_BUILD_TYPE=Release", *extra],
                check=True,
            )
            subprocess.run(["cmake", "--build", build, "--config", "Release"], check=True)
        except subprocess.CalledProcessError as e:
            return e.returncode

        binary = next((p for p in build.rglob("*") if p.name in NAMES and p.is_file()), None)
        if binary is None:
            print("::error::edgetx-luac binary not found after build")
            return 1

        out.mkdir(parents=True, exist_ok=True)
        shutil.copy2(binary, out / binary.name)

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
