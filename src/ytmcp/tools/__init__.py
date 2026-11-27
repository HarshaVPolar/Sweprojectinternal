"""Tool envelope rendering and dependency definitions."""

from collections.abc import Callable
from dataclasses import dataclass

from mcp.types import TextContent

from ytmcp.models import QuotaStatus, ToolResult


@dataclass(frozen=True)
class ToolDeps:
    """Dependencies injected into tool handlers."""

    quota_status: Callable[[], QuotaStatus]


def render_result(result: ToolResult) -> list[TextContent]:
    """Render a ToolResult envelope for the installed MCP SDK."""
    return [
        TextContent(type="text", text=result.summary),
        TextContent(type="text", text=result.model_dump_json()),
    ]
