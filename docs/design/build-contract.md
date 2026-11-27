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
- Only providers/live.py performs HTTP. Only infra/token_store.py touches token secrets. Only services/confirmation_gate.py may set an approval to granted. Only PlaylistService.confirm calls create_playlist or add_playlist_item.
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

<!-- CONTRACT-PART-2-FOLLOWS -->
