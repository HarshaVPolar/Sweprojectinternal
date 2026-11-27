import copy
from datetime import UTC, datetime
from typing import Any

import pytest

from ytmcp.models import Channel, Playlist, PlaylistItem, Subscription, Video
from ytmcp.providers.mapping import (
    MappingError,
    map_categories,
    map_channel,
    map_channels,
    map_playlist,
    map_playlist_item,
    map_playlist_items,
    map_playlists,
    map_search_ids,
    map_subscription,
    map_subscriptions,
    map_video,
    map_videos,
    next_page_token,
    normalise_language,
    parse_keywords,
)

CHANNEL_ID = "UC" + "a" * 22

VIDEO_FULL: dict[str, Any] = {
    "id": "vid00000001",
    "snippet": {
        "publishedAt": "2024-05-01T10:00:00Z",
        "channelId": CHANNEL_ID,
        "title": "Linear algebra basics",
        "description": "Vectors and matrices.",
        "channelTitle": "Math Channel",
        "tags": ["algebra", "math"],
        "categoryId": "27",
        "liveBroadcastContent": "none",
        "defaultAudioLanguage": "en-US",
    },
    "contentDetails": {
        "duration": "PT1H2M3S",
    },
    "status": {
        "privacyStatus": "public",
        "embeddable": True,
    },
    "statistics": {
        "viewCount": "1234",
        "likeCount": "56",
    },
}

VIDEO_MINIMAL: dict[str, Any] = {
    "id": "vid00000002",
    "snippet": {
        "publishedAt": "2024-05-01T10:00:00Z",
        "channelId": CHANNEL_ID,
        "title": "T",
    },
}

CHANNEL_FULL: dict[str, Any] = {
    "id": CHANNEL_ID,
    "snippet": {
        "title": "Math Channel",
        "description": "All about math",
        "publishedAt": "2015-01-02T03:04:05Z",
    },
    "statistics": {
        "subscriberCount": "1500",
        "hiddenSubscriberCount": False,
        "videoCount": "200",
    },
    "brandingSettings": {
        "channel": {
            "keywords": 'math "linear algebra" teaching',
        },
    },
    "topicDetails": {
        "topicIds": ["/m/04rlf", "/m/01k8wb"],
    },
    "contentDetails": {
        "relatedPlaylists": {
            "uploads": "UU" + "a" * 22,
        },
    },
}

CHANNEL_MINIMAL: dict[str, Any] = {
    "id": CHANNEL_ID,
    "snippet": {
        "title": "C",
        "publishedAt": "2015-01-02T03:04:05Z",
    },
}


@pytest.mark.unit
def test_map_video_full() -> None:
    video = map_video(copy.deepcopy(VIDEO_FULL))
    assert isinstance(video, Video)
    assert video.id == "vid00000001"
    assert video.title == "Linear algebra basics"
    assert video.description == "Vectors and matrices."
    assert video.channel_id == CHANNEL_ID
    assert video.channel_title == "Math Channel"
    assert video.tags == ["algebra", "math"]
    assert video.category_id == "27"
    assert video.duration_s == 3723
    assert video.language == "en"
    assert video.published_at == datetime(2024, 5, 1, 10, 0, 0, tzinfo=UTC)
    assert video.privacy == "public"
    assert video.live_status == "none"
    assert video.view_count == 1234
    assert video.like_count == 56
    assert video.embeddable is True


@pytest.mark.unit
def test_map_video_minimal() -> None:
    video = map_video(copy.deepcopy(VIDEO_MINIMAL))
    assert isinstance(video, Video)
    assert video.id == "vid00000002"
    assert video.title == "T"
    assert video.description == ""
    assert video.tags == []
    assert video.category_id is None
    assert video.channel_title == ""
    assert video.duration_s is None
    assert video.language is None
    assert video.privacy == "public"
    assert video.live_status == "none"
    assert video.view_count is None
    assert video.like_count is None
    assert video.embeddable is None


