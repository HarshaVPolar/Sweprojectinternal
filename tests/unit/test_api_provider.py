from collections.abc import Callable, Mapping
from typing import Any

import pytest

from ytmcp.errors import ChannelRequired, NotFoundOrPrivate, QuotaExhausted
from ytmcp.models import Channel, ChannelRef
from ytmcp.providers.api_provider import (
    CHANNEL_PARTS,
    PAGE_SIZE,
    VIDEO_PARTS,
    ApiBackedProvider,
)
from ytmcp.providers.base import YouTubeProvider
from ytmcp.providers.mapping import MappingError
from ytmcp.providers.transport import ApiHttpError, Params


class FakeTransport:
    """Fake transport capturing calls and posts for testing ApiBackedProvider."""

    def __init__(self, handler: Callable[..., dict[str, Any]]) -> None:
        self.handler = handler
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.posts: list[tuple[str, dict[str, Any], dict[str, Any]]] = []

    def call(self, method: str, params: Params) -> dict[str, Any]:
        self.calls.append((method, dict(params)))
        return self.handler(method, dict(params))

    def post(
        self,
        method: str,
        params: Params,
        body: Mapping[str, Any],
    ) -> dict[str, Any]:
        self.posts.append((method, dict(params), dict(body)))
        return self.handler(method, dict(params), dict(body))


@pytest.mark.unit
def test_get_videos_batches_and_order(make_video_item: Any) -> None:
    # 120 distinct IDs in reverse order plus one duplicate of the first ID
    input_ids = [f"vid{i:08d}" for i in range(120, 0, -1)] + ["vid00000120"]

    def handler(method: str, params: dict[str, Any]) -> dict[str, Any]:
        assert method == "videos_list"
        assert params["part"] == VIDEO_PARTS
        requested_ids = params["id"].split(",")
        items = []
        for vid in requested_ids:
            if vid != "vid00000005":
                items.append(make_video_item(video_id=vid))
        return {"items": items}

    transport = FakeTransport(handler)
    provider = ApiBackedProvider(transport)

    videos = provider.get_videos(input_ids)
    expected_ids = [f"vid{i:08d}" for i in range(120, 0, -1) if f"vid{i:08d}" != "vid00000005"]
    assert [v.id for v in videos] == expected_ids
    assert len(transport.calls) == 3
    assert len(transport.calls[0][1]["id"].split(",")) == 50
    assert len(transport.calls[1][1]["id"].split(",")) == 50
    assert len(transport.calls[2][1]["id"].split(",")) == 20

    for _, p in transport.calls:
        ids_in_call = p["id"].split(",")
        assert ids_in_call == sorted(ids_in_call)


@pytest.mark.unit
def test_get_videos_empty() -> None:
    transport = FakeTransport(lambda method, params: {"items": []})
    provider = ApiBackedProvider(transport)
    assert provider.get_videos([]) == []
    assert len(transport.calls) == 0


@pytest.mark.unit
def test_search_pagination() -> None:
    def handler(method: str, params: dict[str, Any]) -> dict[str, Any]:
        assert method == "search_list"
        assert params["part"] == "snippet"
        assert params["q"] == "algebra"
        assert params["type"] == "video"
        page_token = params.get("pageToken")
        if page_token is None:
            return {
                "items": [{"id": {"videoId": f"v1_{i}"}} for i in range(50)],
                "nextPageToken": "T1",
            }
        if page_token == "T1":
            return {
                "items": [{"id": {"videoId": f"v2_{i}"}} for i in range(50)],
                "nextPageToken": "T2",
            }
        if page_token == "T2":
            return {
                "items": [{"id": {"videoId": f"v3_{i}"}} for i in range(50)],
            }
        return {"items": []}

    transport = FakeTransport(handler)
    provider = ApiBackedProvider(transport)

    results = provider.search("algebra", max_results=120)
    assert len(results) == 120
    assert len(set(results)) == 120
    assert len(transport.calls) == 3
    assert transport.calls[0][1]["maxResults"] == 50
    assert transport.calls[1][1]["maxResults"] == 50
    assert transport.calls[2][1]["maxResults"] == 20
    assert transport.calls[1][1]["pageToken"] == "T1"
    assert transport.calls[2][1]["pageToken"] == "T2"


