"""System boot tests for the ytmcp stdio server."""

import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


def _get_hint(ann: object, camel: str, snake: str) -> object:
    val = getattr(ann, camel, None)
    return val if val is not None else getattr(ann, snake, None)


def _extract_payload(result: Any) -> dict[str, Any]:
    structured = getattr(result, "structuredContent", None)
    if structured is None:
        structured = getattr(result, "structured_content", None)
    if structured is not None:
        return cast(dict[str, Any], structured)
    return cast(dict[str, Any], json.loads(result.content[1].text))


@pytest.mark.system
def test_lists_the_tool(tmp_path: Path) -> None:
    async def scenario() -> None:
        server_env = {
            **os.environ,
            "YTMCP_PROVIDER": "fixture",
            "YTMCP_DATA_DIR": str(tmp_path),
        }
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "ytmcp"],
            env=server_env,
        )
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tool_list = await session.list_tools()
                tools = tool_list.tools
                assert len(tools) == 1
                tool = tools[0]
                assert tool.name == "get_quota_status"
                ann = tool.annotations
                assert ann is not None
                assert _get_hint(ann, "readOnlyHint", "read_only_hint") is True
                assert _get_hint(ann, "destructiveHint", "destructive_hint") is False

    asyncio.run(asyncio.wait_for(scenario(), timeout=45))


@pytest.mark.system
def test_call_returns_envelope(tmp_path: Path) -> None:
    async def scenario() -> None:
        server_env = {
            **os.environ,
            "YTMCP_PROVIDER": "fixture",
            "YTMCP_DATA_DIR": str(tmp_path),
        }
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "ytmcp"],
            env=server_env,
        )
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool("get_quota_status", {})
                is_err = (
                    getattr(result, "isError", None)
                    if getattr(result, "isError", None) is not None
                    else getattr(result, "is_error", False)
                )
                assert is_err is False
                assert len(result.content) >= 1

                payload = _extract_payload(result)
                assert payload["ok"] is True
                assert bool(payload["summary"] and payload["summary"].strip())

                data = payload["data"]
                assert set(data.keys()) == {
                    "used_today",
                    "remaining",
                    "reserve",
                    "machine_remaining",
                    "reset_at",
                    "exhausted",
                }
                assert data["used_today"] == 0
                assert data["remaining"] == 9500
                assert data["reserve"] == 500
                assert data["machine_remaining"] == 2000

                reset_dt = datetime.fromisoformat(data["reset_at"])
                assert reset_dt.tzinfo is not None
                assert data["exhausted"] is False

                assert payload["quota"] == {"spent": 0, "remaining": 9500, "estimate": None}
                assert bool(payload["notices"])
                assert payload["error"] is None

    asyncio.run(asyncio.wait_for(scenario(), timeout=45))


@pytest.mark.system
def test_bad_config_exits_cleanly() -> None:
    env = dict(os.environ)
    env["YTMCP_QUOTA__NOPE"] = "1"
    res = subprocess.run(
        [sys.executable, "-m", "ytmcp"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    assert res.returncode == 2
    assert "YTMCP_QUOTA__NOPE" in res.stderr
    assert res.stdout == ""
