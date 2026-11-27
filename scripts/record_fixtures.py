"""Record public YouTube API fixtures.

Reads the API key ONLY from the YT_API_KEY environment variable.
Never reads the API key from a file.
Never prints or logs the API key.
Records public data only.
The default execution mode is --dry-run.
"""

import argparse
import json
import math
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from ytmcp.config import QuotaCosts, load_settings
from ytmcp.models import Channel, ChannelRef, Video
from ytmcp.providers.api_provider import ApiBackedProvider
from ytmcp.providers.transport import ApiHttpError, ApiTransport, Params, fixture_key

ENDPOINT_MAP: dict[str, str] = {
    "videos_list": "videos",
    "search_list": "search",
    "channels_list": "channels",
    "subscriptions_list": "subscriptions",
    "playlists_list": "playlists",
    "playlist_items_list": "playlistItems",
    "video_categories_list": "videoCategories",
}


@dataclass(frozen=True)
class SearchSpec:
    """Specification for a search query in the recording plan."""

    q: str
    type: str
    max_results: int


@dataclass(frozen=True)
class ChannelSpec:
    """Specification for channels to fetch in the recording plan."""

    handles: list[str]
    usernames: list[str]
    custom_names: list[str]
    recent_uploads: int


@dataclass(frozen=True)
class Plan:
    """Recording plan configuration."""

    version: int
    searches: list[SearchSpec]
    channels: ChannelSpec
    categories_region: str
    max_units: int


@dataclass(frozen=True)
class RunSummary:
    """Summary of operations performed during plan execution."""

    search_ids: list[str]
    videos: list[Video]
    resolved: dict[str, str | None]
    channels: list[Channel]
    upload_ids: dict[str, list[str]]
    upload_videos: list[Video]
    categories: dict[str, str]


def _validate_search(item: Any) -> SearchSpec:
    if not isinstance(item, dict):
        raise ValueError("Search item must be a dictionary")
    allowed = {"q", "type", "max_results"}
    if set(item.keys()) != allowed:
        raise ValueError(f"Invalid search keys: {set(item.keys())}")
    q = item["q"]
    stype = item["type"]
    max_results = item["max_results"]
    if not isinstance(q, str) or not q.strip():
        raise ValueError("Search query q must be a non-empty string")
    if stype not in ("video", "channel"):
        raise ValueError(f"Invalid search type '{stype}'")
    if not isinstance(max_results, int) or max_results < 1 or max_results > 100:
        raise ValueError(f"max_results must be between 1 and 100, got {max_results}")
    return SearchSpec(q=q, type=stype, max_results=max_results)


def _validate_channels(item: Any) -> ChannelSpec:
    if not isinstance(item, dict):
        raise ValueError("Channels spec must be a dictionary")
    allowed = {"handles", "usernames", "custom_names", "recent_uploads"}
    if set(item.keys()) != allowed:
        raise ValueError(f"Invalid channels keys: {set(item.keys())}")
    handles = item["handles"]
    usernames = item["usernames"]
    custom_names = item["custom_names"]
    recent_uploads = item["recent_uploads"]

    if not isinstance(handles, list) or not all(
        isinstance(h, str) and h.startswith("@") and len(h) > 1 for h in handles
    ):
        raise ValueError("handles must be a list of non-empty strings starting with '@'")
    if not isinstance(usernames, list) or not all(
        isinstance(u, str) and len(u.strip()) > 0 for u in usernames
    ):
        raise ValueError("usernames must be a list of non-empty strings")
    if not isinstance(custom_names, list) or not all(
        isinstance(c, str) and len(c.strip()) > 0 for c in custom_names
    ):
        raise ValueError("custom_names must be a list of non-empty strings")
    if not isinstance(recent_uploads, int) or recent_uploads < 0:
        raise ValueError("recent_uploads must be an integer >= 0")

    return ChannelSpec(
        handles=list(handles),
        usernames=list(usernames),
        custom_names=list(custom_names),
        recent_uploads=recent_uploads,
    )