@pytest.mark.unit
def test_search_options() -> None:
    transport = FakeTransport(lambda method, params: {"items": []})
    provider = ApiBackedProvider(transport)

    provider.search(
        "math",
        type="channel",
        max_results=10,
        language="en",
        published_after="2024-01-01T00:00:00Z",
    )
    call_params = transport.calls[0][1]
    assert call_params["type"] == "channel"
    assert call_params["maxResults"] == 10
    assert call_params["relevanceLanguage"] == "en"
    assert call_params["publishedAfter"] == "2024-01-01T00:00:00Z"

    # Call without options
    transport.calls.clear()
    provider.search("math")
    c2 = transport.calls[0][1]
    assert "relevanceLanguage" not in c2
    assert "publishedAfter" not in c2
    assert c2["type"] == "video"
    assert c2["maxResults"] == 50


@pytest.mark.unit
def test_search_repeated_token() -> None:
    counter = 0

    def handler(method: str, params: dict[str, Any]) -> dict[str, Any]:
        nonlocal counter
        items = [{"id": {"videoId": f"v_{counter}_{i}"}} for i in range(5)]
        counter += 1
        return {"items": items, "nextPageToken": "SAME"}

    transport = FakeTransport(handler)
    provider = ApiBackedProvider(transport)
    results = provider.search("query", max_results=50)
    assert len(results) == 10
    assert len(transport.calls) == 2


@pytest.mark.unit
def test_get_channels(make_channel_item: Any) -> None:
    c_ids = [f"UC{'a' * 16}{i:06d}" for i in range(60)]

    def handler(method: str, params: dict[str, Any]) -> dict[str, Any]:
        assert method == "channels_list"
        assert params["part"] == CHANNEL_PARTS
        req_ids = params["id"].split(",")
        return {"items": [make_channel_item(cid) for cid in req_ids if cid != c_ids[5]]}

    transport = FakeTransport(handler)
    provider = ApiBackedProvider(transport)

    channels = provider.get_channels(c_ids)
    expected_ids = [cid for cid in c_ids if cid != c_ids[5]]
    assert [c.id for c in channels] == expected_ids
    assert len(transport.calls) == 2
    assert len(transport.calls[0][1]["id"].split(",")) == 50
    assert len(transport.calls[1][1]["id"].split(",")) == 10


@pytest.mark.unit
def test_resolve_channel(make_channel_item: Any) -> None:
    def handler(method: str, params: dict[str, Any]) -> dict[str, Any]:
        if method == "channels_list" and params.get("forHandle") == "@math":
            return {"items": [{"id": "UC_resolved_handle"}]}
        if method == "channels_list" and params.get("forUsername") == "mathchan":
            return {"items": [{"id": "UC_resolved_user"}]}
        if method == "search_list" and params.get("type") == "channel":
            return {"items": [{"id": {"channelId": "UC_resolved_custom"}}]}
        if method == "channels_list" and "UC" + "a" * 22 in params.get("id", ""):
            return {"items": [make_channel_item("UC" + "a" * 22)]}
        return {"items": []}

    transport = FakeTransport(handler)
    provider = ApiBackedProvider(transport)

    assert (
        provider.resolve_channel(ChannelRef(kind="handle", value="@math")) == "UC_resolved_handle"
    )
    assert transport.calls[-1] == ("channels_list", {"part": "id", "forHandle": "@math"})

    assert (
        provider.resolve_channel(ChannelRef(kind="username", value="mathchan"))
        == "UC_resolved_user"
    )
    assert transport.calls[-1] == ("channels_list", {"part": "id", "forUsername": "mathchan"})

    assert (
        provider.resolve_channel(ChannelRef(kind="custom", value="mathchan"))
        == "UC_resolved_custom"
    )
    assert transport.calls[-1] == (
        "search_list",
        {"part": "snippet", "q": "mathchan", "type": "channel", "maxResults": 5},
    )

    valid_id = "UC" + "a" * 22
    assert provider.resolve_channel(ChannelRef(kind="id", value=valid_id)) == valid_id

    missing_id = "UC" + "z" * 22
    assert provider.resolve_channel(ChannelRef(kind="id", value=missing_id)) is None

    assert provider.resolve_channel(ChannelRef(kind="handle", value="@missing")) is None


