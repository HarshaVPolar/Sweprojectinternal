"""Unit tests for scripts/record_fixtures.py."""

import importlib.util
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from ytmcp.config import QuotaCosts, load_settings
from ytmcp.models import Channel, ChannelRef, Video
from ytmcp.providers.transport import ApiHttpError, fixture_key


def _load_script(name: str) -> Any:
    path = Path(__file__).resolve().parent.parent.parent / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


rf = _load_script("record_fixtures")

LITERAL_PLAN = {
    "version": 1,
    "searches": [
        {"q": "linear algebra", "type": "video", "max_results": 50},
        {"q": "linear algebra course lecture", "type": "video", "max_results": 50},
        {"q": "python programming tutorial", "type": "video", "max_results": 50},
    ],
    "channels": {
        "handles": ["@3blue1brown", "@khanacademy", "@mitocw"],
        "usernames": ["khanacademy"],
        "custom_names": ["3blue1brown"],
        "recent_uploads": 15,
    },
    "categories_region": "US",
    "max_units": 600,
}


@pytest.mark.unit
def test_plan_validation() -> None:
    plan = rf.validate_plan(LITERAL_PLAN)
    assert plan.version == 1
    assert len(plan.searches) == 3

    invalid_cases: list[dict[str, Any]] = [
        {**LITERAL_PLAN, "version": 2},
        {k: v for k, v in LITERAL_PLAN.items() if k != "searches"},
        {**LITERAL_PLAN, "searches": []},
        {**LITERAL_PLAN, "searches": [{"q": "q", "type": "video", "max_results": 0}]},
        {**LITERAL_PLAN, "searches": [{"q": "q", "type": "video", "max_results": 101}]},
        {**LITERAL_PLAN, "searches": [{"q": "q", "type": "playlist", "max_results": 50}]},
        {
            **LITERAL_PLAN,
            "channels": {**LITERAL_PLAN["channels"], "handles": ["3blue1brown"]},
        },
        {
            **LITERAL_PLAN,
            "channels": {**LITERAL_PLAN["channels"], "handles": "@3blue1brown"},
        },
        {
            **LITERAL_PLAN,
            "channels": {**LITERAL_PLAN["channels"], "recent_uploads": -1},
        },
        {**LITERAL_PLAN, "categories_region": "us"},
        {**LITERAL_PLAN, "max_units": 0},
        {**LITERAL_PLAN, "extra": "key"},
    ]

    for case in invalid_cases:
        with pytest.raises(ValueError):
            rf.validate_plan(case)


@pytest.mark.unit
def test_committed_plan() -> None:
    plan_path = (
        Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "recording_plan.json"
    )
    loaded = rf.load_plan(plan_path)
    expected = rf.validate_plan(LITERAL_PLAN)
    assert loaded == expected

    costs = load_settings(env={}).quota.costs
    estimated = rf.estimate_units(loaded, costs)
    assert estimated == 416
    assert estimated <= loaded.max_units


@pytest.mark.unit
def test_estimate_formula() -> None:
    """Estimate formula verification.

    Formula breakdown:
    - searches: sum(ceil(max_results / 50)) * search_list
    - video batches: (ceil(sum(max_results) / 50)
      + ceil(recent_uploads * channel_count / 50)) * videos_list
    - channel lookups: (handles + usernames) * channels_list + custom_names * search_list
    - get_channels: ceil(channel_count / 50) * channels_list
    - recent uploads: channel_count * playlist_items_list
    - categories: video_categories_list
    """
    plan = rf.validate_plan(LITERAL_PLAN)
    default_costs = load_settings(env={}).quota.costs
    assert rf.estimate_units(plan, default_costs) == 416

    custom_costs = QuotaCosts(
        search_list=10,
        videos_list=default_costs.videos_list,
        channels_list=default_costs.channels_list,
        subscriptions_list=default_costs.subscriptions_list,
        playlists_list=default_costs.playlists_list,
        playlist_items_list=default_costs.playlist_items_list,
        video_categories_list=default_costs.video_categories_list,
        playlists_insert=default_costs.playlists_insert,
        playlist_items_insert=default_costs.playlist_items_insert,
    )
    assert rf.estimate_units(plan, custom_costs) == 56