def validate_plan(data: Any) -> Plan:
    """Validate a raw dictionary representing a recording plan."""
    if not isinstance(data, dict):
        raise ValueError("Plan must be a dictionary")
    allowed = {"version", "searches", "channels", "categories_region", "max_units"}
    if set(data.keys()) != allowed:
        raise ValueError(f"Invalid top-level plan keys: {set(data.keys())}")

    version = data["version"]
    if version != 1:
        raise ValueError(f"Unsupported plan version: {version}")

    raw_searches = data["searches"]
    if not isinstance(raw_searches, list) or len(raw_searches) == 0:
        raise ValueError("searches must be a non-empty list")
    searches = [_validate_search(s) for s in raw_searches]

    channels = _validate_channels(data["channels"])

    region = data["categories_region"]
    if (
        not isinstance(region, str)
        or len(region) != 2
        or not region.isupper()
        or not region.isalpha()
    ):
        raise ValueError(f"categories_region must be exactly two upper-case letters: {region}")

    max_units = data["max_units"]
    if not isinstance(max_units, int) or max_units < 1:
        raise ValueError(f"max_units must be an integer >= 1: {max_units}")

    return Plan(
        version=version,
        searches=searches,
        channels=channels,
        categories_region=region,
        max_units=max_units,
    )


def load_plan(path: Path | str) -> Plan:
    """Load and validate a recording plan from a JSON file."""
    path = Path(path)
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return validate_plan(data)


def estimate_units(plan: Plan, costs: QuotaCosts) -> int:
    """Estimate total YouTube API quota units consumed by a recording plan."""
    channel_count = (
        len(plan.channels.handles) + len(plan.channels.usernames) + len(plan.channels.custom_names)
    )
    searches_cost = sum(math.ceil(s.max_results / 50) for s in plan.searches) * costs.search_list

    sum_search_max = sum(s.max_results for s in plan.searches)
    video_batches = math.ceil(sum_search_max / 50) + math.ceil(
        plan.channels.recent_uploads * channel_count / 50
    )
    video_cost = video_batches * costs.videos_list

    channel_lookups = (
        len(plan.channels.handles) + len(plan.channels.usernames)
    ) * costs.channels_list + len(plan.channels.custom_names) * costs.search_list

    get_channels_cost = math.ceil(channel_count / 50) * costs.channels_list
    recent_uploads_cost = channel_count * costs.playlist_items_list
    categories_cost = costs.video_categories_list

    return (
        searches_cost
        + video_cost
        + channel_lookups
        + get_channels_cost
        + recent_uploads_cost
        + categories_cost
    )


class KeyApiTransport(ApiTransport):
    """Transport that uses an API key query parameter to access read endpoints."""

    def __init__(self, api_key: str, client: httpx.Client | None = None) -> None:
        self.api_key = api_key
        self.client = client if client is not None else httpx.Client(timeout=15.0)

    def call(self, method: str, params: Params) -> dict[str, Any]:
        """Perform a read request to the YouTube Data API."""
        if method not in ENDPOINT_MAP:
            raise ValueError(f"Unknown read method: {method}")
        endpoint = ENDPOINT_MAP[method]
        url = f"https://www.googleapis.com/youtube/v3/{endpoint}"

        query: dict[str, str] = {"key": self.api_key}
        for k, v in params.items():
            query[k] = str(v)

        resp = self.client.get(url, params=query)
        if resp.status_code >= 400:
            try:
                body = resp.json()
            except Exception:
                body = {}
            raise ApiHttpError(resp.status_code, body)

        return resp.json()

    def post(self, method: str, params: Params, body: Mapping[str, Any]) -> dict[str, Any]:
        """Post request is not implemented for API-key read transport."""
        raise NotImplementedError("KeyApiTransport does not support write operations")


class RawRecordingTransport(ApiTransport):
    """Transport wrapper that saves raw responses to disk."""

    def __init__(self, inner: ApiTransport, raw_dir: Path) -> None:
        self.inner = inner
        self.raw_dir = Path(raw_dir)

    def call(self, method: str, params: Params) -> dict[str, Any]:
        """Call inner transport and write the raw request/response to disk."""
        filtered_args = {k: v for k, v in params.items() if k != "key"}
        fkey = fixture_key(method, filtered_args)
        target = self.raw_dir / f"{fkey}.json"
        self.raw_dir.mkdir(parents=True, exist_ok=True)

        try:
            resp = self.inner.call(method, params)
            payload = {
                "method": method,
                "args": filtered_args,
                "response": resp,
            }
            target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            return resp
        except ApiHttpError as exc:
            payload = {
                "method": method,
                "args": filtered_args,
                "status": exc.status,
                "response": exc.body,
            }
            target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            raise

    def post(self, method: str, params: Params, body: Mapping[str, Any]) -> dict[str, Any]:
        """Post request is not implemented for raw recording."""
        raise NotImplementedError("RawRecordingTransport does not support post")


