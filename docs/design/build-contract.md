# Build contract

Single source of truth for code generation. Version 1.0 (Stage 2).
Derived from SRS v1.0, SRS Addendum 1 and Master Project Plan v3 section 5. Items marked (added) fill gaps that the plan left open. If this file conflicts with the SRS or Addendum 1, they win and this file is corrected by a commit.
Build item briefs (docs/ai/briefs) and the Stage 2 prompts refer to the sections of this file by number.

## 1. Conventions

- Python 3.11 or newer. Type hints everywhere. pydantic v2 models with frozen=True and extra="forbid". No global state: dependencies are passed in.
- Datetimes are timezone-aware and in UTC. Durations are integer seconds. Quota is counted in integer units.
- Identifiers: a video ID matches ^[A-Za-z0-9_-]{11}$; a channel ID matches ^UC[A-Za-z0-9_-]{22}$; a proposal ID is a lower-case UUID4 string.
- Video and channel ID patterns define the required format, not whether the corresponding item exists on YouTube. Existence and availability are checked by the provider/API layer.
- Models hold the raw text that comes from YouTube. Only tools/ and resources/ sanitise and delimit it (section 9).
- Endpoint names: search_list, videos_list, channels_list, subscriptions_list, playlists_list, playlist_items_list, video_categories_list, playlists_insert, playlist_items_insert. They are the keys of quota.costs (section 3) and are used unchanged as quota endpoints, plan endpoints, transport method names and fixture method names.
- Expected failures are YtmcpError subclasses (section 6). Pure domain functions raise ValueError and the calling service converts it.
- Tests: every unit test carries the marker unit (CI runs unit tests on Linux, macOS and Windows). Other levels carry integration, system, negative or security.
- Style: ruff with line length 100 and rules E, F, I, B, UP, C90 (complexity at most 10); mypy strict for ytmcp.domain. Plain ASCII in code and documents.

## 2. Layer rules

Enforced by import-linter (pyproject.toml) and, from build item B18, by tests/test_layers.py.

| Package | May import from ytmcp |
|---|---|
| models, errors, config | nothing else from ytmcp |
| domain | models and errors only; standard library; pure functions with no I/O, no clock and no randomness (time and RNG are arguments); never config |
| infra | models, errors, config |
| providers | models, errors, config, infra and domain (added: providers may import ytmcp.domain.duration for duration parsing; mapping.py also uses the duration parser) |
| services | domain, providers.base, infra, models, errors, config; never a concrete provider (live, fixture, recording) |
| tools, resources | services, models, errors; plus domain.sanitiser for wrapping untrusted text (added: the pyproject import-linter contract gets this single exception when the first tool needs it) |

Provider architecture:
- providers/transport.py defines the transport abstraction used by API-backed providers.
- providers/api_provider.py implements the API-backed provider operations and delegates HTTP transport through the injected transport abstraction.
- providers/live.py is the live provider integration and performs the concrete HTTP execution through the transport implementation. No other provider component performs direct HTTP requests.
- Provider dependencies are passed in; do not introduce global state.
- providers/transport.py and providers/api_provider.py are part of the intended provider architecture and must be included in the relevant build items and prompts.

Further rules:
- Only providers/live.py performs HTTP to the YouTube API and only infra/oauth.py talks to the Google OAuth endpoints (through google-auth-oauthlib). Only infra/token_store.py touches token secrets. Only services/confirmation_gate.py may set an approval to granted. Only PlaylistService.confirm calls create_playlist or add_playlist_item.
- Every service operation that spends quota: build a plan, QuotaGuard.check, execute, record.
- No tool handler calls a provider directly.

## 3. Configuration

Defaults live in config/default.toml (already in the repository; the models must accept exactly its keys). Loader: src/ytmcp/config.py (build item B01).

| Section | Keys | Type and constraint |
|---|---|---|
| quota | daily_budget, machine_daily_budget | int, greater than 0 |
| quota | safety_reserve_pct | int, 0 to 50 |
| quota | reset_tz | string, a valid IANA time zone name |
| quota.costs | search_list, videos_list, channels_list, subscriptions_list, playlists_list, playlist_items_list, video_categories_list, playlists_insert, playlist_items_insert | int, 0 or more |
| similarity | default_limit, channel_default_limit, default_candidates, fr1_search_queries, channel_recent_uploads | int, 1 or more |
| similarity | max_limit, channel_max_limit, max_candidates | int, at least default_limit, channel_default_limit and default_candidates respectively |
| similarity | field_weight_title, field_weight_tags, field_weight_description | int, 1 or more |
| similarity.video | text, tag, category, duration, language | float, 0 or more, sum equal to 1.0 (tolerance 1e-6) |
| similarity.channel | text, topic, cadence, size | float, 0 or more, sum equal to 1.0 (tolerance 1e-6) |
| taste | likes, playlists, subscriptions | float, 0 or more, sum equal to 1.0 (tolerance 1e-6) |
| taste | half_life_days, source_cap, per_channel_top10 | int, 1 or more |
| taste | mmr_lambda | float, 0 to 1 |
| playlist | tolerance_pct | int, 0 to 50 |
| playlist | per_channel_cap, dp_unit_s, dp_top_n, search_queries, min_item_s, topic_max_len, title_max_len, proposal_ttl_min | int, 1 or more |
| playlist | min_total_s, max_total_s | int, 1 or more, max_total_s at least min_total_s |
| playlist | default_visibility | one of private, unlisted, public |
| cache | ttl_video_channel_h, ttl_search_h, ttl_categories_d | int, 1 or more |
| limits | rate_limit_per_min, max_input_len, http_timeout_s | int, 1 or more |
| limits | retry_max | int, 0 or more |
| approval | mode | one of auto, elicitation, oob |