@pytest.mark.unit
def test_key_transport() -> None:
    recorded_requests: list[httpx.Request] = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        if "forbidden" in str(request.url):
            return httpx.Response(403, json={"error": "denied"})
        if "server_err" in str(request.url):
            return httpx.Response(500, text="internal server error")
        return httpx.Response(200, json={"items": ["ok"]})

    transport = rf.KeyApiTransport(
        "K", client=httpx.Client(transport=httpx.MockTransport(mock_handler))
    )

    methods = [
        ("videos_list", "videos"),
        ("search_list", "search"),
        ("channels_list", "channels"),
        ("subscriptions_list", "subscriptions"),
        ("playlists_list", "playlists"),
        ("playlist_items_list", "playlistItems"),
        ("video_categories_list", "videoCategories"),
    ]

    for method, endpoint in methods:
        recorded_requests.clear()
        res = transport.call(method, {"part": "snippet", "maxResults": 50})
        assert res == {"items": ["ok"]}
        req = recorded_requests[0]
        assert req.url.path == f"/youtube/v3/{endpoint}"
        assert req.url.params["key"] == "K"
        assert req.url.params["part"] == "snippet"
        assert req.url.params["maxResults"] == "50"

    with pytest.raises(ApiHttpError) as exc_403:
        transport.call("search_list", {"q": "forbidden"})
    assert exc_403.value.status == 403
    assert exc_403.value.body == {"error": "denied"}

    with pytest.raises(ApiHttpError) as exc_500:
        transport.call("search_list", {"q": "server_err"})
    assert exc_500.value.status == 500
    assert exc_500.value.body == {}

    with pytest.raises(ValueError):
        transport.call("unknown_method", {})

    with pytest.raises(NotImplementedError):
        transport.post("playlists_insert", {}, {})


@pytest.mark.unit
def test_raw_recording(tmp_path: Path) -> None:
    class FakeTransport:
        def call(self, method: str, params: Any) -> dict[str, Any]:
            if params.get("q") == "fail":
                raise ApiHttpError(403, {"error": "quota"})
            return {"items": [1, 2, 3]}

        def post(self, method: str, params: Any, body: Any) -> dict[str, Any]:
            raise NotImplementedError

    raw_dir = tmp_path / "raw"
    recorder = rf.RawRecordingTransport(FakeTransport(), raw_dir)

    success_resp = recorder.call("search_list", {"q": "algebra", "key": "SECRET"})
    assert success_resp == {"items": [1, 2, 3]}

    expected_key = fixture_key("search_list", {"q": "algebra"})
    success_file = raw_dir / f"{expected_key}.json"
    assert success_file.exists()

    data = json.loads(success_file.read_text(encoding="utf-8"))
    assert data["method"] == "search_list"
    assert data["args"] == {"q": "algebra"}
    assert "key" not in data["args"]
    assert data["response"] == {"items": [1, 2, 3]}
    assert "status" not in data

    with pytest.raises(ApiHttpError) as exc_info:
        recorder.call("search_list", {"q": "fail", "key": "SECRET"})
    assert exc_info.value.status == 403

    fail_key = fixture_key("search_list", {"q": "fail"})
    fail_file = raw_dir / f"{fail_key}.json"
    assert fail_file.exists()

    fail_data = json.loads(fail_file.read_text(encoding="utf-8"))
    assert fail_data["method"] == "search_list"
    assert fail_data["args"] == {"q": "fail"}
    assert "key" not in fail_data["args"]
    assert fail_data["status"] == 403
    assert fail_data["response"] == {"error": "quota"}