@pytest.mark.unit
def test_recent_uploads() -> None:
    channel = Channel(
        id="UC" + "a" * 22,
        title="Math",
        published_at="2020-01-01T00:00:00Z",
        uploads_playlist_id="UUxyz",
    )

    # For n=15
    def handler_15(method: str, params: dict[str, Any]) -> dict[str, Any]:
        assert method == "playlist_items_list"
        assert params == {
            "part": "snippet,contentDetails",
            "playlistId": "UUxyz",
            "maxResults": 15,
        }
        return {
            "items": [
                {
                    "snippet": {
                        "playlistId": "UUxyz",
                        "position": i,
                        "publishedAt": "2024-01-01T00:00:00Z",
                        "resourceId": {"kind": "youtube#video", "videoId": f"vid000000{i:02d}"},
                    }
                }
                for i in range(15)
            ]
        }

    t15 = FakeTransport(handler_15)
    p15 = ApiBackedProvider(t15)
    r15 = p15.recent_uploads(channel, n=15)
    assert r15 == [f"vid000000{i:02d}" for i in range(15)]
    assert len(t15.calls) == 1

    # For n=60
    def handler_60(method: str, params: dict[str, Any]) -> dict[str, Any]:
        if "pageToken" not in params:
            assert params["maxResults"] == 50
            return {
                "items": [
                    {
                        "snippet": {
                            "playlistId": "UUxyz",
                            "position": i,
                            "publishedAt": "2024-01-01T00:00:00Z",
                            "resourceId": {"kind": "youtube#video", "videoId": f"vid1_{i:06d}"},
                        }
                    }
                    for i in range(50)
                ],
                "nextPageToken": "PAGE2",
            }
        assert params["maxResults"] == 10
        assert params["pageToken"] == "PAGE2"
        return {
            "items": [
                {
                    "snippet": {
                        "playlistId": "UUxyz",
                        "position": i,
                        "publishedAt": "2024-01-01T00:00:00Z",
                        "resourceId": {"kind": "youtube#video", "videoId": f"vid2_{i:06d}"},
                    }
                }
                for i in range(10)
            ]
        }

    t60 = FakeTransport(handler_60)
    p60 = ApiBackedProvider(t60)
    r60 = p60.recent_uploads(channel, n=60)
    assert len(r60) == 60
    assert len(t60.calls) == 2

    # Channel without uploads
    c_no_uploads = Channel(
        id="UC" + "b" * 22,
        title="No Uploads",
        published_at="2020-01-01T00:00:00Z",
        uploads_playlist_id=None,
    )
    assert p60.recent_uploads(c_no_uploads) == []


def _make_paged_item(method: str, idx: int, make_video_item: Any) -> dict[str, Any]:
    vid = f"vid{idx:08d}"
    if method == "videos_list":
        return make_video_item(video_id=vid)
    if method == "subscriptions_list":
        return {
            "snippet": {
                "publishedAt": "2020-01-01T00:00:00Z",
                "title": f"Sub {idx}",
                "resourceId": {"channelId": "UC" + "a" * 22},
            }
        }
    if method == "playlists_list":
        return {
            "id": f"PL_{idx}",
            "snippet": {
                "title": f"List {idx}",
                "publishedAt": "2020-01-01T00:00:00Z",
            },
            "contentDetails": {"itemCount": 5},
        }
    return {
        "snippet": {
            "playlistId": "PL1",
            "position": idx,
            "publishedAt": "2020-01-01T00:00:00Z",
            "resourceId": {"videoId": vid},
        }
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    ("method_name", "extra_args", "expected_method", "expected_base_params"),
    [
        (
            "list_liked",
            (),
            "videos_list",
            {"part": VIDEO_PARTS, "myRating": "like", "maxResults": 50},
        ),
        (
            "list_subscriptions",
            (),
            "subscriptions_list",
            {"part": "snippet", "mine": "true", "maxResults": 50},
        ),
        (
            "list_playlists",
            (),
            "playlists_list",
            {"part": "snippet,contentDetails", "mine": "true", "maxResults": 50},
        ),
        (
            "list_playlist_items",
            ("PL1",),
            "playlist_items_list",
            {"part": "snippet,contentDetails", "playlistId": "PL1", "maxResults": 50},
        ),
    ],
)
def test_paged_lists(
    method_name: str,
    extra_args: tuple[Any, ...],
    expected_method: str,
    expected_base_params: dict[str, Any],
    make_video_item: Any,
) -> None:
    def handler(method: str, params: dict[str, Any]) -> dict[str, Any]:
        assert method == expected_method
        for k, v in expected_base_params.items():
            assert params[k] == v
        page_token = params.get("pageToken")
        if page_token is None:
            items = [_make_paged_item(method, i, make_video_item) for i in range(3)]
            return {"items": items, "nextPageToken": "P2"}
        if page_token == "P2":
            items = [_make_paged_item(method, i, make_video_item) for i in range(3, 6)]
            return {"items": items}
        return {"items": []}

    transport = FakeTransport(handler)
    provider = ApiBackedProvider(transport)
    func = getattr(provider, method_name)

    # cap 10 -> 6 items, 2 calls
    res10 = func(*extra_args, cap=10)
    assert len(res10) == 6
    assert len(transport.calls) == 2
    assert transport.calls[1][1]["pageToken"] == "P2"

    # cap 4 -> 4 items, 2 calls
    transport.calls.clear()
    res4 = func(*extra_args, cap=4)
    assert len(res4) == 4
    assert len(transport.calls) == 2

    # cap 2 -> 2 items, 1 call
    transport.calls.clear()
    res2 = func(*extra_args, cap=2)
    assert len(res2) == 2
    assert len(transport.calls) == 1

    # cap 0 -> [] and no call
    transport.calls.clear()
    res0 = func(*extra_args, cap=0)
    assert res0 == []
    assert len(transport.calls) == 0


