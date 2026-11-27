"""Unit tests for ytmcp.server."""

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from ytmcp.__main__ import main
from ytmcp.config import ConfigError, load_settings
from ytmcp.infra.clock import FakeClock
from ytmcp.providers.base import YouTubeProvider
from ytmcp.providers.fixture import FixtureYouTubeProvider
from ytmcp.server import (
    DEFAULT_FIXTURE_DIR,
    TOOL_REGISTRARS,
    build_server,
    create_provider,
    stub_quota_status,
)


def _get_hint(ann: object, camel: str, snake: str) -> object:
    val = getattr(ann, camel, None)
    return val if val is not None else getattr(ann, snake, None)


@pytest.mark.unit
def test_stub_status_defaults() -> None:
    settings = load_settings(env={})
    clock = FakeClock(datetime(2026, 1, 15, 12, 0, tzinfo=UTC), reset_tz=settings.quota.reset_tz)
    status = stub_quota_status(settings, clock)

    assert status.used_today == 0
    assert status.remaining == 9500
    assert status.reserve == 500
    assert status.machine_remaining == 2000
    assert status.reset_at == datetime(2026, 1, 16, 8, 0, tzinfo=UTC)
    assert status.exhausted is False


@pytest.mark.unit
def test_stub_status_custom() -> None:
    env = {
        "YTMCP_QUOTA__DAILY_BUDGET": "1000",
        "YTMCP_QUOTA__MACHINE_DAILY_BUDGET": "300",
        "YTMCP_QUOTA__SAFETY_RESERVE_PCT": "10",
    }
    settings = load_settings(env=env)
    clock = FakeClock(datetime(2026, 1, 15, 12, 0, tzinfo=UTC), reset_tz=settings.quota.reset_tz)
    status = stub_quota_status(settings, clock)

    assert status.reserve == 100
    assert status.remaining == 900
    assert status.machine_remaining == 300


@pytest.mark.unit
def test_create_provider(tmp_path: Path) -> None:
    settings_fixture = load_settings(env={"YTMCP_PROVIDER": "fixture"})
    provider = create_provider(settings_fixture, fixture_dir=tmp_path)
    assert isinstance(provider, FixtureYouTubeProvider)
    assert isinstance(provider, YouTubeProvider)

    settings_live = load_settings(env={"YTMCP_PROVIDER": "live"})
    with pytest.raises(NotImplementedError, match="B21"):
        create_provider(settings_live)

    settings_rec = load_settings(env={"YTMCP_PROVIDER": "recording"})
    with pytest.raises(NotImplementedError, match="B21"):
        create_provider(settings_rec)

    bad_settings = load_settings(env={"YTMCP_PROVIDER": "fixture"})
    object.__setattr__(bad_settings, "provider", "unknown")
    with pytest.raises(ValueError, match="Unknown provider"):
        create_provider(bad_settings)


@pytest.mark.unit
def test_default_fixture_dir() -> None:
    assert DEFAULT_FIXTURE_DIR.parts[-3:] == ("tests", "fixtures", "youtube")


@pytest.mark.unit
def test_build_server_registers_one_tool() -> None:
    settings = load_settings(env={})
    clock1 = FakeClock(datetime(2026, 1, 15, 12, 0, tzinfo=UTC))
    clock2 = FakeClock(datetime(2026, 1, 15, 12, 0, tzinfo=UTC))

    s1 = build_server(settings, clock1)
    s2 = build_server(settings, clock2)

    assert s1 is not s2
    assert len(TOOL_REGISTRARS) == 1

    tools = asyncio.run(s1.list_tools())
    assert len(tools) == 1

    tool = tools[0]
    assert tool.name == "get_quota_status"
    assert tool.description is not None
    assert tool.description.strip() != ""

    ann = tool.annotations
    assert ann is not None
    assert _get_hint(ann, "readOnlyHint", "read_only_hint") is True
    assert _get_hint(ann, "destructiveHint", "destructive_hint") is False
    assert _get_hint(ann, "idempotentHint", "idempotent_hint") is True
    assert _get_hint(ann, "openWorldHint", "open_world_hint") is False

    call_result = asyncio.run(s1.call_tool("get_quota_status", {}))
    is_err = (
        getattr(call_result, "isError", None)
        if getattr(call_result, "isError", None) is not None
        else getattr(call_result, "is_error", False)
    )
    assert is_err is False
    assert len(call_result.content) >= 1


@pytest.mark.unit
def test_main_runs_server(monkeypatch: pytest.MonkeyPatch) -> None:
    default_settings = load_settings(env={})

    class DummyServer:
        def __init__(self) -> None:
            self.run_calls = 0

        def run(self, transport: str = "stdio", **_kwargs: Any) -> None:
            assert transport == "stdio"
            self.run_calls += 1

    dummy_server = DummyServer()

    monkeypatch.setattr("ytmcp.__main__.load_settings", lambda: default_settings)
    monkeypatch.setattr("ytmcp.__main__.build_server", lambda _s: dummy_server)

    result = main()
    assert result is None
    assert dummy_server.run_calls == 1


@pytest.mark.unit
def test_main_reports_config_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def raise_config_error() -> Any:
        raise ConfigError("bad")

    monkeypatch.setattr("ytmcp.__main__.load_settings", raise_config_error)

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "bad" in captured.err
    assert captured.out == ""
