import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ytmcp.config import QuotaCosts, load_settings
from ytmcp.models import (
    ENDPOINTS,
    Candidate,
    Channel,
    ChannelProfile,
    ChannelRef,
    ConfirmResult,
    ErrorInfo,
    Estimate,
    PlanItem,
    Playlist,
    PlaylistItem,
    PlaylistRequest,
    Proposal,
    ProposalItem,
    ProposalState,
    QuotaReport,
    QuotaStatus,
    ScoredChannel,
    ScoredVideo,
    SolveResult,
    SolveSpec,
    Subscription,
    TasteProfile,
    TextDoc,
    ToolResult,
    Video,
)

NOW = datetime(2024, 5, 1, 10, 0, 0, tzinfo=UTC)
VIDEO_ID = "dQw4w9WgXcQ"
CHANNEL_ID = "UCuAXFkgsw1L7Un7-uKIDGBA"
UUID4_STR = "12345678-1234-4234-8234-123456789abc"
HASH64 = "a" * 64


def make_valid_video() -> Video:
    return Video(
        id=VIDEO_ID,
        title="Valid Video",
        channel_id=CHANNEL_ID,
        published_at=NOW,
    )


def make_valid_channel() -> Channel:
    return Channel(
        id=CHANNEL_ID,
        title="Valid Channel",
        published_at=NOW,
    )


def make_valid_channel_ref() -> ChannelRef:
    return ChannelRef(kind="handle", value="@validhandle")


def make_valid_subscription() -> Subscription:
    return Subscription(
        channel_id=CHANNEL_ID,
        channel_title="Valid Channel",
        subscribed_at=NOW,
    )


def make_valid_playlist() -> Playlist:
    return Playlist(
        id="PL12345",
        title="Valid Playlist",
        item_count=5,
        published_at=NOW,
    )


def make_valid_playlist_item() -> PlaylistItem:
    return PlaylistItem(
        playlist_id="PL12345",
        video_id=VIDEO_ID,
        added_at=NOW,
        position=0,
    )


def make_valid_text_doc() -> TextDoc:
    return TextDoc(id="doc1", title="Title", description="Desc")


def make_valid_channel_profile() -> ChannelProfile:
    return ChannelProfile(
        channel=make_valid_channel(),
        recent_titles=["Title 1"],
        recent_tags=["tag1"],
        recent_published_at=[NOW],
    )


def make_valid_playlist_request() -> PlaylistRequest:
    return PlaylistRequest(
        topic="Python Tutorial",
        total_duration_s=3600,
        max_video_duration_s=600,
        language="en",
    )


def make_valid_candidate() -> Candidate:
    return Candidate(
        video_id=VIDEO_ID,
        channel_id=CHANNEL_ID,
        duration_s=300,
        relevance=0.9,
    )


def make_valid_solve_spec() -> SolveSpec:
    return SolveSpec(
        target_s=3600,
        tolerance_pct=5,
        max_item_s=600,
        per_channel_cap=2,
        dp_unit_s=10,
        dp_top_n=60,
    )


def make_valid_solve_result() -> SolveResult:
    return SolveResult(
        items=[make_valid_candidate()],
        total_s=3600,
        feasible=True,
        shortfall_s=0,
        message="Optimal solution found",
    )


def make_valid_proposal_item() -> ProposalItem:
    return ProposalItem(
        position=1,
        video_id=VIDEO_ID,
        title="Item 1",
        channel_id=CHANNEL_ID,
        channel_title="Channel 1",
        duration_s=300,
        score=0.95,
    )


def make_valid_proposal() -> Proposal:
    return Proposal(
        proposal_id=UUID4_STR,
        request=make_valid_playlist_request(),
        items=[make_valid_proposal_item()],
        total_s=300,
        feasible=True,
        state=ProposalState.PROPOSED,
        items_hash=HASH64,
        expires_at=NOW,
        estimated_cost=50,
    )


def make_valid_scored_video() -> ScoredVideo:
    return ScoredVideo(
        video_id=VIDEO_ID,
        score=0.85,
        components={"text": 0.5, "tag": None},
        notes=["Good video"],
    )


def make_valid_scored_channel() -> ScoredChannel:
    return ScoredChannel(
        channel_id=CHANNEL_ID,
        score=0.75,
        components={"text": 0.4},
        notes=["Good channel"],
    )


