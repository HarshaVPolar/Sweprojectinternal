from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from ytmcp.errors import ChannelRequired, NotFoundOrPrivate, QuotaExhausted, UpstreamError
from ytmcp.models import Video
from ytmcp.providers.api_provider import CHANNEL_PARTS, VIDEO_PARTS, ApiBackedProvider
from ytmcp.providers.base import YouTubeProvider
from ytmcp.providers.fixture import (
    FixtureMissing,
    FixtureTransport,
    FixtureYouTubeProvider,
)
from ytmcp.providers.transport import ApiHttpError, fixture_key


@pytest.mark.integration
def test_transport_reads_file(tmp_fixture_dir: Path, write_fixture: Any) -> None:
    params = {"part": "snippet", "id": "abc"}
    response_data = {"items": [{"id": "abc"}]}
    write_fixture("videos_list", params, response_data)

    transport = FixtureTransport(tmp_fixture_dir)
    # Key order in params does not matter
    reversed_params = {"id": "abc", "part": "snippet"}
    result = transport.call("videos_list", reversed_params)
    assert result == response_data


@pytest.mark.integration
def test_transport_missing(tmp_fixture_dir: Path) -> None:
    transport = FixtureTransport(tmp_fixture_dir)
    params = {"part": "snippet", "id": "nonexistent"}
    expected_filename = fixture_key("videos_list", params) + ".json"

    with pytest.raises(FixtureMissing) as exc:
        transport.call("videos_list", params)
    assert expected_filename in str(exc.value)

    # Missing directory also raises FixtureMissing
    bad_transport = FixtureTransport(tmp_fixture_dir / "does_not_exist")
    with pytest.raises(FixtureMissing):
        bad_transport.call("videos_list", params)


@pytest.mark.integration
def test_transport_mismatch(tmp_fixture_dir: Path, write_fixture: Any) -> None:
    params = {"part": "snippet", "id": "test"}
    # File with right name but wrong method inside
    file_path = write_fixture("videos_list", params, {"items": []})
    file_path.write_text(
        '{"method": "wrong_method", "args": {"part": "snippet", "id": "test"}, "response": {}}',
        encoding="utf-8",
    )
    transport = FixtureTransport(tmp_fixture_dir)
    with pytest.raises(FixtureMissing):
        transport.call("videos_list", params)

    # File with right name but wrong args inside
    file_path.write_text(
        '{"method": "videos_list", "args": {"part": "other"}, "response": {}}',
        encoding="utf-8",
    )
    with pytest.raises(FixtureMissing):
        transport.call("videos_list", params)


@pytest.mark.integration
def test_transport_error_status(tmp_fixture_dir: Path, write_fixture: Any) -> None:
    params = {"part": "snippet", "id": "err"}
    err_body = {"error": {"message": "bad"}}
    write_fixture("videos_list", params, err_body, status=403)

    transport = FixtureTransport(tmp_fixture_dir)
    with pytest.raises(ApiHttpError) as exc403:
        transport.call("videos_list", params)
    assert exc403.value.status == 403
    assert exc403.value.body == err_body

    p500 = {"part": "snippet", "id": "err500"}
    write_fixture("videos_list", p500, {}, status=500)
    with pytest.raises(ApiHttpError) as exc500:
        transport.call("videos_list", p500)
    assert exc500.value.status == 500


@pytest.mark.integration
def test_transport_post(tmp_fixture_dir: Path) -> None:
    transport = FixtureTransport(tmp_fixture_dir)
    with pytest.raises(NotImplementedError):
        transport.post("playlists_insert", {}, {})


@pytest.mark.integration
def test_provider_reads_fixture(
    tmp_fixture_dir: Path, write_fixture: Any, make_video_item: Any
) -> None:
    v_item = make_video_item(video_id="vid00000001")
    write_fixture(
        "videos_list",
        {"part": VIDEO_PARTS, "id": "vid00000001"},
        {"items": [v_item]},
    )
    provider = FixtureYouTubeProvider(tmp_fixture_dir)
    videos = provider.get_videos(["vid00000001"])
    assert len(videos) == 1
    assert isinstance(videos[0], Video)
    assert videos[0].id == "vid00000001"


@pytest.mark.integration
def test_provider_translates_error_fixture(tmp_fixture_dir: Path, write_fixture: Any) -> None:
    err_body = {"error": {"errors": [{"reason": "quotaExceeded"}]}}
    write_fixture(
        "videos_list",
        {"part": VIDEO_PARTS, "id": "vid00000001"},
        err_body,
        status=403,
    )
    provider = FixtureYouTubeProvider(tmp_fixture_dir)
    with pytest.raises(QuotaExhausted):
        provider.get_videos(["vid00000001"])


