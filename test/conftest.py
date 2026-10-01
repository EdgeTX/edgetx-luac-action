import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def load(name: str) -> ModuleType:
    """Import scripts/<name>.py under a unique module name."""
    spec = importlib.util.spec_from_file_location(f"scripts_{name}", SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def compile_py() -> ModuleType:
    return load("compile")


@pytest.fixture(scope="session")
def resolve_ref() -> ModuleType:
    return load("resolve_ref")


@pytest.fixture(scope="session")
def check_header() -> ModuleType:
    return load("check_header")


@pytest.fixture(scope="session")
def build_py() -> ModuleType:
    return load("build")


@pytest.fixture(autouse=True)
def github_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Point the workflow command files at temp files.

    Under GitHub Actions these variables name the real step's files, which
    the scripts would otherwise append to.
    """
    files = {
        "output": tmp_path / "github_output",
        "summary": tmp_path / "github_step_summary",
    }
    monkeypatch.setenv("GITHUB_OUTPUT", str(files["output"]))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(files["summary"]))
    return files
