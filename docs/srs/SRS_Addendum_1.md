# SRS Addendum 1

Addendum 1 to the Software Requirements Specification v1.0, YouTube Video Intelligence MCP Server (Team Larpers).
Status: accepted when merged by pull request. Precedence: this addendum governs for the items listed here; everything else in SRS v1.0 is unchanged.

## 1. Part A: Resolutions of open items (SRS Appendix C)

| ID | Decision | Notes |
|---|---|---|
| TBD-1 | Refresh tokens are stored in the OS keyring (library keyring). Fallback: an encrypted file using Fernet, with a key derived by scrypt from a passphrase taken from the environment variable YTMCP_TOKEN_PASSPHRASE or an interactive prompt. The passphrase is never stored. Files get mode 0600 on POSIX systems. | SEC-2, SEC-10, ADR-005 |
| TBD-2 | Cache lifetimes: video and channel records 24 hours (they include statistics); search results 24 hours; video categories 7 days. This is stricter than BR-6. | Config keys cache.ttl_video_channel_h, cache.ttl_search_h, cache.ttl_categories_d |
| TBD-3 | Release 1.0 uses MCP over stdio only. Streamable HTTP is deferred. | The loopback approval page in SA-1 is not an MCP transport. |
| TBD-4 | Difficulty for FR-5.7 ordering: d = 0.6 x min(1, duration / max_video_duration) + 0.4 x level. level is 0 if the title or tags contain intro, introduction, basics, beginner, overview, 101 or crash course; 1 if they contain advanced, deep dive, proof, theory, masterclass or graduate; otherwise 0.5. Order ascending d, then relevance descending, then video ID ascending. | FR-5.7 |
| TBD-5 | Fixtures use our own replay tooling: FixtureYouTubeProvider, RecordingProvider and scripts/sanitise_fixture.py. | SE-6, TQ-5 |

## 2. Part B: Changes and clarifications

### SA-1 Human-only approval gate

Changes: SEC-5, FR-5.9, section 4.5.2 (stimulus and response), Appendix D rows for propose_playlist and confirm_playlist, sequence steps 11 to 16 of the playlist creation sequence, the ER column token_hash (renamed approval_hash), and the glossary entry Confirmation token.

1. propose_playlist shall return the proposal without any confirmation token, code, or other value that alone authorises a write.
2. confirm_playlist shall take only proposal_id as input.
3. Approval shall be collected from the human through a channel the AI model cannot read: (a) MCP elicitation when the client advertises that capability; otherwise (b) a loopback approval page on 127.0.0.1 with a random port, a random path nonce, a per-page CSRF value, Host and Origin checks and a single decision. The server opens the page in the system browser; its address shall not appear in any tool output.
4. Configuration key approval.mode takes auto, elicitation or oob. auto uses elicitation when the client advertised it and oob otherwise.
5. The server shall verify, failing closed: the proposal exists; its state is PROPOSED (or PARTIALLY_CREATED on resume); it is unexpired (15 minutes); the items hash is unchanged; the approval is consumed exactly once. Approvals and nonces are stored only as HMAC-SHA256 values keyed with a per-install secret.
6. The intent of SEC-5 is preserved (server-issued, single-use, proposal-bound, time-limited, verified server-side, any change invalidates). Removed: the statement that the token is released to the client together with the proposal.
7. SK-3 and UI-3 are unchanged: the skill still asks the user in chat and stops. Human approval is a second, independent control.
8. No remote exposure is introduced (SRS section 3.4).

Appendix D replacement rows:

| Tool | Inputs | Output | Read-only |
|---|---|---|---|
| propose_playlist | topic, total_duration, max_video_duration, language, title?, visibility? | Proposal with proposal_id, items, totals, constraint report, cost estimate; no secret | Yes (no YouTube write) |
| confirm_playlist | proposal_id | Playlist URL and quota report, or APPROVAL_PENDING, or a partial-progress report | No (write) |

### SA-2 State PARTIALLY_CREATED

Changes: FR-5.11, the proposal lifecycle state machine, the ER tables playlist_proposal and proposal_item.

States: DRAFT, PROPOSED, CONFIRMED, CREATED, PARTIALLY_CREATED, FAILED, REJECTED, EXPIRED.

| From | Event | To |
|---|---|---|
| DRAFT | Constraints solved (feasible, or shortfall reported) | PROPOSED |
| PROPOSED | Approval granted and verified | CONFIRMED |
| PROPOSED | User declines, or approval denied | REJECTED |
| PROPOSED | Time-to-live of 15 minutes elapsed | EXPIRED |
| CONFIRMED | Playlist and all items added | CREATED |
| CONFIRMED | Playlist exists but at least one item failed | PARTIALLY_CREATED |
| CONFIRMED | Failure before any playlist exists | FAILED |
| PARTIALLY_CREATED | User asks to resume, with a new approval | CONFIRMED |

Rules:
1. The playlist identifier is stored on the proposal (column playlist_id). Each item has a flag added_ok.
2. Before resuming, the server lists the items of the playlist (playlistItems.list, 1 unit) so that a lost response never causes a duplicate.
3. Resume requires a new approval for the same proposal_id and the same items hash, adds only the missing items, and must happen within a 15-minute window from the resume request.
4. Estimated cost of a resume: 1 + 50 x number of missing items.

### SA-3 Error codes

Add APPROVAL_PENDING (approval not yet granted; retry after the human acts) and EMPTY_PROFILE (no likes, subscriptions or playlists; already used in section 4.3.2) to Appendix D.2. PROPOSAL_INVALID also covers a declined approval.

### SA-4 Clarifications

| ID | Clarification |
|---|---|
| C-1 | The tool parameters total_duration and max_video_duration are integers in seconds. |
| C-2 | Quota: in addition to QTA-3, machine_daily_budget is a soft per-machine limit. QuotaGuard rejects a request when its estimate exceeds the smaller of the global remaining budget and the machine remaining budget. Ledgers are local, so the API response quotaExceeded is the only global signal. |
| C-3 | FR-1 uses one search.list query by default (about 102 units cold: 1 videos.list for the seed, 100 for the search, 1 videos.list for up to 50 candidates). Playlist proposals use two queries (SRS Appendix D.3, 653 units in total). |
| C-4 | Channel input resolution (FR-2.1): a /channel/ID URL or UC identifier is used directly; @handle uses channels.list forHandle (1 unit); /user/name uses channels.list forUsername (1 unit); /c/name uses search.list type=channel (100 units) and returns a notice. |
| C-5 | FR-4.6 states the data limitations (no watch history; liked videos have no like timestamps) in every report. FR-4.7 requires local processing only. |

## 3. Diagram sources

SRS v1.0 refers to figures. Their sources (PlantUML or Mermaid) are created in Stage 2 (task S2-3) under docs/design/: context, layers, class, sequences for FR-1, FR-3 and FR-5, proposal state machine (SA-2), use cases, ER, data flow.

## 4. Traceability of changes

| Change | SRS items | Master Project Plan v3 | ADR |
|---|---|---|---|
| TBD-1 to TBD-5 | Appendix C | Sections 1.2, 5.11 | ADR-005, ADR-003 |
| SA-1 | SEC-5, FR-5.9, App. D | Sections 5.8, 5.10 | ADR-004 |
| SA-2 | FR-5.11 | Section 5.9 | ADR-004 |
| SA-3 | App. D.2 | Section 5.5 | none |
| SA-4 | QTA-3, FR-1, FR-2.1, FR-4.6, FR-4.7 | Sections 5.8, 5.12 | none |
