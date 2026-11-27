"""Domain models and schema definitions for YouTube Video Intelligence MCP."""

from enum import StrEnum
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

Visibility = Literal["private", "unlisted", "public"]
Privacy = Literal["private", "unlisted", "public"]
LiveStatus = Literal["none", "live", "upcoming"]

Endpoint = Literal[
    "search_list",
    "videos_list",
    "channels_list",
    "subscriptions_list",
    "playlists_list",
    "playlist_items_list",
    "video_categories_list",
    "playlists_insert",
    "playlist_items_insert",
]

ENDPOINTS: tuple[Endpoint, ...] = (
    "search_list",
    "videos_list",
    "channels_list",
    "subscriptions_list",
    "playlists_list",
    "playlist_items_list",
    "video_categories_list",
    "playlists_insert",
    "playlist_items_insert",
)


class ProposalState(StrEnum):
    """Lifecycle state of a playlist generation proposal."""

    DRAFT = "DRAFT"
    PROPOSED = "PROPOSED"
    CONFIRMED = "CONFIRMED"
    CREATED = "CREATED"
    PARTIALLY_CREATED = "PARTIALLY_CREATED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class Video(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=r"^[A-Za-z0-9_-]{11}$")
    title: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    category_id: str | None = None
    duration_s: int | None = Field(default=None, ge=0)
    channel_id: str = Field(pattern=r"^UC[A-Za-z0-9_-]{22}$")
    channel_title: str = ""
    language: str | None = None
    published_at: AwareDatetime
    privacy: Privacy = "public"
    live_status: LiveStatus = "none"
    view_count: int | None = Field(default=None, ge=0)
    like_count: int | None = Field(default=None, ge=0)
    embeddable: bool | None = None


class Channel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=r"^UC[A-Za-z0-9_-]{22}$")
    title: str
    description: str = ""
    keywords: list[str] = Field(default_factory=list)
    topic_ids: list[str] = Field(default_factory=list)
    subscriber_count: int | None = Field(default=None, ge=0)
    video_count: int | None = Field(default=None, ge=0)
    uploads_playlist_id: str | None = None
    published_at: AwareDatetime


class ChannelRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["id", "handle", "username", "custom"]
    value: str = Field(min_length=1)


