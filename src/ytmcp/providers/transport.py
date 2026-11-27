"""Transport protocols, helpers, fixture keying and error translation for YouTube API."""

import hashlib
import json
from collections.abc import Mapping
from typing import Any, Protocol, TypeAlias, runtime_checkable

from ytmcp.errors import (
    AuthRequired,
    ChannelRequired,
    InvalidParameter,
    NotFoundOrPrivate,
    QuotaExhausted,
    RateLimited,
    ReauthRequired,
    UpstreamError,
    YtmcpError,
)

ParamValue: TypeAlias = str | int | float | bool
Params: TypeAlias = Mapping[str, ParamValue]

READ_METHODS: tuple[str, ...] = (
    "videos_list",
    "search_list",
    "channels_list",
    "subscriptions_list",
    "playlists_list",
    "playlist_items_list",
    "video_categories_list",
)

WRITE_METHODS: tuple[str, ...] = (
    "playlists_insert",
    "playlist_items_insert",
)


class FixtureMissing(LookupError):
    """Raised when a fixture file cannot be served."""


class ApiHttpError(Exception):
    """Raised when the YouTube API returns an HTTP status of 400 or more."""

    def __init__(self, status: int, body: Any = None) -> None:
        super().__init__(f"API error {status}: {body}")
        self.status = status
        self.body = body


@runtime_checkable
class ApiTransport(Protocol):
    """Transport protocol for raw YouTube Data API v3 calls."""

    def call(self, method: str, params: Params) -> dict[str, Any]:
        """Perform a read request and return decoded JSON body."""
        ...

    def post(
        self,
        method: str,
        params: Params,
        body: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Perform a write request with a body and return decoded JSON body."""
        ...


def canonical_json(obj: Any) -> str:
    """Serialise an object to deterministic JSON with sorted keys and compact separators."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fixture_key(method: str, params: Params) -> str:
    """Compute deterministic fixture key: {method}__{sha256[:16]}."""
    digest = hashlib.sha256(canonical_json(params).encode("utf-8")).hexdigest()[:16]
    return f"{method}__{digest}"


def error_reasons(body: Any) -> set[str]:
    """Extract reason strings from body['error']['errors'][*]['reason']."""
    reasons: set[str] = set()
    if not isinstance(body, Mapping):
        return reasons
    err = body.get("error")
    if not isinstance(err, Mapping):
        return reasons
    errors_list = err.get("errors")
    if not isinstance(errors_list, list):
        return reasons
    for item in errors_list:
        if isinstance(item, Mapping):
            reason = item.get("reason")
            if isinstance(reason, str):
                reasons.add(reason)
    return reasons


def translate_api_error(status: int, body: Any = None) -> YtmcpError:
    """Translate YouTube API HTTP status and body to a catalogue YtmcpError instance."""
    reasons = error_reasons(body)

    # 1. Quota exhausted
    if bool(reasons & {"quotaExceeded", "dailyLimitExceeded"}):
        return QuotaExhausted()

    # 2. Rate limited
    if bool(reasons & {"rateLimitExceeded", "userRateLimitExceeded"}) or status == 429:
        return RateLimited()

    # 3. Channel required
    if "youtubeSignupRequired" in reasons:
        return ChannelRequired()

    # 4. Re-authorisation required
    if status == 401 or bool(reasons & {"authError", "invalidCredentials"}):
        return ReauthRequired()

    # 5. Authorisation required
    if "insufficientPermissions" in reasons:
        return AuthRequired()

    # 6. Not found or private
    if status == 404 or bool(
        reasons & {"notFound", "videoNotFound", "channelNotFound", "playlistNotFound"}
    ):
        return NotFoundOrPrivate()

    # 7. Invalid parameter
    if status == 400:
        return InvalidParameter()

    # 8. Upstream error (anything else)
    return UpstreamError()
