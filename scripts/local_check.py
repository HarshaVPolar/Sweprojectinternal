"""Local health check script for YouTube Video Intelligence MCP server.

Builds the project, runs tests, starts the MCP server using fixture provider,
calls one read-only tool, and reports PASS, FAIL, or SKIP for each step.
"""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class StepResult:
    """Result of a single local-check step."""

    name: str
    passed: bool
    detail: str
    output_tail: str = ""
    skipped: bool = False


def tail(text: str, lines: int = 20) -> str:
    """Return the last requested number of lines from text."""
    if not text:
        return ""
    stripped = text.rstrip("\r\n")
    if not stripped:
        return ""
    all_lines = stripped.splitlines()
    if len(all_lines) <= lines:
        return "\n".join(all_lines)
    return "\n".join(all_lines[-lines:])


def run_command(
    name: str,
    args: Sequence[str],
    timeout: float | int,
    env: Mapping[str, str] | None = None,
) -> StepResult:
    """Run an external command and return a StepResult."""
    try:
        res = subprocess.run(
            list(args),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            cwd=REPO_ROOT,
            env=env,
            timeout=timeout,
        )
        passed = res.returncode == 0
        detail = f"exit code {res.returncode}"
        output = res.stdout or ""
        return StepResult(name=name, passed=passed, detail=detail, output_tail=tail(output, 20))
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or exc.output or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        return StepResult(
            name=name,
            passed=False,
            detail=f"timed out after {timeout} s",
            output_tail=tail(output, 20),
        )
    except OSError as exc:
        target = args[0] if args else name
        return StepResult(
            name=name,
            passed=False,
            detail=f"failed to execute '{target}': {exc}",
            output_tail="",
        )


def format_step(result: StepResult) -> str:
    """Format a StepResult for console reporting."""
    if result.skipped:
        prefix = "[SKIP]"
    elif result.passed:
        prefix = "[PASS]"
    else:
        prefix = "[FAIL]"
    return f"{prefix} {result.name}: {result.detail}"


def step_build() -> StepResult:
    """Byte-compile files and verify package import."""
    cmd1 = [sys.executable, "-m", "compileall", "-q", "src", "scripts", "tests"]
    res1 = run_command("build", cmd1, timeout=60)
    if not res1.passed:
        return res1

    cmd2 = [sys.executable, "-c", "import ytmcp; print(ytmcp.__version__)"]
    res2 = run_command("build", cmd2, timeout=30)
    if not res2.passed:
        return res2

    version = (res2.output_tail or "").strip()
    detail = f"byte-compiled and imported package ({version})" if version else "ok"
    return StepResult(name="build", passed=True, detail=detail, output_tail="")


def step_tests() -> StepResult:
    """Run non-live test suite."""
    cmd = [sys.executable, "-m", "pytest", "-m", "not live", "-q"]
    return run_command("tests", cmd, timeout=900)


def _extract_payload(result: Any) -> dict[str, Any]:
    structured = getattr(result, "structuredContent", None)
    if structured is None:
        structured = getattr(result, "structured_content", None)
    if structured is not None and isinstance(structured, dict):
        return cast(dict[str, Any], structured)
    content = getattr(result, "content", None)
    if isinstance(content, list):
        for item in content:
            text = getattr(item, "text", None)
            if isinstance(text, str):
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, dict):
                        return parsed
                except json.JSONDecodeError:
                    continue
    return {}


async def _run_server_check() -> list[StepResult]:
    with tempfile.TemporaryDirectory() as tmp_dir:
        server_env = {
            **os.environ,
            "YTMCP_PROVIDER": "fixture",
            "YTMCP_DATA_DIR": tmp_dir,
        }
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "ytmcp"],
            env=server_env,
        )
        try:
            async with stdio_client(params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    tool_list = await session.list_tools()
                    tool_names = [t.name for t in tool_list.tools]
                    if "get_quota_status" not in tool_names:
                        return [
                            StepResult(
                                name="server start",
                                passed=False,
                                detail="get_quota_status tool not found",
                            ),
                            StepResult(
                                name="read-only call",
                                passed=False,
                                detail="server did not start",
                                skipped=True,
                            ),
                        ]

                    start_result = StepResult(
                        name="server start",
                        passed=True,
                        detail="initialized and tools listed",
                    )

                    res = await session.call_tool("get_quota_status", {})
                    is_err = (
                        getattr(res, "isError", None)
                        if getattr(res, "isError", None) is not None
                        else getattr(res, "is_error", False)
                    )
                    if is_err:
                        return [
                            start_result,
                            StepResult(
                                name="read-only call",
                                passed=False,
                                detail="call_tool returned error",
                            ),
                        ]

                    payload = _extract_payload(res)
                    if payload.get("ok") is not True:
                        return [
                            start_result,
                            StepResult(
                                name="read-only call",
                                passed=False,
                                detail=f"payload ok was not true: {payload}",
                            ),
                        ]

                    call_result = StepResult(
                        name="read-only call",
                        passed=True,
                        detail="get_quota_status succeeded with ok=true",
                    )
                    return [start_result, call_result]
        except Exception as exc:
            return [
                StepResult(
                    name="server start",
                    passed=False,
                    detail=f"server error: {exc}",
                ),
                StepResult(
                    name="read-only call",
                    passed=False,
                    detail="server did not start",
                    skipped=True,
                ),
            ]


def step_server() -> list[StepResult]:
    """Start MCP server with fixture provider and verify tools and calls."""
    try:
        return asyncio.run(asyncio.wait_for(_run_server_check(), timeout=60))
    except TimeoutError:
        return [
            StepResult(
                name="server start",
                passed=False,
                detail="timed out after 60 s",
            ),
            StepResult(
                name="read-only call",
                passed=False,
                detail="server did not start",
                skipped=True,
            ),
        ]


def _print_failed_tails(results: Sequence[StepResult]) -> None:
    for res in results:
        if not res.passed and res.output_tail:
            print(f"\n---- output tail (last 20 lines) of {res.name} ----")
            print(res.output_tail)


def _tally_results(results: Sequence[StepResult]) -> tuple[int, int, int]:
    failed = 0
    passed = 0
    total = 0
    for res in results:
        if res.skipped:
            if "server did not start" in res.detail:
                failed += 1
            elif res.name == "tests" and "skipped by --skip-tests" in res.detail:
                pass
            else:
                passed += 1
                total += 1
        elif res.passed:
            passed += 1
            total += 1
        else:
            failed += 1
    return passed, total, failed


def main(argv: list[str] | None = None) -> int:
    """Run local check suite."""
    args = list(sys.argv[1:] if argv is None else argv)
    if "--live" in args:
        print("live mode is not available until build item B21")
        return 2

    skip_tests = "--skip-tests" in args

    results: list[StepResult] = [step_build()]
    if skip_tests:
        results.append(
            StepResult(
                name="tests",
                passed=True,
                detail="skipped by --skip-tests",
                skipped=True,
            )
        )
    else:
        results.append(step_tests())

    results.extend(step_server())

    for res in results:
        print(format_step(res))

    _print_failed_tails(results)

    passed, total, failed = _tally_results(results)
    if failed == 0:
        print(f"\nlocal-check: PASS ({passed}/{total} steps)")
        return 0

    print(f"\nlocal-check: FAIL ({failed} failed)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
