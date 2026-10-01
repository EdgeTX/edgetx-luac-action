"""Resolve the EdgeTX ref to build edgetx-luac from.

Usage: resolve_ref.py <owner/repo> <ref>

Prints the full commit SHA. In a workflow it also sets these step outputs:
    sha    full commit SHA
    dir    directory to keep the built binary in
    bin    path to the binary
    built  "true" if an earlier step in this job already built it
"""

import os
import re
import subprocess
import sys
from pathlib import Path


def resolve(repo: str, ref: str) -> str | None:
    """Return the commit SHA for a branch, tag or SHA, or None if not found."""
    if re.fullmatch(r"[0-9a-f]{40}", ref):
        return ref

    # prefer the commit a tag points at, then the tag, then a branch
    wanted = [f"refs/tags/{ref}^{{}}", f"refs/tags/{ref}", f"refs/heads/{ref}"]
    result = subprocess.run(
        ["git", "ls-remote", f"https://github.com/{repo}", *wanted],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"::error::git ls-remote failed for {repo}: {result.stderr.strip()}")
        return None

    refs: dict[str, str] = {}
    for line in result.stdout.splitlines():
        sha, name = line.split("\t")
        refs[name] = sha
    return next((refs[name] for name in wanted if name in refs), None)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    repo, ref = argv

    sha = resolve(repo, ref)
    if not sha:
        print(f"::error::Could not find '{ref}' in {repo} (use a branch, tag or full commit SHA)")
        return 1
    print(sha)

    if "GITHUB_OUTPUT" in os.environ:
        bin_dir = Path(os.environ["RUNNER_TEMP"], "edgetx-luac", sha)
        binary = bin_dir / ("edgetx-luac.exe" if os.name == "nt" else "edgetx-luac")
        with open(os.environ["GITHUB_OUTPUT"], "a", newline="\n") as f:
            f.write(f"sha={sha}\ndir={bin_dir}\nbin={binary}\n")
            if binary.is_file():
                f.write("built=true\n")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