@pytest.mark.integration
def test_write_simulation(tmp_fixture_dir: Path) -> None:
    provider = FixtureYouTubeProvider(tmp_fixture_dir)

    pl1 = provider.create_playlist("Title 1", "Desc 1", "private")
    pl2 = provider.create_playlist("Title 2", "Desc 2", "public")
    assert pl1 == "PLfixture0001"
    assert pl2 == "PLfixture0002"

    assert provider.created_playlists == [
        {
            "id": "PLfixture0001",
            "title": "Title 1",
            "description": "Desc 1",
            "visibility": "private",
        },
        {
            "id": "PLfixture0002",
            "title": "Title 2",
            "description": "Desc 2",
            "visibility": "public",
        },
    ]

    provider.add_playlist_item(pl1, "vid00000001")
    provider.add_playlist_item(pl1, "vid00000001")
    assert provider.added_items == [(pl1, "vid00000001"), (pl1, "vid00000001")]
    assert provider.add_attempts == 2


@pytest.mark.integration
def test_list_playlist_items_in_memory(tmp_fixture_dir: Path, write_fixture: Any) -> None:
    provider = FixtureYouTubeProvider(tmp_fixture_dir)
    pl = provider.create_playlist("List")
    provider.add_playlist_item(pl, "vid00000001")
    provider.add_playlist_item(pl, "vid00000002")
    provider.add_playlist_item(pl, "vid00000003")

    items = provider.list_playlist_items(pl)
    assert len(items) == 3
    for i, it in enumerate(items):
        assert it.position == i
        assert it.playlist_id == pl
        assert it.video_id == f"vid0000000{i + 1}"
        assert it.added_at == datetime(2026, 1, 1, 0, 0, i, tzinfo=UTC)

    # cap 2
    items_cap2 = provider.list_playlist_items(pl, cap=2)
    assert len(items_cap2) == 2

    # Other playlist reads fixture
    write_fixture(
        "playlist_items_list",
        {"part": "snippet,contentDetails", "playlistId": "PLother", "maxResults": 50},
        {
            "items": [
                {
                    "snippet": {
                        "playlistId": "PLother",
                        "position": 0,
                        "publishedAt": "2024-01-01T00:00:00Z",
                        "resourceId": {"videoId": "vidfixture1"},
                    }
                }
            ]
        },
    )
    other_items = provider.list_playlist_items("PLother")
    assert len(other_items) == 1
    assert other_items[0].video_id == "vidfixture1"


@pytest.mark.integration
def test_failure_injection(tmp_fixture_dir: Path) -> None:
    provider = FixtureYouTubeProvider(tmp_fixture_dir, fail_add_item_at=3)
    pl = provider.create_playlist("Fail Playlist")

    # Unknown playlist raises NotFoundOrPrivate and does NOT count as attempt
    with pytest.raises(NotFoundOrPrivate):
        provider.add_playlist_item("PLunknown", "v1")
    assert provider.add_attempts == 0

    provider.add_playlist_item(pl, "v1")
    assert provider.add_attempts == 1

    provider.add_playlist_item(pl, "v2")
    assert provider.add_attempts == 2

    # 3rd attempt raises UpstreamError and is not recorded
    with pytest.raises(UpstreamError):
        provider.add_playlist_item(pl, "v3")
    assert provider.add_attempts == 3
    assert len(provider.added_items) == 2

    # Custom fail_error
    p2 = FixtureYouTubeProvider(
        tmp_fixture_dir,
        fail_add_item_at=1,
        fail_error=QuotaExhausted,
    )
    pl2 = p2.create_playlist("Custom Error")
    with pytest.raises(QuotaExhausted):
        p2.add_playlist_item(pl2, "v1")


@pytest.mark.integration
def test_no_channel(tmp_fixture_dir: Path, write_fixture: Any, make_channel_item: Any) -> None:
    p_no_chan = FixtureYouTubeProvider(tmp_fixture_dir, channel_present=False)
    assert p_no_chan.my_channel() is None
    with pytest.raises(ChannelRequired):
        p_no_chan.create_playlist("Title")

    p_has_chan = FixtureYouTubeProvider(tmp_fixture_dir, channel_present=True)
    c_item = make_channel_item("UC" + "a" * 22)
    write_fixture(
        "channels_list",
        {"part": CHANNEL_PARTS, "mine": "true"},
        {"items": [c_item]},
    )
    channel = p_has_chan.my_channel()
    assert channel is not None
    assert channel.id == "UC" + "a" * 22


@pytest.mark.integration
def test_is_a_provider(tmp_fixture_dir: Path) -> None:
    provider = FixtureYouTubeProvider(tmp_fixture_dir)
    assert isinstance(provider, ApiBackedProvider)
    assert isinstance(provider, YouTubeProvider)
