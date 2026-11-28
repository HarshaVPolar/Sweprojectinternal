from collections.abc import Mapping
from typing import Any

import pytest

from ytmcp.errors import (
    AuthRequired,
    ChannelRequired,
    InvalidParameter,
    NotFoundOrPrivate,
    QuotaExhausted,
    RateLimited,
    ReauthRequired,
    UpstreamError,
)
from ytmcp.providers.transport import (
    READ_METHODS,
    WRITE_METHODS,
    ApiHttpError,
    ApiTransport,
    FixtureMissing,
    canonical_json,
    error_reasons,
    fixture_key,
    translate_api_error,
)


@pytest.mark.unit
def test_constants() -> None:
    assert READ_METHODS == (
        "videos_list",
        "search_list",
        "channels_list",
        "subscriptions_list",
        "playlists_list",
        "playlist_items_list",
        "video_categories_list",
    )
    assert WRITE_METHODS == ("playlists_insert", "playlist_items_insert")


@pytest.mark.unit
def test_exceptions() -> None:
    assert issubclass(FixtureMissing, LookupError)
    assert issubclass(ApiHttpError, Exception)

    err = ApiHttpError(404, {"error": "not found"})
    assert err.status == 404
    assert err.body == {"error": "not found"}
    assert "404" in str(err)


@pytest.mark.unit
def test_canonical_json_primitives_and_ordering() -> None:
    assert canonical_json({"q": "café", "n": 1}) == '{"n":1,"q":"caf\\u00e9"}'
    assert canonical_json({"b": 2, "a": 1}) == '{"a":1,"b":2}'
    assert canonical_json({"nested": {"z": 26, "a": 1}}) == '{"nested":{"a":1,"z":26}}'
    assert canonical_json([3, 2, 1]) == "[3,2,1]"
    assert canonical_json(True) == "true"
    assert canonical_json(False) == "false"


@pytest.mark.unit
def test_fixture_key_golden_values() -> None:
    k1 = fixture_key("videos_list", {"id": "abc", "part": "snippet"})
    assert k1 == "videos_list__7700128999ee1617"

    k2 = fixture_key(
        "search_list",
        {"part": "snippet", "q": "linear algebra", "type": "video", "maxResults": 50},
    )
    assert k2 == "search_list__65bb0d0980a50a3f"


@pytest.mark.unit
def test_error_reasons_extraction() -> None:
    valid_body = {
        "error": {
            "errors": [
                {"reason": "quotaExceeded", "message": "Quota exceeded"},
                {"reason": "dailyLimitExceeded"},
            ]
        }
    }
    assert error_reasons(valid_body) == {"quotaExceeded", "dailyLimitExceeded"}


@pytest.mark.unit
@pytest.mark.parametrize(
    "malformed_body",
    [
        None,
        {},
        {"error": None},
        {"error": "not a dict"},
        {"error": {"errors": None}},
        {"error": {"errors": "not a list"}},
        {"error": {"errors": [None, 123, "string", {}, {"other": "value"}, {"reason": 42}]}},
    ],
)
def test_error_reasons_malformed(malformed_body: Any) -> None:
    assert error_reasons(malformed_body) == set()


@pytest.mark.unit
@pytest.mark.parametrize(
    ("status", "reason", "expected_cls"),
    [
        (403, "quotaExceeded", QuotaExhausted),
        (403, "dailyLimitExceeded", QuotaExhausted),
        (403, "rateLimitExceeded", RateLimited),
        (403, "userRateLimitExceeded", RateLimited),
        (429, None, RateLimited),
        (429, "arbitraryReason", RateLimited),
        (403, "youtubeSignupRequired", ChannelRequired),
        (401, None, ReauthRequired),
        (401, "arbitraryReason", ReauthRequired),
        (403, "authError", ReauthRequired),
        (403, "invalidCredentials", ReauthRequired),
        (403, "insufficientPermissions", AuthRequired),
        (404, None, NotFoundOrPrivate),
        (404, "arbitraryReason", NotFoundOrPrivate),
        (403, "notFound", NotFoundOrPrivate),
        (403, "videoNotFound", NotFoundOrPrivate),
        (403, "channelNotFound", NotFoundOrPrivate),
        (403, "playlistNotFound", NotFoundOrPrivate),
        (400, None, InvalidParameter),
        (400, "arbitraryReason", InvalidParameter),
        (500, None, UpstreamError),
        (503, None, UpstreamError),
        (403, "unknownReason", UpstreamError),
    ],
)
def test_translate_api_error_rules(
    status: int,
    reason: str | None,
    expected_cls: type[Exception],
) -> None:
    body: dict[str, Any] = {}
    if reason is not None:
        body = {"error": {"errors": [{"reason": reason}]}}

    err = translate_api_error(status, body)
    assert isinstance(err, expected_cls)


