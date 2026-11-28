# Provider and fixture design

Version 1.0 (Stage 2). The specification of record is docs/design/build-contract.md section 8; this page adds the operating details. Architecture overview: docs/design/architecture.md section 5.

## 1. Overview

All YouTube access goes through the abstract YouTubeProvider. ApiBackedProvider implements every method once: it builds the request parameters, batches ids, follows pagination, translates API errors and maps raw JSON to models. It talks to an ApiTransport. The only differences between offline and live use are the transport and, for the fixture provider, the in-memory write simulation.

| Class | File | Transport | Build item |
|---|---|---|---|
| FixtureYouTubeProvider | providers/fixture.py | FixtureTransport (replays files) | B04 |
| LiveYouTubeProvider | providers/live.py | LiveTransport (httpx) | B21 |
| RecordingProvider | providers/recording.py | RecordingTransport around the live transport | B21 |

## 2. Interface

| Method | Quota class | Notes |
|---|---|---|
| get_videos(ids) | 1 unit per batch of 50 | input order, missing ids absent |
| search(q, type, max_results, language, published_after) | 100 units per page | IDs only |
| get_channels(ids) | 1 unit per batch of 50 | |
| resolve_channel(ref) | 1 unit (handle, username, id) or 100 units (custom) | |
| recent_uploads(channel, n) | 1 unit | uses the uploads playlist |
| list_liked, list_subscriptions, list_playlists, list_playlist_items | 1 unit per page of 50 | need OAuth |
| video_categories(region) | 1 unit | cached 7 days |
| my_channel() | 1 unit | None when there is no channel |
| create_playlist, add_playlist_item | 50 units each | need OAuth with the youtube scope |

## 3. Endpoints

Base URL: https://www.googleapis.com/youtube/v3. Request parameters per method are in build contract section 8.4.

| Transport method | HTTP | Path | Cost | Authorisation |
|---|---|---|---|---|
| videos_list | GET | /videos | 1 | API key or OAuth; myRating=like needs OAuth |
| search_list | GET | /search | 100 | API key or OAuth |
| channels_list | GET | /channels | 1 | API key or OAuth; mine=true needs OAuth |
| subscriptions_list | GET | /subscriptions | 1 | OAuth |
| playlists_list | GET | /playlists | 1 | OAuth for mine=true |
| playlist_items_list | GET | /playlistItems | 1 | API key for public playlists, OAuth for private |
| video_categories_list | GET | /videoCategories | 1 | API key or OAuth |
| playlists_insert | POST | /playlists | 50 | OAuth with the youtube scope |
| playlist_items_insert | POST | /playlistItems | 50 | OAuth with the youtube scope |

## 4. Fixture files and keys

- A fixture is tests/fixtures/youtube/<method>__<hash16>.json with the keys method, args, response and optionally status (an integer HTTP status; absent means 200). A status of 400 or more replays an API error.
- canonical_json is json.dumps with sorted keys, separators "," and ":" and ensure_ascii true. hash16 is the first 16 hexadecimal characters of the SHA-256 of the UTF-8 bytes of canonical_json(args).
- Golden values that pin the algorithm: fixture_key("videos_list", {"id": "abc", "part": "snippet"}) is videos_list__7700128999ee1617; fixture_key("search_list", {"part": "snippet", "q": "linear algebra", "type": "video", "maxResults": 50}) is search_list__65bb0d0980a50a3f.
- The recorder, the sanitiser, the synthetic generator and FixtureTransport all use fixture_key from ytmcp.providers.transport.

## 5. Recording real data

1. Public data only (searches, videos, channels, uploads, categories). The plan is tests/fixtures/recording_plan.json.
2. python scripts/record_fixtures.py --dry-run prints the estimated units (416 for the committed plan, at most the plan limit of 600).
3. Set YT_API_KEY in your own terminal (never in a file, never in a prompt) and run python scripts/record_fixtures.py --run. Raw responses go to tests/fixtures/_raw, which is git-ignored.
4. Run python scripts/sanitise_fixture.py. It redacts emails and tokens, drops etag, thumbnails and localized keys and truncates descriptions to 300 characters.
5. Commit the sanitised files and update the date in tests/fixtures/README.md.

## 6. Synthetic fixtures

scripts/make_synthetic_fixtures.py writes 16 deterministic files: two pages of 64 liked videos, two pages of 60 subscriptions, 5 playlists with 8 items each, the signed-in channel, and five API error responses (quotaExceeded, youtubeSignupRequired, authError, rateLimitExceeded, backendError). No real user data is ever recorded (SRS SEC-7).

