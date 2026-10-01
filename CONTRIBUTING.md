# Contributing

## Setup

- **Python 3.9 or later**, to run the scripts.
- **[uv](https://docs.astral.sh/uv/)**, for the lint tools. `uv run …` installs them from `uv.lock` on first use.
- To build the compiler locally: **CMake**, a **C compiler**, and a checkout of
  [EdgeTX/edgetx](https://github.com/EdgeTX/edgetx).

## How it fits together

`action.yml` is a composite action whose steps are Python scripts in `scripts/`:

| Script | Does |
| ------ | ---- |
| `resolve_ref.py` | Turns `edgetx-ref` into a commit SHA and works out where the binary is cached |
| `build.py` | Builds `edgetx-luac` with CMake |
| `compile.py` | Matches the globs and compiles or checks each script |
| `check_header.py` | Checks `.luac` headers (used by the tests and the release workflow) |

The scripts use only the Python standard library, because the action runs them with the runner's own
`python` and can't install anything. Please keep it that way.

## Code style

CI checks these, so run them before opening a PR:

```sh
uv run ruff check
uv run ruff format --check   # or `uv run ruff format` to fix
uv run ec                    # every file follows .editorconfig
```

## Testing locally

Build the compiler from your EdgeTX checkout, then run the scripts against the fixtures:

```sh
python scripts/build.py ../edgetx /tmp/luac
LUAC=/tmp/luac/edgetx-luac FILES='test/fixtures/ok/**/*.lua' CHECK_ONLY=true python scripts/compile.py
```

The test workflow runs the action itself on Linux (x64 and arm64), macOS and Windows. Check all four jobs:
most of the bugs found so far only showed up on one platform.

## Commits and pull requests

- Use [Conventional Commits](https://www.conventionalcommits.org): `type(scope): description`.
- Open PRs against `main`. They're squash-merged, so fix review comments with follow-up commits rather
  than rewriting what you've pushed.
- If you change an input or output, update the tables in `README.md` to match.

## Updating the compiler

Set `inputs.edgetx-ref.default` in `action.yml` to the new EdgeTX commit's **full** SHA, and open a PR.
The test workflow builds that commit on every platform, and the release workflow builds the binaries
from the same commit.

Don't use a commit from before [EdgeTX/edgetx#7848](https://github.com/EdgeTX/edgetx/pull/7848).
Earlier commits don't build with MSVC, so Windows would break.

## Releasing

1. Tag the release: `git tag v1.2.3 && git push origin v1.2.3`.
   Tags with a suffix (`v1.2.3-rc1`) become pre-releases.
2. The release workflow builds the binaries and creates a **draft** release.
   Check the assets and notes, then publish it.
3. Move the major tag: `git tag -f v1 v1.2.3 && git push -f origin v1`.

The version is the action's own, not EdgeTX's. Bump the major only when EdgeTX changes its bytecode
format, and add a row to the compatibility table in `README.md`.

## AI tools

[`AGENTS.md`](AGENTS.md) is the guide for AI tools. Most read it directly, and `CLAUDE.md` imports it for
Claude Code. Update it when the workflow changes, or when you find yourself correcting an AI tool on the
same point twice.
