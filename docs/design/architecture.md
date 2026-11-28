# Architecture

Version 1.0 (Stage 2). The build contract (docs/design/build-contract.md) is the detailed specification; this document explains how the parts fit together. Decisions: docs/adr/001 to 005. Security: docs/design/security.md. Diagrams: docs/design/diagrams.md.

## 1. System context

The end user talks to an AI client (the MCP host). The client calls tools and reads resources of the ytmcp server over MCP on stdio (JSON-RPC). The server calls the YouTube Data API v3 over HTTPS with credentials the user granted through Google OAuth 2.0, keeps a SQLite file for cache, quota ledger, proposals and audit log, and keeps refresh tokens in the operating system keyring. For approvals the server may open a loopback page in the user's browser. CI runs the tests on recorded fixtures only. The server is the only component under the team's control.

## 2. Packages and responsibilities

| Package (src/ytmcp) | Responsibility | May depend on |
|---|---|---|
| models, errors, config | typed data, the error catalogue, settings | nothing else in ytmcp |
| domain | pure functions: tokenising, TF-IDF, scoring, ranking, duration parsing, constraint solving, input validation, sanitising, statistics | models, errors |
| infra | clock, SQLite, cache, quota ledger, rate limiter, audit log, token store, OAuth, approval page | models, errors, config |
| providers | YouTubeProvider interface, API-backed provider, transports (fixture, live, recording), response mapping | models, errors, config, infra, domain |
| services | QuotaGuard, SimilarityService, RecommendationService, EngagementService, PlaylistService, ConfirmationGate | domain, providers.base, infra, models, errors, config |
| tools, resources | thin MCP handlers that validate input, call one service and render the result envelope | services, models, errors, domain.sanitiser |
| server.py, __main__.py | composition root: builds settings, clock, provider and services and registers the tools | everything |

Rules that are tested: domain never imports I/O or other packages (import-linter and tests/test_layers.py); only providers/live.py performs HTTP; only infra/token_store.py touches token secrets; only services/confirmation_gate.py grants approvals; only PlaylistService.confirm writes to YouTube.

## 3. Composition and dependency injection

server.py is the only place where concrete classes are chosen. build_server(settings, clock) creates the FastMCP server and calls the registrar of every tool module (the tuple TOOL_REGISTRARS), passing a ToolDeps object that holds the services the tools need. Services receive their dependencies in their constructors (provider, ledger, cache, clock). Nothing uses global state, so tests build their own small graphs with a FakeClock, a fixture provider and a temporary database.

## 4. Life of a request

Read tool (for example find_similar_videos):
1. The tool validates the parameters (input_validator) and calls the service.
2. The service builds a quota plan (a list of endpoint counts) and asks QuotaGuard.check; an estimate above the remaining budget is rejected before any API call (QUOTA_BUDGET_EXCEEDED).
3. The service reads the cache, calls the provider for what is missing, records the units spent and fills the cache.
4. Pure domain functions score and rank. The service returns models.
5. The tool sanitises and delimits every string that came from YouTube, builds the ToolResult envelope (structured payload, text summary, quota report, notices) and returns it.

Write path (playlist):
1. propose_playlist validates the request, checks the quota plan, gathers candidates through the provider, filters on metadata, scores relevance, solves the duration constraint, orders the result, stores the proposal (state PROPOSED, 15-minute expiry) and returns it without any secret.
2. confirm_playlist asks the ConfirmationGate for a human approval (elicitation or the loopback page), verifies the proposal (state, expiry, items hash, single-use approval), checks the quota plan (1 + 50 + 50 per item), creates the playlist and adds the items one by one, recording each success. A failure part-way gives PARTIALLY_CREATED and a later resume adds only the missing items after a new approval.

## 5. Provider architecture

YouTubeProvider (base.py) is the abstract interface. ApiBackedProvider (api_provider.py) implements every method once: it builds the request parameters, batches ids in groups of 50, follows pagination, translates API errors to the error catalogue and maps raw JSON to models (mapping.py). It talks to an ApiTransport with two methods, call (reads) and post (writes). The transports are: FixtureTransport (replays tests/fixtures/youtube files named method__hash16.json), LiveTransport (httpx, retries, quota recording, build item B21) and RecordingTransport (wraps the live transport and saves raw responses). FixtureYouTubeProvider adds in-memory write simulation with failure injection, which makes the offline demo and the playlist tests possible. Because fixtures and the live API use the same code path, a replayed test exercises the real request building and mapping.

## 6. State and storage

SQLite (WAL) holds the cache, the quota ledger, the request log, proposals with their items and the audit log (docs/design/schema.md). Refresh tokens are in the keyring, with an encrypted-file fallback. Taste profiles are kept only in memory or in the cache and can be purged. Configuration defaults are in config/default.toml with environment overrides.

## 7. Error handling

Expected failures are YtmcpError subclasses with a stable code, a plain message, a next step and a retryable flag. Pure domain code raises ValueError and the calling service converts it. Tool handlers turn an error into a ToolResult with ok false and an ErrorInfo. Transient upstream failures are retried at most three times with backoff and jitter; client errors are never retried.

## 8. Testing architecture

| Level | Directory | Marker | Data |
|---|---|---|---|
| Unit | tests/unit | unit | in memory; also run on macOS and Windows in CI |
| Integration | tests/integration | integration | fixtures and a temporary SQLite file |
| System | tests/system | system | the real server over stdio with the fixture provider |
| Negative | tests/negative | negative | error fixtures and fakes |
| Security | tests/security | security | injection corpus, gate bypass, scanners |
| Skill evaluations | tests/skill_eval | none | recorded scenarios |

CI never calls the live API. A scheduled workflow with a small fixed budget uses only an API key (build item B18).

## 9. Build order

| Wave | Items | Result |
|---|---|---|
| Foundations | B01 config, B02 errors and models, B03 clock, B04 providers and fixtures, B05 server skeleton, B06 fixtures, B11 duration | walking skeleton: the server starts and answers get_quota_status from the fixture provider |
| Infrastructure and pure logic | B07 logging, B08 database, B09 cache, B10 validator and sanitiser, B12 solver, B13 difficulty, B14 TF-IDF, B15 rate limiter, B16 quota guard, B17 audit log, B18 CI | tested building blocks |
| Authorisation and playlist | B19 tokens, B20 OAuth, B21 live provider, B22 approval gate, B23 ranker, B24 propose, B25 confirm, B26 similar videos | first working slice of FR-5 and FR-1 |
| Remaining features and skills | B27 channels, B28 recommendations, B29 engagement, B30 status tools, B31 video-to-playlist, B32 local-check, B33 skill evaluations | all features and skills |
| Hardening | H1 to H6 | benchmarks, mutation testing, compliance, documentation |

An item may start when every item in its Needs line is done (see docs/ai/briefs).
