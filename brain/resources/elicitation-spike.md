---
title: elicitation-spike
type: resource
created: 2026-11-28
tags: [mcp, approval, spike]
requirements: [SEC-5, A-4]
sources: [Team test of the demonstration MCP client, docs/design/elicitation-spike.md]
status: distilled
---

# Summary

Spike ES-1 tested whether the demonstration MCP client supports MCP elicitation, which the approval gate of ADR-004 prefers. Result: PASS.

# Key facts

- Client: Cursor version not recorded. MCP SDK version used by the server: 2.3.0. Date: 2026-11-28.
- Criterion A, the client advertises the capability: yes. Criterion B, the call blocks until the user answers: yes. Criterion C, accept and decline both return: yes. Criterion D, the prompt text is shown verbatim: yes. Criterion E, the model sees only the outcome: yes.
- Notes from the test: Decline was not manually triggered in Cursor; marked yes based on the existing server implementation and SDK decline mapping.
- The procedure and the script are in docs/design/elicitation-spike.md and scripts/spikes/elicitation_spike.py.

# Implications for design

The default approval.mode of auto works with this client: elicitation is used and the oob page is the fallback for clients without the capability. Both paths are still implemented and tested in build item B22.

# Related

- [[mcp-overview]]
- [[prompt-injection]]
