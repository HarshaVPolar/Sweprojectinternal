"""Mapping functions turning raw YouTube Data API v3 JSON into domain models."""

import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any, Literal, TypeVar

from ytmcp.domain.duration import parse_iso8601_duration
from ytmcp.models import (
    Channel,
    LiveStatus,
    Playlist,
    PlaylistItem,
    Privacy,
    Subscription,
    Video,
)

T = TypeVar("T")


class MappingError(ValueError):
    """Raised when an API response is missing required fields or has invalid formats."""


def _get_mapping(val: Any) -> Mapping[str, Any]:
    """Return val as a Mapping if valid, otherwise empty dict."""
    return val if isinstance(val, Mapping) else {}


def _require_str(
    mapping: Mapping[str, Any],
    key: str,
    path: str,
    item_id: str | None = None,
) -> str:
    """Read a required string field from mapping; raise MappingError if absent or not str."""
    val = mapping.get(key)
    if not isinstance(val, str):
        suffix = f" for item '{item_id}'" if item_id else ""
        raise MappingError(f"Missing required field '{path}'{suffix}")
    return val


def _require_mapping(
    mapping: Mapping[str, Any],
    key: str,
    path: str,
    item_id: str | None = None,
) -> Mapping[str, Any]:
    """Read a required mapping from mapping; raise MappingError if absent or not mapping."""
    val = mapping.get(key)
    if not isinstance(val, Mapping):
        suffix = f" for item '{item_id}'" if item_id else ""
        raise MappingError(f"Missing required field '{path}'{suffix}")
    return val


def _parse_timestamp(val: Any, path: str, item_id: str | None = None) -> datetime:
    """Parse ISO timestamp replacing Z with +00:00, treating naive as UTC."""
    if not isinstance(val, str) or not val.strip():
        suffix = f" for item '{item_id}'" if item_id else ""
        raise MappingError(f"Missing required timestamp '{path}'{suffix}")
    raw = val.strip()
    if raw.endswith("Z") or raw.endswith("z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except (ValueError, TypeError) as err:
        suffix = f" for item '{item_id}'" if item_id else ""
        raise MappingError(f"Invalid ISO timestamp '{path}': {val!r}{suffix}") from err
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _optional_int(
    mapping: Mapping[str, Any],
    key: str,
    path: str,
    item_id: str | None = None,
) -> int | None:
    """Read an optional integer string from mapping; raise MappingError if not numeric."""
    val = mapping.get(key)
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError) as err:
        suffix = f" for item '{item_id}'" if item_id else ""
        raise MappingError(f"Invalid integer in '{path}': {val!r}{suffix}") from err


def normalise_language(code: str | None) -> str | None:
    """Normalise language code to two lowercase ASCII letters, or None."""
    if code is None:
        return None
    s = code.strip()
    if not s:
        return None
    s = s.lower().replace("_", "-")
    part = s.split("-")[0]
    if len(part) == 2 and part.isascii() and part.isalpha():
        return part
    return None


def parse_keywords(text: str | None) -> list[str]:
    """Parse channel keywords handling double-quoted phrases and whitespace."""
    if text is None:
        return []
    s = text.strip()
    if not s:
        return []
    if s.count('"') % 2 != 0:
        cleaned = s.replace('"', "")
        return [tok for tok in cleaned.split() if tok]
    pattern = re.compile(r'"([^"]*)"|(\S+)')
    results: list[str] = []
    for match in pattern.finditer(s):
        token = match.group(1) if match.group(1) is not None else match.group(2)
        if token:
            results.append(token)
    return results


