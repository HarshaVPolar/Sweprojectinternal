"""Fixture transport and in-memory simulated FixtureYouTubeProvider."""

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from ytmcp.errors import ChannelRequired, NotFoundOrPrivate, UpstreamError
from ytmcp.models import Channel, PlaylistItem, Visibility
from ytmcp.providers.api_provider import ApiBackedProvider
from ytmcp.providers.transport import (
    ApiHttpError,
    FixtureMissing,
    Params,
    fixture_key,
)

__all__ = [
    "FixtureMissing",
    "FixtureTransport",
    "FixtureYouTubeProvider",
]


class FixtureTransport:
    """Transport that reads pre-recorded fixture JSON files from disk."""

    def __init__(self, fixture_dir: str | Path) -> None:
        self.fixture_dir = Path(fixture_dir)

    def call(self, method: str, params: Params) -> dict[str, Any]:
        """Read matching fixture JSON file or raise FixtureMissing / ApiHttpError."""
        key = fixture_key(method, params)
        expected_filename = f"{key}.json"
        file_path = self.fixture_dir / expected_filename

        if not file_path.is_file():
            raise FixtureMissing(f"Fixture file missing: {expected_filename}")

        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as err:
            raise FixtureMissing(f"Error reading fixture {expected_filename}: {err}") from err

        if not isinstance(data, dict):
            raise FixtureMissing(f"Fixture {expected_filename} is not a JSON object")

        if data.get("method") != method:
            raise FixtureMissing(
                f"Fixture {expected_filename} method mismatch: "
                f"expected {method}, got {data.get('method')}"
            )

        if data.get("args") != dict(params):
            raise FixtureMissing(f"Fixture {expected_filename} args mismatch")

        status = data.get("status", 200)
        if status >= 400:
            raise ApiHttpError(status, data.get("response"))

        response_payload = data.get("response")
        return response_payload if isinstance(response_payload, dict) else {}

    def post(
        self,
        method: str,
        params: Params,
        body: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Post is not supported by FixtureTransport."""
        raise NotImplementedError("FixtureTransport does not support post")


class FixtureYouTubeProvider(ApiBackedProvider):
    """Fixture-backed provider with in-memory write simulation and failure injection."""

    def __init__(
        self,
        fixture_dir: str | Path,
        *,
        channel_present: bool = True,
        fail_add_item_at: int | None = None,
        fail_error: type[Exception] = UpstreamError,
    ) -> None:
        transport = FixtureTransport(fixture_dir)
        super().__init__(transport)
        self.fixture_dir = Path(fixture_dir)
        self.channel_present = channel_present
        self.fail_add_item_at = fail_add_item_at
        self.fail_error = fail_error

        self.created_playlists: list[dict[str, Any]] = []
        self.added_items: list[tuple[str, str]] = []
        self.add_attempts: int = 0
        self._playlist_counter: int = 0
        self._created_playlist_ids: set[str] = set()

    def create_playlist(
        self,
        title: str,
        description: str = "",
        visibility: Visibility = "private",
    ) -> str:
        """Create playlist in memory; raises ChannelRequired when channel_present is false."""
        if not self.channel_present:
            raise ChannelRequired()
        self._playlist_counter += 1
        pl_id = f"PLfixture{self._playlist_counter:04d}"
        self.created_playlists.append(
            {
                "id": pl_id,
                "title": title,
                "description": description,
                "visibility": visibility,
            }
        )
        self._created_playlist_ids.add(pl_id)
        return pl_id

    def add_playlist_item(self, playlist_id: str, video_id: str) -> None:
        """Add item in memory with failure injection and unknown playlist check."""
        if playlist_id not in self._created_playlist_ids:
            raise NotFoundOrPrivate(f"Playlist {playlist_id} not found in memory")
        self.add_attempts += 1
        if self.fail_add_item_at is not None and self.add_attempts == self.fail_add_item_at:
            raise self.fail_error()
        self.added_items.append((playlist_id, video_id))

    def list_playlist_items(self, playlist_id: str, cap: int = 200) -> list[PlaylistItem]:
        """List items from memory if created in memory, otherwise read fixture."""
        if playlist_id in self._created_playlist_ids:
            items_for_pl = [vid for (pid, vid) in self.added_items if pid == playlist_id]
            results: list[PlaylistItem] = []
            base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
            for pos, vid in enumerate(items_for_pl):
                if len(results) >= cap:
                    break
                added_at = base_time + timedelta(seconds=pos)
                results.append(
                    PlaylistItem(
                        playlist_id=playlist_id,
                        video_id=vid,
                        added_at=added_at,
                        position=pos,
                    )
                )
            return results
        return super().list_playlist_items(playlist_id, cap=cap)

    def my_channel(self) -> Channel | None:
        """Return None when channel_present is false, otherwise read fixture."""
        if not self.channel_present:
            return None
        return super().my_channel()
