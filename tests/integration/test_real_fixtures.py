"""Integration tests proving offline replay of the recording plan against real fixtures."""

import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest

from ytmcp.providers.fixture import FixtureYouTubeProvider
from ytmcp.providers.transport import READ_METHODS, fixture_key


def _load_record_fixtures_module() -> Any:
    path = Path(__file__).resolve().parent.parent.parent / "scripts" / "record_fixtures.py"
    spec = importlib.util.spec_from_file_location("record_fixtures", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["record_fixtures"] = module
    spec.loader.exec_module(module)
    return module


rf = _load_record_fixtures_module()
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PLAN_PATH = REPO_ROOT / "tests" / "fixtures" / "recording_plan.json"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "youtube"


@pytest.fixture(scope="module")
def run_summary() -> Any:
    """Run the recording plan once per module against FixtureYouTubeProvider."""
    plan = rf.load_plan(PLAN_PATH)
    provider = FixtureYouTubeProvider(FIXTURES_DIR)
    return rf.run_plan(provider, plan)


@pytest.mark.integration
def test_replay_completes(run_summary: Any) -> None:
    assert run_summary is not None


@pytest.mark.integration
def test_search_and_videos(run_summary: Any) -> None:
    search_ids = run_summary.search_ids
    assert len(search_ids) >= 100
    assert len(search_ids) == len(set(search_ids))

    videos = run_summary.videos
    assert len(videos) >= 90

    for v in videos:
        assert v.title.strip() != ""
        assert v.channel_id.strip() != ""
        assert v.published_at.tzinfo is not None

    tagged_count = sum(1 for v in videos if len(v.tags) > 0)
    assert tagged_count >= 40

    short_count = sum(1 for v in videos if v.duration_s is not None and v.duration_s < 600)
    assert short_count >= 5

    long_count = sum(1 for v in videos if v.duration_s is not None and v.duration_s >= 1200)
    assert long_count >= 5


@pytest.mark.integration
def test_channels_resolve(run_summary: Any) -> None:
    resolved = run_summary.resolved
    expected_keys = (
        "handle:@3blue1brown",
        "handle:@khanacademy",
        "handle:@mitocw",
        "username:khanacademy",
        "custom:3blue1brown",
    )
    channel_id_pattern = re.compile(r"^UC[A-Za-z0-9_-]{22}$")

    for k in expected_keys:
        val = resolved.get(k)
        assert val is not None, f"Key {k} resolved to None"
        assert channel_id_pattern.match(val), f"Channel ID {val} invalid for {k}"

    assert resolved["handle:@khanacademy"] == resolved["username:khanacademy"]
    assert resolved["handle:@3blue1brown"] == resolved["custom:3blue1brown"]

    distinct_channel_ids = {resolved[k] for k in expected_keys}
    assert len(distinct_channel_ids) >= 3

    channels = run_summary.channels
    assert len(channels) == len(distinct_channel_ids)
    for ch in channels:
        assert ch.id in distinct_channel_ids
        assert ch.title.strip() != ""


@pytest.mark.integration
def test_uploads(run_summary: Any) -> None:
    channels = run_summary.channels
    upload_ids = run_summary.upload_ids

    for ch in channels:
        assert ch.id in upload_ids
        assert len(upload_ids[ch.id]) >= 10

    upload_videos = run_summary.upload_videos
    assert isinstance(upload_videos, list)
    for uv in upload_videos:
        assert uv.title.strip() != ""


@pytest.mark.integration
def test_categories(run_summary: Any) -> None:
    cats = run_summary.categories
    assert "27" in cats
    assert "28" in cats
    for v in cats.values():
        assert isinstance(v, str)
        assert v.strip() != ""


@pytest.mark.integration
def test_file_hygiene() -> None:
    all_json = list(FIXTURES_DIR.glob("*.json"))
    assert len(all_json) >= 16 + 15

    for fpath in all_json:
        assert fpath.stat().st_size <= 400_000, f"{fpath.name} exceeds 400,000 bytes"

        data = json.loads(fpath.read_text(encoding="utf-8"))
        assert "method" in data
        assert "args" in data
        assert "response" in data

        method = data["method"]
        args = data["args"]
        assert method in READ_METHODS

        expected_name = f"{fixture_key(method, args)}.json"
        assert fpath.name == expected_name


def _check_forbidden_keys(obj: Any, fpath_name: str) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            assert k not in ("etag", "thumbnails", "localized"), f"{fpath_name} contains key {k}"
            _check_forbidden_keys(v, fpath_name)
    elif isinstance(obj, list):
        for item in obj:
            _check_forbidden_keys(item, fpath_name)


@pytest.mark.integration
def test_descriptions_truncated() -> None:
    for fpath in FIXTURES_DIR.glob("*.json"):
        data = json.loads(fpath.read_text(encoding="utf-8"))
        _check_forbidden_keys(data, fpath.name)

        if data.get("method") == "videos_list":
            items = data.get("response", {}).get("items", [])
            for item in items:
                desc = item.get("snippet", {}).get("description", "")
                assert len(desc) <= 300, f"Description in {fpath.name} exceeds 300 characters"


@pytest.mark.integration
def test_pagination_tokens_synthetic() -> None:
    """Verify nextPageTokens in real fixtures are synthetic and compatible with pagination."""
    found_tokens = 0
    for fpath in FIXTURES_DIR.glob("*.json"):
        data = json.loads(fpath.read_text(encoding="utf-8"))
        token = data.get("response", {}).get("nextPageToken")
        if token is not None:
            found_tokens += 1
            assert token.startswith("SYNTH_"), f"Token {token} in {fpath.name} is not synthetic"
    assert found_tokens >= 7
