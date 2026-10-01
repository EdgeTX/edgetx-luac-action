import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A workspace of scripts, with the current directory set to it."""
    work = tmp_path / "work"
    for name in [
        "a.lua",
        "sub/b.lua",
        "sub/deep/c.lua",
        "dir with space/d.lua",
        ".hidden/e.lua",
        "sub/.f.lua",
        "exclude/g.lua",
        "notes.txt",
        "sub/x.luac",
    ]:
        path = work / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("return {}\n")
    (work / "folder.lua").mkdir()  # a directory with a script-like name
    monkeypatch.chdir(work)
    return work


class FakeLuac:
    """Stands in for subprocess.run: records calls, fails on files named bad*."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
        self.calls.append(cmd)
        if any(Path(arg).name.startswith("bad") for arg in cmd[1:]):
            stderr = f"{cmd[0]}: {cmd[-1]}:3: unexpected symbol near 'end'\n"
            return subprocess.CompletedProcess(cmd, 1, "", stderr)
        return subprocess.CompletedProcess(cmd, 0, "", "")


@pytest.fixture
def luac(compile_py, monkeypatch: pytest.MonkeyPatch) -> FakeLuac:
    fake = FakeLuac()
    monkeypatch.setattr(compile_py.subprocess, "run", fake)
    monkeypatch.setenv("LUAC", "/opt/edgetx-luac")
    for name in ["STRIP", "CHECK_ONLY", "OUTPUT_DIR", "EXCLUDE"]:
        monkeypatch.delenv(name, raising=False)
    return fake


def test_escape(compile_py):
    assert compile_py.escape("50% done\r\nnext") == "50%25 done%0D%0Anext"


@pytest.mark.parametrize(
    ("patterns", "expected"),
    [
        ("*.lua", ["a.lua"]),
        ("sub/*.lua", ["sub/b.lua"]),
        ("sub/**/*.lua", ["sub/b.lua", "sub/deep/c.lua"]),
        (
            "**/*.lua",
            ["a.lua", "dir with space/d.lua", "exclude/g.lua", "sub/b.lua", "sub/deep/c.lua"],
        ),
        ("**/*", ["a.lua", "dir with space/d.lua", "exclude/g.lua", "sub/b.lua", "sub/deep/c.lua"]),
        (".hidden/*.lua", [".hidden/e.lua"]),
        ("dir with space/*.lua", ["dir with space/d.lua"]),
        ("nowhere/*.lua", []),
    ],
)
def test_find_scripts_follows_globstar_rules(compile_py, tree, patterns, expected):
    assert compile_py.find_scripts(patterns, "") == expected


def test_find_scripts_keeps_first_seen_order_without_duplicates(compile_py, tree):
    patterns = "sub/b.lua\n\n  ./a.lua  \n**/*.lua\n"
    assert compile_py.find_scripts(patterns, "") == [
        "sub/b.lua",
        "a.lua",
        "dir with space/d.lua",
        "exclude/g.lua",
        "sub/deep/c.lua",
    ]


@pytest.mark.parametrize("exclude", ["exclude", "exclude/", "./exclude"])
def test_find_scripts_exclude_drops_that_directory(compile_py, tree, exclude):
    assert "exclude/g.lua" not in compile_py.find_scripts("**/*.lua", exclude)


def test_find_scripts_exclude_matches_whole_directories_only(compile_py, tree):
    # a plain string-prefix check would wrongly drop exclude/ for "exc"
    assert "exclude/g.lua" in compile_py.find_scripts("**/*.lua", "exc")


@pytest.mark.parametrize(
    ("stderr", "expected"),
    [
        (
            "edgetx-luac: test/bad.lua:3: unexpected symbol near 'end'\n",
            "::error file=x.lua,line=3::unexpected symbol near 'end'",
        ),
        (
            r"D:\a\_temp\edgetx-luac.exe: bad.lua:12: '=' expected near 'x'",
            "::error file=x.lua,line=12::'=' expected near 'x'",
        ),
        (
            "/tmp/edgetx-luac: ...ng/path/bad.lua:7: unfinished string",
            "::error file=x.lua,line=7::unfinished string",
        ),
        (
            "edgetx-luac: cannot open nope.lua",
            "::error file=x.lua::cannot open nope.lua",
        ),
        (
            "edgetx-luac: bad.lua:1: 100% wrong\nsecond line",
            "::error file=x.lua,line=1::100%25 wrong%0Asecond line",
        ),
    ],
)
def test_annotate(compile_py, capsys, stderr, expected):
    compile_py.annotate("x.lua", stderr)
    assert capsys.readouterr().out.strip() == expected


