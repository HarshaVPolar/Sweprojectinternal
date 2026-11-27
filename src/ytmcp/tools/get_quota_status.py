"""Tool implementation for get_quota_status."""

from typing import Any

from mcp.types import ToolAnnotations

from ytmcp.models import QuotaReport, ToolResult
from ytmcp.tools import ToolDeps, render_result


def register(mcp: Any, deps: ToolDeps) -> None:
    """Register the get_quota_status tool with the MCP server."""
    annotations = ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    )
    description = (
        "Report today's YouTube API quota use and what remains. Read-only; spends no quota."
    )

    @mcp.tool(
        name="get_quota_status",
        description=description,
        annotations=annotations,
    )
    def get_quota_status() -> Any:
        status = deps.quota_status()
        summary = (
            f"Quota used today: {status.used_today}; "
            f"remaining: {status.remaining}; "
            f"resets at {status.reset_at.isoformat()}"
        )
        result = ToolResult(
            ok=True,
            summary=summary,
            data=status.model_dump(mode="json"),
            quota=QuotaReport(spent=0, remaining=status.remaining, estimate=None),
            notices=["Stub values until build item B16 (the real QuotaGuard)."],
            error=None,
        )
        return render_result(result)
