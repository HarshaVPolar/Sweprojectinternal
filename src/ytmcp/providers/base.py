"""Abstract provider interface for YouTube Data API operations."""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from ytmcp.models import (
    Channel,
    ChannelRef,
    Playlist,
    PlaylistItem,
    Subscription,
    Video,
    Visibility,
)


class YouTubeProvider(ABC):
    """Abstract interface for YouTube access, separating domain from transport."""

    @abstractmethod
    def get_videos(self, ids: Sequence[str]) -> list[Video]:
        """Fetch video metadata in input order (missing IDs absent; 1 quota unit per 50)."""

    @abstractmethod
    def search(
        self,
        q: str,
        *,
        type: str = "video",
        max_results: int = 50,
        language: str | None = None,
        published_after: str | None = None,
    ) -> list[str]:
        """Search YouTube and return matching IDs (100 quota units per page of 50)."""

    @abstractmethod
    def get_channels(self, ids: Sequence[str]) -> list[Channel]:
        """Fetch channel metadata in input order (missing IDs absent; 1 quota unit per 50)."""

    @abstractmethod
    def resolve_channel(self, ref: ChannelRef) -> str | None:
        """Resolve a ChannelRef to a canonical channel ID or None (1-100 quota units)."""

    @abstractmethod
    def recent_uploads(self, channel: Channel, n: int = 15) -> list[str]:
        """Fetch newest upload video IDs for a channel (1 quota unit per page of 50)."""

    @abstractmethod
    def list_liked(self, cap: int = 200) -> list[Video]:
        """List current user's liked videos up to cap (1 quota unit per page of 50)."""

    @abstractmethod
    def list_subscriptions(self, cap: int = 200) -> list[Subscription]:
        """List current user's subscriptions up to cap (1 quota unit per page of 50)."""

    @abstractmethod
    def list_playlists(self, cap: int = 200) -> list[Playlist]:
        """List current user's playlists up to cap (1 quota unit per page of 50)."""

    @abstractmethod
    def list_playlist_items(self, playlist_id: str, cap: int = 200) -> list[PlaylistItem]:
        """List items in a playlist up to cap (1 quota unit per page of 50)."""

    @abstractmethod
    def video_categories(self, region: str = "US") -> dict[str, str]:
        """Map category IDs to display names for a region (1 quota unit)."""

    @abstractmethod
    def my_channel(self) -> Channel | None:
        """Fetch the authenticated user's channel, or None if none exists (1 quota unit)."""

    @abstractmethod
    def create_playlist(
        self,
        title: str,
        description: str = "",
        visibility: Visibility = "private",
    ) -> str:
        """Create a new playlist and return its ID (50 quota units)."""

    @abstractmethod
    def add_playlist_item(self, playlist_id: str, video_id: str) -> None:
        """Add a video to a playlist (50 quota units)."""
