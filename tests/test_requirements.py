from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"


def requirement_lines(filename):
    return {
        line.strip()
        for line in (BACKEND_DIR / filename).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def test_runtime_and_development_requirements_are_separated():
    runtime = requirement_lines("requirements.txt")
    development = requirement_lines("requirements-dev.txt")

    assert "pytest" not in runtime
    assert "filelock>=3.13,<4" in runtime
    assert "fastmcp>=3.4,<4" in runtime
    assert "websockets>=16.0,<17" in runtime
    assert development == {
        "-r requirements.txt",
        "pytest>=7.4,<8",
    }
