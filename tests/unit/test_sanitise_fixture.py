"""Unit tests for scripts/sanitise_fixture.py."""

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from ytmcp.providers.transport import fixture_key


def _load_script(name: str) -> Any:
    path = Path(__file__).resolve().parent.parent.parent / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sf = _load_script("sanitise_fixture")


@pytest.mark.unit
def test_redact_text() -> None:
    assert (
        sf.redact_text("Contact a.b+c@example.com or x@y.org for info.")
        == "Contact redacted@example.invalid or redacted@example.invalid for info."
    )
    assert sf.redact_text("ya29.A0ARrdaM-abc_DEF") == "REDACTED"
    assert sf.redact_text("1//0gAbCdEf-ghIJ") == "REDACTED"
    assert sf.redact_text("AIza" + "a" * 35) == "REDACTED"
    assert sf.redact_text("Bearer abcdefghijklmnopqrstuvwxyz0123") == "REDACTED"
    assert sf.redact_text("@3blue1brown is great") == "@3blue1brown is great"

    mixed = "Token ya29.A0ARrdaM-abc_DEF with 1//0gAbCdEf-ghIJ and " + ("AIza" + "a" * 35) + " key."
    assert sf.redact_text(mixed) == "Token REDACTED with REDACTED and REDACTED key."


@pytest.mark.unit
def test_descriptions() -> None:
    long_desc = "d" * 400
    fixture = {
        "method": "videos_list",
        "args": {},
        "response": {
            "items": [
                {
                    "snippet": {
                        "description": long_desc,
                        "title": "t" * 400,
                    }
                }
            ]
        },
    }
    sanitised = sf.sanitise_fixture(fixture)
    item = sanitised["response"]["items"][0]["snippet"]
    assert len(item["description"]) == 300
    assert len(item["title"]) == 400

    short_desc = "short description"
    san_short = sf.sanitise_fixture(
        {"method": "v", "args": {}, "response": {"description": short_desc}}
    )
    assert san_short["response"]["description"] == short_desc

    email_desc = "email: user@test.com and " + "x" * 400
    san_email = sf.sanitise_fixture(
        {"method": "v", "args": {}, "response": {"description": email_desc}}
    )
    desc = san_email["response"]["description"]
    assert "redacted@example.invalid" in desc
    assert len(desc) == 300


@pytest.mark.unit
def test_dropped_keys() -> None:
    fixture = {
        "method": "videos_list",
        "args": {},
        "response": {
            "etag": "tag123",
            "items": [
                {
                    "etag": "item_tag",
                    "thumbnails": {"default": {"url": "http://img"}},
                    "localized": {"title": "loc"},
                    "title": "keep this",
                }
            ],
        },
    }
    sanitised = sf.sanitise_fixture(fixture)
    resp = sanitised["response"]
    assert "etag" not in resp
    item = resp["items"][0]
    assert "etag" not in item
    assert "thumbnails" not in item
    assert "localized" not in item
    assert item["title"] == "keep this"


@pytest.mark.unit
def test_sanitise_fixture() -> None:
    fixture = {
        "method": "search_list",
        "args": {"q": "algebra"},
        "status": 200,
        "response": {"user": "contact me at me@example.com"},
    }
    res = sf.sanitise_fixture(fixture)
    assert res["method"] == "search_list"
    assert res["args"] == {"q": "algebra"}
    assert res["status"] == 200
    assert res["response"]["user"] == "contact me at redacted@example.invalid"

    sensitive_args_cases = [
        {"key": "SECRET"},
        {"access_token": "TOK"},
        {"nested": {"refresh_token": "TOK"}},
        {"list": [{"client_secret": "SEC"}]},
    ]
    for bad_args in sensitive_args_cases:
        with pytest.raises(ValueError, match="Forbidden sensitive key"):
            sf.sanitise_fixture({"method": "m", "args": bad_args, "response": {}})


def _create_valid_raw_fixture(raw_dir: Path, method: str, args: dict[str, Any]) -> Path:
    fkey = fixture_key(method, args)
    path = raw_dir / f"{fkey}.json"
    data = {
        "method": method,
        "args": args,
        "response": {
            "items": [
                {
                    "etag": "drop_me",
                    "title": f"Title for {method}",
                    "description": "desc with contact@example.com",
                }
            ]
        },
    }
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


@pytest.mark.unit
def test_main_files(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    out_dir = tmp_path / "youtube"
    raw_dir.mkdir(parents=True)

    f1 = _create_valid_raw_fixture(raw_dir, "search_list", {"q": "math"})
    f2 = _create_valid_raw_fixture(raw_dir, "videos_list", {"id": "abc12345678"})

    ret = sf.main(["--raw-dir", str(raw_dir), "--out-dir", str(out_dir)])
    assert ret == 0

    out_f1 = out_dir / f1.name
    out_f2 = out_dir / f2.name
    assert out_f1.exists()
    assert out_f2.exists()

    bytes1 = out_f1.read_bytes()
    assert bytes1.endswith(b"\n")
    data1 = json.loads(bytes1.decode("utf-8"))
    assert data1["method"] == "search_list"
    assert "etag" not in data1["response"]["items"][0]

    out_dir_2 = tmp_path / "youtube_re"
    ret_again = sf.main(["--raw-dir", str(out_dir), "--out-dir", str(out_dir_2)])
    assert ret_again == 0
    assert (out_dir_2 / f1.name).read_bytes() == bytes1


@pytest.mark.parametrize(
    "error_kind,expected_msg",
    [
        ("no_files", "No raw files found"),
        ("invalid_json", "is not valid JSON"),
        ("mismatched_key", "does not match expected fixture key"),
        ("oversized", "exceeds 400000 bytes"),
    ],
)
@pytest.mark.unit
def test_main_errors(
    error_kind: str,
    expected_msg: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    raw_dir = tmp_path / f"raw_{error_kind}"
    out_dir = tmp_path / f"out_{error_kind}"
    raw_dir.mkdir(parents=True)

    if error_kind == "no_files":
        pass
    elif error_kind == "invalid_json":
        bad_json = raw_dir / "test.json"
        bad_json.write_text("{not valid json", encoding="utf-8")
    elif error_kind == "mismatched_key":
        bad_name = raw_dir / "wrong_name.json"
        data = {"method": "search_list", "args": {"q": "calc"}, "response": {}}
        bad_name.write_text(json.dumps(data), encoding="utf-8")
    elif error_kind == "oversized":
        args: dict[str, Any] = {"q": "big"}
        fkey = fixture_key("search_list", args)
        big_file = raw_dir / f"{fkey}.json"
        big_data = {
            "method": "search_list",
            "args": args,
            "response": {"big_data": "x" * 401_000},
        }
        big_file.write_text(json.dumps(big_data), encoding="utf-8")

    ret = sf.main(["--raw-dir", str(raw_dir), "--out-dir", str(out_dir)])
    assert ret == 2
    err = capsys.readouterr().err
    assert expected_msg in err

    if error_kind == "oversized":
        assert not (out_dir / f"{fkey}.json").exists()
