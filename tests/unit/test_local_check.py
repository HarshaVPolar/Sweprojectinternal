"""Unit tests for scripts/local_check.py."""

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest


def _load_local_check() -> Any:
    path = Path(__file__).resolve().parent.parent.parent / "scripts" / "local_check.py"
    spec = importlib.util.spec_from_file_location("local_check", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["local_check"] = module
    spec.loader.exec_module(module)
    return module


lc = _load_local_check()


@pytest.mark.unit
def test_tail() -> None:
    assert lc.tail("a\nb\nc\nd", 2) == "c\nd"
    assert lc.tail("", 20) == ""
    assert lc.tail("line 1\nline 2\nline 3", 20) == "line 1\nline 2\nline 3"
    assert lc.tail("a\nb\n", 5) == "a\nb"


@pytest.mark.unit
def test_run_command_pass() -> None:
    res = lc.run_command("demo", [sys.executable, "-c", "print('ok')"], timeout=30)
    assert res.name == "demo"
    assert res.passed is True
    assert "exit code 0" in res.detail


@pytest.mark.unit
def test_run_command_fail() -> None:
    res = lc.run_command(
        "failing",
        [sys.executable, "-c", "import sys; sys.stderr.write('boom'); sys.exit(3)"],
        timeout=30,
    )
    assert res.passed is False
    assert "exit code 3" in res.detail
    assert "boom" in res.output_tail


@pytest.mark.unit
def test_run_command_timeout() -> None:
    res = lc.run_command(
        "sleep",
        [sys.executable, "-c", "import time; time.sleep(5)"],
        timeout=1,
    )
    assert res.passed is False
    assert "timed out after 1" in res.detail


@pytest.mark.unit
def test_run_command_missing() -> None:
    res = lc.run_command(
        "missing",
        ["/nonexistent_command_12345_xyz"],
        timeout=10,
    )
    assert res.passed is False
    assert bool(res.detail)
    assert "nonexistent_command_12345_xyz" in res.detail or "No such file" in res.detail


@pytest.mark.unit
def test_output_tail_limit() -> None:
    res = lc.run_command(
        "fifty",
        [sys.executable, "-c", "for i in range(50): print(f'line {i}')"],
        timeout=30,
    )
    assert res.passed is True
    tail_lines = res.output_tail.splitlines()
    assert len(tail_lines) == 20
    assert tail_lines[0] == "line 30"
    assert tail_lines[-1] == "line 49"


@pytest.mark.unit
def test_format_line() -> None:
    assert lc.format_step(lc.StepResult("build", True, "ok", "")) == "[PASS] build: ok"
    fail_res = lc.format_step(lc.StepResult("build", False, "exit code 1", ""))
    assert fail_res.startswith("[FAIL] build: ")
    assert (
        lc.format_step(lc.StepResult("tests", False, "reason", "", skipped=True))
        == "[SKIP] tests: reason"
    )


@pytest.mark.unit
def test_main_live_rejected(capsys: pytest.CaptureFixture[str]) -> None:
    code = lc.main(["--live"])
    assert code == 2
    out = capsys.readouterr().out
    assert "B21" in out


@pytest.mark.unit
def test_main_all_pass(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(lc, "step_build", lambda: lc.StepResult("build", True, "ok"))
    monkeypatch.setattr(lc, "step_tests", lambda: lc.StepResult("tests", True, "ok"))
    monkeypatch.setattr(
        lc,
        "step_server",
        lambda: [
            lc.StepResult("server start", True, "ok"),
            lc.StepResult("read-only call", True, "ok"),
        ],
    )

    code = lc.main([])
    assert code == 0
    out = capsys.readouterr().out
    assert out.strip().endswith("local-check: PASS (4/4 steps)")


@pytest.mark.unit
def test_main_failure_and_skip(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        lc,
        "step_build",
        lambda: lc.StepResult("build", False, "exit code 1", output_tail="error trace line"),
    )
    monkeypatch.setattr(lc, "step_tests", lambda: lc.StepResult("tests", True, "ok"))
    monkeypatch.setattr(
        lc,
        "step_server",
        lambda: [
            lc.StepResult("server start", True, "ok"),
            lc.StepResult("read-only call", True, "ok"),
        ],
    )

    code = lc.main([])
    assert code == 1
    out = capsys.readouterr().out
    assert "[FAIL] build" in out
    assert "output tail" in out
    assert "error trace line" in out
    assert out.strip().endswith("local-check: FAIL (1 failed)")

    # Also test: server start failed and read-only call skipped with "server did not start"
    capsys.readouterr()
    monkeypatch.setattr(lc, "step_build", lambda: lc.StepResult("build", True, "ok"))
    monkeypatch.setattr(lc, "step_tests", lambda: lc.StepResult("tests", True, "ok"))
    monkeypatch.setattr(
        lc,
        "step_server",
        lambda: [
            lc.StepResult("server start", False, "connection failed"),
            lc.StepResult("read-only call", False, "server did not start", skipped=True),
        ],
    )

    code2 = lc.main([])
    assert code2 == 1
    out2 = capsys.readouterr().out
    assert "[SKIP] read-only call" in out2


@pytest.mark.unit
def test_main_skip_tests(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    tests_called = False

    def fake_tests() -> Any:
        nonlocal tests_called
        tests_called = True
        return lc.StepResult("tests", True, "ok")

    monkeypatch.setattr(lc, "step_build", lambda: lc.StepResult("build", True, "ok"))
    monkeypatch.setattr(lc, "step_tests", fake_tests)
    monkeypatch.setattr(
        lc,
        "step_server",
        lambda: [
            lc.StepResult("server start", True, "ok"),
            lc.StepResult("read-only call", True, "ok"),
        ],
    )

    code = lc.main(["--skip-tests"])
    assert code == 0
    assert tests_called is False
    out = capsys.readouterr().out
    assert "[SKIP] tests: skipped by --skip-tests" in out
    assert out.strip().endswith("local-check: PASS (3/3 steps)")