@pytest.mark.unit
def test_translate_api_error_rule_precedence() -> None:
    # Rule 1 beats Rule 2 (status 429 with quota reasons -> QuotaExhausted, not RateLimited)
    b_q = {"error": {"errors": [{"reason": "quotaExceeded"}]}}
    err_q = translate_api_error(429, b_q)
    assert isinstance(err_q, QuotaExhausted)
    assert not isinstance(err_q, RateLimited)

    b_d = {"error": {"errors": [{"reason": "dailyLimitExceeded"}]}}
    err_d = translate_api_error(429, b_d)
    assert isinstance(err_d, QuotaExhausted)
    assert not isinstance(err_d, RateLimited)

    # Rule 1 beats Rule 7 (status 400 with quotaExceeded -> QuotaExhausted)
    b1 = {"error": {"errors": [{"reason": "quotaExceeded"}]}}
    assert isinstance(translate_api_error(400, b1), QuotaExhausted)

    # Rule 2 beats Rule 4 (status 401 with rateLimitExceeded -> RateLimited)
    b2 = {"error": {"errors": [{"reason": "rateLimitExceeded"}]}}
    assert isinstance(translate_api_error(401, b2), RateLimited)

    # Rule 3 beats Rule 4 (status 401 with youtubeSignupRequired -> ChannelRequired)
    b3 = {"error": {"errors": [{"reason": "youtubeSignupRequired"}]}}
    assert isinstance(translate_api_error(401, b3), ChannelRequired)

    # Rule 4 beats Rule 6 (status 404 with authError -> ReauthRequired)
    b4 = {"error": {"errors": [{"reason": "authError"}]}}
    assert isinstance(translate_api_error(404, b4), ReauthRequired)

    # Rule 6 beats Rule 7 (status 400 with notFound -> NotFoundOrPrivate)
    b5 = {"error": {"errors": [{"reason": "notFound"}]}}
    assert isinstance(translate_api_error(400, b5), NotFoundOrPrivate)


@pytest.mark.unit
@pytest.mark.parametrize("reason", ["quotaExceeded", "dailyLimitExceeded"])
def test_translate_api_error_429_quota_precedence(reason: str) -> None:
    body = {"error": {"errors": [{"reason": reason}]}}
    err = translate_api_error(429, body)
    assert isinstance(err, QuotaExhausted)
    assert not isinstance(err, RateLimited)


@pytest.mark.unit
def test_api_transport_protocol() -> None:
    class MockTransport:
        def call(self, method: str, params: Mapping[str, Any]) -> dict[str, Any]:
            return {"method": method, "params": dict(params)}

        def post(
            self,
            method: str,
            params: Mapping[str, Any],
            body: Mapping[str, Any],
        ) -> dict[str, Any]:
            return {"method": method, "params": dict(params), "body": dict(body)}

    mock = MockTransport()
    assert isinstance(mock, ApiTransport)
    assert mock.call("videos_list", {"id": "123"}) == {
        "method": "videos_list",
        "params": {"id": "123"},
    }
    assert mock.post("playlists_insert", {"part": "snippet"}, {"title": "Test"}) == {
        "method": "playlists_insert",
        "params": {"part": "snippet"},
        "body": {"title": "Test"},
    }