Top-level additions (added): provider (one of fixture, live, recording; default fixture) and data_dir (a path; default ~/.local/share/ytmcp expanded).

Class names in config.py: Settings, QuotaConfig, QuotaCosts, SimilarityConfig, VideoWeights, ChannelWeights, TasteConfig, PlaylistConfig, CacheConfig, LimitsConfig, ApprovalConfig, plus ConfigError (a ValueError subclass). Settings has the fields quota, similarity, taste, playlist, cache, limits, approval, provider, data_dir. QuotaConfig has the nested field costs; SimilarityConfig has the nested fields video and channel.

Loader API: load_settings(path=None, env=None) returns Settings. path defaults to DEFAULT_CONFIG_PATH, which is <repository root>/config/default.toml. env defaults to the process environment; an explicit empty mapping means no environment at all.

Environment rules:
- Override: a variable named YTMCP_<PATH> whose <PATH> contains the separator "__". <PATH> is lower-cased and split on "__" into a key path. Examples: YTMCP_QUOTA__COSTS__SEARCH_LIST sets quota.costs.search_list; YTMCP_APPROVAL__MODE sets approval.mode. The value is a string that is coerced to the type of the key.
- An override must name an existing value key. An unknown key, an unknown section, a table instead of a value, a path that continues below a value, or an empty path segment is a ConfigError that names the variable.
- Special variables without "__": YTMCP_PROVIDER sets provider; YTMCP_DATA_DIR sets data_dir (a leading ~ is expanded; an empty string counts as unset).
- Every other variable is ignored. In particular YTMCP_TOKEN_PASSPHRASE is never read by the configuration and secrets are never stored in Settings.

## 4. Models (src/ytmcp/models.py)

All models are pydantic v2 models with frozen=True and extra="forbid". List and dict fields default to empty collections using default_factory; mutable collection defaults must not be shared between model instances. "aware datetime" means pydantic AwareDatetime (a naive datetime is rejected).

Aliases and constants: Visibility is one of "private", "unlisted", "public". Privacy has the same three values. LiveStatus is one of "none", "live", "upcoming". Endpoint is one of the nine endpoint names of section 1, and ENDPOINTS is the tuple of those nine names in the order listed in section 1. ProposalState is a StrEnum whose values equal their names, in this order: DRAFT, PROPOSED, CONFIRMED, CREATED, PARTIALLY_CREATED, FAILED, REJECTED, EXPIRED.

| Model | Fields |
|---|---|
| Video | id: str matching ^[A-Za-z0-9_-]{11}$; title: str; description: str = ""; tags: list[str] default empty; category_id: str or None = None; duration_s: int or None, 0 or more = None; channel_id: str matching ^UC[A-Za-z0-9_-]{22}$; channel_title: str = ""; language: str or None = None; published_at: aware datetime; privacy: Privacy = "public"; live_status: LiveStatus = "none"; view_count: int or None, 0 or more = None; like_count: int or None, 0 or more = None; embeddable: bool or None = None |
| Channel | id: str matching ^UC[A-Za-z0-9_-]{22}$; title: str; description: str = ""; keywords: list[str] default empty; topic_ids: list[str] default empty; subscriber_count: int or None, 0 or more = None (None when hidden); video_count: int or None, 0 or more = None; uploads_playlist_id: str or None = None; published_at: aware datetime |
| ChannelRef | kind: one of "id", "handle", "username", "custom"; value: str (1 or more chars) |
| Subscription | channel_id: str matching ^UC[A-Za-z0-9_-]{22}$; channel_title: str; subscribed_at: aware datetime |
| Playlist | id: str; title: str; item_count: int, 0 or more; published_at: aware datetime |
| PlaylistItem | playlist_id: str; video_id: str matching ^[A-Za-z0-9_-]{11}$; added_at: aware datetime; position: int, 0 or more |
| TextDoc (added) | id: str; title: str = ""; tags: list[str] default empty; description: str = "" |
| ChannelProfile (added) | channel: Channel; recent_titles: list[str] default empty; recent_tags: list[str] default empty; recent_published_at: list of aware datetimes default empty |
| PlaylistRequest | topic: str, 1 to 200 chars; total_duration_s: int, 300 to 86400; max_video_duration_s: int, 60 or more and at most total_duration_s (model-level check); language: str matching ^[a-z]{2}$; title: str or None, 1 to 150 chars when present = None; visibility: Visibility = "private"; tolerance_pct: int, 0 to 50 = 5 |
| Candidate | video_id: str matching ^[A-Za-z0-9_-]{11}$; channel_id: str matching ^UC[A-Za-z0-9_-]{22}$; duration_s: int, 0 or more; relevance: float; difficulty: float = 0.0 |
| SolveSpec | target_s: int, 1 or more; tolerance_pct: int, 0 to 50; max_item_s: int, 1 or more; per_channel_cap: int, 1 or more; dp_unit_s: int, 1 or more; dp_top_n: int, 1 or more |
| SolveResult | items: list[Candidate] default empty; total_s: int, 0 or more; feasible: bool; shortfall_s: int, 0 or more; message: str |
| ProposalItem | position: int, 1 or more; video_id: str matching ^[A-Za-z0-9_-]{11}$; title: str; channel_id: str matching ^UC[A-Za-z0-9_-]{22}$; channel_title: str; duration_s: int, 0 or more; score: float |
| Proposal | proposal_id: str matching the lower-case UUID4 pattern ^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$; request: PlaylistRequest; items: list[ProposalItem] default empty; total_s: int, 0 or more; feasible: bool; shortfall_message: str or None = None; state: ProposalState; items_hash: str matching ^[0-9a-f]{64}$; expires_at: aware datetime; estimated_cost: int, 0 or more; playlist_id: str or None = None |
| ScoredVideo | video_id: str matching ^[A-Za-z0-9_-]{11}$; score: float; components: dict of str to float or None default empty; notes: list[str] default empty |
| ScoredChannel | channel_id: str matching ^UC[A-Za-z0-9_-]{22}$; score: float; components: dict of str to float or None default empty; notes: list[str] default empty |
| TasteProfile (added) | vector: dict of str to float default empty; top_terms: list[str] default empty; source_counts: dict of str to int default empty |
| PlanItem | endpoint: Endpoint; count: int, 0 or more |
| Estimate | units: int, 0 or more; remaining_after: int |
| QuotaStatus | used_today: int, 0 or more; remaining: int; reserve: int, 0 or more; machine_remaining: int; reset_at: aware datetime; exhausted: bool |
| QuotaReport (added) | spent: int, 0 or more; remaining: int; estimate: int or None = None |
| ErrorInfo (added) | code: str; message: str; next_step: str |
| ToolResult | ok: bool; summary: str; data: dict of str to any default empty; quota: QuotaReport; notices: list[str] default empty; error: ErrorInfo or None = None. Rule: ok true requires error None; ok false requires an error |
| ConfirmResult (added) | state: ProposalState; playlist_id: str or None = None; playlist_url: str or None = None; items_added: int, 0 or more; items_missing: int, 0 or more; notices: list[str] default empty |