def make_valid_taste_profile() -> TasteProfile:
    return TasteProfile(
        vector={"python": 0.8},
        top_terms=["python"],
        source_counts={"likes": 10},
    )


def make_valid_plan_item() -> PlanItem:
    return PlanItem(endpoint="videos_list", count=2)


def make_valid_estimate() -> Estimate:
    return Estimate(units=10, remaining_after=1990)


def make_valid_quota_status() -> QuotaStatus:
    return QuotaStatus(
        used_today=100,
        remaining=9900,
        reserve=500,
        machine_remaining=1900,
        reset_at=NOW,
        exhausted=False,
    )


def make_valid_quota_report() -> QuotaReport:
    return QuotaReport(spent=10, remaining=9990, estimate=10)


def make_valid_error_info() -> ErrorInfo:
    return ErrorInfo(
        code="INVALID_ID",
        message="Invalid ID provided",
        next_step="Check ID format",
    )


def make_valid_tool_result_ok() -> ToolResult:
    return ToolResult(
        ok=True,
        summary="Success",
        data={"key": "val"},
        quota=make_valid_quota_report(),
        notices=["Notice 1"],
    )


def make_valid_tool_result_error() -> ToolResult:
    return ToolResult(
        ok=False,
        summary="Failed",
        quota=make_valid_quota_report(),
        error=make_valid_error_info(),
    )


def make_valid_confirm_result() -> ConfirmResult:
    return ConfirmResult(
        state=ProposalState.CONFIRMED,
        playlist_id="PL123",
        playlist_url="https://youtube.com/playlist?list=PL123",
        items_added=1,
        items_missing=0,
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "factory",
    [
        make_valid_video,
        make_valid_channel,
        make_valid_channel_ref,
        make_valid_subscription,
        make_valid_playlist,
        make_valid_playlist_item,
        make_valid_text_doc,
        make_valid_channel_profile,
        make_valid_playlist_request,
        make_valid_candidate,
        make_valid_solve_spec,
        make_valid_solve_result,
        make_valid_proposal_item,
        make_valid_proposal,
        make_valid_scored_video,
        make_valid_scored_channel,
        make_valid_taste_profile,
        make_valid_plan_item,
        make_valid_estimate,
        make_valid_quota_status,
        make_valid_quota_report,
        make_valid_error_info,
        make_valid_tool_result_ok,
        make_valid_tool_result_error,
        make_valid_confirm_result,
    ],
)
def test_round_trip(factory) -> None:
    instance = factory()
    cls = type(instance)
    json_data = instance.model_dump_json()
    reloaded = cls.model_validate_json(json_data)
    assert reloaded == instance


@pytest.mark.unit
def test_defaults() -> None:
    v = Video(
        id=VIDEO_ID,
        title="Title",
        channel_id=CHANNEL_ID,
        published_at=NOW,
    )
    assert v.description == ""
    assert v.tags == []
    assert v.category_id is None
    assert v.duration_s is None
    assert v.channel_title == ""
    assert v.language is None
    assert v.privacy == "public"
    assert v.live_status == "none"
    assert v.view_count is None
    assert v.like_count is None
    assert v.embeddable is None

    c = Channel(
        id=CHANNEL_ID,
        title="Channel Title",
        published_at=NOW,
    )
    assert c.description == ""
    assert c.keywords == []
    assert c.topic_ids == []
    assert c.subscriber_count is None
    assert c.video_count is None
    assert c.uploads_playlist_id is None

    cand = Candidate(
        video_id=VIDEO_ID,
        channel_id=CHANNEL_ID,
        duration_s=120,
        relevance=0.8,
    )
    assert cand.difficulty == 0.0

    pr = PlaylistRequest(
        topic="Coding",
        total_duration_s=1000,
        max_video_duration_s=200,
        language="en",
    )
    assert pr.visibility == "private"
    assert pr.tolerance_pct == 5
    assert pr.title is None


@pytest.mark.unit
def test_frozen() -> None:
    v = make_valid_video()
    with pytest.raises((ValidationError, TypeError)):
        v.title = "New Title"  # type: ignore[misc]

    pr = make_valid_playlist_request()
    with pytest.raises((ValidationError, TypeError)):
        pr.topic = "New Topic"  # type: ignore[misc]

    p = make_valid_proposal()
    with pytest.raises((ValidationError, TypeError)):
        p.feasible = False  # type: ignore[misc]