@pytest.mark.unit
def test_video_categories_and_my_channel(make_channel_item: Any) -> None:
    def handler(method: str, params: dict[str, Any]) -> dict[str, Any]:
        if method == "video_categories_list":
            assert params == {"part": "snippet", "regionCode": "IN"}
            return {"items": [{"id": "1", "snippet": {"title": "Film"}}]}
        if method == "channels_list":
            assert params == {"part": CHANNEL_PARTS, "mine": "true"}
            return {"items": [make_channel_item("UC" + "a" * 22)]}
        return {"items": []}

    transport = FakeTransport(handler)
    provider = ApiBackedProvider(transport)

    assert provider.video_categories("IN") == {"1": "Film"}
    channel = provider.my_channel()
    assert channel is not None
    assert channel.id == "UC" + "a" * 22

    # Empty channel response returns None
    t_empty = FakeTransport(lambda m, p: {"items": []})
    p_empty = ApiBackedProvider(t_empty)
    assert p_empty.my_channel() is None


@pytest.mark.unit
def test_create_and_add() -> None:
    def handler(method: str, params: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
        if method == "playlists_insert":
            assert params == {"part": "snippet,status"}
            assert body == {
                "snippet": {"title": "T", "description": "D"},
                "status": {"privacyStatus": "private"},
            }
            return {"id": "PL_new_123"}
        if method == "playlist_items_insert":
            assert params == {"part": "snippet"}
            assert body == {
                "snippet": {
                    "playlistId": "PL1",
                    "resourceId": {"kind": "youtube#video", "videoId": "vid00000001"},
                }
            }
            return {"id": "item_123"}
        return {}

    transport = FakeTransport(handler)
    provider = ApiBackedProvider(transport)

    pl_id = provider.create_playlist("T", "D", "private")
    assert pl_id == "PL_new_123"

    provider.add_playlist_item("PL1", "vid00000001")
    assert len(transport.posts) == 2

    # Missing ID raises MappingError
    t_bad = FakeTransport(lambda m, p, b: {})
    p_bad = ApiBackedProvider(t_bad)
    with pytest.raises(MappingError):
        p_bad.create_playlist("T", "D", "private")


@pytest.mark.unit
def test_http_errors_translated() -> None:
    # 403 quotaExceeded
    def fail_quota(method: str, params: dict[str, Any]) -> dict[str, Any]:
        raise ApiHttpError(403, {"error": {"errors": [{"reason": "quotaExceeded"}]}})

    p1 = ApiBackedProvider(FakeTransport(fail_quota))
    with pytest.raises(QuotaExhausted) as exc1:
        p1.get_videos(["v1"])
    assert isinstance(exc1.value.__cause__, ApiHttpError)

    # 401 youtubeSignupRequired on post
    def fail_signup(method: str, params: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
        raise ApiHttpError(401, {"error": {"errors": [{"reason": "youtubeSignupRequired"}]}})

    p2 = ApiBackedProvider(FakeTransport(fail_signup))
    with pytest.raises(ChannelRequired) as exc2:
        p2.create_playlist("T")
    assert isinstance(exc2.value.__cause__, ApiHttpError)

    # 404
    def fail_404(method: str, params: dict[str, Any]) -> dict[str, Any]:
        raise ApiHttpError(404, {"error": {"errors": [{"reason": "notFound"}]}})

    p3 = ApiBackedProvider(FakeTransport(fail_404))
    with pytest.raises(NotFoundOrPrivate) as exc3:
        p3.get_channels(["UC" + "a" * 22])
    assert isinstance(exc3.value.__cause__, ApiHttpError)


@pytest.mark.unit
def test_provider_is_a_youtube_provider() -> None:
    provider = ApiBackedProvider(FakeTransport(lambda m, p: {"items": []}))
    assert isinstance(provider, YouTubeProvider)
    assert VIDEO_PARTS == "snippet,contentDetails,statistics,status"
    assert CHANNEL_PARTS == "snippet,contentDetails,statistics,brandingSettings,topicDetails"
    assert PAGE_SIZE == 50