## 7. FixtureYouTubeProvider

- Reads through FixtureTransport; a missing fixture raises FixtureMissing with the expected file name.
- Simulates writes in memory: create_playlist returns PLfixture0001, PLfixture0002 and so on; added_items records every added pair, duplicates included; list_playlist_items reflects the in-memory playlist.
- Failure injection: fail_add_item_at makes the n-th accepted add attempt raise fail_error (default UpstreamError). channel_present=False makes my_channel return None and create_playlist raise ChannelRequired. These switches make the partial-failure and resume tests possible.

## 8. Fixture fallbacks (added)

Recorded fixtures replay only the exact calls of the recorder, but services build their own batches and queries. When no exact file exists and FixtureTransport was created with synthetic_fallback true (the default), it answers as follows. The first build item among B24, B26, B27 and B28 that needs this implements it, with tests in tests/integration/test_fixture_provider.py.

- Index: on first use read every fixture file whose status is below 400 once and build three indexes: videos by id (from videos_list items), channels by id (from channels_list items) and nothing else.
- videos_list with an id parameter and without myRating: answer {"items": [...]} with the indexed items for the requested ids in the order of the id parameter; unknown ids are absent, exactly like the real API.
- channels_list with an id parameter and without mine: the same from the channel index. Requests with forHandle, forUsername or mine are answered from exact files only.
- search_list: tokenise q with ytmcp.domain.tokenizer; for type video score each indexed video by the number of distinct query tokens found in the tokens of its title and tags; keep scores of 1 or more; sort by score descending, then id ascending; return the first maxResults as items shaped {"id": {"kind": "youtube#video", "videoId": id}} and no nextPageToken. For type channel do the same over indexed channels using title, description and keywords with items shaped {"id": {"kind": "youtube#channel", "channelId": id}}.
- The transport keeps a list synthetic_calls of the requests it answered this way, so tests can assert on it. Results are deterministic but are not the real search ranking.
- An exact fixture file always wins over a fallback.

Acceptance details for the fallback behaviour:

- The index is built once and reused; it is not rebuilt for every request.
- Only successful fixture responses (status below 400) are indexed.
- ID lookup preserves the order of the requested IDs.
- Unknown IDs are omitted rather than represented by placeholder objects.
- An exact fixture always takes precedence over fallback behaviour.
- synthetic_calls records only calls answered by fallback, not exact fixture replays.
- Fallback search is deterministic: equal scores are ordered by ID ascending.
- Fallback search uses the specified tokenizer and the specified fields for each resource type.
- Requests using myRating, mine, forHandle or forUsername do not receive an inappropriate ID-index fallback.
- The fallback is explicitly documented as synthetic behaviour and must not be described as equivalent to real YouTube search ranking.

## 9. Live and recording providers (build item B21)

- LiveTransport uses an httpx client with the timeout limits.http_timeout_s. Public reads use the API key (environment variable YT_API_KEY) unless an authorisation is available; calls with mine, myRating or a write use an OAuth bearer token from the OAuth manager (scope youtube.readonly for reads, youtube for writes).
- Status 400 or more becomes ApiHttpError(status, body); ApiBackedProvider translates it (build contract section 8.6).
- Retries: at most limits.retry_max (3). Retry on connect and read timeouts and on HTTP 5xx; on HTTP 429 and on the reason rateLimitExceeded wait for Retry-After seconds (capped at 30) when present. The wait before retry n is otherwise 0.5 x 2 to the power n seconds plus a random jitter of at most 0.25 seconds. Never retry other 4xx answers. After the last retry a rate-limit answer becomes RATE_LIMITED and anything else UPSTREAM_ERROR. The sleep function and the random generator are injected so that tests are instant and deterministic.
- Quota: after every successful call the transport reports (endpoint, units from quota.costs) to an injected recorder, which the server connects to QuotaGuard.record with the current request id.
- RecordingTransport wraps another transport and writes raw responses in the format of section 4.
- Contract tests run the same read-method checks on FixtureYouTubeProvider and on LiveYouTubeProvider over httpx.MockTransport that serves the fixture files. The live smoke test (marker live) uses only the API key and at most 500 units.

## 10. Adding or refreshing a fixture

1. Add the call to tests/fixtures/recording_plan.json, or extend scripts/make_synthetic_fixtures.py for synthetic data.
2. Record or generate, sanitise and run tests/security/test_fixture_clean.py.
3. Commit the new files together with the test that needs them.
4. Never edit a recorded fixture by hand except through the sanitiser rules.
