"""API-backed YouTubeProvider implementation handling batching, pagination and mapping."""

from collections.abc import Callable, Mapping, Sequence
from typing import Any, TypeVar

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
from ytmcp.providers.mapping import (
    MappingError,
    map_categories,
    map_channels,
    map_playlist_items,
    map_playlists,
    map_search_ids,
    map_subscriptions,
    map_videos,
    next_page_token,
)
from ytmcp.providers.transport import (
    ApiHttpError,
    ApiTransport,
    Params,
    ParamValue,
    translate_api_error,
)

VIDEO_PARTS: str = "snippet,contentDetails,statistics,status"
CHANNEL_PARTS: str = "snippet,contentDetails,statistics,brandingSettings,topicDetails"
PAGE_SIZE: int = 50

T = TypeVar("T")


def _chunk_list(items: Sequence[str], chunk_size: int) -> list[list[str]]:
    """Split a sequence into sublists of at most chunk_size."""
    return [list(items[i : i + chunk_size]) for i in range(0, len(items), chunk_size)]


def _first_channel_id(res: Mapping[str, Any]) -> str | None:
    """Extract channel ID string from the first item of a channels_list response."""
    items = res.get("items")
    if isinstance(items, list) and items:
        first = items[0]
        if isinstance(first, Mapping):
            val = first.get("id")
            if isinstance(val, str):
                return val
    return None