@pytest.mark.unit
@pytest.mark.parametrize(
    "modifier",
    [
        lambda d: d.pop("id"),
        lambda d: d.update({"id": {"nested": "not a string"}}),
        lambda d: d.pop("snippet"),
        lambda d: d["snippet"].pop("title"),
        lambda d: d["snippet"].pop("channelId"),
        lambda d: d["snippet"].pop("publishedAt"),
    ],
)
def test_map_video_missing_required(modifier: Any) -> None:
    data = copy.deepcopy(VIDEO_FULL)
    modifier(data)
    with pytest.raises(MappingError):
        map_video(data)


@pytest.mark.unit
def test_map_video_bad_values() -> None:
    d1 = copy.deepcopy(VIDEO_FULL)
    d1["contentDetails"]["duration"] = "garbage"
    with pytest.raises(MappingError):
        map_video(d1)

    d2 = copy.deepcopy(VIDEO_FULL)
    d2["snippet"]["publishedAt"] = "yesterday"
    with pytest.raises(MappingError):
        map_video(d2)

    d3 = copy.deepcopy(VIDEO_FULL)
    d3["statistics"]["viewCount"] = "abc"
    with pytest.raises(MappingError):
        map_video(d3)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("audio_lang", "default_lang", "expected"),
    [
        ("fr", "en", "fr"),
        (None, "de-DE", "de"),
        ("zxx", None, None),
        ("zxx", "en", "en"),
        (None, None, None),
    ],
)
def test_map_video_language(
    audio_lang: str | None,
    default_lang: str | None,
    expected: str | None,
) -> None:
    data = copy.deepcopy(VIDEO_MINIMAL)
    if audio_lang is not None:
        data["snippet"]["defaultAudioLanguage"] = audio_lang
    if default_lang is not None:
        data["snippet"]["defaultLanguage"] = default_lang
    video = map_video(data)
    assert video.language == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    ("live_content", "expected_status"),
    [
        ("live", "live"),
        ("upcoming", "upcoming"),
        ("none", "none"),
        ("completed", "none"),
        ("weird", "none"),
    ],
)
def test_map_video_live_status(live_content: str, expected_status: str) -> None:
    data = copy.deepcopy(VIDEO_MINIMAL)
    data["snippet"]["liveBroadcastContent"] = live_content
    video = map_video(data)
    assert video.live_status == expected_status


@pytest.mark.unit
def test_map_video_live_duration_zero() -> None:
    data = copy.deepcopy(VIDEO_MINIMAL)
    data["snippet"]["liveBroadcastContent"] = "live"
    data["contentDetails"] = {"duration": "P0D"}
    video = map_video(data)
    assert video.live_status == "live"
    assert video.duration_s == 0


@pytest.mark.unit
@pytest.mark.parametrize(
    ("privacy_input", "expected_privacy"),
    [
        ("public", "public"),
        ("unlisted", "unlisted"),
        ("private", "private"),
        ("weird", "public"),
    ],
)
def test_map_video_privacy(privacy_input: str, expected_privacy: str) -> None:
    data = copy.deepcopy(VIDEO_MINIMAL)
    data["status"] = {"privacyStatus": privacy_input}
    video = map_video(data)
    assert video.privacy == expected_privacy


@pytest.mark.unit
def test_map_video_privacy_missing_and_embeddable_not_bool() -> None:
    data = copy.deepcopy(VIDEO_MINIMAL)
    video = map_video(data)
    assert video.privacy == "public"

    data["status"] = {"embeddable": "yes"}
    video2 = map_video(data)
    assert video2.embeddable is None


@pytest.mark.unit
def test_map_video_hidden_likes() -> None:
    data = copy.deepcopy(VIDEO_FULL)
    data["statistics"].pop("likeCount")
    video = map_video(data)
    assert video.like_count is None
    assert video.view_count == 1234


@pytest.mark.unit
def test_map_videos() -> None:
    response = {"items": [copy.deepcopy(VIDEO_FULL), copy.deepcopy(VIDEO_MINIMAL)]}
    videos = map_videos(response)
    assert len(videos) == 2
    assert videos[0].id == "vid00000001"
    assert videos[1].id == "vid00000002"

    assert map_videos({}) == []
    assert map_videos({"items": []}) == []


