# ADR-004: Human-only approval gate for playlist creation

Status: accepted
Date: 2026-11-28

## Context

Creating a playlist writes to the user's YouTube account. The server is driven by an AI model that reads untrusted text: titles, descriptions, tags and channel names written by strangers. SRS v1.0 SEC-5 had the server issue a confirmation token and release it to the client together with the proposal. A prompt-injected model could read that token and call confirm_playlist itself, so the gate would prove only that a token matched, not that a human approved (SRS Addendum 1, SA-1).

## Decision

1. propose_playlist stores the proposal and returns no secret, token or code. confirm_playlist takes only proposal_id.
2. Approval is collected through a channel the model cannot read. Mode elicitation: an MCP elicitation request shows a server-built summary and the client UI collects accept or decline. Mode oob: a loopback approval page on 127.0.0.1 with a random port, a random 128-bit path nonce, a per-page CSRF value, Host and Origin checks and a single decision; the server opens it in the system browser and the address never appears in a tool output (it is printed on the server's stderr). Mode auto uses elicitation when the client advertised the capability and oob otherwise. The configuration key is approval.mode and its default is auto.
3. The server checks, failing closed: the proposal exists; its state is PROPOSED (or PARTIALLY_CREATED on resume); it is unexpired (15 minutes); the recomputed items hash equals the stored one; the approval is consumed exactly once; the write scope is available; a channel exists. Approval values and nonces are stored only as HMAC-SHA256 with a per-install secret.
4. The skill still asks the user in chat and stops (SK-3). The human approval is a second, independent control.
5. The spike ES-1 tests which mode the demonstration client supports. The oob mode is built and tested whatever the result.
6. Only services/confirmation_gate.py can set an approval to granted, and only PlaylistService.confirm can create a playlist or add an item.

## Consequences

- The oob mode needs a browser on the same machine. Remote or hosted MCP clients are out of scope (SRS section 3.4).
- A malicious program on the user's machine, or an AI agent that can operate the user's browser, is not stopped by this gate (see docs/design/security.md, residual risks).
- More code and tests are needed (build item B22) and a resume after a partial creation needs a new approval (SRS Addendum 1, SA-2).
- The gate does not rely on tool annotations, which clients may ignore (assumption A-4).

## Brain notes cited

- [[prompt-injection]]
- [[mcp-overview]]
