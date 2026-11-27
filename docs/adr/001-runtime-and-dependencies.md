# ADR-001: Python runtime and approved dependencies

Status: accepted
Date: 2026-11-28

## Context

SRS section 2.4 allows Python 3.11 or newer, or Node.js 20 or newer. The server is small, text and maths heavy (TF-IDF, a dynamic-programming solver, statistics), talks to one HTTP API and one local database, and is written largely with AI coding assistants that are strongest in Python. The official MCP SDK exists for Python as the package mcp, with the FastMCP interface.

## Decision

- Runtime: Python 3.11 or newer. Package name ytmcp, src layout. MCP over stdio only in release 1.0 (SRS Addendum 1, TBD-3).
- Approved runtime dependencies: mcp, httpx, pydantic (version 2 or newer), keyring, google-auth-oauthlib, cryptography, tzdata.
- Approved development dependencies: pytest, pytest-cov, pytest-xdist, hypothesis, ruff, mypy, import-linter, pip-audit, pip-licenses, bandit, pre-commit. mutmut is an optional extra and runs only on Linux, macOS or WSL.
- Any other package needs a new ADR. Package names are verified on PyPI before they are added and versions are pinned in requirements.lock.
- tzdata is required so that zoneinfo knows America/Los_Angeles on Windows.

## Consequences

- One language for server, scripts and tests. The standard library covers text processing, SQLite, hashing and time zones.
- Type checking is strict only for the pure domain package (mypy strict on ytmcp.domain). The rest is covered by tests, ruff and the layer rules.
- Node.js is not used. Choosing it later would need a new ADR and a rewrite.
- Mutation testing does not run natively on Windows, so it runs on Linux, macOS, WSL or in CI.

## Brain notes cited

- [[mcp-overview]]
- [[agent-skills-format]]
