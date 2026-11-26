---
name: local-check
description: Runs the local health check of the YouTube Video Intelligence MCP server project. It builds the project, runs the tests, starts the server, calls one read-only tool and reports pass or fail for each step. Use when the user asks to verify the local setup or to run local-check. STUB until build item B32.
---

# local-check

Status: STUB (Stage 1). The script scripts/local_check.py and the full instructions are written in Stage 2 (first version) and build item B32. If this skill is invoked now, tell the user that it is not implemented yet and stop.

## Planned steps (SRS SK-9 to SK-12)

1. Build the project.
2. Run the automated test suite.
3. Start the local server.
4. Invoke one read-only tool, using the fixture provider by default so that it works offline and spends no quota.
5. Report pass or fail for each step. Exit non-zero if any step fails and print the tail of the failing step's output.

## Brain notes

- [[agent-skills-format]]
