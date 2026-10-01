import subprocess
from pathlib import Path

import pytest


class FakeCmake:
    """Stands in for subprocess.run; `--build` drops a binary where MSBuild would."""

    def __init__(self, name: str | None = "edgetx-luac", fail_with: int = 0) -> None:
        self.name = name
        self.fail_with = fail_with
        self.calls: list[list[str]] = []
        self.build_dir: Path | None = None

    def __call__(self, cmd: list, check: bool = False, **kwargs) -> subprocess.CompletedProcess:
        cmd = [str(arg) for arg in cmd]
        self.calls.append(cmd)
        if self.fail_with:
            raise subprocess.CalledProcessError(self.fail_with, cmd)
        if "-B" in cmd:
            self.build_dir = Path(cmd[cmd.index("-B") + 1])
        if "--build" in cmd and self.name:
            binary = Path(cmd[cmd.index("--build") + 1]) / "Release" / self.name
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b"\x7fELF")
        return subprocess.CompletedProcess(cmd, 0)


@pytest.fixture
def cmake(build_py, monkeypatch: pytest.MonkeyPatch):
    def install(**kwargs) -> FakeCmake:
        fake = FakeCmake(**kwargs)
        monkeypatch.setattr(build_py.subprocess, "run", fake)
        return fake

    return install


def test_usage(build_py, capsys):
    assert build_py.main(["only-one-arg"]) == 2
    assert "Usage" in capsys.readouterr().out


@pytest.mark.parametrize("name", ["edgetx-luac", "edgetx-luac.exe"])
def test_builds_and_copies_the_binary(build_py, cmake, tmp_path, name):
    fake = cmake(name=name)
    out = tmp_path / "out"

    assert build_py.main(["/src/edgetx", str(out), "-DEXTRA=1"]) == 0
    assert (out / name).read_bytes() == b"\x7fELF"

    configure, build = fake.calls
    assert configure[:3] == ["cmake", "-S", str(Path("/src/edgetx/radio/src/thirdparty/Lua"))]
    assert configure[-2:] == ["-DCMAKE_BUILD_TYPE=Release", "-DEXTRA=1"]
    assert build[-2:] == ["--config", "Release"]
    # the temporary build directory is cleaned up
    assert fake.build_dir is not None and not fake.build_dir.exists()


def test_cmake_failure_returns_its_exit_code(build_py, cmake, tmp_path):
    cmake(fail_with=3)
    assert build_py.main(["/src/edgetx", str(tmp_path / "out")]) == 3
    assert not (tmp_path / "out").exists()


def test_missing_binary_is_an_error(build_py, cmake, tmp_path, capsys):
    cmake(name=None)
    assert build_py.main(["/src/edgetx", str(tmp_path / "out")]) == 1
    assert "::error::edgetx-luac binary not found after build" in capsys.readouterr().out