def map_video(item: Mapping[str, Any]) -> Video:
    """Map raw video resource JSON to a Video model."""
    video_id = _require_str(item, "id", "id")
    snippet = _require_mapping(item, "snippet", "snippet", item_id=video_id)
    title = _require_str(snippet, "title", "snippet.title", item_id=video_id)
    channel_id = _require_str(snippet, "channelId", "snippet.channelId", item_id=video_id)
    published_at = _parse_timestamp(
        snippet.get("publishedAt"), "snippet.publishedAt", item_id=video_id
    )

    desc = snippet.get("description")
    description = desc if isinstance(desc, str) else ""

    c_title = snippet.get("channelTitle")
    channel_title = c_title if isinstance(c_title, str) else ""

    tags_raw = snippet.get("tags")
    tags = [t for t in tags_raw if isinstance(t, str)] if isinstance(tags_raw, list) else []

    cat_id_raw = snippet.get("categoryId")
    category_id = cat_id_raw if isinstance(cat_id_raw, str) and cat_id_raw else None

    language = normalise_language(snippet.get("defaultAudioLanguage"))
    if language is None:
        language = normalise_language(snippet.get("defaultLanguage"))

    live_val = snippet.get("liveBroadcastContent")
    live_status: LiveStatus = live_val if live_val in ("live", "upcoming") else "none"

    status = _get_mapping(item.get("status"))
    privacy_val = status.get("privacyStatus")
    privacy: Privacy = privacy_val if privacy_val in ("public", "unlisted", "private") else "public"

    emb_val = status.get("embeddable")
    embeddable = emb_val if isinstance(emb_val, bool) else None

    content_details = _get_mapping(item.get("contentDetails"))
    dur_raw = content_details.get("duration")
    if dur_raw is None:
        duration_s = None
    elif not isinstance(dur_raw, str):
        raise MappingError(f"Invalid duration format for item '{video_id}'")
    else:
        try:
            duration_s = parse_iso8601_duration(dur_raw)
        except ValueError as err:
            raise MappingError(
                f"Invalid ISO 8601 duration '{dur_raw}' for item '{video_id}'"
            ) from err

    statistics = _get_mapping(item.get("statistics"))
    view_count = _optional_int(statistics, "viewCount", "statistics.viewCount", item_id=video_id)
    like_count = _optional_int(statistics, "likeCount", "statistics.likeCount", item_id=video_id)

    return Video(
        id=video_id,
        title=title,
        description=description,
        tags=tags,
        category_id=category_id,
        duration_s=duration_s,
        channel_id=channel_id,
        channel_title=channel_title,
        language=language,
        published_at=published_at,
        privacy=privacy,
        live_status=live_status,
        view_count=view_count,
        like_count=like_count,
        embeddable=embeddable,
    )


def map_channel(item: Mapping[str, Any]) -> Channel:
    """Map raw channel resource JSON to a Channel model."""
    channel_id = _require_str(item, "id", "id")
    snippet = _require_mapping(item, "snippet", "snippet", item_id=channel_id)
    title = _require_str(snippet, "title", "snippet.title", item_id=channel_id)
    published_at = _parse_timestamp(
        snippet.get("publishedAt"), "snippet.publishedAt", item_id=channel_id
    )

    desc = snippet.get("description")
    description = desc if isinstance(desc, str) else ""

    branding = _get_mapping(item.get("brandingSettings"))
    keywords_raw = _get_mapping(branding.get("channel")).get("keywords")
    keywords = parse_keywords(keywords_raw if isinstance(keywords_raw, str) else None)

    topics = _get_mapping(item.get("topicDetails"))
    topic_ids_raw = topics.get("topicIds")
    topic_ids = (
        [t for t in topic_ids_raw if isinstance(t, str)] if isinstance(topic_ids_raw, list) else []
    )

    content_details = _get_mapping(item.get("contentDetails"))
    rel_playlists = _get_mapping(content_details.get("relatedPlaylists"))
    uploads_id = rel_playlists.get("uploads")
    uploads_playlist_id = uploads_id if isinstance(uploads_id, str) and uploads_id else None

    statistics = _get_mapping(item.get("statistics"))
    if statistics.get("hiddenSubscriberCount") is True:
        subscriber_count = None
    else:
        subscriber_count = _optional_int(
            statistics, "subscriberCount", "statistics.subscriberCount", item_id=channel_id
        )
    video_count = _optional_int(
        statistics, "videoCount", "statistics.videoCount", item_id=channel_id
    )

    return Channel(
        id=channel_id,
        title=title,
        description=description,
        keywords=keywords,
        topic_ids=topic_ids,
        subscriber_count=subscriber_count,
        video_count=video_count,
        uploads_playlist_id=uploads_playlist_id,
        published_at=published_at,
    )


def map_subscription(item: Mapping[str, Any]) -> Subscription:
    """Map raw subscription resource JSON to a Subscription model."""
    snippet = _require_mapping(item, "snippet", "snippet")
    resource_id = _require_mapping(snippet, "resourceId", "snippet.resourceId")
    channel_id = _require_str(resource_id, "channelId", "snippet.resourceId.channelId")
    channel_title = _require_str(snippet, "title", "snippet.title")
    subscribed_at = _parse_timestamp(
        snippet.get("publishedAt"), "snippet.publishedAt", item_id=channel_id
    )

    return Subscription(
        channel_id=channel_id,
        channel_title=channel_title,
        subscribed_at=subscribed_at,
    )