class StubProvider:
    """Stub provider recording call sequence for run_plan tests."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def search(self, q: str, type: str = "video", max_results: int = 50) -> list[str]:
        self.calls.append(("search", {"q": q, "type": type, "max_results": max_results}))
        if "tutorial" in q:
            return ["vid_py1_001", "vid_py2_002"]
        if "lecture" in q:
            return ["vid_la2_002", "vid_la3_003"]
        return ["vid_la1_001", "vid_la2_002"]

    def get_videos(self, ids: Sequence[str]) -> list[Video]:
        self.calls.append(("get_videos", list(ids)))
        dt = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
        return [
            Video(
                id=vid,
                title=f"Title {vid}",
                channel_id="UC1234567890123456789012",
                published_at=dt,
            )
            for vid in ids
        ]

    def resolve_channel(self, ref: ChannelRef) -> str | None:
        self.calls.append(("resolve_channel", ref))
        mapping = {
            "handle:@3blue1brown": "UC3b1b111111111111111111",
            "handle:@khanacademy": "UCkhan111111111111111111",
            "handle:@mitocw": "UCmit1111111111111111111",
            "username:khanacademy": "UCkhan111111111111111111",
            "custom:3blue1brown": "UC3b1b111111111111111111",
        }
        return mapping.get(f"{ref.kind}:{ref.value}")

    def get_channels(self, ids: Sequence[str]) -> list[Channel]:
        self.calls.append(("get_channels", list(ids)))
        dt = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
        return [
            Channel(
                id=cid,
                title=f"Channel {cid}",
                published_at=dt,
            )
            for cid in ids
        ]

    def recent_uploads(self, channel: Channel, n: int = 15) -> list[str]:
        self.calls.append(("recent_uploads", (channel.id, n)))
        if "3b1b" in channel.id:
            return ["vid_la1_001", "vid_new1_01"]
        return ["vid_new2_02"]

    def video_categories(self, region: str = "US") -> dict[str, str]:
        self.calls.append(("video_categories", region))
        return {"1": "Film", "27": "Education"}


def _assert_search_and_videos(calls: list[tuple[str, Any]], summary: Any) -> None:
    assert calls[0][0] == "search"
    assert calls[1][0] == "search"
    assert calls[2][0] == "search"
    assert calls[3][0] == "get_videos"
    assert calls[3][1] == [
        "vid_la1_001",
        "vid_la2_002",
        "vid_la3_003",
        "vid_py1_001",
        "vid_py2_002",
    ]
    assert summary.search_ids == [
        "vid_la1_001",
        "vid_la2_002",
        "vid_la3_003",
        "vid_py1_001",
        "vid_py2_002",
    ]
    assert len(summary.videos) == 5


def _assert_channel_resolution(calls: list[tuple[str, Any]], summary: Any) -> None:
    resolve_calls = calls[4:9]
    assert [c[0] for c in resolve_calls] == ["resolve_channel"] * 5
    kinds = [c[1].kind for c in resolve_calls]
    assert kinds == ["handle", "handle", "handle", "username", "custom"]

    assert calls[9][0] == "get_channels"
    expected_sorted = [
        "UC3b1b111111111111111111",
        "UCkhan111111111111111111",
        "UCmit1111111111111111111",
    ]
    assert calls[9][1] == expected_sorted
    assert len(summary.channels) == 3


def _assert_recent_uploads_and_second_fetch(calls: list[tuple[str, Any]], summary: Any) -> None:
    upload_calls = calls[10:13]
    assert [c[0] for c in upload_calls] == ["recent_uploads"] * 3
    channel_ids_called = [c[1][0] for c in upload_calls]
    assert channel_ids_called == sorted(channel_ids_called)

    assert calls[13][0] == "get_videos"
    assert calls[13][1] == ["vid_new1_01", "vid_new2_02"]
    assert len(summary.upload_videos) == 2

    assert calls[14][0] == "video_categories"
    assert calls[14][1] == "US"


def _assert_run_summary(summary: Any) -> None:
    assert len(summary.categories) == 2
    assert summary.resolved["handle:@3blue1brown"] == "UC3b1b111111111111111111"
    assert len(summary.upload_ids) == 3


@pytest.mark.unit
def test_run_plan_order() -> None:
    stub = StubProvider()
    plan = rf.validate_plan(LITERAL_PLAN)
    summary = rf.run_plan(stub, plan)

    _assert_search_and_videos(stub.calls, summary)
    _assert_channel_resolution(stub.calls, summary)
    _assert_recent_uploads_and_second_fetch(stub.calls, summary)
    _assert_run_summary(summary)


@pytest.mark.unit
def test_main_dry_run(capsys: pytest.CaptureFixture[str]) -> None:
    plan_path = (
        Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "recording_plan.json"
    )

    ret1 = rf.main(["--dry-run", "--plan", str(plan_path)])
    assert ret1 == 0
    out1 = capsys.readouterr().out
    assert "estimated units: 416" in out1

    ret2 = rf.main([])
    assert ret2 == 0
    out2 = capsys.readouterr().out
    assert "estimated units: 416" in out2


@pytest.mark.unit
def test_main_run_guards(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.delenv("YT_API_KEY", raising=False)
    ret1 = rf.main(["--run"])
    assert ret1 == 2
    err1 = capsys.readouterr().err
    assert "YT_API_KEY" in err1

    small_plan = tmp_path / "small_plan.json"
    small_plan_data = {**LITERAL_PLAN, "max_units": 10}
    small_plan.write_text(json.dumps(small_plan_data), encoding="utf-8")

    monkeypatch.setenv("YT_API_KEY", "SUPER_SECRET_KEY_12345")
    ret2 = rf.main(["--run", "--plan", str(small_plan)])
    assert ret2 == 2
    err2 = capsys.readouterr().err
    assert "exceeds" in err2
    assert "SUPER_SECRET_KEY_12345" not in err2
    assert "SUPER_SECRET_KEY_12345" not in capsys.readouterr().out
