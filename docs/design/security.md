# Security design: threat model and approval gate

Version 1.0 (Stage 2). Requirements: SEC-1 to SEC-11, BR-1, SK-3. Decisions: ADR-004 and ADR-005. Details: docs/design/build-contract.md sections 9 and 10.

## 1. Assets and trust boundaries

Assets: the user's YouTube account (write access), OAuth tokens, the user's taste data (likes, subscriptions, playlists), the YouTube API quota, the integrity of the proposal that the user approved.

Trust boundaries: (1) AI client and server over stdio; (2) server and the YouTube API over HTTPS; (3) server and the Google OAuth server over HTTPS; (4) server and local storage (SQLite file, keyring or encrypted file); (5) server and the user's browser over the loopback approval page; (6) the repository and CI.

Untrusted data: every string that comes from YouTube (titles, descriptions, tags, channel names, playlist names). The AI model is treated as steerable by that data and is therefore not trusted to authorise a write.

## 2. Threats (STRIDE-lite)

Letters: S spoofing, T tampering, R repudiation, I information disclosure, D denial of service, E elevation of privilege.

| ID | Boundary | Threat | STRIDE | Mitigation | Build item and test |
|---|---|---|---|---|---|
| T-01 | 1 | Instructions hidden in video metadata make the model call confirm_playlist | T, E | Human-only approval gate (ADR-004); no secret in any tool output; the skill asks in chat | B22, B25, B31: security gate bypass tests, injection corpus, skill evaluation |
| T-02 | 1 | Metadata is read by the model as instructions | T, E | Sanitise and delimit all YouTube text at the tool boundary (SEC-6, UI-6); tool descriptions state that delimited text is data | B10: injection corpus of 20 or more payloads |
| T-03 | 5 | A web page in the user's browser forges a POST to the approval page | T, E | Random path nonce, per-page CSRF value, Host and Origin checks, a single decision | B22: gate bypass tests (POST without CSRF is rejected) |
| T-04 | 5 | DNS rebinding or another origin reaches the loopback page | S, E | Host header check; random port and nonce; bound to 127.0.0.1 only (SEC-8) | B22 |
| T-05 | 5 | An approval is replayed or reused | R, T | Single-use approval stored as HMAC-SHA256, state transitions, 15-minute expiry | B22: reuse and expiry tests |
| T-06 | 1 | The proposal is changed between propose and confirm | T | The items hash is recomputed and compared before any write | B22, B25: altered-hash tests |
| T-07 | 4 | Token theft from disk or logs | I | OS keyring or Fernet file with mode 0600; tokens never logged or stored in fixtures; log redaction (SEC-2, SEC-7, SEC-10) | B19, B07: token store and redaction tests |
| T-08 | 3 | The app holds more permission than needed | E | Incremental scopes: youtube.readonly for reads, youtube only when creating (SEC-1) | B20: exact scope string tests |
| T-09 | 1 | A runaway AI loop exhausts the quota | D | Rate limit of 30 calls per minute (SEC-11), QuotaGuard estimate before any call (BR-2), machine budget | B15, B16, B30 |
| T-10 | 2 | Upstream error details leak to the model or logs | I | Errors are translated to the fixed catalogue with generic messages (UI-4); redacted logs | B04, B21 |
| T-11 | 6 | A malicious or mistyped dependency | T | Approved dependency list (ADR-001), pinned versions, pip-audit (SEC-9), names verified on PyPI | B18, H4 |
| T-12 | 6 | Secrets or personal data committed | I | .gitignore, gitleaks in pre-commit and CI (SEC-3), fixture scanner (SEC-7) | tests/security/test_fixture_clean.py |
| T-13 | 4 | Local tampering with the database or cache | T | File mode 0600 (SEC-10); the ledger is a soft control; a hostile local user is out of scope | B08 |
| T-14 | 4 | A write cannot be traced to its approval | R | Audit log of confirm and create events with opaque IDs (FR-5.14) | B17, B25 |
| T-15 | 1 | The offline fixture mode is mistaken for real writes | R | The fixture provider simulates writes in memory only and never calls the network | B04 |

## 3. Approval design

Flow in mode elicitation:
1. propose_playlist returns the proposal text and proposal_id; the proposal is stored in state PROPOSED with a 15-minute expiry.
2. The user says yes in chat; the client calls confirm_playlist(proposal_id).
3. The server builds a summary from the stored proposal (title, number of videos, total duration, visibility, shortfall if any, estimated cost) and sends an MCP elicitation request.
4. The client UI collects accept or decline. Accept: the server verifies the checks of ADR-004 point 3 and creates the playlist. Decline: the state becomes REJECTED.

Flow in mode oob:
1. Steps 1 and 2 as above.
2. The server sets approval_state to pending, starts the loopback listener, opens the approval page and returns APPROVAL_PENDING without the address.
3. The user presses Approve on the page; the server sets approval_state to granted (only the gate writes this).
4. The user tells the AI client to continue; the client calls confirm_playlist again; the server verifies the checks and creates the playlist.

Failure cases: the browser cannot be opened (the address is on stderr); the user closes the page (the proposal stays pending until it expires); the client closes (nothing is written); the proposal expires (state EXPIRED, propose again); a partial creation (state PARTIALLY_CREATED, resume needs a new approval); any doubt means refuse (fail closed).

## 4. Residual risks

- An AI agent that can control the user's browser or screen could press Approve on the page. Do not give such an agent computer control while a playlist is created.
- A malicious program running as the same user can read the database, the keyring and the loopback page. This is outside the threat model of a local developer tool.
- A user may approve without reading. The summary is short and states the count, duration, visibility and any shortfall.
- Some clients may truncate or restyle the elicitation prompt; the spike ES-1 checks that the text is shown.
- In Testing mode tokens expire every 7 days; this is a usability risk, not a security hole.

## 5. Verification

Security tests (TQ-SEC): scopes, token storage, secret scan, input fuzzing, the injection corpus, the gate bypass tests and log redaction, as listed in the SRS and in docs/design/build-contract.md. A skill evaluation covers an injection attempt (SK-8).

## 6. Brain notes

- [[prompt-injection]]
- [[oauth-testing-mode]]
- [[sqlite-wal]]
- [[youtube-api-quota]]
