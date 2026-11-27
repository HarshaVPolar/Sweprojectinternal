# ADR-002: SQLite for cache, quota ledger, proposals and audit log

Status: accepted
Date: 2026-11-28

## Context

The server must persist the quota ledger across restarts (NFR-REL-3), cached API data with time-to-live (BR-6), playlist proposals with a state and an expiry (FR-5.8) and an audit log (FR-5.14). There is no server process to rely on, the product runs on one machine, and several tool calls may arrive at the same time (NFR-PERF-4). Updates must be atomic (NFR-REL-4).

## Decision

- Use the standard library module sqlite3 with one database file under the configured data directory. No ORM.
- Every connection sets journal_mode=WAL, busy_timeout=5000, foreign_keys=ON and synchronous=NORMAL. Write transactions start with BEGIN IMMEDIATE.
- The schema is in migrations/001_init.sql and described in docs/design/build-contract.md section 5; a schema_version table records the version and every schema change is a new migration file.
- Files are created with mode 0600 on Linux and macOS. On Windows the user profile permissions apply and tests do not check mode bits.
- Secrets never go into the database. Refresh tokens live in the OS keyring (ADR-005); the table oauth_token holds metadata only.
- Tests use a temporary database file, not an in-memory one, because WAL does not apply to in-memory databases.

## Consequences

- All processes that use the database must run on the same machine and a local file system.
- After a power failure the last committed transactions may be lost. This is acceptable for a cache, and the quota ledger is a soft local control anyway.
- No separate database server to install or secure.
- Schema changes need a migration and a test.

## Brain notes cited

- [[sqlite-wal]]
- [[youtube-api-quota]]
