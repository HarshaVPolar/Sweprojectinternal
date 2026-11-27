"""Composition root and MCP server setup."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

try:
    from mcp.server.fastmcp import FastMCP  # type: ignore[attr-defined]
except ImportError:
    from mcp.server.mcpserver import MCPServer as FastMCP  # type: ignore[no-redef]

from ytmcp.config import Settings
from ytmcp.infra.clock import Clock, SystemClock
from ytmcp.models import QuotaStatus
from ytmcp.providers.base import YouTubeProvider
from ytmcp.providers.fixture import FixtureYouTubeProvider
from ytmcp.tools import ToolDeps, get_quota_status

DEFAULT_FIXTURE_DIR = (
    Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "youtube"
)


def stub_quota_status(settings: Settings, clock: Clock) -> QuotaStatus:
    """Compute stub QuotaStatus from configuration and clock."""
    used_today = 0
    reserve = settings.quota.daily_budget * settings.quota.safety_reserve_pct // 100
    remaining = settings.quota.daily_budget - reserve - used_today
    machine_remaining = settings.quota.machine_daily_budget
    reset_at = clock.next_reset()
    exhausted = False
    return QuotaStatus(
        used_today=used_today,
        remaining=remaining,
        reserve=reserve,
        machine_remaining=machine_remaining,
        reset_at=reset_at,
        exhausted=exhausted,
    )


def create_provider(settings: Settings, fixture_dir: Path | None = None) -> YouTubeProvider:
    """Create a YouTubeProvider instance based on settings."""
    if settings.provider == "fixture":
        f_dir = fixture_dir if fixture_dir is not None else DEFAULT_FIXTURE_DIR
        return FixtureYouTubeProvider(f_dir)
    if settings.provider in ("live", "recording"):
        raise NotImplementedError(f"Provider '{settings.provider}' implemented in B21")
    raise ValueError(f"Unknown provider '{settings.provider}'")


TOOL_REGISTRARS: tuple[Callable[[Any, ToolDeps], None], ...] = (get_quota_status.register,)


def build_server(settings: Settings, clock: Clock | None = None) -> FastMCP:
    """Build and configure the FastMCP server instance."""
    server = FastMCP("ytmcp")
    clk = clock if clock is not None else SystemClock(reset_tz=settings.quota.reset_tz)
    deps = ToolDeps(quota_status=lambda: stub_quota_status(settings, clk))
    for registrar in TOOL_REGISTRARS:
        registrar(server, deps)
    return server
