"""Error catalogue and exception hierarchy for YouTube Video Intelligence MCP."""

from enum import StrEnum
from typing import Any, ClassVar


class ErrorCode(StrEnum):
    """Enumeration of standard error codes in the catalogue."""

    INVALID_ID = "INVALID_ID"
    INVALID_PARAMETER = "INVALID_PARAMETER"
    NOT_FOUND_OR_PRIVATE = "NOT_FOUND_OR_PRIVATE"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    REAUTH_REQUIRED = "REAUTH_REQUIRED"
    CHANNEL_REQUIRED = "CHANNEL_REQUIRED"
    EMPTY_PROFILE = "EMPTY_PROFILE"
    QUOTA_BUDGET_EXCEEDED = "QUOTA_BUDGET_EXCEEDED"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    RATE_LIMITED = "RATE_LIMITED"
    APPROVAL_PENDING = "APPROVAL_PENDING"
    PROPOSAL_INVALID = "PROPOSAL_INVALID"
    UPSTREAM_ERROR = "UPSTREAM_ERROR"


class YtmcpError(Exception):
    """Base exception for all errors defined in the catalogue."""

    code: ClassVar[ErrorCode]
    retryable: ClassVar[bool]
    default_message: ClassVar[str]
    default_next_step: ClassVar[str]

    def __init__(
        self,
        message: str | None = None,
        *,
        next_step: str | None = None,
    ) -> None:
        self.message: str = self.default_message if message is None else message
        self.next_step: str = self.default_next_step if next_step is None else next_step
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Serialise the error to a dictionary matching the catalogue schema."""
        return {
            "code": self.code.value,
            "message": self.message,
            "next_step": self.next_step,
            "retryable": self.retryable,
        }


class InvalidId(YtmcpError):
    code: ClassVar[ErrorCode] = ErrorCode.INVALID_ID
    retryable: ClassVar[bool] = False
    default_message: ClassVar[str] = "The video, channel or playlist identifier is not valid."
    default_next_step: ClassVar[str] = "Check the URL or ID format."


class InvalidParameter(YtmcpError):
    code: ClassVar[ErrorCode] = ErrorCode.INVALID_PARAMETER
    retryable: ClassVar[bool] = False
    default_message: ClassVar[str] = "A parameter is missing or out of range."
    default_next_step: ClassVar[str] = "Check the parameter values against the tool description."


class NotFoundOrPrivate(YtmcpError):
    code: ClassVar[ErrorCode] = ErrorCode.NOT_FOUND_OR_PRIVATE
    retryable: ClassVar[bool] = False
    default_message: ClassVar[str] = "The item does not exist or is private."
    default_next_step: ClassVar[str] = "Use a public video or channel."


class AuthRequired(YtmcpError):
    code: ClassVar[ErrorCode] = ErrorCode.AUTH_REQUIRED
    retryable: ClassVar[bool] = True
    default_message: ClassVar[str] = "Authorisation is required."
    default_next_step: ClassVar[str] = "Authorise this app in the browser window, then retry."


class ReauthRequired(YtmcpError):
    code: ClassVar[ErrorCode] = ErrorCode.REAUTH_REQUIRED
    retryable: ClassVar[bool] = True
    default_message: ClassVar[str] = "The authorisation has expired or was revoked."
    default_next_step: ClassVar[str] = "Re-authorise in the browser, then retry."


class ChannelRequired(YtmcpError):
    code: ClassVar[ErrorCode] = ErrorCode.CHANNEL_REQUIRED
    retryable: ClassVar[bool] = True
    default_message: ClassVar[str] = "This Google account has no YouTube channel."
    default_next_step: ClassVar[str] = "Create a YouTube channel, then retry."


class EmptyProfile(YtmcpError):
    code: ClassVar[ErrorCode] = ErrorCode.EMPTY_PROFILE
    retryable: ClassVar[bool] = False
    default_message: ClassVar[str] = "There are no likes, subscriptions or playlists to learn from."
    default_next_step: ClassVar[str] = "Provide a topic or a seed video."


class QuotaBudgetExceeded(YtmcpError):
    code: ClassVar[ErrorCode] = ErrorCode.QUOTA_BUDGET_EXCEEDED
    retryable: ClassVar[bool] = True
    default_message: ClassVar[str] = "The estimated cost exceeds the remaining quota budget."
    default_next_step: ClassVar[str] = "Reduce the request or wait until the quota resets."


class QuotaExhausted(YtmcpError):
    code: ClassVar[ErrorCode] = ErrorCode.QUOTA_EXHAUSTED
    retryable: ClassVar[bool] = True
    default_message: ClassVar[str] = "The YouTube API quota is used up for today."
    default_next_step: ClassVar[str] = "Wait until the quota resets (midnight Pacific Time)."


class RateLimited(YtmcpError):
    code: ClassVar[ErrorCode] = ErrorCode.RATE_LIMITED
    retryable: ClassVar[bool] = True
    default_message: ClassVar[str] = "Too many requests."
    default_next_step: ClassVar[str] = "Wait a moment, then retry."


class ApprovalPending(YtmcpError):
    code: ClassVar[ErrorCode] = ErrorCode.APPROVAL_PENDING
    retryable: ClassVar[bool] = True
    default_message: ClassVar[str] = "Waiting for the human approval."
    default_next_step: ClassVar[str] = (
        "Approve in the browser window opened on your computer, then ask me to continue."
    )


class ProposalInvalid(YtmcpError):
    code: ClassVar[ErrorCode] = ErrorCode.PROPOSAL_INVALID
    retryable: ClassVar[bool] = False
    default_message: ClassVar[str] = (
        "The proposal is unknown, expired, altered, already used or was declined."
    )
    default_next_step: ClassVar[str] = "Ask for a new proposal."


class UpstreamError(YtmcpError):
    code: ClassVar[ErrorCode] = ErrorCode.UPSTREAM_ERROR
    retryable: ClassVar[bool] = True
    default_message: ClassVar[str] = "YouTube or the network failed after retries."
    default_next_step: ClassVar[str] = "Try again shortly; partial progress is reported if any."


ERROR_CLASSES: dict[ErrorCode, type[YtmcpError]] = {
    ErrorCode.INVALID_ID: InvalidId,
    ErrorCode.INVALID_PARAMETER: InvalidParameter,
    ErrorCode.NOT_FOUND_OR_PRIVATE: NotFoundOrPrivate,
    ErrorCode.AUTH_REQUIRED: AuthRequired,
    ErrorCode.REAUTH_REQUIRED: ReauthRequired,
    ErrorCode.CHANNEL_REQUIRED: ChannelRequired,
    ErrorCode.EMPTY_PROFILE: EmptyProfile,
    ErrorCode.QUOTA_BUDGET_EXCEEDED: QuotaBudgetExceeded,
    ErrorCode.QUOTA_EXHAUSTED: QuotaExhausted,
    ErrorCode.RATE_LIMITED: RateLimited,
    ErrorCode.APPROVAL_PENDING: ApprovalPending,
    ErrorCode.PROPOSAL_INVALID: ProposalInvalid,
    ErrorCode.UPSTREAM_ERROR: UpstreamError,
}

__all__ = [
    "ERROR_CLASSES",
    "ApprovalPending",
    "AuthRequired",
    "ChannelRequired",
    "EmptyProfile",
    "ErrorCode",
    "InvalidId",
    "InvalidParameter",
    "NotFoundOrPrivate",
    "ProposalInvalid",
    "QuotaBudgetExceeded",
    "QuotaExhausted",
    "RateLimited",
    "ReauthRequired",
    "UpstreamError",
    "YtmcpError",
]
