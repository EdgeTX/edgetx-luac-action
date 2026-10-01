"""Compile (or syntax-check) Lua scripts with edgetx-luac.

Environment:
    LUAC        path to the edgetx-luac binary
    FILES       newline-separated glob patterns
    STRIP       "true" to strip debug information
    CHECK_ONLY  "true" to only check syntax, writing nothing
    OUTPUT_DIR  directory for .luac files (default: next to each source)
    EXCLUDE     directory to leave out of the matches
"""

import glob
import os
import re
import subprocess
import sys
from pathlib import Path, PurePath


def escape(message: str) -> str:
    """Escape a workflow command message."""
    return message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def find_scripts(patterns: str, exclude: str) -> list[str]:
    """Expand glob patterns to .lua files, in order and without duplicates."""
    scripts: dict[str, None] = {}  # a dict keeps first-seen order
    for pattern in patterns.splitlines():
        pattern = pattern.strip()
        if not pattern:
            continue
        for match in sorted(glob.glob(pattern, recursive=True)):
            path = PurePath(os.path.normpath(match))
            if path.suffix != ".lua" or not os.path.isfile(path):
                continue
            if exclude and path.is_relative_to(exclude):
                continue
            scripts[path.as_posix()] = None
    return list(scripts)


def annotate(script: str, error: str) -> None:
    """Report an edgetx-luac error as an annotation on the script."""
    # "<progname>: <chunk>:<line>: <message>"
    message = error.strip().split(": ", 1)[-1]
    m = re.match(r"[^:]*:(\d+): (.*)", message, re.DOTALL)
    if m:
        print(f"::error file={script},line={m[1]}::{escape(m[2])}")
    else:
        print(f"::error file={script}::{escape(message)}")


def main() -> int:
    luac = os.environ["LUAC"]
    patterns = os.environ["FILES"]
    strip = os.environ.get("STRIP", "true") == "true"
    check_only = os.environ.get("CHECK_ONLY", "false") == "true"
    output_dir = os.environ.get("OUTPUT_DIR", "")

    scripts = find_scripts(patterns, os.environ.get("EXCLUDE", ""))
    if not scripts:
        print(f"::error::No .lua files matched: {escape(patterns)}")
        return 1

    failed = 0
    outputs: list[str] = []
    for script in scripts:
        if check_only:
            out = None
            args = ["-p", script]
        else:
            out = script.removesuffix(".lua") + ".luac"
            if output_dir:
                out = PurePath(output_dir, out).as_posix()
                Path(out).parent.mkdir(parents=True, exist_ok=True)
            args = (["-s"] if strip else []) + ["-o", out, script]

        result = subprocess.run([luac] + args, capture_output=True, text=True)
        if result.returncode != 0:
            failed += 1
            annotate(script, result.stderr or result.stdout)
        elif out:
            print(f"ok  {script} -> {out}")
            outputs.append(out)
        else:
            print(f"ok  {script}")

    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a", newline="\n") as f:
            f.write("files<<EDGETX_LUAC_EOF\n")
            f.writelines(f"{out}\n" for out in outputs)
            f.write("EDGETX_LUAC_EOF\n")

    verb = "checked" if check_only else "compiled"
    summary = f"edgetx-luac: {verb} {len(scripts) - failed} of {len(scripts)} scripts"
    if failed:
        summary += f", {failed} failed"
    print(summary)
    if "GITHUB_STEP_SUMMARY" in os.environ:
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", newline="\n") as f:
            f.write(summary + "\n")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