## 5. SQLite schema (migrations/001_init.sql, build item B08)

Pragmas on every connection: journal_mode=WAL, busy_timeout=5000, foreign_keys=ON, synchronous=NORMAL.

```sql
CREATE TABLE schema_version(version INTEGER NOT NULL);
CREATE TABLE oauth_token(token_id INTEGER PRIMARY KEY, account_hash TEXT, scopes TEXT, keyring_ref TEXT,
                         issued_at TEXT, expires_at TEXT);
CREATE TABLE quota_ledger(entry_id INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT NOT NULL,
                          endpoint TEXT NOT NULL, units INTEGER NOT NULL, pt_day TEXT NOT NULL, created_at TEXT);
CREATE TABLE request_log(request_id TEXT PRIMARY KEY, tool_name TEXT, est_units INTEGER, actual_units INTEGER,
                         outcome TEXT, created_at TEXT);
CREATE TABLE video_cache(video_id TEXT PRIMARY KEY, json TEXT, etag TEXT, fetched_at TEXT, ttl_s INTEGER);
CREATE TABLE channel_cache(channel_id TEXT PRIMARY KEY, json TEXT, etag TEXT, fetched_at TEXT, ttl_s INTEGER);
CREATE TABLE kv_cache(key TEXT PRIMARY KEY, json TEXT, fetched_at TEXT, ttl_s INTEGER);
CREATE TABLE playlist_proposal(proposal_id TEXT PRIMARY KEY, request_json TEXT, items_hash TEXT, total_s INTEGER,
                               feasible INTEGER, state TEXT, approval_state TEXT DEFAULT 'none',
                               approval_hash TEXT, playlist_id TEXT, created_at TEXT, expires_at TEXT);
CREATE TABLE proposal_item(proposal_id TEXT, pos INTEGER, video_id TEXT, score REAL, duration_s INTEGER,
                           added_ok INTEGER DEFAULT 0, PRIMARY KEY(proposal_id, pos),
                           FOREIGN KEY(proposal_id) REFERENCES playlist_proposal(proposal_id));
CREATE TABLE audit_log(audit_id INTEGER PRIMARY KEY AUTOINCREMENT, event TEXT, proposal_id TEXT, actor TEXT,
                       created_at TEXT);
```

approval_state is one of none, pending, granted, denied. oauth_token holds metadata only; the secret stays in the keyring. audit_log holds opaque IDs only.

## 6. Error catalogue (src/ytmcp/errors.py, build item B02)

Retryable is true when repeating the same request later, after waiting or after a human action, can succeed.

| Code | Class | Retryable | Default message | Default next step |
|---|---|---|---|---|
| INVALID_ID | InvalidId | false | The video, channel or playlist identifier is not valid. | Check the URL or ID format. |
| INVALID_PARAMETER | InvalidParameter | false | A parameter is missing or out of range. | Check the parameter values against the tool description. |
| NOT_FOUND_OR_PRIVATE | NotFoundOrPrivate | false | The item does not exist or is private. | Use a public video or channel. |
| AUTH_REQUIRED | AuthRequired | true | Authorisation is required. | Authorise this app in the browser window, then retry. |
| REAUTH_REQUIRED | ReauthRequired | true | The authorisation has expired or was revoked. | Re-authorise in the browser, then retry. |
| CHANNEL_REQUIRED | ChannelRequired | true | This Google account has no YouTube channel. | Create a YouTube channel, then retry. |
| EMPTY_PROFILE | EmptyProfile | false | There are no likes, subscriptions or playlists to learn from. | Provide a topic or a seed video. |
| QUOTA_BUDGET_EXCEEDED | QuotaBudgetExceeded | true | The estimated cost exceeds the remaining quota budget. | Reduce the request or wait until the quota resets. |
| QUOTA_EXHAUSTED | QuotaExhausted | true | The YouTube API quota is used up for today. | Wait until the quota resets (midnight Pacific Time). |
| RATE_LIMITED | RateLimited | true | Too many requests. | Wait a moment, then retry. |
| APPROVAL_PENDING | ApprovalPending | true | Waiting for the human approval. | Approve in the browser window opened on your computer, then ask me to continue. |
| PROPOSAL_INVALID | ProposalInvalid | false | The proposal is unknown, expired, altered, already used or was declined. | Ask for a new proposal. |
| UPSTREAM_ERROR | UpstreamError | true | YouTube or the network failed after retries. | Try again shortly; partial progress is reported if any. |

