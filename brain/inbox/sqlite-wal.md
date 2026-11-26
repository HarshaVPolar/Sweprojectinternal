---
title: sqlite-wal
type: inbox
created: 2026-11-26
tags: [sqlite, storage, reliability]
requirements: [NFR-PERF-4, NFR-REL-3, NFR-REL-4, SEC-10]
sources: [https://www.sqlite.org/wal.html, https://www.sqlite.org/pragma.html]
status: raw
---

# Summary

The server keeps its cache, quota ledger, proposals and audit log in one local SQLite file. Write-ahead logging (WAL) lets readers and one writer work at the same time, which suits several tool calls arriving together.

# Key facts

- In WAL mode changes are appended to a separate -wal file and later copied into the main file by a checkpoint. Readers do not block the writer and the writer does not block readers. There is still only one writer at a time.
- PRAGMA journal_mode=WAL is stored in the database file, so it persists. The extra files end in -wal and -shm and are covered by the .gitignore patterns for sqlite files.
- PRAGMA busy_timeout sets how many milliseconds a connection waits for a lock before it fails with a busy error. This project uses 5000 (NFR-PERF-4).
- PRAGMA synchronous=NORMAL in WAL mode cannot corrupt the database. After a power loss or operating-system crash the last committed transactions may be lost, which is acceptable for a cache and a ledger that can be rebuilt.
- PRAGMA foreign_keys applies to one connection only and is off by default, so it must be switched on every time a connection is opened.
- A write transaction should start with BEGIN IMMEDIATE so that a lock conflict shows up at the start and not in the middle of the work.
- WAL needs all processes on the same machine and does not work reliably on a network file system.
- The database and token files are created with mode 0600 on Linux and macOS (SEC-10). On Windows the user profile permissions apply and tests must not check mode bits.

# Implications for design

- Build item B08 opens every connection with WAL, busy_timeout 5000, foreign_keys ON and synchronous NORMAL, and exposes one transaction helper.
- Every update is a transaction, so a crash in the middle leaves a consistent store (NFR-REL-4). The quota ledger survives restarts (NFR-REL-3).
- Tests use a temporary file, not an in-memory database, because WAL does not apply to in-memory databases.

# Related

- (links added during brain-refine)
