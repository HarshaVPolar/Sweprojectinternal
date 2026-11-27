"""Shared pytest fixtures for the YouTube Video Intelligence MCP test suite."""

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest

from ytmcp.providers.transport import fixture_key


@pytest.fixture
def tmp_fixture_dir(tmp_path: Path) -> Path:
    """Create and return a fresh directory named youtube inside pytest tmp_path."""
    d = tmp_path / "youtube"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture
def write_fixture(
    tmp_fixture_dir: Path,
) -> Callable[..., Path]:
    """Return a callable that writes a JSON fixture file and returns its path."""

    def _writer(
        method: str,
        params: Mapping[str, Any],
        response: Any,
        status: int | None = None,
    ) -> Path:
        key = fixture_key(method, params)
        file_path = tmp_fixture_dir / f"{key}.json"
        payload: dict[str, Any] = {
            "method": method,
            "args": dict(params),
            "response": response,
        }
        if status is not None:
            payload["status"] = status
        file_path.write_text(json.dumps(payload), encoding="utf-8")
        return file_path

    return _writer


@pytest.fixture
def make_video_item() -> Callable[..., dict[str, Any]]:
    """Return a factory for raw API video items."""

    def _factory(
        video_id: str = "vid00000001",
        title: str = "Linear algebra basics",
    ) -> dict[str, Any]:
        return {
            "id": video_id,
            "snippet": {
                "publishedAt": "2024-05-01T10:00:00Z",
                "channelId": "UC" + "a" * 22,
                "title": title,
                "description": "Vectors and matrices.",
                "channelTitle": "Math Channel",
                "tags": ["algebra", "math"],
                "categoryId": "27",
                "liveBroadcastContent": "none",
                "defaultAudioLanguage": "en",
            },
            "contentDetails": {
                "duration": "PT10M",
            },
            "status": {
                "privacyStatus": "public",
                "embeddable": True,
            },
            "statistics": {
                "viewCount": "100",
                "likeCount": "10",
            },
        }

    return _factory


@pytest.fixture
def make_channel_item() -> Callable[[str], dict[str, Any]]:
    """Return a factory for raw API channel items."""

    def _factory(channel_id: str) -> dict[str, Any]:
        return {
            "id": channel_id,
            "snippet": {
                "title": f"Channel {channel_id}",
                "description": "Channel description",
                "publishedAt": "2020-01-01T00:00:00Z",
            },
            "statistics": {
                "subscriberCount": "100",
                "hiddenSubscriberCount": False,
                "videoCount": "5",
            },
            "contentDetails": {
                "relatedPlaylists": {
                    "uploads": "UU" + channel_id[2:],
                },
            },
        }

    return _factory