## 7. Signatures

### 7.1 Domain (pure functions, src/ytmcp/domain)

| Module | Signature | Notes |
|---|---|---|
| duration.py | parse_iso8601_duration(s: str) -> int; format_mmss(seconds: int) -> str | B11 |
| tokenizer.py | tokenize(text: str) -> list[str] | B14 |
| tfidf.py | build_corpus(docs: list[TextDoc]) -> Corpus; vectorise(doc: TextDoc, corpus: Corpus) -> dict[str, float] | B14 |
| cosine.py | cosine(a, b) -> float; jaccard(a: set[str], b: set[str]) -> float or None; proximity(x: float, y: float, factor: float) -> float or None | B14 |
| ranker.py | rank_videos(seed: Video, cands: list[Video], w: Mapping[str, float], limit: int) -> list[ScoredVideo]; rank_channels(seed: ChannelProfile, cands: list[ChannelProfile], w: Mapping[str, float], limit: int) -> list[ScoredChannel] | B23; w is a weight group of section 3 as a plain mapping |
| constraint_solver.py | solve(cands: list[Candidate], spec: SolveSpec) -> SolveResult | B12 |
| difficulty.py | difficulty(v: Video, max_item_s: int) -> float; order_playlist(items: list[Candidate]) -> list[Candidate] | B13 |
| input_validator.py | normalise_video_id(raw: str) -> str; normalise_channel_ref(raw: str) -> ChannelRef; validate_playlist_request(raw: Mapping[str, object]) -> PlaylistRequest | B10; raise InvalidId or InvalidParameter |
| sanitiser.py | sanitise_text(s: str, max_len: int = 500) -> str; wrap_untrusted(s: str) -> str | B10 |
| taste_profile.py | build_taste_profile(...) -> TasteProfile; mmr_select(...) -> list[ScoredVideo] | B28; exact parameters are fixed in that brief |
| stats.py | top_channels, category_distribution, trend, duration_stats(durations_s: list[int]) -> dict, compare_periods(cur: Mapping, prev: Mapping) -> dict | B29; exact parameters are fixed in that brief |

### 7.2 Infrastructure (src/ytmcp/infra)

| Module | Interface | Notes |
|---|---|---|
| clock.py | Clock (abstract): now() -> datetime (UTC); reset_day() -> str (YYYY-MM-DD in the configured reset time zone); next_reset() -> datetime (UTC, added). SystemClock(reset_tz). FakeClock(start, reset_tz) with set(value) and advance(seconds). make_rng(seed=None) -> random.Random | B03 |
| db.py | connect(path) -> sqlite3.Connection; migrate(conn) -> None; a transaction helper | B08 |
| cache.py | Cache.get(key, kind) -> dict or None; Cache.put(key, kind, value) -> None; kinds are video, channel, search, categories | B09 |
| rate_limiter.py | RateLimiter.acquire(client_id) -> None, raises RateLimited | B15 |
| quota_ledger.py | records endpoint and units per call by reset-time-zone day | B16 |
| token_store.py | TokenStore.save(account, refresh_token, scopes), load(), delete() | B19 |
| oauth.py | OAuthManager.credentials(scopes) -> Credentials | B20 |
| audit_log.py | AuditLog.write(event, proposal_id, actor) | B17 |
| approval_server.py | loopback approval page (section 10) | B22 |

### 7.3 Services (src/ytmcp/services)

| Class | Methods |
|---|---|
| QuotaGuard | check(plan: list[PlanItem], request_id: str) -> Estimate (raises QuotaBudgetExceeded before any call); record(endpoint, units, request_id); status() -> QuotaStatus; mark_exhausted() |
| SimilarityService | similar_videos(video, limit, filters); similar_channels(channel, limit, exclude_subscribed) |
| RecommendationService | recommend(limit, sources, filters) |
| EngagementService | analyse(period, compare_to, dimensions, top_k) |
| PlaylistService | propose(req: PlaylistRequest) -> Proposal; confirm(proposal_id) -> ConfirmResult |
| ConfirmationGate | request_approval(proposal, ctx) returns granted, denied or pending; verify_and_consume(proposal_id) |

## 8. Providers (YouTube access)

### 8.1 Files and roles

| File | Content | Build item |
|---|---|---|
| providers/base.py | YouTubeProvider, the abstract interface (8.2) | B04 |
| providers/transport.py | (added) ParamValue, Params, READ_METHODS, WRITE_METHODS, ApiTransport, FixtureMissing, ApiHttpError, canonical_json, fixture_key, error_reasons, translate_api_error (8.3, 8.6) | B04 |
| providers/mapping.py | MappingError and the functions that turn raw API JSON into models (8.5) | B04 |
| providers/api_provider.py | (added) ApiBackedProvider: builds API requests, follows pagination, translates errors, maps responses (8.4). No I/O of its own | B04 |
| providers/fixture.py | FixtureTransport and FixtureYouTubeProvider (8.7) | B04 |
| providers/live.py | LiveTransport (httpx, retries) and LiveYouTubeProvider | B21 |
| providers/recording.py | RecordingTransport and RecordingProvider (wrap the live transport and save raw responses) | B21 |

