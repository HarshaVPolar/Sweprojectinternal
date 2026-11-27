"""Integration tests verifying synthetic fixtures against FixtureYouTubeProvider."""

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

from ytmcp.errors import (
    ChannelRequired,
    QuotaExhausted,
    RateLimited,
    ReauthRequired,
    UpstreamError,
)
from ytmcp.providers.fixture import FixtureYouTubeProvider


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
FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "youtube"


@pytest.mark.integration
def test_committed_files_match_generator() -> None:
    fixtures = synth.build_fixtures()
    for name, content in fixtures.items():
        file_path = FIXTURE_DIR / name
        assert file_path.exists(), f"Committed fixture {name} missing"
        with file_path.open(encoding="utf-8") as f:
            import json

            loaded = json.load(f)
        assert loaded == content, f"Fixture {name} drifted from generator"


@pytest.mark.integration
def test_liked() -> None:
    provider = FixtureYouTubeProvider(FIXTURE_DIR)
    liked_all = provider.list_liked(cap=200)
    assert len(liked_all) == 64
    assert len({v.id for v in liked_all}) == 64

    liked_10 = provider.list_liked(cap=10)
    assert len(liked_10) == 10
    assert liked_10 == liked_all[:10]


@pytest.mark.integration
def test_subscriptions_and_playlists() -> None:
    provider = FixtureYouTubeProvider(FIXTURE_DIR)
    subs = provider.list_subscriptions(cap=200)
    assert len(subs) == 60

    playlists = provider.list_playlists(cap=200)
    assert len(playlists) == 5
    for pl in playlists:
        assert pl.item_count == 8
        items = provider.list_playlist_items(pl.id, cap=200)
        assert len(items) == 8


@pytest.mark.integration
def test_my_channel() -> None:
    provider = FixtureYouTubeProvider(FIXTURE_DIR)
    ch = provider.my_channel()
    assert ch is not None
    assert ch.title == "Synthetic Learner"


@pytest.mark.integration
@pytest.mark.parametrize(
    "vid_id,expected_error",
    [
        ("errquota001", QuotaExhausted),
        ("errsignup01", ChannelRequired),
        ("errreauth01", ReauthRequired),
        ("errrate0001", RateLimited),
        ("errserver01", UpstreamError),
    ],
)
def test_error_replay(vid_id: str, expected_error: type[Exception]) -> None:
    provider = FixtureYouTubeProvider(FIXTURE_DIR)
    with pytest.raises(expected_error):
        provider.get_videos([vid_id])