class ApiBackedProvider(YouTubeProvider):
    """YouTubeProvider implementation wrapping an ApiTransport."""

    def __init__(self, transport: ApiTransport) -> None:
        self._transport = transport

    def _call(self, method: str, params: Params) -> dict[str, Any]:
        """Wrap transport.call and translate ApiHttpError to catalogue exceptions."""
        try:
            return self._transport.call(method, params)
        except ApiHttpError as err:
            raise translate_api_error(err.status, err.body) from err

    def _post(
        self,
        method: str,
        params: Params,
        body: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Wrap transport.post and translate ApiHttpError to catalogue exceptions."""
        try:
            return self._transport.post(method, params, body)
        except ApiHttpError as err:
            raise translate_api_error(err.status, err.body) from err

    def _paginate(
        self,
        method: str,
        base_params: Mapping[str, ParamValue],
        mapper: Callable[[Mapping[str, Any]], list[T]],
        cap: int,
    ) -> list[T]:
        """Paginate a list endpoint up to cap items, stopping on exhaustion or repeated token."""
        if cap <= 0:
            return []
        results: list[T] = []
        seen_tokens: set[str] = set()
        page_token: str | None = None

        while len(results) < cap:
            params: dict[str, ParamValue] = dict(base_params)
            if page_token is not None:
                params["pageToken"] = page_token
            res = self._call(method, params)
            items = mapper(res)
            for item in items:
                results.append(item)
                if len(results) >= cap:
                    break
            token = next_page_token(res)
            if not token or token in seen_tokens:
                break
            seen_tokens.add(token)
            page_token = token

        return results

    def get_videos(self, ids: Sequence[str]) -> list[Video]:
        """Fetch video metadata in input order (missing IDs absent; 1 quota unit per 50)."""
        unique_ids = list(dict.fromkeys(ids))
        if not unique_ids:
            return []

        id_to_video: dict[str, Video] = {}
        for chunk in _chunk_list(unique_ids, PAGE_SIZE):
            sorted_id_str = ",".join(sorted(chunk))
            res = self._call(
                "videos_list",
                {"part": VIDEO_PARTS, "id": sorted_id_str},
            )
            for video in map_videos(res):
                id_to_video[video.id] = video

        return [id_to_video[vid] for vid in unique_ids if vid in id_to_video]

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
        if max_results <= 0:
            return []

        collected: list[str] = []
        collected_set: set[str] = set()
        seen_tokens: set[str] = set()
        page_token: str | None = None

        while len(collected) < max_results:
            needed = max_results - len(collected)
            page_size = min(PAGE_SIZE, needed)
            params: dict[str, ParamValue] = {
                "part": "snippet",
                "q": q,
                "type": type,
                "maxResults": page_size,
            }
            if language is not None:
                params["relevanceLanguage"] = language
            if published_after is not None:
                params["publishedAfter"] = published_after
            if page_token is not None:
                params["pageToken"] = page_token

            res = self._call("search_list", params)
            ids = map_search_ids(res, type)
            for item_id in ids:
                if item_id not in collected_set:
                    collected_set.add(item_id)
                    collected.append(item_id)
                    if len(collected) >= max_results:
                        break

            token = next_page_token(res)
            if not token or token in seen_tokens:
                break
            seen_tokens.add(token)
            page_token = token

        return collected[:max_results]

    def get_channels(self, ids: Sequence[str]) -> list[Channel]:
        """Fetch channel metadata in input order (missing IDs absent; 1 quota unit per 50)."""
        unique_ids = list(dict.fromkeys(ids))
        if not unique_ids:
            return []

        id_to_channel: dict[str, Channel] = {}
        for chunk in _chunk_list(unique_ids, PAGE_SIZE):
            sorted_id_str = ",".join(sorted(chunk))
            res = self._call(
                "channels_list",
                {"part": CHANNEL_PARTS, "id": sorted_id_str},
            )
            for channel in map_channels(res):
                id_to_channel[channel.id] = channel

        return [id_to_channel[cid] for cid in unique_ids if cid in id_to_channel]

    def resolve_channel(self, ref: ChannelRef) -> str | None:
        """Resolve a ChannelRef to a canonical channel ID or None (1-100 quota units)."""
        if ref.kind == "id":
            channels = self.get_channels([ref.value])
            return ref.value if channels else None

        if ref.kind == "handle":
            res = self._call("channels_list", {"part": "id", "forHandle": ref.value})
            return _first_channel_id(res)

        if ref.kind == "username":
            res = self._call("channels_list", {"part": "id", "forUsername": ref.value})
            return _first_channel_id(res)

        if ref.kind == "custom":
            res = self._call(
                "search_list",
                {
                    "part": "snippet",
                    "q": ref.value,
                    "type": "channel",
                    "maxResults": 5,
                },
            )
            ids = map_search_ids(res, "channel")
            return ids[0] if ids else None

        return None

    def recent_uploads(self, channel: Channel, n: int = 15) -> list[str]:
        """Fetch newest upload video IDs for a channel (1 quota unit per page of 50)."""
        if not channel.uploads_playlist_id or n <= 0:
            return []

        collected: list[str] = []
        seen_tokens: set[str] = set()
        page_token: str | None = None

        while len(collected) < n:
            needed = n - len(collected)
            page_size = min(PAGE_SIZE, needed)
            params: dict[str, ParamValue] = {
                "part": "snippet,contentDetails",
                "playlistId": channel.uploads_playlist_id,
                "maxResults": page_size,
            }
            if page_token is not None:
                params["pageToken"] = page_token

            res = self._call("playlist_items_list", params)
            items = map_playlist_items(res)
            for item in items:
                collected.append(item.video_id)
                if len(collected) >= n:
                    break

            token = next_page_token(res)
            if not token or token in seen_tokens:
                break
            seen_tokens.add(token)
            page_token = token

        return collected[:n]

    def list_liked(self, cap: int = 200) -> list[Video]:
        """List current user's liked videos up to cap (1 quota unit per page of 50)."""
        return self._paginate(
            "videos_list",
            {"part": VIDEO_PARTS, "myRating": "like", "maxResults": 50},
            map_videos,
            cap,
        )

    def list_subscriptions(self, cap: int = 200) -> list[Subscription]:
        """List current user's subscriptions up to cap (1 quota unit per page of 50)."""
        return self._paginate(
            "subscriptions_list",
            {"part": "snippet", "mine": "true", "maxResults": 50},
            map_subscriptions,
            cap,
        )

    def list_playlists(self, cap: int = 200) -> list[Playlist]:
        """List current user's playlists up to cap (1 quota unit per page of 50)."""
        return self._paginate(
            "playlists_list",
            {"part": "snippet,contentDetails", "mine": "true", "maxResults": 50},
            map_playlists,
            cap,
        )

    def list_playlist_items(self, playlist_id: str, cap: int = 200) -> list[PlaylistItem]:
        """List items in a playlist up to cap (1 quota unit per page of 50)."""
        return self._paginate(
            "playlist_items_list",
            {
                "part": "snippet,contentDetails",
                "playlistId": playlist_id,
                "maxResults": 50,
            },
            map_playlist_items,
            cap,
        )

    def video_categories(self, region: str = "US") -> dict[str, str]:
        """Map category IDs to display names for a region (1 quota unit)."""
        res = self._call(
            "video_categories_list",
            {"part": "snippet", "regionCode": region},
        )
        return map_categories(res)

    def my_channel(self) -> Channel | None:
        """Fetch the authenticated user's channel, or None if none exists (1 quota unit)."""
        res = self._call("channels_list", {"part": CHANNEL_PARTS, "mine": "true"})
        channels = map_channels(res)
        return channels[0] if channels else None

    def create_playlist(
        self,
        title: str,
        description: str = "",
        visibility: Visibility = "private",
    ) -> str:
        """Create a new playlist and return its ID (50 quota units)."""
        params: dict[str, ParamValue] = {"part": "snippet,status"}
        body = {
            "snippet": {"title": title, "description": description},
            "status": {"privacyStatus": visibility},
        }
        res = self._post("playlists_insert", params, body)
        playlist_id = res.get("id")
        if not isinstance(playlist_id, str) or not playlist_id:
            raise MappingError("Missing 'id' in playlists_insert response")
        return playlist_id

    def add_playlist_item(self, playlist_id: str, video_id: str) -> None:
        """Add a video to a playlist (50 quota units)."""
        params: dict[str, ParamValue] = {"part": "snippet"}
        body = {
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {"kind": "youtube#video", "videoId": video_id},
            }
        }
        self._post("playlist_items_insert", params, body)