FixtureYouTubeProvider, LiveYouTubeProvider and RecordingProvider all derive from ApiBackedProvider and differ only in the transport (and, for the fixture provider, in simulated writes). One request-building and mapping code path therefore serves fixtures and the live API.

Quota recording is owned by the service/QuotaGuard flow described in sections 2 and 7.3. Transports do not independently record quota. Each service operation that spends quota must build a plan, call QuotaGuard.check before execution, and record the actual usage through QuotaGuard after execution.

### 8.2 YouTubeProvider (all methods abstract)

| Method | Signature | Meaning |
|---|---|---|
| get_videos | (ids: Sequence[str]) -> list[Video] | metadata in input order; ids that do not exist are absent |
| search | (q: str, *, type: "video" or "channel" = "video", max_results: int = 50, language: str or None = None, published_after: str or None = None) -> list[str] | IDs only |
| get_channels | (ids: Sequence[str]) -> list[Channel] | |
| resolve_channel | (ref: ChannelRef) -> str or None | channel ID or None |
| recent_uploads | (channel: Channel, n: int = 15) -> list[str] | video IDs of the newest uploads |
| list_liked | (cap: int = 200) -> list[Video] | |
| list_subscriptions | (cap: int = 200) -> list[Subscription] | |
| list_playlists | (cap: int = 200) -> list[Playlist] | |
| list_playlist_items | (playlist_id: str, cap: int = 200) -> list[PlaylistItem] | |
| video_categories | (region: str = "US") -> dict[str, str] | category ID to name |
| my_channel | () -> Channel or None | None when the account has no channel |
| create_playlist | (title: str, description: str, visibility: Visibility) -> str | playlist ID |
| add_playlist_item | (playlist_id: str, video_id: str) -> None | |

### 8.3 Transport

- ParamValue is str or int. Params is a mapping of str to ParamValue.
- READ_METHODS: videos_list, search_list, channels_list, subscriptions_list, playlists_list, playlist_items_list, video_categories_list. WRITE_METHODS: playlists_insert, playlist_items_insert.
- ApiTransport (a typing Protocol) has call(method: str, params: Params) -> dict, for read methods, and post(method: str, params: Params, body: Mapping) -> dict, for write methods. Both return the decoded JSON body and raise ApiHttpError(status, body) when the API answers with a status of 400 or more.
- FixtureMissing is a LookupError subclass raised when a fixture cannot be served.
- canonical_json(obj) is json.dumps with sorted keys, separators "," and ":" and ensure_ascii true.
- fixture_key(method, params) is the method name, two underscores, and the first 16 hexadecimal characters of the SHA-256 of canonical_json(params) encoded as UTF-8.
- Fixture file: tests/fixtures/youtube/<fixture_key>.json, a UTF-8 JSON object with the keys method, args and response, and an optional integer status (absent means 200). A status of 400 or more replays an API error.
- Reference values: canonical_json of {"q": "caf<e acute>", "n": 1}, with the e acute written as the single character U+00E9, is {"n":1,"q":"caf\u00e9"} (the backslash-u sequence is literal text). fixture_key("videos_list", {"id": "abc", "part": "snippet"}) is videos_list__7700128999ee1617. fixture_key("search_list", {"part": "snippet", "q": "linear algebra", "type": "video", "maxResults": 50}) is search_list__65bb0d0980a50a3f.

### 8.4 Requests built by ApiBackedProvider

Constants: VIDEO_PARTS is "snippet,contentDetails,statistics,status". CHANNEL_PARTS is "snippet,contentDetails,statistics,brandingSettings,topicDetails". PAGE_SIZE is 50.

| Provider method | Transport method and params | Rules |
|---|---|---|
| get_videos(ids) | videos_list: part=VIDEO_PARTS, id=comma-joined sorted IDs of one batch | remove duplicate IDs keeping the first; batches of 50; result keeps input order; no ids means no call |
| search(...) | search_list: part=snippet, q, type, maxResults=min(50, still needed); relevanceLanguage when language is given; publishedAfter when published_after is given; pageToken on later pages | follow nextPageToken until max_results IDs are collected or no token or a repeated token; no duplicates; return the first max_results IDs |
| get_channels(ids) | channels_list: part=CHANNEL_PARTS, id=comma-joined sorted IDs of one batch | same batching and ordering rules as get_videos |
| resolve_channel(ref) | kind id: get_channels([value]), return value if found else None. kind handle: channels_list part=id, forHandle=value. kind username: channels_list part=id, forUsername=value. kind custom: search_list part=snippet, q=value, type=channel, maxResults=5 | for handle and username read the raw item IDs; for custom read the first channel ID; return the first ID or None |
| recent_uploads(channel, n) | playlist_items_list: part=snippet,contentDetails, playlistId=channel.uploads_playlist_id, maxResults=min(n, 50), pageToken on later pages | paginate until n video IDs are collected, no nextPageToken is returned, or a token repeats; return at most n IDs; no uploads playlist or n <= 0 means an empty list and no call |
| list_liked(cap) | videos_list: part=VIDEO_PARTS, myRating=like, maxResults=50, pageToken on later pages | paged; a cap of 0 or less means an empty list and no call |
| list_subscriptions(cap) | subscriptions_list: part=snippet, mine=true, maxResults=50 | paged |
| list_playlists(cap) | playlists_list: part=snippet,contentDetails, mine=true, maxResults=50 | paged |
| list_playlist_items(playlist_id, cap) | playlist_items_list: part=snippet,contentDetails, playlistId, maxResults=50 | paged |
| video_categories(region) | video_categories_list: part=snippet, regionCode=region | |
| my_channel() | channels_list: part=CHANNEL_PARTS, mine=true | first channel or None |
| create_playlist(title, description, visibility) | post playlists_insert with params part=snippet,status and body {"snippet": {"title", "description"}, "status": {"privacyStatus": visibility}} | return the string "id" of the response; a missing id raises MappingError |
| add_playlist_item(playlist_id, video_id) | post playlist_items_insert with params part=snippet and body {"snippet": {"playlistId", "resourceId": {"kind": "youtube#video", "videoId"}}} | |