def _run_channel_resolutions(provider: Any, channels_spec: ChannelSpec) -> dict[str, str | None]:
    resolved: dict[str, str | None] = {}
    for h in channels_spec.handles:
        ref = ChannelRef(kind="handle", value=h)
        resolved[f"handle:{h}"] = provider.resolve_channel(ref)
    for u in channels_spec.usernames:
        ref = ChannelRef(kind="username", value=u)
        resolved[f"username:{u}"] = provider.resolve_channel(ref)
    for c in channels_spec.custom_names:
        ref = ChannelRef(kind="custom", value=c)
        resolved[f"custom:{c}"] = provider.resolve_channel(ref)
    return resolved


def _fetch_channel_uploads(
    provider: Any, channels: Sequence[Channel], n: int, seen_ids: set[str]
) -> tuple[dict[str, list[str]], list[Video]]:
    upload_ids: dict[str, list[str]] = {}
    sorted_channels = sorted(channels, key=lambda ch: ch.id)
    for channel in sorted_channels:
        uids = provider.recent_uploads(channel, n=n)
        upload_ids[channel.id] = uids

    new_video_ids: list[str] = []
    for uids in upload_ids.values():
        for vid in uids:
            if vid not in seen_ids:
                seen_ids.add(vid)
                new_video_ids.append(vid)

    upload_videos = provider.get_videos(new_video_ids) if new_video_ids else []
    return upload_ids, upload_videos


def run_plan(provider: Any, plan: Plan) -> RunSummary:
    """Execute all plan steps against a provider in contract-specified order."""
    search_ids: list[str] = []
    seen_ids: set[str] = set()

    for s in plan.searches:
        vids = provider.search(q=s.q, type=s.type, max_results=s.max_results)
        for vid in vids:
            if vid not in seen_ids:
                seen_ids.add(vid)
                search_ids.append(vid)

    videos = provider.get_videos(search_ids)

    resolved = _run_channel_resolutions(provider, plan.channels)
    resolved_ids = sorted({cid for cid in resolved.values() if cid is not None})
    channels = provider.get_channels(resolved_ids)

    upload_ids, upload_videos = _fetch_channel_uploads(
        provider, channels, plan.channels.recent_uploads, seen_ids
    )

    categories = provider.video_categories(region=plan.categories_region)

    return RunSummary(
        search_ids=search_ids,
        videos=videos,
        resolved=resolved,
        channels=channels,
        upload_ids=upload_ids,
        upload_videos=upload_videos,
        categories=categories,
    )


def _execute_run(plan: Plan, raw_dir: Path) -> int:
    api_key = os.environ.get("YT_API_KEY")
    if not api_key:
        sys.stderr.write("Error: YT_API_KEY environment variable is required for --run.\n")
        return 2

    costs = load_settings(env={}).quota.costs
    estimated = estimate_units(plan, costs)
    if estimated > plan.max_units:
        sys.stderr.write(
            f"Error: estimated units ({estimated}) exceeds maximum allowed ({plan.max_units}).\n"
        )
        return 2

    key_transport = KeyApiTransport(api_key)
    recording_transport = RawRecordingTransport(key_transport, raw_dir)
    provider = ApiBackedProvider(recording_transport)

    summary = run_plan(provider, plan)
    sys.stdout.write(
        f"Recorded {len(summary.videos)} search videos, "
        f"{len(summary.channels)} channels, "
        f"{len(summary.upload_videos)} upload videos.\n"
    )
    sys.stdout.write("Done. Next command:\npython scripts/sanitise_fixture.py\n")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for recording fixtures."""
    parser = argparse.ArgumentParser(description="Record YouTube API fixtures.")
    parser.add_argument("--dry-run", action="store_true", help="Print quota estimate only.")
    parser.add_argument("--run", action="store_true", help="Record real fixtures.")
    parser.add_argument(
        "--plan",
        default="tests/fixtures/recording_plan.json",
        help="Path to recording plan JSON file.",
    )
    parser.add_argument(
        "--raw-dir",
        default="tests/fixtures/_raw",
        help="Directory to write raw fixture files.",
    )

    args = parser.parse_args(argv)
    plan = load_plan(args.plan)

    if args.run:
        return _execute_run(plan, Path(args.raw_dir))

    costs = load_settings(env={}).quota.costs
    estimated = estimate_units(plan, costs)
    total_channels = (
        len(plan.channels.handles) + len(plan.channels.usernames) + len(plan.channels.custom_names)
    )
    sys.stdout.write(f"Plan: {len(plan.searches)} searches, {total_channels} channels\n")
    sys.stdout.write(f"estimated units: {estimated}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
