# EdgeTX Lua compiler action

Precompiles Lua scripts to EdgeTX bytecode (`.luac`) in GitHub Actions, and publishes
a standalone `edgetx-luac` compiler for Linux, macOS and Windows.

When a radio loads a `.lua` file, it compiles it on the radio first. Compiling needs much
more memory than running the result. On radios with little RAM (X9D, X9 Lite, …) large
scripts can fail with *"not enough memory"* even though they would run fine
([EdgeTX#7251](https://github.com/EdgeTX/edgetx/issues/7251)). Shipping precompiled `.luac`
files avoids that step.

## Compatibility

| Action | Bytecode for |
| ------ | ------------ |
| `v1`   | EdgeTX 2.11.0 and later |

Radios older than 2.11 use a different Lua version and can't load this bytecode.

## Usage

```yaml
- uses: actions/checkout@v7

- uses: EdgeTX/edgetx-luac-action@v1
  with:
    files: |
      SCRIPTS/**/*.lua
      WIDGETS/**/*.lua
```

This writes a `.luac` next to each matched `.lua` file. Then package both files as usual:

```yaml
- run: zip -r my-scripts.zip SCRIPTS WIDGETS
```

### Inputs

| Input | Default | Description |
| ----- | ------- | ----------- |
| `files` | `**/*.lua` | Newline-separated glob patterns, relative to the workspace. `**` matches any depth. Files that don't end in `.lua` are skipped. |
| `strip` | `true` | Strip debug information. The files are smaller, but runtime errors lose line numbers. The radio strips too when it compiles. |
| `check-only` | `false` | Only check syntax and write nothing. This is useful as a lint step on pull requests. |
| `output-dir` | | Write `.luac` files here, keeping each script's relative path, instead of next to the source. |
| `edgetx-ref` | pinned commit | Branch, tag or full commit SHA of EdgeTX to build the compiler from. Each release of this action pins a tested commit. |
| `edgetx-repo` | `EdgeTX/edgetx` | Repository to build the compiler from, e.g. a fork, to test compiler changes. |

### Outputs

| Output | Description |
| ------ | ----------- |
| `files` | Newline-separated list of the `.luac` files written. |
| `luac` | Path to the `edgetx-luac` binary, for running it directly in later steps. |

Syntax errors appear as annotations on the offending line, and the action then fails.

### Lint on pull requests

```yaml
- uses: EdgeTX/edgetx-luac-action@v1
  with:
    check-only: true
```

## How the radio chooses between `.lua` and `.luac`

When both files exist, the radio loads whichever is **newer**. The `.luac` wins if they're
the same age. The action writes each `.luac` after reading its `.lua`, so the `.luac` is
newer. Zip archives keep those timestamps.

If a user later copies the files in a way that makes the `.lua` newer, the radio
compiles the `.lua` again, which is exactly what the `.luac` was meant to avoid. If the
`.luac` can't be loaded (e.g. on an older firmware), the radio falls back to the `.lua`.
So shipping both is the safe default.

## Standalone compiler

Every [release](../../releases) has `edgetx-luac` binaries attached:

| File | Platform |
| ---- | -------- |
| `edgetx-luac-<version>-linux-x64.tar.gz` | Linux x86-64 (static) |
| `edgetx-luac-<version>-linux-arm64.tar.gz` | Linux ARM64, e.g. Raspberry Pi (static) |
| `edgetx-luac-<version>-macos-universal.tar.gz` | macOS, Apple silicon and Intel |
| `edgetx-luac-<version>-windows-x64.zip` | Windows x64 |

`SHA256SUMS` lists their checksums.

```sh
edgetx-luac -s -o script.luac script.lua
```

The macOS binary isn't signed. Allow it with `xattr -d com.apple.quarantine edgetx-luac`,
or right-click it and choose **Open** once.

You can also compile in the browser at <https://edgetx-luac.pages.dev>.

## Maintainers

### Updating the compiler

Set `inputs.edgetx-ref.default` in `action.yml` to the new EdgeTX commit SHA, and open a PR.
The test workflow builds that commit on every platform.

### Releasing

1. Tag the release: `git tag v1.2.3 && git push origin v1.2.3`.
   Tags with a suffix (`v1.2.3-rc1`) become pre-releases.
2. The release workflow builds the binaries and creates a **draft** release.
   Check it, then publish it.
3. Move the major tag: `git tag -f v1 v1.2.3 && git push -f origin v1`.

Bump the major version only when EdgeTX changes its bytecode format, and add a row to the
compatibility table.
