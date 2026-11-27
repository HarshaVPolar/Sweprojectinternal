"""System tests for scripts/local_check.py."""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "local_check.py"


@pytest.mark.system
def test_quick_run_passes() -> None:
    res = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--skip-tests"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert res.returncode == 0
    assert "[PASS] build" in res.stdout
    assert "[SKIP] tests" in res.stdout
    assert "[PASS] server start" in res.stdout
    assert "[PASS] read-only call" in res.stdout
    assert res.stdout.strip().endswith("local-check: PASS (3/3 steps)")


@pytest.mark.system
def test_live_flag_rejected() -> None:
    res = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--live"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert res.returncode == 2
