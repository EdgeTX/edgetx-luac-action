import os
import subprocess
from pathlib import Path

import pytest

SHA = "0123456789abcdef0123456789abcdef01234567"
TAG_OBJECT = "1111111111111111111111111111111111111111"
TAG_COMMIT = "2222222222222222222222222222222222222222"
BRANCH = "3333333333333333333333333333333333333333"


def ls_remote(monkeypatch, module, stdout="", returncode=0, stderr=""):
    """Replace git ls-remote with canned output; returns the recorded calls."""
    calls: list[list[str]] = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, returncode, stdout, stderr)

    monkeypatch.setattr(module.subprocess, "run", run)
    return calls


def test_full_sha_is_used_as_is(resolve_ref, monkeypatch):
    calls = ls_remote(monkeypatch, resolve_ref)
    assert resolve_ref.resolve("EdgeTX/edgetx", SHA) == SHA
    assert calls == []


def test_short_sha_is_looked_up_as_a_ref(resolve_ref, monkeypatch):
    calls = ls_remote(monkeypatch, resolve_ref)
    assert resolve_ref.resolve("EdgeTX/edgetx", SHA[:7]) is None
    assert calls and calls[0][:3] == ["git", "ls-remote", "https://github.com/EdgeTX/edgetx"]


def test_annotated_tag_resolves_to_its_commit(resolve_ref, monkeypatch):
    ls_remote(
        monkeypatch,
        resolve_ref,
        f"{TAG_OBJECT}\trefs/tags/v1.0\n{TAG_COMMIT}\trefs/tags/v1.0^{{}}\n",
    )
    assert resolve_ref.resolve("EdgeTX/edgetx", "v1.0") == TAG_COMMIT


def test_lightweight_tag(resolve_ref, monkeypatch):
    ls_remote(monkeypatch, resolve_ref, f"{TAG_COMMIT}\trefs/tags/v1.0\n")
    assert resolve_ref.resolve("EdgeTX/edgetx", "v1.0") == TAG_COMMIT


def test_tag_wins_over_branch_of_the_same_name(resolve_ref, monkeypatch):
    ls_remote(
        monkeypatch,
        resolve_ref,
        f"{BRANCH}\trefs/heads/v1.0\n{TAG_COMMIT}\trefs/tags/v1.0\n",
    )
    assert resolve_ref.resolve("EdgeTX/edgetx", "v1.0") == TAG_COMMIT


def test_branch(resolve_ref, monkeypatch):
    ls_remote(monkeypatch, resolve_ref, f"{BRANCH}\trefs/heads/main\n")
    assert resolve_ref.resolve("EdgeTX/edgetx", "main") == BRANCH


def test_unknown_ref(resolve_ref, monkeypatch):
    ls_remote(monkeypatch, resolve_ref, "")
    assert resolve_ref.resolve("EdgeTX/edgetx", "nope") is None


def test_git_failure_is_reported(resolve_ref, monkeypatch, capsys):
    ls_remote(monkeypatch, resolve_ref, returncode=128, stderr="fatal: repository not found\n")
    assert resolve_ref.resolve("EdgeTX/nope", "main") is None
    assert "::error::git ls-remote failed for EdgeTX/nope: fatal: repository not found" in (
        capsys.readouterr().out
    )


def test_main_usage(resolve_ref, capsys):
    assert resolve_ref.main([]) == 2
    assert "Usage" in capsys.readouterr().out


def test_main_unknown_ref(resolve_ref, monkeypatch, capsys):
    ls_remote(monkeypatch, resolve_ref, "")
    assert resolve_ref.main(["EdgeTX/edgetx", "nope"]) == 1
    assert "::error::Could not find 'nope' in EdgeTX/edgetx" in capsys.readouterr().out


@pytest.fixture
def runner_temp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    temp = tmp_path / "runner_temp"
    monkeypatch.setenv("RUNNER_TEMP", str(temp))
    return temp


def binary_name() -> str:
    return "edgetx-luac.exe" if os.name == "nt" else "edgetx-luac"


def test_main_writes_step_outputs(resolve_ref, runner_temp, github_files, capsys):
    assert resolve_ref.main(["EdgeTX/edgetx", SHA]) == 0
    assert capsys.readouterr().out.strip() == SHA

    bin_dir = runner_temp / "edgetx-luac" / SHA
    output = github_files["output"].read_bytes()
    assert b"\r" not in output
    assert output.decode().splitlines() == [
        f"sha={SHA}",
        f"dir={bin_dir}",
        f"bin={bin_dir / binary_name()}",
    ]


def test_main_marks_an_already_built_binary(resolve_ref, runner_temp, github_files):
    binary = runner_temp / "edgetx-luac" / SHA / binary_name()
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"")

    assert resolve_ref.main(["EdgeTX/edgetx", SHA]) == 0
    assert github_files["output"].read_text().splitlines()[-1] == "built=true"