def test_main_compiles_next_to_each_script(compile_py, tree, luac, github_files, monkeypatch):
    monkeypatch.setenv("FILES", "a.lua\nsub/*.lua")

    assert compile_py.main() == 0
    assert luac.calls == [
        ["/opt/edgetx-luac", "-s", "-o", "a.luac", "a.lua"],
        ["/opt/edgetx-luac", "-s", "-o", "sub/b.luac", "sub/b.lua"],
    ]
    output = github_files["output"].read_bytes()
    assert output == b"files<<EDGETX_LUAC_EOF\na.luac\nsub/b.luac\nEDGETX_LUAC_EOF\n"
    assert "compiled 2 of 2 scripts" in github_files["summary"].read_text()


def test_main_writes_lf_only_outputs(compile_py, tree, luac, github_files, monkeypatch):
    # Python's text mode would write CRLF on Windows, leaving a \r on each value
    monkeypatch.setenv("FILES", "**/*.lua")
    compile_py.main()
    assert b"\r" not in github_files["output"].read_bytes()
    assert b"\r" not in github_files["summary"].read_bytes()


def test_main_without_strip(compile_py, tree, luac, monkeypatch):
    monkeypatch.setenv("FILES", "a.lua")
    monkeypatch.setenv("STRIP", "false")
    compile_py.main()
    assert luac.calls == [["/opt/edgetx-luac", "-o", "a.luac", "a.lua"]]


def test_main_check_only_writes_nothing(compile_py, tree, luac, github_files, monkeypatch):
    monkeypatch.setenv("FILES", "a.lua")
    monkeypatch.setenv("CHECK_ONLY", "true")

    assert compile_py.main() == 0
    assert luac.calls == [["/opt/edgetx-luac", "-p", "a.lua"]]
    assert github_files["output"].read_text() == "files<<EDGETX_LUAC_EOF\nEDGETX_LUAC_EOF\n"
    assert "checked 1 of 1 scripts" in github_files["summary"].read_text()


@pytest.mark.parametrize("output_dir", ["dist", "dist/"])
def test_main_output_dir_keeps_relative_paths(
    compile_py, tree, luac, github_files, monkeypatch, output_dir
):
    monkeypatch.setenv("FILES", "sub/deep/*.lua")
    monkeypatch.setenv("OUTPUT_DIR", output_dir)

    assert compile_py.main() == 0
    assert luac.calls[0][-3:] == ["-o", "dist/sub/deep/c.luac", "sub/deep/c.lua"]
    assert (tree / "dist/sub/deep").is_dir()
    assert "dist/sub/deep/c.luac\n" in github_files["output"].read_text()


def test_main_reports_failures_and_carries_on(
    compile_py, tree, luac, github_files, monkeypatch, capsys
):
    (tree / "bad.lua").write_text("local x =\n")
    monkeypatch.setenv("FILES", "*.lua")

    assert compile_py.main() == 1
    out = capsys.readouterr().out
    assert "::error file=bad.lua,line=3::unexpected symbol near 'end'" in out
    assert "ok  a.lua -> a.luac" in out
    assert "bad.luac" not in github_files["output"].read_text()
    assert "compiled 1 of 2 scripts, 1 failed" in github_files["summary"].read_text()


def test_main_fails_when_nothing_matches(compile_py, tree, luac, monkeypatch, capsys):
    monkeypatch.setenv("FILES", "nowhere/*.lua")
    assert compile_py.main() == 1
    assert "::error::No .lua files matched: nowhere/*.lua" in capsys.readouterr().out
    assert luac.calls == []
