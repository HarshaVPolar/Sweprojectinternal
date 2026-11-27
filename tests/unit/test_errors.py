from enum import StrEnum

import pytest

import ytmcp.errors as errors
from ytmcp.errors import (
    ERROR_CLASSES,
    ErrorCode,
    InvalidId,
    QuotaExhausted,
    RateLimited,
    YtmcpError,
)

ERROR_TABLE: list[tuple[str, str, bool, str, str]] = [
    (
        "INVALID_ID",
        "InvalidId",
        False,
        "The video, channel or playlist identifier is not valid.",
        "Check the URL or ID format.",
    ),
    (
        "INVALID_PARAMETER",
        "InvalidParameter",
        False,
        "A parameter is missing or out of range.",
        "Check the parameter values against the tool description.",
    ),
    (
        "NOT_FOUND_OR_PRIVATE",
        "NotFoundOrPrivate",
        False,
        "The item does not exist or is private.",
        "Use a public video or channel.",
    ),
    (
        "AUTH_REQUIRED",
        "AuthRequired",
        True,
        "Authorisation is required.",
        "Authorise this app in the browser window, then retry.",
    ),
    (
        "REAUTH_REQUIRED",
        "ReauthRequired",
        True,
        "The authorisation has expired or was revoked.",
        "Re-authorise in the browser, then retry.",
    ),
    (
        "CHANNEL_REQUIRED",
        "ChannelRequired",
        True,
        "This Google account has no YouTube channel.",
        "Create a YouTube channel, then retry.",
    ),
    (
        "EMPTY_PROFILE",
        "EmptyProfile",
        False,
        "There are no likes, subscriptions or playlists to learn from.",
        "Provide a topic or a seed video.",
    ),
    (
        "QUOTA_BUDGET_EXCEEDED",
        "QuotaBudgetExceeded",
        True,
        "The estimated cost exceeds the remaining quota budget.",
        "Reduce the request or wait until the quota resets.",
    ),
    (
        "QUOTA_EXHAUSTED",
        "QuotaExhausted",
        True,
        "The YouTube API quota is used up for today.",
        "Wait until the quota resets (midnight Pacific Time).",
    ),
    (
        "RATE_LIMITED",
        "RateLimited",
        True,
        "Too many requests.",
        "Wait a moment, then retry.",
    ),
    (
        "APPROVAL_PENDING",
        "ApprovalPending",
        True,
        "Waiting for the human approval.",
        "Approve in the browser window opened on your computer, then ask me to continue.",
    ),
    (
        "PROPOSAL_INVALID",
        "ProposalInvalid",
        False,
        "The proposal is unknown, expired, altered, already used or was declined.",
        "Ask for a new proposal.",
    ),
    (
        "UPSTREAM_ERROR",
        "UpstreamError",
        True,
        "YouTube or the network failed after retries.",
        "Try again shortly; partial progress is reported if any.",
    ),
]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("code", "class_name", "retryable", "default_message", "default_next_step"),
    ERROR_TABLE,
)
def test_error_table(
    code: str,
    class_name: str,
    retryable: bool,
    default_message: str,
    default_next_step: str,
) -> None:
    cls = getattr(errors, class_name)
    assert issubclass(cls, YtmcpError)
    assert issubclass(cls, Exception)
    assert cls.code == ErrorCode[code]
    assert cls.retryable is retryable
    assert cls.default_message == default_message
    assert cls.default_next_step == default_next_step

    instance = cls()
    assert instance.message == default_message
    assert instance.next_step == default_next_step
    assert str(instance) == default_message


@pytest.mark.unit
def test_error_code_enum() -> None:
    assert issubclass(ErrorCode, StrEnum)
    assert len(ErrorCode) == 13
    expected_codes = [row[0] for row in ERROR_TABLE]
    assert list(ErrorCode) == [ErrorCode[c] for c in expected_codes]

    for member in ErrorCode:
        assert member.value == member.name
        assert member == member.name


@pytest.mark.unit
def test_custom_message_and_next_step() -> None:
    err = InvalidId("custom", next_step="do this")
    assert err.message == "custom"
    assert err.next_step == "do this"
    assert str(err) == "custom"
    assert err.retryable is False
    assert err.code == ErrorCode.INVALID_ID

    err_empty = InvalidId("")
    assert err_empty.message == ""
    assert str(err_empty) == ""


@pytest.mark.unit
def test_to_dict() -> None:
    err = QuotaExhausted()
    d = err.to_dict()
    assert set(d.keys()) == {"code", "message", "next_step", "retryable"}
    assert d["code"] == "QUOTA_EXHAUSTED"
    assert type(d["code"]) is str
    assert d["message"] == "The YouTube API quota is used up for today."
    assert d["next_step"] == "Wait until the quota resets (midnight Pacific Time)."
    assert d["retryable"] is True


@pytest.mark.unit
def test_registry() -> None:
    assert len(ERROR_CLASSES) == 13
    classes = list(ERROR_CLASSES.values())
    assert len(set(classes)) == 13
    for member in ErrorCode:
        cls = ERROR_CLASSES[member]
        assert cls.code == member


@pytest.mark.unit
def test_raise_and_catch() -> None:
    try:
        raise RateLimited()
    except YtmcpError as caught:
        assert caught.code == ErrorCode.RATE_LIMITED


@pytest.mark.unit
def test_base_not_usable_directly() -> None:
    with pytest.raises(AttributeError):
        _ = YtmcpError.code
