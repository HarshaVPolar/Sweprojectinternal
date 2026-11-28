# Schema design

Version 1.0 (Stage 2). The SQL is in docs/design/build-contract.md section 5 and becomes migrations/001_init.sql in build item B08. This document explains the tables. Decision: docs/adr/002-sqlite-storage.md.

## 1. Connection settings

Every connection sets journal_mode=WAL, busy_timeout=5000, foreign_keys=ON and synchronous=NORMAL. Write transactions start with BEGIN IMMEDIATE. The file is created with mode 0600 on Linux and macOS. The table schema_version holds one row with the migration number (1 after migration 001).

## 2. Tables

| Table | Purpose | Key columns | Lifetime |
|---|---|---|---|
| schema_version | current migration number | version | permanent |
| oauth_token | metadata of the stored authorisation: account hash, scopes, keyring reference, issue and expiry dates; never the secret | token_id | until re-authorisation or purge |
| quota_ledger | one row per API call: endpoint, units, Pacific-time day | entry_id; request_id; pt_day | kept for the current and previous days, older rows may be deleted |
| request_log | one row per tool call: tool, estimated and actual units, outcome | request_id | short-lived, no personal data |
| video_cache | normalised video record as JSON with fetch time and time to live | video_id | 24 hours (cache.ttl_video_channel_h) |
| channel_cache | same for channels | channel_id | 24 hours |
| kv_cache | search results (24 hours) and video categories (7 days) by key | key | per kind |
| playlist_proposal | a proposal: request, items hash, total duration, feasibility, state, approval state, approval hash, playlist id, creation and expiry | proposal_id | until purge |
| proposal_item | the ordered items of a proposal, with an added flag for resume | (proposal_id, pos) | with its proposal |
| audit_log | confirm and create events with opaque IDs | audit_id | permanent, no personal data |

## 3. Relationships

- proposal_item belongs to playlist_proposal (foreign key on proposal_id).
- quota_ledger.request_id refers logically to request_log.request_id; there is no foreign key so that a ledger entry can never be blocked by a log row.
- audit_log.proposal_id refers logically to playlist_proposal.proposal_id; it is not a foreign key so that audit rows survive a purge of proposals.

## 4. States and values

- playlist_proposal.state holds a ProposalState name: DRAFT, PROPOSED, CONFIRMED, CREATED, PARTIALLY_CREATED, FAILED, REJECTED or EXPIRED (transitions in build contract section 10).
- playlist_proposal.approval_state is none, pending, granted or denied. approval_hash holds an HMAC-SHA256 value, never a plain code or nonce.
- proposal_item.added_ok is 0 or 1 and is set right after each successful playlistItems insert.
- Dates are ISO 8601 text in UTC; pt_day is YYYY-MM-DD in the reset time zone.

## 5. Indexes and performance

Release 1.0 has no secondary indexes beyond the primary keys. The ledger is summed by day, which is a scan of a small table. If the benchmarks of NFR-PERF-6 are missed, add indexes on quota_ledger(pt_day) and audit_log(proposal_id) in a new migration.

## 6. Data protection and purge

Taste data (likes, subscriptions, playlists) is kept in memory or in the cache only and is removed by the purge command (scripts/purge_cache.py, task H3). Cached API data follows the retention rules of NFR-CMP-1 and BR-6. Logs and the audit log contain only opaque IDs.