Paged methods stop when the cap is reached, when there is no nextPageToken, or when a token repeats, and return the first cap items. Every transport call is wrapped so that ApiHttpError becomes translate_api_error(status, body) (8.6) raised as the translated error.

### 8.5 Mapping rules (providers/mapping.py)

MappingError is a ValueError subclass. A timestamp is parsed with datetime.fromisoformat after replacing a trailing Z with +00:00; a naive result is treated as UTC; an invalid timestamp is a MappingError. A response without an items list means an empty list.

| Function | Rules |
|---|---|
| map_video(item) | Required: id (str), snippet.title, snippet.channelId, snippet.publishedAt; otherwise MappingError. description default empty; tags default empty list; categoryId to category_id or None; channelTitle default empty; language is normalise_language(defaultAudioLanguage) or, if that is None, normalise_language(defaultLanguage); privacy is status.privacyStatus when it is public, unlisted or private, otherwise public; live_status is snippet.liveBroadcastContent when it is live or upcoming, otherwise none; duration_s from contentDetails.duration through parse_iso8601_duration (missing means None, invalid means MappingError); view_count and like_count from statistics (strings to int; missing means None; not numeric means MappingError); embeddable is status.embeddable when it is a bool, otherwise None |
| map_channel(item) | Required: id, snippet.title, snippet.publishedAt. description default empty; keywords from parse_keywords(brandingSettings.channel.keywords); topic_ids from topicDetails.topicIds (default empty); subscriber_count from statistics.subscriberCount, but None when statistics.hiddenSubscriberCount is true or the value is missing; video_count from statistics.videoCount or None; uploads_playlist_id from contentDetails.relatedPlaylists.uploads or None |
| map_subscription(item) | Required: snippet.resourceId.channelId, snippet.title, snippet.publishedAt (becomes subscribed_at) |
| map_playlist(item) | Required: id, snippet.title, snippet.publishedAt; item_count from contentDetails.itemCount, default 0 |
| map_playlist_item(item) | Required: snippet.playlistId, snippet.position (int), snippet.publishedAt (becomes added_at); video_id from snippet.resourceId.videoId, else contentDetails.videoId, else MappingError |
| map_categories(response) | dict of item id to snippet.title |
| map_search_ids(response, kind) | for kind video the id.videoId of each item, for kind channel the id.channelId; items without that key are skipped; keep order; no duplicates |
| next_page_token(response) | the nextPageToken when it is a non-empty string, otherwise None |
| parse_keywords(text) | None or blank gives an empty list; split on whitespace, but a double-quoted phrase is one keyword; an unclosed quote is treated as ordinary text with the quote characters stripped; empty tokens are dropped |
| normalise_language(code) | None or blank gives None; lower-case, replace "_" by "-", take the part before the first "-"; the result must be exactly two ASCII letters, otherwise None |
| map_videos, map_channels, map_subscriptions, map_playlists, map_playlist_items | apply the singular function to each item of response["items"] |

### 8.6 Error translation (providers/transport.py)

error_reasons(body) returns the set of string "reason" values found at body["error"]["errors"][*]["reason"]; any other shape gives an empty set. translate_api_error(status, body) returns (does not raise) an instance, using the first matching rule:

| Order | Condition | Result |
|---|---|---|
| 1 | reason quotaExceeded or dailyLimitExceeded | QuotaExhausted |
| 2 | reason rateLimitExceeded or userRateLimitExceeded, or status 429 | RateLimited |
| 3 | reason youtubeSignupRequired | ChannelRequired |
| 4 | status 401, or reason authError or invalidCredentials | ReauthRequired |
| 5 | reason insufficientPermissions | AuthRequired |
| 6 | status 404, or reason notFound, videoNotFound, channelNotFound or playlistNotFound | NotFoundOrPrivate |
| 7 | status 400 | InvalidParameter |
| 8 | anything else | UpstreamError |

### 8.7 FixtureYouTubeProvider (providers/fixture.py)

- FixtureTransport(fixture_dir): call reads <fixture_dir>/<fixture_key(method, params)>.json. A missing file, or a file whose method or args do not match the request, raises FixtureMissing whose message contains the expected file name. A status of 400 or more raises ApiHttpError(status, response). post raises NotImplementedError.
- FixtureYouTubeProvider(fixture_dir, *, channel_present=True, fail_add_item_at=None, fail_error=UpstreamError) is an ApiBackedProvider over a FixtureTransport. It simulates writes in memory so that the offline demo and the playlist tests work. Attributes: created_playlists (list of dicts with id, title, description, visibility), added_items (list of (playlist_id, video_id) tuples, duplicates included) and add_attempts (int).
- create_playlist: raises ChannelRequired when channel_present is false; otherwise the ID is "PLfixture" plus a four-digit counter starting at 0001; it appends to created_playlists and returns the ID.
- add_playlist_item: an unknown playlist ID raises NotFoundOrPrivate and does not count as an attempt; otherwise add_attempts increases by one; when add_attempts equals fail_add_item_at, fail_error() is raised and nothing is recorded; otherwise the pair is appended to added_items.
- list_playlist_items(playlist_id, cap): for a playlist created in memory, return its added items in insertion order as PlaylistItem with positions 0, 1, 2 and added_at equal to 2026-01-01T00:00:00Z plus the position in seconds, limited to cap; for any other playlist, read the fixture file.
- my_channel(): None when channel_present is false, otherwise read the fixture file.

