---
title: mcp-overview
type: inbox
created: 2026-11-26
tags: [mcp, protocol, architecture]
requirements: [NFR-POR-2, UI-1, SEC-5, A-4]
sources: [https://modelcontextprotocol.io, SRS section 3.3.1]
status: raw
---

# Summary

The Model Context Protocol (MCP) is an open protocol that lets an AI client (the host) use tools and data offered by a server. Our product is an MCP server: the AI client calls its tools, and the server talks to YouTube.

# Key facts

- Messages use JSON-RPC 2.0. Two transports exist: stdio, where the client starts the server as a child process (the default for local use and the only one in release), and Streamable HTTP (deferred).
- Tools are operations the model can call; each has a name, a description and a JSON Schema for its inputs. Resources are read-only data identified by a URI. Prompts are reusable templates and are not used here. This project exposes 9 tools and 4 resources.
- Tool annotations such as readOnlyHint, destructiveHint, idempotentHint and openWorldHint are hints for the client, for example to ask the user before a write. They are not a security guarantee.
- Elicitation lets a server ask the user for input through the client while a tool call is running. It is an optional client capability, so the server must check at initialisation whether the client announced it.
- Errors: a failure inside a tool is returned in the tool result with an error flag so that the model can read it; protocol problems such as an unknown tool use a JSON-RPC error.
- The server is written in Python with the official SDK (package mcp, FastMCP interface).

# Implications for design

- The server-side approval gate is the authoritative control for writes; the client may or may not honour annotations (assumption A-4).
- Every tool result carries a structured payload and a short text summary (UI-1).
- The server must work with any compliant client and contain no client-specific code (NFR-POR-2).

# Related

- (links added during brain-refine)