class Subscription(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    channel_id: str = Field(pattern=r"^UC[A-Za-z0-9_-]{22}$")
    channel_title: str
    subscribed_at: AwareDatetime


class Playlist(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    title: str
    item_count: int = Field(ge=0)
    published_at: AwareDatetime


class PlaylistItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    playlist_id: str
    video_id: str = Field(pattern=r"^[A-Za-z0-9_-]{11}$")
    added_at: AwareDatetime
    position: int = Field(ge=0)


class TextDoc(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    title: str = ""
    tags: list[str] = Field(default_factory=list)
    description: str = ""


class ChannelProfile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    channel: Channel
    recent_titles: list[str] = Field(default_factory=list)
    recent_tags: list[str] = Field(default_factory=list)
    recent_published_at: list[AwareDatetime] = Field(default_factory=list)


class PlaylistRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    topic: str = Field(min_length=1, max_length=200)
    total_duration_s: int = Field(ge=300, le=86400)
    max_video_duration_s: int = Field(ge=60)
    language: str = Field(pattern=r"^[a-z]{2}$")
    title: str | None = Field(default=None, min_length=1, max_length=150)
    visibility: Visibility = "private"
    tolerance_pct: int = Field(default=5, ge=0, le=50)

    @model_validator(mode="after")
    def validate_max_duration(self) -> "PlaylistRequest":
        if self.max_video_duration_s > self.total_duration_s:
            raise ValueError("max_video_duration_s must not exceed total_duration_s")
        return self


class Candidate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    video_id: str = Field(pattern=r"^[A-Za-z0-9_-]{11}$")
    channel_id: str = Field(pattern=r"^UC[A-Za-z0-9_-]{22}$")
    duration_s: int = Field(ge=0)
    relevance: float
    difficulty: float = 0.0


class SolveSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    target_s: int = Field(ge=1)
    tolerance_pct: int = Field(ge=0, le=50)
    max_item_s: int = Field(ge=1)
    per_channel_cap: int = Field(ge=1)
    dp_unit_s: int = Field(ge=1)
    dp_top_n: int = Field(ge=1)


class SolveResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    items: list[Candidate] = Field(default_factory=list)
    total_s: int = Field(default=0, ge=0)
    feasible: bool
    shortfall_s: int = Field(ge=0)
    message: str


class ProposalItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    position: int = Field(ge=1)
    video_id: str = Field(pattern=r"^[A-Za-z0-9_-]{11}$")
    title: str
    channel_id: str = Field(pattern=r"^UC[A-Za-z0-9_-]{22}$")
    channel_title: str
    duration_s: int = Field(ge=0)
    score: float


class Proposal(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    proposal_id: str = Field(
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
    )
    request: PlaylistRequest
    items: list[ProposalItem] = Field(default_factory=list)
    total_s: int = Field(default=0, ge=0)
    feasible: bool
    shortfall_message: str | None = None
    state: ProposalState
    items_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    expires_at: AwareDatetime
    estimated_cost: int = Field(ge=0)
    playlist_id: str | None = None


class ScoredVideo(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    video_id: str = Field(pattern=r"^[A-Za-z0-9_-]{11}$")
    score: float
    components: dict[str, float | None] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ScoredChannel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    channel_id: str = Field(pattern=r"^UC[A-Za-z0-9_-]{22}$")
    score: float
    components: dict[str, float | None] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class TasteProfile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    vector: dict[str, float] = Field(default_factory=dict)
    top_terms: list[str] = Field(default_factory=list)
    source_counts: dict[str, int] = Field(default_factory=dict)


class PlanItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    endpoint: Endpoint
    count: int = Field(ge=0)


class Estimate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    units: int = Field(ge=0)
    remaining_after: int


class QuotaStatus(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    used_today: int = Field(ge=0)
    remaining: int
    reserve: int = Field(ge=0)
    machine_remaining: int
    reset_at: AwareDatetime
    exhausted: bool


class QuotaReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    spent: int = Field(ge=0)
    remaining: int
    estimate: int | None = None


class ErrorInfo(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    message: str
    next_step: str


class ToolResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ok: bool
    summary: str
    data: dict[str, Any] = Field(default_factory=dict)
    quota: QuotaReport
    notices: list[str] = Field(default_factory=list)
    error: ErrorInfo | None = None

    @model_validator(mode="after")
    def validate_ok_error(self) -> "ToolResult":
        if self.ok and self.error is not None:
            raise ValueError("When ok is True, error must be None")
        if not self.ok and self.error is None:
            raise ValueError("When ok is False, error must be provided")
        return self


class ConfirmResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    state: ProposalState
    playlist_id: str | None = None
    playlist_url: str | None = None
    items_added: int = Field(default=0, ge=0)
    items_missing: int = Field(default=0, ge=0)
    notices: list[str] = Field(default_factory=list)


__all__ = [
    "ENDPOINTS",
    "Candidate",
    "Channel",
    "ChannelProfile",
    "ChannelRef",
    "ConfirmResult",
    "Endpoint",
    "ErrorInfo",
    "Estimate",
    "LiveStatus",
    "PlanItem",
    "Playlist",
    "PlaylistItem",
    "PlaylistRequest",
    "Privacy",
    "Proposal",
    "ProposalItem",
    "ProposalState",
    "QuotaReport",
    "QuotaStatus",
    "ScoredChannel",
    "ScoredVideo",
    "SolveResult",
    "SolveSpec",
    "Subscription",
    "TasteProfile",
    "TextDoc",
    "ToolResult",
    "Video",
    "Visibility",
]
