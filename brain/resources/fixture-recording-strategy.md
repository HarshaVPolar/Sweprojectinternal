---
title: fixture-recording-strategy
type: resource
created: 2026-11-26
tags: [testing, fixtures, ci]
requirements: [TQ-2, TQ-5, SEC-7, SE-6, CON-7]
sources: [SRS v1.0 section 6.2, Master Project Plan v3 section 7.4]
status: distilled
---

# Summary

CI must never call the live API. Instead the tests replay recorded and sanitised API responses through a fixture provider. Recording happens rarely, by hand, and costs a little quota.

# Key facts

- All YouTube access goes through the provider interface, so the live provider, the fixture provider and test doubles are interchangeable (SE-6).
- Record: scripts/record_fixtures.py calls the API with the API key for public data and writes the raw JSON responses to tests/fixtures/_raw/, which is git-ignored.
- Sanitise: scripts/sanitise_fixture.py removes tokens, email addresses, account identifiers and private content and writes tests/fixtures/youtube/METHOD__HASH16.json. Each file has the keys method, args and response. HASH16 is the first 16 hexadecimal characters of the SHA-256 of the arguments written as canonical JSON (sorted keys, compact separators).
- Replay: the fixture provider computes the same name from the call and reads the file. If the file is missing it raises FixtureMissing, so a test fails loudly instead of silently returning nothing.
- Data about the user (likes, subscriptions, playlists) is synthetic only: 60 or more items over 18 months. Real user data never enters the repository (SEC-7).
- The set must include a linear-algebra seed with about 60 candidates (short, long, without tags, wrong language, live, deleted), 3 channels reachable by the three URL forms, the category list, and error responses (403 quotaExceeded, 403 youtubeSignupRequired, 401 invalid_grant, 429, 500).
- A test scans tests/fixtures for email patterns, token patterns and real account identifiers and fails if it finds any.
- Expected outputs are stored as snapshots in tests/fixtures/expected/; changing a snapshot needs a justified comment in the pull request.
- Contract tests run the same checks on the fixture provider and, by hand, on the live provider, which catches invented fields.

# Implications for design

- Record each fixture once to save quota. Re-record only when Google changes a response (assumption A-5).
- The scheduled live smoke test uses only the API key and a 500-unit budget (QTA-7); the manual live test covers everything that needs OAuth.

# Related

- [[youtube-api-quota]]
- [[iso8601-durations]]
