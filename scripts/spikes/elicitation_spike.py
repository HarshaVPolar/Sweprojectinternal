from __future__ import annotations

import sys
from datetime import UTC, datetime

from mcp import types
from mcp.server.mcpserver import Context, MCPServer
from pydantic import BaseModel, Field

FastMCP = MCPServer
server = FastMCP("elicitation-spike")


class ApprovalSchema(BaseModel):
    approve: bool = Field(title="Approve")


@server.tool(annotations=types.ToolAnnotations(readOnlyHint=True))
async def ask_to_confirm(item: str, ctx: Context) -> str:
    """Ask for human confirmation via elicitation."""
    caps = ctx.client_capabilities
    capability = caps is not None and caps.elicitation is not None

    if not capability:
        return "ELICITATION_NOT_SUPPORTED\ncapability=false"

    now_req = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    sys.stderr.write(f"elicitation requested at {now_req}\n")
    sys.stderr.flush()

    msg = f'Approve the spike action for item "{item}"? This is only a test, nothing is created.'
    result = await ctx.elicit(
        message=msg,
        schema=ApprovalSchema,
    )

    now_ans = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    sys.stderr.write(f"elicitation answered at {now_ans}\n")
    sys.stderr.flush()

    if result.action == "accept":
        if isinstance(result.data, ApprovalSchema) and result.data.approve is True:
            outcome = "ACCEPTED"
        elif isinstance(result.data, ApprovalSchema) and result.data.approve is False:
            outcome = "ACCEPTED_BUT_NOT_APPROVED"
        else:
            raise ValueError(f"Malformed elicitation data: {result.data!r}")
    elif result.action == "decline":
        outcome = "DECLINED"
    elif result.action == "cancel":
        outcome = "CANCELLED"
    else:
        raise ValueError(f"Unexpected elicitation action: {getattr(result, 'action', None)!r}")

    return f"{outcome}\ncapability=true"


if __name__ == "__main__":
    server.run()