@pytest.mark.unit
def test_map_channel_full() -> None:
    channel = map_channel(copy.deepcopy(CHANNEL_FULL))
    assert isinstance(channel, Channel)
    assert channel.id == CHANNEL_ID
    assert channel.title == "Math Channel"
    assert channel.description == "All about math"
    assert channel.keywords == ["math", "linear algebra", "teaching"]
    assert channel.topic_ids == ["/m/04rlf", "/m/01k8wb"]
    assert channel.subscriber_count == 1500
    assert channel.video_count == 200
    assert channel.uploads_playlist_id == "UU" + "a" * 22
    assert channel.published_at == datetime(2015, 1, 2, 3, 4, 5, tzinfo=UTC)


@pytest.mark.unit
def test_map_channel_hidden() -> None:
    data = copy.deepcopy(CHANNEL_FULL)
    data["statistics"]["hiddenSubscriberCount"] = True
    channel = map_channel(data)
    assert channel.subscriber_count is None
    assert channel.video_count == 200

    data2 = copy.deepcopy(CHANNEL_FULL)
    data2.pop("statistics")
    channel2 = map_channel(data2)
    assert channel2.subscriber_count is None
    assert channel2.video_count is None


@pytest.mark.unit
def test_map_channel_minimal() -> None:
    channel = map_channel(copy.deepcopy(CHANNEL_MINIMAL))
    assert isinstance(channel, Channel)
    assert channel.id == CHANNEL_ID
    assert channel.title == "C"
    assert channel.description == ""
    assert channel.keywords == []
    assert channel.topic_ids == []
    assert channel.subscriber_count is None
    assert channel.video_count is None
    assert channel.uploads_playlist_id is None


@pytest.mark.unit
@pytest.mark.parametrize(
    "modifier",
    [
        lambda d: d.pop("id"),
        lambda d: d["snippet"].pop("title"),
        lambda d: d["snippet"].pop("publishedAt"),
    ],
)
def test_map_channel_missing_required(modifier: Any) -> None:
    data = copy.deepcopy(CHANNEL_FULL)
    modifier(data)
    with pytest.raises(MappingError):
        map_channel(data)


@pytest.mark.unit
def test_map_channels() -> None:
    resp = {"items": [copy.deepcopy(CHANNEL_FULL), copy.deepcopy(CHANNEL_MINIMAL)]}
    channels = map_channels(resp)
    assert len(channels) == 2
    assert channels[0].title == "Math Channel"
    assert channels[1].title == "C"

    assert map_channels({}) == []
    assert map_channels({"items": []}) == []


@pytest.mark.unit
def test_map_subscription() -> None:
    sample = {
        "snippet": {
            "publishedAt": "2023-02-03T04:05:06Z",
            "title": "Chan",
            "resourceId": {
                "kind": "youtube#channel",
                "channelId": CHANNEL_ID,
            },
        }
    }
    sub = map_subscription(copy.deepcopy(sample))
    assert isinstance(sub, Subscription)
    assert sub.channel_id == CHANNEL_ID
    assert sub.channel_title == "Chan"
    assert sub.subscribed_at == datetime(2023, 2, 3, 4, 5, 6, tzinfo=UTC)

    bad = copy.deepcopy(sample)
    bad["snippet"].pop("resourceId")
    with pytest.raises(MappingError):
        map_subscription(bad)

    subs = map_subscriptions({"items": [sample]})
    assert len(subs) == 1
    assert subs[0].channel_id == CHANNEL_ID


@pytest.mark.unit
def test_map_playlist() -> None:
    sample = {
        "id": "PL1",
        "snippet": {
            "title": "My list",
            "publishedAt": "2022-01-01T00:00:00Z",
        },
        "contentDetails": {
            "itemCount": 7,
        },
    }
    pl = map_playlist(copy.deepcopy(sample))
    assert isinstance(pl, Playlist)
    assert pl.id == "PL1"
    assert pl.title == "My list"
    assert pl.item_count == 7
    assert pl.published_at == datetime(2022, 1, 1, 0, 0, 0, tzinfo=UTC)

    without_details = copy.deepcopy(sample)
    without_details.pop("contentDetails")
    pl_default = map_playlist(without_details)
    assert pl_default.item_count == 0

    without_id = copy.deepcopy(sample)
    without_id.pop("id")
    with pytest.raises(MappingError):
        map_playlist(without_id)

    playlists = map_playlists({"items": [sample]})
    assert len(playlists) == 1
    assert playlists[0].id == "PL1"


