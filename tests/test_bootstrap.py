"""Tests for the .env handling of scripts/bootstrap.sh and scripts/bootstrap.ps1.

Each script runs in a throw-away copy of the repo with a stub `docker` on PATH, so no
containers are started. The PowerShell variant runs only where `pwsh` is installed
(GitHub's ubuntu runners have it).
"""

import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
KEY = re.compile(r"^JWT_SECRET_KEY=([0-9a-f]{64})$", re.MULTILINE)

STUB_DOCKER = "#!/bin/sh\nexit 0\n"

RUNNERS = [
    pytest.param(["bash", "scripts/bootstrap.sh"], id="bash"),
    pytest.param(
        ["pwsh", "-NoProfile", "-File", "scripts/bootstrap.ps1"],
        id="pwsh",
        marks=pytest.mark.skipif(shutil.which("pwsh") is None, reason="pwsh not installed"),
    ),
]


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "scripts").mkdir()
    for name in ("bootstrap.sh", "bootstrap.ps1"):
        shutil.copy(REPO / "scripts" / name, tmp_path / "scripts" / name)
    shutil.copy(REPO / ".env.example", tmp_path / ".env.example")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text(STUB_DOCKER)
    docker.chmod(docker.stat().st_mode | stat.S_IXUSR)
    return tmp_path


def run(repo: Path, runner: list[str]) -> None:
    env = {**os.environ, "PATH": f"{repo / 'bin'}{os.pathsep}{os.environ['PATH']}"}
    result = subprocess.run(runner, cwd=repo, env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr


def env_text(repo: Path) -> str:
    return (repo / ".env").read_bytes().decode("utf-8")


@pytest.mark.parametrize("runner", RUNNERS)
def test_creates_env_with_generated_key_and_keeps_it(repo: Path, runner: list[str]) -> None:
    run(repo, runner)
    first = env_text(repo)
    assert len(KEY.findall(first)) == 1
    assert "POSTGRES_DB=fixit" in first

    run(repo, runner)
    assert env_text(repo) == first


@pytest.mark.parametrize("runner", RUNNERS)
@pytest.mark.parametrize(
    "assignment",
    [
        "JWT_SECRET_KEY=existing_secret",
        "JWT_SECRET_KEY= existing_secret",
        "JWT_SECRET_KEY = existing_secret",
        "export JWT_SECRET_KEY=existing_secret",
        'JWT_SECRET_KEY="existing_secret"',
        "JWT_SECRET_KEY='existing_secret'",
        "JWT_SECRET_KEY=existing_secret # comment",
    ],
)
def test_keeps_existing_key_in_any_format(repo: Path, runner: list[str], assignment: str) -> None:
    original = f"APP_NAME=FixIt API\n{assignment}\nPOSTGRES_PORT=5433\n".encode()
    (repo / ".env").write_bytes(original)

    run(repo, runner)

    assert (repo / ".env").read_bytes() == original


@pytest.mark.parametrize("runner", RUNNERS)
@pytest.mark.parametrize(
    "assignment",
    [
        "JWT_SECRET_KEY=",
        "JWT_SECRET_KEY=   ",
        'JWT_SECRET_KEY=""',
        "JWT_SECRET_KEY=''",
        "JWT_SECRET_KEY = ",
        "JWT_SECRET_KEY= # no value yet",
    ],
)
def test_fills_empty_key(repo: Path, runner: list[str], assignment: str) -> None:
    (repo / ".env").write_text(f"APP_NAME=FixIt API\n{assignment}\nPOSTGRES_PORT=5433\n")

    run(repo, runner)

    text = env_text(repo)
    assert len(KEY.findall(text)) == 1
    assert text.count("JWT_SECRET_KEY") == 1
    assert "APP_NAME=FixIt API" in text
    assert "POSTGRES_PORT=5433" in text


@pytest.mark.parametrize("runner", RUNNERS)
def test_appends_missing_key(repo: Path, runner: list[str]) -> None:
    (repo / ".env").write_text("APP_NAME=FixIt API\n")

    run(repo, runner)

    text = env_text(repo)
    assert len(KEY.findall(text)) == 1
    assert text.startswith("APP_NAME=FixIt API\n")


@pytest.mark.parametrize("runner", RUNNERS)
def test_keeps_non_ascii_values_and_writes_no_bom(repo: Path, runner: list[str]) -> None:
    (repo / ".env").write_bytes(
        "APP_NAME=ФіксІт API\nPOSTGRES_PASSWORD=пароль€\nJWT_SECRET_KEY=\n".encode()
    )

    run(repo, runner)

    raw = (repo / ".env").read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8")
    assert "APP_NAME=ФіксІт API" in text
    assert "POSTGRES_PASSWORD=пароль€" in text
    assert len(KEY.findall(text)) == 1