@pytest.mark.unit
def test_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        Video(
            id=VIDEO_ID,
            title="Title",
            channel_id=CHANNEL_ID,
            published_at=NOW,
            extra_field="disallowed",  # type: ignore[call-arg]
        )


@pytest.mark.unit
def test_naive_datetime_rejected() -> None:
    naive_dt = datetime(2024, 5, 1, 10, 0, 0)
    with pytest.raises(ValidationError):
        Video(
            id=VIDEO_ID,
            title="Title",
            channel_id=CHANNEL_ID,
            published_at=naive_dt,
        )

    with pytest.raises(ValidationError):
        Channel(
            id=CHANNEL_ID,
            title="Title",
            published_at=naive_dt,
        )

    with pytest.raises(ValidationError):
        Subscription(
            channel_id=CHANNEL_ID,
            channel_title="Title",
            subscribed_at=naive_dt,
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "kwargs",
    [
        {"total_duration_s": 299},
        {"total_duration_s": 86401},
        {"max_video_duration_s": 59},
        {"total_duration_s": 600, "max_video_duration_s": 601},
        {"language": "eng"},
        {"language": "EN"},
        {"language": "e1"},
        {"topic": ""},
        {"topic": "a" * 201},
        {"title": ""},
        {"title": "a" * 151},
        {"visibility": "secret"},
        {"tolerance_pct": 51},
        {"tolerance_pct": -1},
    ],
)
def test_playlist_request_invalid(kwargs) -> None:
    base = {
        "topic": "Python",
        "total_duration_s": 1000,
        "max_video_duration_s": 300,
        "language": "en",
    }
    base.update(kwargs)
    with pytest.raises(ValidationError):
        PlaylistRequest(**base)


@pytest.mark.unit
def test_playlist_request_valid_edges() -> None:
    pr1 = PlaylistRequest(
        topic="T",
        total_duration_s=300,
        max_video_duration_s=60,
        language="en",
    )
    assert pr1.total_duration_s == 300
    assert pr1.max_video_duration_s == 60

    pr2 = PlaylistRequest(
        topic="T",
        total_duration_s=86400,
        max_video_duration_s=86400,
        language="en",
    )
    assert pr2.total_duration_s == 86400
    assert pr2.max_video_duration_s == 86400

    pr3 = PlaylistRequest(
        topic="x" * 200,
        total_duration_s=1000,
        max_video_duration_s=100,
        language="en",
        title="y" * 150,
    )
    assert len(pr3.topic) == 200
    assert pr3.title == "y" * 150

    for vis in ("private", "unlisted", "public"):
        pr = PlaylistRequest(
            topic="T",
            total_duration_s=1000,
            max_video_duration_s=100,
            language="en",
            visibility=vis,  # type: ignore[arg-type]
        )
        assert pr.visibility == vis


@pytest.mark.unit
def test_video_invalid() -> None:
    with pytest.raises(ValidationError):
        Video(
            id=VIDEO_ID,
            title="T",
            channel_id=CHANNEL_ID,
            published_at=NOW,
            privacy="secret",  # type: ignore[arg-type]
        )

    with pytest.raises(ValidationError):
        Video(
            id=VIDEO_ID,
            title="T",
            channel_id=CHANNEL_ID,
            published_at=NOW,
            live_status="finished",  # type: ignore[arg-type]
        )

    with pytest.raises(ValidationError):
        Video(
            id=VIDEO_ID,
            title="T",
            channel_id=CHANNEL_ID,
            published_at=NOW,
            duration_s=-1,
        )

    with pytest.raises(ValidationError):
        Video(
            id=VIDEO_ID,
            title="T",
            channel_id=CHANNEL_ID,
            published_at=NOW,
            view_count=-5,
        )

    with pytest.raises(ValidationError):
        Video(
            id="",
            title="T",
            channel_id=CHANNEL_ID,
            published_at=NOW,
        )