@pytest.mark.unit
def test_map_playlist_item() -> None:
    sample = {
        "snippet": {
            "playlistId": "PL1",
            "position": 3,
            "publishedAt": "2022-01-02T00:00:00Z",
            "resourceId": {
                "kind": "youtube#video",
                "videoId": "vid00000001",
            },
        },
        "contentDetails": {
            "videoId": "vid00000009",
        },
    }
    item = map_playlist_item(copy.deepcopy(sample))
    assert isinstance(item, PlaylistItem)
    assert item.video_id == "vid00000001"
    assert item.position == 3
    assert item.playlist_id == "PL1"
    assert item.added_at == datetime(2022, 1, 2, 0, 0, 0, tzinfo=UTC)

    no_resource = copy.deepcopy(sample)
    no_resource["snippet"].pop("resourceId")
    item2 = map_playlist_item(no_resource)
    assert item2.video_id == "vid00000009"

    no_video_id = copy.deepcopy(no_resource)
    no_video_id.pop("contentDetails")
    with pytest.raises(MappingError):
        map_playlist_item(no_video_id)

    no_position = copy.deepcopy(sample)
    no_position["snippet"].pop("position")
    with pytest.raises(MappingError):
        map_playlist_item(no_position)

    items = map_playlist_items({"items": [sample]})
    assert len(items) == 1
    assert items[0].video_id == "vid00000001"


@pytest.mark.unit
def test_map_categories() -> None:
    response = {
        "items": [
            {"id": "1", "snippet": {"title": "Film & Animation"}},
            {"id": "27", "snippet": {"title": "Education"}},
        ]
    }
    cats = map_categories(response)
    assert cats == {"1": "Film & Animation", "27": "Education"}
    assert map_categories({}) == {}


@pytest.mark.unit
def test_map_search_ids() -> None:
    response = {
        "items": [
            {"id": {"videoId": "vid00000001"}},
            {"id": {"videoId": "vid00000002"}},
            {"id": {"videoId": "vid00000001"}},
            {"id": {"channelId": CHANNEL_ID}},
            {"id": "not-an-object"},
            {"unrelated": 123},
        ]
    }
    video_ids = map_search_ids(response, "video")
    assert video_ids == ["vid00000001", "vid00000002"]

    channel_ids = map_search_ids(response, "channel")
    assert channel_ids == [CHANNEL_ID]

    assert map_search_ids({}, "video") == []


@pytest.mark.unit
def test_next_page_token() -> None:
    assert next_page_token({"nextPageToken": "ABC"}) == "ABC"
    assert next_page_token({}) is None
    assert next_page_token({"nextPageToken": ""}) is None
    assert next_page_token({"nextPageToken": 5}) is None


@pytest.mark.unit
@pytest.mark.parametrize(
    ("input_text", "expected"),
    [
        (None, []),
        ("", []),
        ("   ", []),
        ("linear algebra math", ["linear", "algebra", "math"]),
        ('linear "khan academy" math', ["linear", "khan academy", "math"]),
        ('"a b" "c d"', ["a b", "c d"]),
        (' "unclosed phrase here', ["unclosed", "phrase", "here"]),
        ('x  ""', ["x"]),
        ("tab\tsep\nnl", ["tab", "sep", "nl"]),
    ],
)
def test_parse_keywords(input_text: str | None, expected: list[str]) -> None:
    assert parse_keywords(input_text) == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    ("input_code", "expected"),
    [
        (None, None),
        ("", None),
        ("en", "en"),
        ("EN", "en"),
        ("en-US", "en"),
        ("pt_BR", "pt"),
        ("fil", None),
        ("zxx", None),
        (" de-DE ", "de"),
        ("e", None),
        ("1a", None),
        ("é-FR", None),
    ],
)
def test_normalise_language(input_code: str | None, expected: str | None) -> None:
    assert normalise_language(input_code) == expected


@pytest.mark.unit
def test_mapping_error_type() -> None:
    assert issubclass(MappingError, ValueError)
    data = copy.deepcopy(VIDEO_FULL)
    data["snippet"].pop("title")
    with pytest.raises(MappingError) as exc_info:
        map_video(data)
    assert "title" in str(exc_info.value)
