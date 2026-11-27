"""Security test scanning fixtures for personal or sensitive data."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from ytmcp.providers.transport import READ_METHODS, fixture_key

EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
AIZA_PATTERN = re.compile(r"AIza[A-Za-z0-9_-]{35}")
BEARER_PATTERN = re.compile(r"Bearer\s+[A-Za-z0-9_.-]{20,}")

FORBIDDEN_ARG_KEYS = {"key", "access_token", "refresh_token", "client_secret"}
FORBIDDEN_TEXT_LITERALS = (
    "ya29.",
    "1//0",
    "GOCSPX-",
    "-----BEGIN",
    "access_token",
    "refresh_token",
    "client_secret",
)

FIXTURES_ROOT = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures"


@pytest.mark.security
def test_no_personal_data() -> None:
    for file_path in FIXTURES_ROOT.rglob("*"):
        if file_path.is_dir():
            continue
        if "_raw" in file_path.parts:
            continue

        text = file_path.read_text(encoding="utf-8", errors="replace")

        for literal in FORBIDDEN_TEXT_LITERALS:
            assert literal not in text, f"Found forbidden literal '{literal}' in {file_path}"

        assert not AIZA_PATTERN.search(text), f"Found API key pattern in {file_path}"
        assert not BEARER_PATTERN.search(text), f"Found Bearer token pattern in {file_path}"

        emails = EMAIL_PATTERN.findall(text)
        for email in emails:
            assert email == "redacted@example.invalid", (
                f"Found unredacted email '{email}' in {file_path}"
            )


@pytest.mark.security
def test_fixture_files_wellformed() -> None:
    yt_dir = FIXTURES_ROOT / "youtube"
    json_files = list(yt_dir.glob("*.json"))
    assert json_files, "No fixture files found in tests/fixtures/youtube"

    for file_path in json_files:
        assert file_path.stat().st_size < 400_000, f"{file_path} exceeds 400,000 bytes"

        data = json.loads(file_path.read_text(encoding="utf-8"))
        assert "method" in data
        assert "args" in data
        assert "response" in data

        method = data["method"]
        args = data["args"]
        assert method in READ_METHODS

        expected_name = f"{fixture_key(method, args)}.json"
        assert file_path.name == expected_name

        for k in args:
            assert k not in FORBIDDEN_ARG_KEYS

        if "status" in data:
            assert isinstance(data["status"], int)


@pytest.mark.security
def test_raw_not_tracked() -> None:
    if shutil.which("git") is None:
        pytest.skip("git binary not available")

    dummy_path = "tests/fixtures/_raw/x.json"
    res = subprocess.run(
        ["git", "check-ignore", "-q", dummy_path],
        cwd=str(FIXTURES_ROOT.parent.parent),
        capture_output=True,
    )
    assert res.returncode == 0, f"{dummy_path} is not ignored by git"
