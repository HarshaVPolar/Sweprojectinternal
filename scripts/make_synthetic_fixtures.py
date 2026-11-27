"""Deterministic generator of synthetic YouTube API user-data and error fixtures.

No randomness, no current time. Exposes ANCHOR, WINDOW_DAYS, build_fixtures,
write_fixtures and a CLI entry point.
"""

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from ytmcp.providers.api_provider import CHANNEL_PARTS, VIDEO_PARTS
from ytmcp.providers.transport import fixture_key

ANCHOR = datetime(2026, 6, 30, 12, 0, 0, tzinfo=UTC)
WINDOW_DAYS = 540

TOPICS: tuple[dict[str, Any], ...] = (
    {
        "topic": "linear algebra",
        "title_fmt": "Linear algebra lesson {n}: vectors and matrices",
        "tags": ["linear algebra", "vectors", "matrices", "math"],
        "category_id": "27",
    },
    {
        "topic": "python programming",
        "title_fmt": "Python programming tutorial {n}: functions and classes",
        "tags": ["python", "programming", "tutorial", "code"],
        "category_id": "28",
    },
    {
        "topic": "classical piano",
        "title_fmt": "Classical piano performance {n}: sonata in practice",
        "tags": ["piano", "classical", "music", "sonata"],
        "category_id": "10",
    },
    {
        "topic": "world history",
        "title_fmt": "World history lecture {n}: empires and trade",
        "tags": ["history", "world", "lecture", "empires"],
        "category_id": "27",
    },
)


def _make_channel_id(seed: str) -> str:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:22]
    return f"UC{digest}"


def _build_liked_item(i: int) -> dict[str, Any]:
    n = i + 1
    tinfo = TOPICS[i % 4]
    c = i % 16
    channel_id = _make_channel_id(f"synthetic-channel-{c}")
    channel_title = f"Synthetic Channel {c + 1:02d}"

    pub_dt = ANCHOR - timedelta(days=(i * 8) % WINDOW_DAYS, hours=i % 24)
    pub_str = pub_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    seconds = 300 + (i * 137) % 3300
    m = seconds // 60
    s = seconds % 60
    duration_str = f"PT{m}M{s}S"

    vid_id = f"synlike{n:04d}"
    return {
        "kind": "youtube#video",
        "id": vid_id,
        "snippet": {
            "publishedAt": pub_str,
            "channelId": channel_id,
            "title": tinfo["title_fmt"].format(n=n),
            "description": f"Synthetic description about {tinfo['topic']}.",
            "channelTitle": channel_title,
            "tags": list(tinfo["tags"]),
            "categoryId": tinfo["category_id"],
            "liveBroadcastContent": "none",
            "defaultAudioLanguage": "en",
        },
        "contentDetails": {
            "duration": duration_str,
        },
        "status": {
            "privacyStatus": "public",
            "embeddable": True,
        },
        "statistics": {
            "viewCount": str(1000 + i * 37),
            "likeCount": str(10 + i * 3),
        },
    }


def _build_liked_fixtures() -> dict[str, dict[str, Any]]:
    items = [_build_liked_item(i) for i in range(64)]

    args1 = {"part": VIDEO_PARTS, "myRating": "like", "maxResults": 50}
    resp1 = {"items": items[:50], "nextPageToken": "SYNTH_LIKED_P2"}
    fkey1 = f"{fixture_key('videos_list', args1)}.json"

    args2 = {
        "part": VIDEO_PARTS,
        "myRating": "like",
        "maxResults": 50,
        "pageToken": "SYNTH_LIKED_P2",
    }
    resp2 = {"items": items[50:]}
    fkey2 = f"{fixture_key('videos_list', args2)}.json"

    return {
        fkey1: {"method": "videos_list", "args": args1, "response": resp1},
        fkey2: {"method": "videos_list", "args": args2, "response": resp2},
    }


def _build_subscription_item(j: int) -> dict[str, Any]:
    pub_dt = ANCHOR - timedelta(days=(j * 9) % WINDOW_DAYS)
    pub_str = pub_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    channel_id = _make_channel_id(f"synthetic-subscription-{j}")

    return {
        "kind": "youtube#subscription",
        "snippet": {
            "title": f"Synthetic Subscription {j + 1:02d}",
            "publishedAt": pub_str,
            "resourceId": {
                "kind": "youtube#channel",
                "channelId": channel_id,
            },
        },
    }


def _build_subscription_fixtures() -> dict[str, dict[str, Any]]:
    items = [_build_subscription_item(j) for j in range(60)]

    args1 = {"part": "snippet", "mine": "true", "maxResults": 50}
    resp1 = {"items": items[:50], "nextPageToken": "SYNTH_SUBS_P2"}
    fkey1 = f"{fixture_key('subscriptions_list', args1)}.json"

    args2 = {"part": "snippet", "mine": "true", "maxResults": 50, "pageToken": "SYNTH_SUBS_P2"}
    resp2 = {"items": items[50:]}
    fkey2 = f"{fixture_key('subscriptions_list', args2)}.json"

    return {
        fkey1: {"method": "subscriptions_list", "args": args1, "response": resp1},
        fkey2: {"method": "subscriptions_list", "args": args2, "response": resp2},
    }


