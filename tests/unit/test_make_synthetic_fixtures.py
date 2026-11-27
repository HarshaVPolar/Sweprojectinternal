"""Unit tests for scripts/make_synthetic_fixtures.py."""

import importlib.util
import re
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from ytmcp.domain.duration import parse_iso8601_duration
from ytmcp.providers.mapping import (
    map_channel,
    map_playlist,
    map_playlist_item,
    map_subscription,
    map_video,
)
from ytmcp.providers.transport import fixture_key


def _load_script(name: str) -> Any:
    path = Path(__file__).resolve().parent.parent.parent / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


synth = _load_script("make_synthetic_fixtures")


@pytest.mark.unit
def test_file_count_and_names() -> None:
    fixtures = synth.build_fixtures()
    assert len(fixtures) == 16

    method_counts: dict[str, int] = {}
    for name, content in fixtures.items():
        method = content["method"]
        args = content["args"]
        expected_name = f"{fixture_key(method, args)}.json"
        assert name == expected_name
        method_counts[method] = method_counts.get(method, 0) + 1

    assert method_counts["videos_list"] == 7
    assert method_counts["subscriptions_list"] == 2
    assert method_counts["playlists_list"] == 1
    assert method_counts["playlist_items_list"] == 5
    assert method_counts["channels_list"] == 1


@pytest.mark.unit
def test_deterministic(tmp_path: Path) -> None:
    f1 = synth.build_fixtures()
    f2 = synth.build_fixtures()
    assert f1 == f2

    dir1 = tmp_path / "dir1"
    dir2 = tmp_path / "dir2"

    names1 = synth.write_fixtures(dir1)
    names2 = synth.write_fixtures(dir2)

    assert names1 == names2
    assert len(names1) == 16

    for name in names1:
        bytes1 = (dir1 / name).read_bytes()
        bytes2 = (dir2 / name).read_bytes()
        assert bytes1 == bytes2


@pytest.mark.unit
def test_liked_videos() -> None:
    fixtures = synth.build_fixtures()
    liked_files = [
        content
        for content in fixtures.values()
        if content["method"] == "videos_list" and content["args"].get("myRating") == "like"
    ]
    assert len(liked_files) == 2

    p1 = next(f for f in liked_files if "pageToken" not in f["args"])
    p2 = next(f for f in liked_files if f["args"].get("pageToken") == "SYNTH_LIKED_P2")

    assert p1["response"].get("nextPageToken") == "SYNTH_LIKED_P2"
    assert len(p1["response"]["items"]) == 50
    assert "nextPageToken" not in p2["response"]
    assert len(p2["response"]["items"]) == 14

    all_items = p1["response"]["items"] + p2["response"]["items"]
    assert len(all_items) == 64

    ids = [it["id"] for it in all_items]
    assert len(set(ids)) == 64
    for vid in ids:
        assert vid.startswith("synlike")
        assert len(vid) == 11

    topics_found: list[str] = []
    min_date = synth.ANCHOR - timedelta(days=synth.WINDOW_DAYS)

    for item in all_items:
        video = map_video(item)
        assert 300 <= video.duration_s <= 3599
        dur = parse_iso8601_duration(item["contentDetails"]["duration"])
        assert dur == video.duration_s

        assert min_date <= video.published_at <= synth.ANCHOR

        for tinfo in synth.TOPICS:
            if tinfo["topic"] in video.description:
                topics_found.append(tinfo["topic"])
                break

    for tinfo in synth.TOPICS:
        assert topics_found.count(tinfo["topic"]) == 16


@pytest.mark.unit
def test_subscriptions() -> None:
    fixtures = synth.build_fixtures()
    sub_files = [
        content for content in fixtures.values() if content["method"] == "subscriptions_list"
    ]
    assert len(sub_files) == 2

    p1 = next(f for f in sub_files if "pageToken" not in f["args"])
    p2 = next(f for f in sub_files if f["args"].get("pageToken") == "SYNTH_SUBS_P2")

    assert len(p1["response"]["items"]) == 50
    assert len(p2["response"]["items"]) == 10

    all_subs = p1["response"]["items"] + p2["response"]["items"]
    assert len(all_subs) == 60

    min_date = synth.ANCHOR - timedelta(days=synth.WINDOW_DAYS)
    cids = []
    pattern = re.compile(r"^UC[A-Za-z0-9_-]{22}$")

    for item in all_subs:
        sub = map_subscription(item)
        assert pattern.match(sub.channel_id)
        assert min_date <= sub.subscribed_at <= synth.ANCHOR
        cids.append(sub.channel_id)

    assert len(set(cids)) == 60


@pytest.mark.unit
def test_playlists_and_items() -> None:
    fixtures = synth.build_fixtures()
    pl_content = next(
        content for content in fixtures.values() if content["method"] == "playlists_list"
    )
    playlists = pl_content["response"]["items"]
    assert len(playlists) == 5

    for p in playlists:
        mapped_pl = map_playlist(p)
        assert mapped_pl.item_count == 8

    liked_ids = {
        it["id"]
        for f in fixtures.values()
        if f["method"] == "videos_list" and f["args"].get("myRating") == "like"
        for it in f["response"]["items"]
    }

    item_files = [
        content for content in fixtures.values() if content["method"] == "playlist_items_list"
    ]
    assert len(item_files) == 5

    for ifile in item_files:
        items = ifile["response"]["items"]
        assert len(items) == 8
        positions = []
        for it in items:
            pitem = map_playlist_item(it)
            positions.append(pitem.position)
            assert pitem.video_id in liked_ids
        assert positions == list(range(8))


@pytest.mark.unit
def test_my_channel_and_errors() -> None:
    fixtures = synth.build_fixtures()
    ch_content = next(
        content for content in fixtures.values() if content["method"] == "channels_list"
    )
    channel = map_channel(ch_content["response"]["items"][0])
    assert channel.title == "Synthetic Learner"
    assert channel.uploads_playlist_id is not None
    assert channel.uploads_playlist_id.startswith("UU")

    err_files = [
        content
        for content in fixtures.values()
        if content["method"] == "videos_list" and "status" in content
    ]
    assert len(err_files) == 5

    expected_errors = {
        "errquota001": (403, "quotaExceeded"),
        "errsignup01": (403, "youtubeSignupRequired"),
        "errreauth01": (401, "authError"),
        "errrate0001": (429, "rateLimitExceeded"),
        "errserver01": (500, "backendError"),
    }

    for ef in err_files:
        vid_id = ef["args"]["id"]
        status, reason = expected_errors[vid_id]
        assert ef["status"] == status
        err_item = ef["response"]["error"]["errors"][0]
        assert err_item["reason"] == reason


@pytest.mark.unit
def test_cli(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    ret = synth.main(["--out-dir", str(out_dir)])
    assert ret == 0
    assert len(list(out_dir.glob("*.json"))) == 16

    with pytest.raises(SystemExit):
        synth.main(["--unknown-opt"])