## 9. MCP tools

Every tool returns the ToolResult envelope of section 4 (UI-1, UI-5). Integers named total_duration and max_video_duration are seconds. Every string that originates from YouTube is passed through sanitise_text and then wrap_untrusted when it enters a tool result or resource; only tools/ and resources/ do this. The delimiters are the lines [[UNTRUSTED_YOUTUBE_TEXT]] and [[/UNTRUSTED_YOUTUBE_TEXT]] around the text. sanitise_text removes control characters, markup tags and any occurrence of the delimiter tokens, collapses whitespace and truncates to max_len.

| Tool and annotations | Parameters | Data returned | Worst-case quota plan |
|---|---|---|---|
| find_similar_videos (read-only) | video: str (URL or ID); limit: int 10 [1..50]; max_duration_s: int?; language: str?; published_after: date?; exclude_channels: list of str, at most 50 | results[{video_id, title, channel, duration_mmss, url, score, components}], notices | videos_list 1 + search_list 100 per 50 candidates + videos_list 1 per 50 candidates; default 50 candidates: 102 |
| find_similar_channels (read-only) | channel: str (URL, @handle, UC ID); limit: int 10 [1..30]; exclude_subscribed: bool false | results[{channel_id, title, score, shared_topics, example_videos (at most 3)}] | up to 100 (custom URL resolution) + channels_list 1 + 2 x search_list 200 + about 30 profile fetches: about 210, at most 350 |
| recommend_videos (read-only) | limit: int 10 [1..50]; sources: list of likes, playlists, subscriptions (default all); max_duration_s: int?; language: str?; topic: str, at most 200 chars? | results[{video_id, title, channel, score, because (at most 3 titles)}] | user reads at most 40 + 2 x search_list 200 + videos_list at most 4: about 210 typical, 250 at most |
| analyse_engagement (read-only) | period: last_30d, last_90d, last_365d or all (default last_90d); compare_to: previous_period or none; dimensions: list of channels, categories, trend, duration; top_k: int 10 [1..50]; granularity: month or week | statistics per dimension, comparison, timestamp_used, limitations text, narrative | user reads plus video_categories_list 1: 10 to 30 |
| propose_playlist (read-only, no YouTube write) | topic: str [1..200]; total_duration: int [300..86400]; max_video_duration: int [60..total_duration]; language: str of 2 letters; title: str?; visibility: private, unlisted or public (default private; set only if the user said so) | proposal_id, items, total_s, feasible, constraint report, shortfall message, expires_at, estimated confirm cost, proposal text. No secret, token or code | 2 x search_list 200 + videos_list 2 + channels_list 1: 203 |
| confirm_playlist (read_only false, destructive false, idempotent false) | proposal_id: str (UUID4) | playlist_url, items_added, state; or APPROVAL_PENDING; or a partial-progress report | channels_list 1 + playlists_insert 50 + playlist_items_insert 50 per item; resume: playlist_items_list 1 + 50 per missing item |
| summarise_video (read-only) | video: str | metadata-based summary, stated as such | videos_list 1 |
| get_quota_status (read-only) | none | used, remaining, reserve, reset_at | 0 |
| get_auth_status (read-only) | none | scopes, expiry, channel_present; no token values | about 1 |

Resources (read-only): youtube://quota/status, youtube://video/{id} (cached, untrusted text delimited), youtube://playlist/proposal/{id} (state and expiry, never any approval data), youtube://auth/status.

## 10. Proposal state machine and approval gate

| From | Event | To | Notes |
|---|---|---|---|
| DRAFT | constraints solved (feasible or shortfall reported) | PROPOSED | time to live 15 minutes; a shortfall proposal can still be confirmed by an informed human |
| PROPOSED | approval granted and verified | CONFIRMED | unexpired, items hash unchanged, single use |
| PROPOSED | user declines or approval denied | REJECTED | terminal |
| PROPOSED | time to live elapsed | EXPIRED | terminal; propose again |
| CONFIRMED | playlist and all items added | CREATED | |
| CONFIRMED | playlist exists and at least one item failed | PARTIALLY_CREATED | playlist_id stored; added_ok per item |
| CONFIRMED | failure before a playlist exists | FAILED | terminal |
| PARTIALLY_CREATED | user asks to resume | CONFIRMED | new approval for the same proposal ID and items hash; first list the playlist items (1 unit) so lost responses cannot cause duplicates; add only missing items; 15-minute window |