def _build_playlist_fixtures() -> dict[str, dict[str, Any]]:
    playlists = []
    for k in range(5):
        pub_dt = ANCHOR - timedelta(days=k * 100)
        pub_str = pub_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        pid = f"PLsynthetic{k + 1:02d}"
        playlists.append(
            {
                "kind": "youtube#playlist",
                "id": pid,
                "snippet": {
                    "title": f"Synthetic playlist {k + 1}",
                    "publishedAt": pub_str,
                },
                "contentDetails": {
                    "itemCount": 8,
                },
            }
        )

    args = {"part": "snippet,contentDetails", "mine": "true", "maxResults": 50}
    resp = {"items": playlists}
    fkey = f"{fixture_key('playlists_list', args)}.json"
    return {fkey: {"method": "playlists_list", "args": args, "response": resp}}


def _build_playlist_items_fixtures() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for k in range(5):
        pid = f"PLsynthetic{k + 1:02d}"
        base_pub = ANCHOR - timedelta(days=k * 100)
        items = []
        for p in range(8):
            liked_idx = (k * 8 + p) % 64
            vid_id = f"synlike{liked_idx + 1:04d}"
            item_pub = base_pub + timedelta(days=p)
            item_pub_str = item_pub.strftime("%Y-%m-%dT%H:%M:%SZ")
            items.append(
                {
                    "kind": "youtube#playlistItem",
                    "snippet": {
                        "playlistId": pid,
                        "position": p,
                        "publishedAt": item_pub_str,
                        "resourceId": {
                            "kind": "youtube#video",
                            "videoId": vid_id,
                        },
                    },
                    "contentDetails": {
                        "videoId": vid_id,
                    },
                }
            )

        args = {"part": "snippet,contentDetails", "playlistId": pid, "maxResults": 50}
        resp = {"items": items}
        fkey = f"{fixture_key('playlist_items_list', args)}.json"
        result[fkey] = {"method": "playlist_items_list", "args": args, "response": resp}

    return result


def _build_my_channel_fixture() -> dict[str, dict[str, Any]]:
    channel_id = _make_channel_id("synthetic-me")
    uploads_id = f"UU{channel_id[2:]}"
    pub_dt = ANCHOR - timedelta(days=800)
    pub_str = pub_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    item = {
        "kind": "youtube#channel",
        "id": channel_id,
        "snippet": {
            "title": "Synthetic Learner",
            "description": "Synthetic account used for offline tests.",
            "publishedAt": pub_str,
        },
        "statistics": {
            "subscriberCount": "5",
            "hiddenSubscriberCount": False,
            "videoCount": "0",
        },
        "contentDetails": {
            "relatedPlaylists": {
                "uploads": uploads_id,
            },
        },
    }

    args = {"part": CHANNEL_PARTS, "mine": "true"}
    resp = {"items": [item]}
    fkey = f"{fixture_key('channels_list', args)}.json"
    return {fkey: {"method": "channels_list", "args": args, "response": resp}}


def _build_error_fixtures() -> dict[str, dict[str, Any]]:
    error_specs = [
        (
            "errquota001",
            403,
            "quotaExceeded",
            "The request cannot be completed because you have exceeded your quota.",
        ),
        (
            "errsignup01",
            403,
            "youtubeSignupRequired",
            "The user has not completed registration on YouTube.",
        ),
        ("errreauth01", 401, "authError", "Invalid Credentials"),
        ("errrate0001", 429, "rateLimitExceeded", "Too Many Requests"),
        ("errserver01", 500, "backendError", "Backend Error"),
    ]

    result: dict[str, dict[str, Any]] = {}
    for vid_id, status, reason, message in error_specs:
        args = {"part": VIDEO_PARTS, "id": vid_id}
        resp = {
            "error": {
                "code": status,
                "message": message,
                "errors": [
                    {
                        "message": message,
                        "domain": "youtube.quota",
                        "reason": reason,
                    }
                ],
            }
        }
        fkey = f"{fixture_key('videos_list', args)}.json"
        result[fkey] = {
            "method": "videos_list",
            "args": args,
            "status": status,
            "response": resp,
        }

    return result


def build_fixtures() -> dict[str, dict[str, Any]]:
    """Build all 16 deterministic synthetic fixture definitions."""
    fixtures: dict[str, dict[str, Any]] = {}
    fixtures.update(_build_liked_fixtures())
    fixtures.update(_build_subscription_fixtures())
    fixtures.update(_build_playlist_fixtures())
    fixtures.update(_build_playlist_items_fixtures())
    fixtures.update(_build_my_channel_fixture())
    fixtures.update(_build_error_fixtures())
    return fixtures


def write_fixtures(out_dir: Path | str) -> list[str]:
    """Write all generated fixtures to disk and return sorted filenames."""
    path = Path(out_dir)
    path.mkdir(parents=True, exist_ok=True)

    fixtures = build_fixtures()
    sorted_names = sorted(fixtures.keys())
    for name in sorted_names:
        content = fixtures[name]
        serialized = json.dumps(content, sort_keys=True, indent=1, ensure_ascii=True) + "\n"
        (path / name).write_text(serialized, encoding="utf-8")

    return sorted_names


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for writing synthetic fixtures."""
    parser = argparse.ArgumentParser(description="Generate synthetic YouTube API fixtures.")
    parser.add_argument(
        "--out-dir",
        default="tests/fixtures/youtube",
        help="Target directory for generated fixtures.",
    )
    args = parser.parse_args(argv)

    written = write_fixtures(args.out_dir)
    sys.stdout.write(f"Wrote {len(written)} synthetic fixture files to {args.out_dir}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