@pytest.mark.unit
def test_proposal_invalid() -> None:
    req = make_valid_playlist_request()
    with pytest.raises(ValidationError):
        Proposal(
            proposal_id="not-a-uuid",
            request=req,
            total_s=100,
            feasible=True,
            state=ProposalState.PROPOSED,
            items_hash=HASH64,
            expires_at=NOW,
            estimated_cost=10,
        )

    uuid1_str = str(uuid.uuid1())
    with pytest.raises(ValidationError):
        Proposal(
            proposal_id=uuid1_str,
            request=req,
            total_s=100,
            feasible=True,
            state=ProposalState.PROPOSED,
            items_hash=HASH64,
            expires_at=NOW,
            estimated_cost=10,
        )

    with pytest.raises(ValidationError):
        Proposal(
            proposal_id=UUID4_STR,
            request=req,
            total_s=100,
            feasible=True,
            state=ProposalState.PROPOSED,
            items_hash="abc",
            expires_at=NOW,
            estimated_cost=10,
        )

    with pytest.raises(ValidationError):
        Proposal(
            proposal_id=UUID4_STR,
            request=req,
            total_s=100,
            feasible=True,
            state=ProposalState.PROPOSED,
            items_hash=HASH64,
            expires_at=NOW,
            estimated_cost=-1,
        )

    valid_p = Proposal(
        proposal_id=str(uuid.uuid4()),
        request=req,
        total_s=100,
        feasible=True,
        state=ProposalState.PROPOSED,
        items_hash=HASH64,
        expires_at=NOW,
        estimated_cost=10,
    )
    assert valid_p.feasible is True


@pytest.mark.unit
def test_proposal_state_values() -> None:
    expected = [
        "DRAFT",
        "PROPOSED",
        "CONFIRMED",
        "CREATED",
        "PARTIALLY_CREATED",
        "FAILED",
        "REJECTED",
        "EXPIRED",
    ]
    assert [state.value for state in ProposalState] == expected
    for state in ProposalState:
        assert state == state.name


@pytest.mark.unit
def test_plan_item_endpoint() -> None:
    for ep in ENDPOINTS:
        item = PlanItem(endpoint=ep, count=1)
        assert item.endpoint == ep

    with pytest.raises(ValidationError):
        PlanItem(endpoint="search", count=1)  # type: ignore[arg-type]

    with pytest.raises(ValidationError):
        PlanItem(endpoint="videos.list", count=1)  # type: ignore[arg-type]

    with pytest.raises(ValidationError):
        PlanItem(endpoint="videos_list", count=-1)


@pytest.mark.unit
def test_endpoints_match_config() -> None:
    expected_order = (
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
    assert ENDPOINTS == expected_order
    costs_fields = set(QuotaCosts.model_fields.keys())
    assert set(ENDPOINTS) == costs_fields


@pytest.mark.unit
def test_request_bounds_match_config() -> None:
    settings = load_settings(env={})
    assert settings.playlist.min_total_s == 300
    assert settings.playlist.max_total_s == 86400
    assert settings.playlist.topic_max_len == 200
    assert settings.playlist.title_max_len == 150


@pytest.mark.unit
def test_tool_result_rule() -> None:
    qr = make_valid_quota_report()
    err = make_valid_error_info()

    with pytest.raises(ValidationError):
        ToolResult(ok=True, summary="Ok with error", quota=qr, error=err)

    with pytest.raises(ValidationError):
        ToolResult(ok=False, summary="Fail without error", quota=qr, error=None)

    t1 = ToolResult(ok=True, summary="All good", quota=qr)
    assert t1.ok is True
    assert t1.error is None

    t2 = ToolResult(ok=False, summary="Something bad", quota=qr, error=err)
    assert t2.ok is False
    assert t2.error == err


@pytest.mark.unit
def test_solve_and_ranking_models() -> None:
    sr = SolveResult(feasible=False, shortfall_s=120, message="Under target")
    assert sr.feasible is False
    assert sr.shortfall_s == 120
    assert sr.total_s == 0
    assert sr.items == []

    sv = make_valid_scored_video()
    sv_json = sv.model_dump_json()
    assert ScoredVideo.model_validate_json(sv_json) == sv

    cp = make_valid_channel_profile()
    cp_json = cp.model_dump_json()
    assert ChannelProfile.model_validate_json(cp_json) == cp

    tp = make_valid_taste_profile()
    tp_json = tp.model_dump_json()
    assert TasteProfile.model_validate_json(tp_json) == tp