Approval gate (SRS Addendum 1, SA-1):
- propose_playlist stores the proposal and returns no secret. confirm_playlist takes only proposal_id.
- Mode elicitation: the server sends an MCP elicitation request with a server-built summary (title, number of videos, total duration, visibility, shortfall if any, cost); accept proceeds, decline rejects.
- Mode oob: if approval_state is none, the server sets it to pending, starts a loopback HTTP listener on 127.0.0.1 on a random port with a random 128-bit path nonce, opens the system browser on a page with the same summary and Approve and Decline buttons protected by a per-page CSRF value, and returns APPROVAL_PENDING without the URL or nonce in any tool output. The page checks Host and Origin and accepts one decision. The URL is also printed to the server's stderr. Approve sets approval_state to granted (only the gate writes this). The next confirm_playlist call proceeds.
- Mode auto: elicitation when the client advertised the capability, otherwise oob.
- Server side, failing closed: the proposal exists; its state is PROPOSED (or PARTIALLY_CREATED on resume); it is unexpired; the recomputed items hash equals the stored one; the approval is consumed exactly once; approval values and nonces are stored only as HMAC-SHA256 with a per-install secret; the write scope is available; a channel exists.
- The skill still asks the user in chat and stops (SK-3); the human approval is a second, independent control.

## 11. Formulas and algorithms

| Item | Definition |
|---|---|
| Tokenisation | lower case, Unicode NFKC, split on every non-alphanumeric character, small English stop-word list, no stemming |
| TF-IDF | tf = count / number of tokens; idf = ln((1 + N) / (1 + df)) + 1; the term counts of the title are multiplied by field_weight_title, of the tags by field_weight_tags, of the description by field_weight_description before tf is computed; vectors are L2-normalised; cosine is the dot product (0.0 if either vector is empty). Corpus: the seed plus its candidates (FR-1), or the topic query plus its candidates (FR-5) |
| proximity(x, y, factor) | 1 - min(1, abs(ln(x / y)) / ln(factor)); undefined (None) if x or y is 0 or less |
| Video score (FR-1.7) | S = 0.50 C + 0.20 J + 0.15 K + 0.10 D + 0.05 L (weights from similarity.video). C text cosine; J tag Jaccard; K category equality 0 or 1; D duration proximity with factor 4; L language equality 0 or 1. An undefined component (no tags on either side, missing category, missing language) is dropped and the remaining weights are divided by their sum (FR-1.12). Sort by score descending, then video ID ascending |
| Channel score (FR-2.6) | 0.55 cosine of profile vectors + 0.20 Jaccard of topic_ids + 0.15 cadence + 0.10 size. Profile text: title, description, keywords plus titles and tags of up to 15 recent uploads. Cadence: uploads per day from the recent upload dates, proximity with factor 4. Size: proximity of subscriber counts with factor 100; a hidden count drops size and renormalises |
| Taste profile (FR-3.2) | weighted centroid of TF-IDF vectors: likes 0.5, playlist videos 0.3, subscribed channels 0.2; each item weighted by 0.5 to the power (age in days / 180). Score = cosine to the centroid; popularity only as tie-break or quality floor (BR-3). MMR with lambda 0.7 and at most 2 videos per channel in the top 10 |
| Playlist relevance | cosine of the topic vector and the candidate vector; no popularity. Hard filters first: duration at most max, language match, privacy public, live_status none, embeddable not false |
| Difficulty (TBD-4) | d = 0.6 x min(1, duration / max_item_s) + 0.4 x level. level 0 if the title or tags contain intro, introduction, basics, beginner, overview, 101 or crash course; 1 if they contain advanced, deep dive, proof, theory, masterclass or graduate; otherwise 0.5. Order by d ascending, then relevance descending, then video ID ascending |
| Solver (FR-5.5, 5.6) | window lo = T x (1 - tol) and hi = T x (1 + tol) in exact seconds. Dynamic programming over units of dp_unit_s (rounded half up) on the top dp_top_n candidates by relevance; value is the sum of relevance with back-pointers; examine unit sums inside the unit window in descending value and accept the first whose exact total lies in [lo, hi]. Enforce the per-channel cap by removing the lowest-relevance excess, refilling greedily from unused candidates and re-verifying. If nothing fits: the closest set (largest total at most hi, ties by relevance) with feasible false and a message such as "only 1h38m found under 20 min". Greedy fallback when fewer than 10 candidates. Deterministic: ties by total closest to T, then by the sorted list of video IDs |

## 12. Quota rules

- A plan is a list of PlanItem(endpoint, count). The estimate is the sum of count x cost (section 3), leaving out items whose exact cache key is already fresh (a cache hit costs 0 and is recorded).
- QuotaGuard.check rejects with QUOTA_BUDGET_EXCEEDED when the estimate is more than the smaller of the global remaining budget and the machine remaining budget. Global remaining = daily_budget x (1 - safety_reserve_pct / 100) minus used today. Machine remaining = machine_daily_budget minus used today. The ledger day is the date in the configured reset time zone (midnight in that configured time zone).
- The ledger is local to each machine, so machine_daily_budget is a soft control for a shared project quota. On the API answer quotaExceeded the day is marked exhausted, calls stop and the reset time is reported.
- Reference workflow: a full two-hour playlist costs 653 units (200 + 2 + 1 + 50 + 400).

## 13. Input validation rules (build item B10)

- Video ID ^[A-Za-z0-9_-]{11}$; channel ID ^UC[A-Za-z0-9_-]{22}$; handle ^@[A-Za-z0-9._-]{3,30}$.
- Video URL forms: youtube.com/watch?v=ID, youtu.be/ID, youtube.com/shorts/ID, youtube.com/embed/ID. Channel URL forms: /channel/UC..., /@handle, /user/name, /c/name, giving ChannelRef kinds id, handle, username and custom.
- Allowed hosts: youtube.com, www.youtube.com, m.youtube.com, youtu.be. Reject other hosts, userinfo in a URL, schemes other than http and https, whitespace, SQL fragments and input longer than limits.max_input_len.
- Always normalise first and then re-check the grammar before any API call; failures raise InvalidId.