def map_playlist(item: Mapping[str, Any]) -> Playlist:
    """Map raw playlist resource JSON to a Playlist model."""
    playlist_id = _require_str(item, "id", "id")
    snippet = _require_mapping(item, "snippet", "snippet", item_id=playlist_id)
    title = _require_str(snippet, "title", "snippet.title", item_id=playlist_id)
    published_at = _parse_timestamp(
        snippet.get("publishedAt"), "snippet.publishedAt", item_id=playlist_id
    )

    content_details = _get_mapping(item.get("contentDetails"))
    item_count_raw = content_details.get("itemCount")
    if item_count_raw is not None:
        try:
            item_count = int(item_count_raw)
        except (ValueError, TypeError) as err:
            raise MappingError(
                f"Invalid itemCount for playlist '{playlist_id}': {item_count_raw!r}"
            ) from err
    else:
        item_count = 0

    return Playlist(
        id=playlist_id,
        title=title,
        item_count=item_count,
        published_at=published_at,
    )


def map_playlist_item(item: Mapping[str, Any]) -> PlaylistItem:
    """Map raw playlistItem resource JSON to a PlaylistItem model."""
    snippet = _require_mapping(item, "snippet", "snippet")
    playlist_id = _require_str(snippet, "playlistId", "snippet.playlistId")

    pos_raw = snippet.get("position")
    if pos_raw is None:
        raise MappingError("Missing required field 'snippet.position'")
    try:
        position = int(pos_raw)
    except (ValueError, TypeError) as err:
        raise MappingError("Invalid integer in 'snippet.position'") from err

    added_at = _parse_timestamp(snippet.get("publishedAt"), "snippet.publishedAt")

    resource_id = _get_mapping(snippet.get("resourceId"))
    video_id = resource_id.get("videoId")
    if not isinstance(video_id, str) or not video_id:
        content_details = _get_mapping(item.get("contentDetails"))
        video_id = content_details.get("videoId")
    if not isinstance(video_id, str) or not video_id:
        raise MappingError("Missing required videoId in resourceId or contentDetails")

    return PlaylistItem(
        playlist_id=playlist_id,
        video_id=video_id,
        added_at=added_at,
        position=position,
    )


def map_categories(response: Mapping[str, Any]) -> dict[str, str]:
    """Map categories response to dictionary of ID to category title."""
    items = response.get("items")
    if not isinstance(items, list):
        return {}
    result: dict[str, str] = {}
    for item in items:
        if isinstance(item, Mapping):
            cat_id = item.get("id")
            snippet = _get_mapping(item.get("snippet"))
            title = snippet.get("title")
            if isinstance(cat_id, str) and isinstance(title, str):
                result[cat_id] = title
    return result


def map_search_ids(
    response: Mapping[str, Any],
    kind: Literal["video", "channel"] | str,
) -> list[str]:
    """Extract search result IDs for given kind, preserving order without duplicates."""
    items = response.get("items")
    if not isinstance(items, list):
        return []
    key = "videoId" if kind == "video" else ("channelId" if kind == "channel" else None)
    if key is None:
        return []
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if isinstance(item, Mapping):
            id_obj = item.get("id")
            if isinstance(id_obj, Mapping):
                val = id_obj.get(key)
                if isinstance(val, str) and val and val not in seen:
                    seen.add(val)
                    result.append(val)
    return result


def next_page_token(response: Mapping[str, Any]) -> str | None:
    """Return nextPageToken if non-empty string, else None."""
    token = response.get("nextPageToken")
    if isinstance(token, str) and token:
        return token
    return None


def _map_items(response: Mapping[str, Any], mapper: Callable[[Mapping[str, Any]], T]) -> list[T]:
    """Helper to map a list of items using a singular mapper function."""
    items = response.get("items")
    if not isinstance(items, list):
        return []
    return [mapper(item) for item in items]


def map_videos(response: Mapping[str, Any]) -> list[Video]:
    """Map response items to list of Video models."""
    return _map_items(response, map_video)


def map_channels(response: Mapping[str, Any]) -> list[Channel]:
    """Map response items to list of Channel models."""
    return _map_items(response, map_channel)


def map_subscriptions(response: Mapping[str, Any]) -> list[Subscription]:
    """Map response items to list of Subscription models."""
    return _map_items(response, map_subscription)


def map_playlists(response: Mapping[str, Any]) -> list[Playlist]:
    """Map response items to list of Playlist models."""
    return _map_items(response, map_playlist)


def map_playlist_items(response: Mapping[str, Any]) -> list[PlaylistItem]:
    """Map response items to list of PlaylistItem models."""
    return _map_items(response, map_playlist_item)
