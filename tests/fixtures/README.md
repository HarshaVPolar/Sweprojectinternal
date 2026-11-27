# Test fixtures

Fixtures are JSON files named METHOD__HASH16.json in tests/fixtures/youtube. They let CI and local-check run without calling the YouTube API.

| Kind | Source | Tool |
|---|---|---|
| Public data (searches, videos, channels, uploads, categories) | Recorded once from the real API with an API key, then sanitised | scripts/record_fixtures.py, scripts/sanitise_fixture.py, plan in tests/fixtures/recording_plan.json |
| User data (likes, subscriptions, playlists, signed-in channel) and API errors | Synthetic, generated deterministically | scripts/make_synthetic_fixtures.py |

Last recorded: 2026-11-28. The recording used one API key and about 416 quota units.

Rules:
- Raw recordings stay in tests/fixtures/_raw, which is git-ignored. Only sanitised files are committed.
- Real user data never enters the repository (SRS SEC-7). tests/security/test_fixture_clean.py scans every fixture.
- Recorded files are API data. SRS NFR-CMP-1 requires respecting the data-retention limits of the YouTube API Services policies: re-record before the release and whenever the policy requires it, and delete fixtures that are no longer needed.
- To re-record: python scripts/record_fixtures.py --dry-run, then set YT_API_KEY in your own terminal and run python scripts/record_fixtures.py --run, then python scripts/sanitise_fixture.py.
