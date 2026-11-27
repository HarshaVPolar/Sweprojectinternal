import inspect
from collections.abc import Sequence

import pytest

from ytmcp.models import (
    Channel,
    ChannelRef,
    Playlist,
    PlaylistItem,
    Subscription,
    Video,
    Visibility,
)
from ytmcp.providers.base import YouTubeProvider


class DummyProvider(YouTubeProvider):
    """Dummy provider implementing all abstract methods for testing."""

    def get_videos(self, ids: Sequence[str]) -> list[Video]:
        return []

    def search(
        self,
        q: str,
        *,
        type: str = "video",
        max_results: int = 50,
        language: str | None = None,
        published_after: str | None = None,
    ) -> list[str]:
        return []

    def get_channels(self, ids: Sequence[str]) -> list[Channel]:
        return []

    def resolve_channel(self, ref: ChannelRef) -> str | None:
        return None

    def recent_uploads(self, channel: Channel, n: int = 15) -> list[str]:
        return []

    def list_liked(self, cap: int = 200) -> list[Video]:
        return []

    def list_subscriptions(self, cap: int = 200) -> list[Subscription]:
        return []

    def list_playlists(self, cap: int = 200) -> list[Playlist]:
        return []

    def list_playlist_items(self, playlist_id: str, cap: int = 200) -> list[PlaylistItem]:
        return []

    def video_categories(self, region: str = "US") -> dict[str, str]:
        return {}

    def my_channel(self) -> Channel | None:
        return None

    def create_playlist(
        self,
        title: str,
        description: str = "",
        visibility: Visibility = "private",
    ) -> str:
        return "PL123"

    def add_playlist_item(self, playlist_id: str, video_id: str) -> None:
        pass


@pytest.mark.unit
def test_abstract_provider_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        YouTubeProvider()  # type: ignore[abstract]


@pytest.mark.unit
def test_incomplete_subclass_cannot_be_instantiated() -> None:
    class IncompleteProvider(YouTubeProvider):
        def get_videos(self, ids: Sequence[str]) -> list[Video]:
            return []

    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        IncompleteProvider()  # type: ignore[abstract]


@pytest.mark.unit
def test_concrete_provider_can_be_instantiated() -> None:
    provider = DummyProvider()
    assert isinstance(provider, YouTubeProvider)
    assert provider.get_videos(["v1"]) == []
    assert provider.search("python") == []
    assert provider.get_channels(["c1"]) == []
    valid_channel_id = "UC" + "a" * 22
    assert provider.resolve_channel(ChannelRef(kind="id", value=valid_channel_id)) is None
    channel = Channel(
        id=valid_channel_id,
        title="Channel Title",
        published_at="2026-01-01T00:00:00+00:00",
    )
    assert provider.recent_uploads(channel) == []
    assert provider.list_liked() == []
    assert provider.list_subscriptions() == []
    assert provider.list_playlists() == []
    assert provider.list_playlist_items("PL123") == []
    assert provider.video_categories() == {}
    assert provider.my_channel() is None
    assert provider.create_playlist("Title") == "PL123"
    assert provider.add_playlist_item("PL123", "v1") is None


@pytest.mark.unit
def test_abstract_methods_exact_set() -> None:
    expected_methods = {
        "get_videos",
        "search",
        "get_channels",
        "resolve_channel",
        "recent_uploads",
        "list_liked",
        "list_subscriptions",
        "list_playlists",
        "list_playlist_items",
        "video_categories",
        "my_channel",
        "create_playlist",
        "add_playlist_item",
    }
    assert YouTubeProvider.__abstractmethods__ == expected_methods


@pytest.mark.unit
def test_method_signatures_and_defaults() -> None:
    sig_search = inspect.signature(YouTubeProvider.search)
    assert sig_search.parameters["type"].default == "video"
    assert sig_search.parameters["max_results"].default == 50
    assert sig_search.parameters["language"].default is None
    assert sig_search.parameters["published_after"].default is None

    sig_recent = inspect.signature(YouTubeProvider.recent_uploads)
    assert sig_recent.parameters["n"].default == 15

    sig_liked = inspect.signature(YouTubeProvider.list_liked)
    assert sig_liked.parameters["cap"].default == 200

    sig_subs = inspect.signature(YouTubeProvider.list_subscriptions)
    assert sig_subs.parameters["cap"].default == 200

    sig_pls = inspect.signature(YouTubeProvider.list_playlists)
    assert sig_pls.parameters["cap"].default == 200

    sig_items = inspect.signature(YouTubeProvider.list_playlist_items)
    assert sig_items.parameters["cap"].default == 200

    sig_cats = inspect.signature(YouTubeProvider.video_categories)
    assert sig_cats.parameters["region"].default == "US"

    sig_create = inspect.signature(YouTubeProvider.create_playlist)
    assert sig_create.parameters["description"].default == ""
    assert sig_create.parameters["visibility"].default == "private"


@pytest.mark.unit
def test_abstract_methods_have_docstrings() -> None:
    for method_name in YouTubeProvider.__abstractmethods__:
        method = getattr(YouTubeProvider, method_name)
        doc = inspect.getdoc(method)
        assert doc is not None and len(doc.strip()) > 0, f"Missing docstring on {method_name}"
