# EdgeTX Lua compiler action — guide for AI tools

Context for AI tools working in this repository: how the action is built, tested and released, and
the rules that keep it working on every runner.

## 1. Project Overview & Purpose

- **Primary goal:** a GitHub Action that precompiles Lua scripts to EdgeTX bytecode (`.luac`), plus
  standalone `edgetx-luac` binaries attached to each release.
- **Why it exists:** compiling a script on the radio needs far more RAM than running it. On radios with
  little memory (X9D, X9 Lite, …) large scripts fail with "not enough memory"
  ([EdgeTX#7251](https://github.com/EdgeTX/edgetx/issues/7251)). Shipping precompiled `.luac` avoids that.
- **Where the compiler comes from:** it isn't vendored. The action builds `edgetx-luac` from
  `radio/src/thirdparty/Lua` in [EdgeTX/edgetx](https://github.com/EdgeTX/edgetx) at a pinned commit
  (the `edgetx-ref` input's default in `action.yml`). The release binaries are built from that same commit.
- **Compatibility:** the bytecode is identical across EdgeTX 2.11, 2.12 and later. Radios before 2.11 use a
  different Lua and can't load it.

## 2. Core Technologies & Stack

- **Action type:** composite action (`action.yml`). There's no JavaScript and no build step.
- **Scripts:** Python 3, **standard library only**. The action runs them with whatever `python` the
  runner provides, so nothing can be installed at runtime.
- **Compiler build:** CMake plus the runner's C compiler (GCC, Apple clang, MSVC).
- **Dev tooling:** [uv](https://docs.astral.sh/uv/) manages the dev dependency group in `pyproject.toml`
  (`ruff`, `editorconfig-checker`, `actionlint-py`, `shellcheck-py`, `commitizen`, `pre-commit`),
  locked in `uv.lock`. These are for development and CI only and are never used by the action itself.
  `shellcheck-py` is there because actionlint uses whatever shellcheck is on PATH to check `run:`
  scripts. The locked copy makes local runs match CI, whose runner has its own shellcheck.
- **Checks:** `.pre-commit-config.yaml` has only local hooks, and each one runs `uv run --frozen <tool>`.
  `uv.lock` is therefore the single source of tool versions for the hooks, CI and direct `uv run` calls.
  Don't switch hooks to hosted repos with their own `rev`s: that would bring back a second set of
  versions.

## 3. Architecture

```
action.yml                 # composite action: resolve ref -> cache -> sparse checkout -> build -> compile
scripts/
  resolve_ref.py           # edgetx-ref -> commit SHA; sets sha/dir/bin/built step outputs
  build.py                 # cmake configure + build of edgetx-luac, copies the binary out
  compile.py               # glob matching, runs edgetx-luac per file, annotations, `files` output
  check_header.py          # asserts the .luac header matches the radio's 32-bit layout
test/
  conftest.py              # loads scripts/*.py by path; points GITHUB_OUTPUT/STEP_SUMMARY at temp files
  test_*.py                # pytest unit tests, one file per script (subprocess is faked, no network)
  fixtures/ok/             # valid scripts, incl. a nested dir and a dir with a space
  fixtures/bad/broken.lua  # syntax error on line 3 (tests rely on the line number)
.github/workflows/
  test.yml                 # lint job + action tests on ubuntu x64/arm64, macOS, Windows
  release.yml              # on v* tags: build binaries, package, create a DRAFT release
```

**Action flow:** `resolve_ref.py` resolves the ref. If the binary is already in `$RUNNER_TEMP` from an
earlier call in the same job, everything else is skipped. Otherwise `actions/cache` (keyed on
OS + arch + SHA) is tried. On a miss, the action sparse-checks-out only `radio/src/thirdparty/Lua` into
`.edgetx-luac-src`, builds it, and deletes the checkout. Then `compile.py` runs.

**Bytecode header:** `1b4c7561 53 00 19930d0a1a0a 04 04 04 04 04` (signature, Lua 5.3, format, LUAC_DATA,
then int / size_t-as-int / Instruction / lua_Integer / lua_Number, all 4 bytes). EdgeTX writes
`sizeof(int)` where stock Lua writes `sizeof(size_t)`, which is why a 64-bit host build produces
bytecode the radio can load. `check_header.py` holds the expected bytes.

## 4. Coding Conventions

- **Python:** ruff (rules `E F W I UP B SIM`) with 100-character lines, configured in `pyproject.toml`. Format
  with `uv run ruff format`.
- **All files:** `.editorconfig` is enforced in CI. That means 2-space indentation (4 for Python), LF line
  endings, a final newline and no trailing whitespace. `.gitattributes` forces LF on checkout too.
- **Rules learned the hard way. Don't break these:**
  - **Standard library only in `scripts/`.** Adding a dependency breaks every user of the action.
  - **Python 3.12 is the minimum** (`requires-python`), because that's the default `python` on
    `windows-latest` (Windows 2025). Ubuntu 26.04 and macOS ship 3.14. So the Windows test job checks the
    scripts on the minimum version. Raise the minimum only when the oldest runner image the action
    supports ships something newer.
  - **Write `GITHUB_OUTPUT` and `GITHUB_STEP_SUMMARY` with `open(..., "a", newline="\n")`.** Without it,
    Python on Windows writes CRLF and every output value gains a trailing `\r`.
  - **Inline bash in workflows must work on bash 3.2.** That's what macOS runners use for
    `shell: bash`. So no `mapfile`, `globstar`, `declare -A` or `${var,,}`. Put anything non-trivial in a
    Python script instead.
  - **Glob semantics are Python's `glob(recursive=True)`:** `*` stays within a directory, `**/` matches
    any depth, and hidden paths are skipped. The README documents this. Don't hand-roll matching.
  - **Paths in annotations and outputs use forward slashes**, even on Windows (`PurePath.as_posix()`).
  - **Composite steps that compute a value with `$(...)` must assign it first**, so a failure fails the
    step. `echo "x=$(cmd)" >> "$GITHUB_OUTPUT"` swallows errors.
- **Keep the README in sync:** its inputs and outputs tables must match `action.yml`.

## 5. Key Files & Entrypoints

- `action.yml` — inputs, outputs and the step sequence. `inputs.edgetx-ref.default` is the pinned compiler commit.
- `scripts/compile.py` — the part users interact with: matching, compiling and error reporting.
- `.github/workflows/release.yml` — reads the pinned SHA from `action.yml`, so it must stay a full 40-character SHA.
- `pyproject.toml` / `uv.lock` — dev tooling only.
- `README.md` — user documentation. `CONTRIBUTING.md` — contributor and maintainer documentation.

## 6. Development Workflow

```sh
uv sync                              # once: install the dev tools into .venv
uv run pre-commit run --all-files    # all checks, exactly as CI runs them
uv run pytest                        # unit tests
uv run ruff format                   # format Python
```

The hooks check Python with ruff, every file against `.editorconfig`, the workflows with actionlint, that
`uv.lock` matches `pyproject.toml`, run the unit tests whenever a file in `scripts/` or `test/` changes,
and (at the commit-msg stage) check that the message follows Conventional Commits. CI's lint job skips the
pytest hook (`SKIP: pytest`), because the test matrix runs the tests on every platform. A hook that modifies files (`ruff check --fix`, `ruff format`) reports "Failed": re-stage the
changes and commit again.

The unit tests fake `subprocess.run`, so they need neither the compiler nor the network. When you change a
script, add or update its tests, especially for platform-specific behaviour (path separators, newlines),
which CI checks on all four runners. Never let a test write to the real `GITHUB_OUTPUT` or
`GITHUB_STEP_SUMMARY`: the autouse fixture in `conftest.py` redirects them.

Test failure paths (syntax errors, unknown refs) in the unit tests, not with workflow steps that make the
action fail. A deliberately failing `uses: ./` step leaves red failure annotations on a green run, which
hides real failures. If a workflow step must run a failing case, capture its output instead of printing it.

To exercise the scripts for real, you need a checkout of EdgeTX/edgetx:

```sh
python scripts/build.py ../edgetx /tmp/luac
LUAC=/tmp/luac/edgetx-luac FILES='test/fixtures/ok/**/*.lua' CHECK_ONLY=true python scripts/compile.py
python scripts/check_header.py some.luac
```

`compile.py` reads `LUAC`, `FILES`, `STRIP`, `CHECK_ONLY`, `OUTPUT_DIR` and `EXCLUDE` from the
environment (see its docstring).

## 7. CI/CD

| Workflow | Trigger | What it does |
|---|---|---|
| `test.yml` | push to `main`, PRs, manual | **Lint** (`pre-commit run --all-files`) and **Test**: pytest unit tests with the runner's own
python, then the action via `uses: ./`, on ubuntu-26.04, ubuntu-26.04-arm, macos-latest and windows-latest: fixtures, output dir, glob rules, and the real compiler's error format |
| `release.yml` | `v[0-9]+.[0-9]+.[0-9]+*` tags | Builds static Linux x64/arm64, universal macOS and static-CRT Windows binaries, smoke-tests them, packages them with both licences, and creates a **draft** release |

- **Runners:** every Ubuntu job (test and release) uses the same LTS image, `ubuntu-26.04` /
  `ubuntu-26.04-arm`. macOS and Windows use `-latest`. The Linux release binaries are statically linked,
  so the build image's glibc doesn't limit where they run: the only requirement is the minimum kernel,
  which the release smoke test prints.
  `.github/actionlint.yaml` declares the 26.04 labels only because actionlint v1.7.12 doesn't know
  them yet. Delete it once actionlint does.
- **Dependabot** (`.github/dependabot.yml`) opens monthly grouped PRs for `uv.lock` and for the actions used
  in the workflows and `action.yml`.
- **`main` is protected by a ruleset (named `main`):** changes go through a PR, merges are squash only, and
  force-pushes and deletion are blocked. Merging requires the checks `Lint`, `Test (ubuntu-26.04)`,
  `Test (ubuntu-26.04-arm)`, `Test (macos-latest)` and `Test (windows-latest)`. These are matched by job
  name, so **if you rename a job or change the test matrix, update the ruleset's required checks in the
  same change.** Otherwise every PR waits for a check that never runs. Tags aren't covered, so moving `v1`
  still works.
- **Action version policy:** reference actions by their latest **major** tag (`actions/checkout@v7`).
  `astral-sh/setup-uv` publishes immutable releases with no moving major tag, so pin it to the latest
  exact version (`@v10.2.0`).
- **Updating the compiler:** set `inputs.edgetx-ref.default` to a new full EdgeTX commit SHA. Never pick a
  commit from before EdgeTX/edgetx#7848, because MSVC can't build those (Windows would break).
- **Versioning:** the action uses its own semver, not EdgeTX's version numbers. Bump the **major** only if
  EdgeTX changes its bytecode format, and add a row to the README compatibility table.
- **Releasing:** the steps are in `CONTRIBUTING.md`. Agents must not push release tags or publish releases
  unless explicitly asked.

## 8. AI Collaboration Guidelines

### Commits

- Use Conventional Commits, as EdgeTX does: `type(scope): description`, e.g.
  `fix(compile): keep paths POSIX on Windows`. The commit-msg hook (`cz check`) enforces this.
- Commits authored by an AI agent must include a trailer identifying the model, e.g.
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Never amend or rewrite commits that have been pushed. Fix things with a follow-up commit. PRs are
  squash-merged, so the follow-ups don't end up in `main`'s history.

### Pull Requests

Make changes on a branch and open a PR against `main` of `EdgeTX/edgetx-luac-action`. Run
`uv run pre-commit run --all-files` first. CI runs the action on all four platforms, so check the
Windows and macOS jobs as well as Linux.

### What Lives Where

- Agent-facing guidance → `AGENTS.md` (this file). `CLAUDE.md` only imports it.
- User-facing documentation → `README.md`.
- Contributor and maintainer documentation (setup, updating the compiler, releasing) → `CONTRIBUTING.md`.
- Don't duplicate content across these files.
