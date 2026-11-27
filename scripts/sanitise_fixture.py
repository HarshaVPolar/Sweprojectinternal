"""Sanitise raw YouTube API fixture files."""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from ytmcp.providers.transport import fixture_key

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
YA29_PATTERN = re.compile(r"ya29\.[a-zA-Z0-9_.-]+")
REFRESH_PATTERN = re.compile(r"1//[a-zA-Z0-9_.-]+")
AIZA_PATTERN = re.compile(r"AIza[a-zA-Z0-9_-]{35}")
BEARER_PATTERN = re.compile(r"Bearer\s+[a-zA-Z0-9_.-]{20,}")

DROP_KEYS = {"etag", "thumbnails", "localized"}
FORBIDDEN_ARG_KEYS = {"key", "access_token", "refresh_token", "client_secret"}
MAX_OUTPUT_BYTES = 400_000


def redact_text(text: str) -> str:
    """Redact sensitive patterns from text."""
    text = BEARER_PATTERN.sub("REDACTED", text)
    text = YA29_PATTERN.sub("REDACTED", text)
    text = REFRESH_PATTERN.sub("REDACTED", text)
    text = AIZA_PATTERN.sub("REDACTED", text)
    text = EMAIL_PATTERN.sub("redacted@example.invalid", text)
    return text


def _check_sensitive_keys(args: Any) -> None:
    if isinstance(args, dict):
        for k, v in args.items():
            if k in FORBIDDEN_ARG_KEYS:
                raise ValueError(f"Forbidden sensitive key '{k}' found in args")
            _check_sensitive_keys(v)
    elif isinstance(args, list):
        for item in args:
            _check_sensitive_keys(item)


def _sanitise_value(key: str | None, value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for k, v in value.items():
            if k in DROP_KEYS:
                continue
            result[k] = _sanitise_value(k, v)
        return result
    if isinstance(value, list):
        return [_sanitise_value(key, item) for item in value]
    if isinstance(value, str):
        redacted = redact_text(value)
        if key == "description" and len(redacted) > 300:
            return redacted[:300]
        return redacted
    return value


def sanitise_fixture(data: dict[str, Any]) -> dict[str, Any]:
    """Sanitise a single fixture dictionary."""
    if "args" in data:
        _check_sensitive_keys(data["args"])

    result: dict[str, Any] = {
        "method": data["method"],
        "args": data["args"],
    }
    if "status" in data:
        result["status"] = data["status"]

    result["response"] = _sanitise_value(None, data.get("response"))
    return result


def _process_fixture_file(file_path: Path, out_dir: Path) -> tuple[Path, bytes]:
    try:
        content = file_path.read_text(encoding="utf-8")
        data = json.loads(content)
    except Exception as exc:
        raise ValueError(f"File {file_path.name} is not valid JSON: {exc}") from exc

    if not isinstance(data, dict) or "method" not in data or "args" not in data:
        raise ValueError(f"File {file_path.name} missing method or args")

    method = data["method"]
    args = data["args"]
    expected_name = f"{fixture_key(method, args)}.json"
    if file_path.name != expected_name:
        raise ValueError(
            f"File {file_path.name} does not match expected fixture key {expected_name}"
        )

    sanitised = sanitise_fixture(data)
    serialized = json.dumps(sanitised, sort_keys=True, indent=1, ensure_ascii=True) + "\n"
    encoded = serialized.encode("utf-8")

    if len(encoded) > MAX_OUTPUT_BYTES:
        raise ValueError(
            f"Output file {file_path.name} exceeds {MAX_OUTPUT_BYTES} bytes ({len(encoded)} bytes)"
        )

    return out_dir / file_path.name, encoded


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for sanitising fixture files."""
    parser = argparse.ArgumentParser(description="Sanitise raw YouTube API fixtures.")
    parser.add_argument(
        "--raw-dir",
        default="tests/fixtures/_raw",
        help="Directory containing raw fixture JSON files.",
    )
    parser.add_argument(
        "--out-dir",
        default="tests/fixtures/youtube",
        help="Directory to write sanitised fixture JSON files.",
    )

    args = parser.parse_args(argv)
    raw_dir = Path(args.raw_dir)
    out_dir = Path(args.out_dir)

    if not raw_dir.is_dir():
        sys.stderr.write(f"No raw files found in {raw_dir}\n")
        return 2

    raw_files = sorted(raw_dir.glob("*.json"))
    if not raw_files:
        sys.stderr.write(f"No raw files found in {raw_dir}\n")
        return 2

    pending_writes: list[tuple[Path, bytes]] = []
    for file_path in raw_files:
        try:
            target_path, encoded = _process_fixture_file(file_path, out_dir)
            pending_writes.append((target_path, encoded))
        except ValueError as exc:
            sys.stderr.write(f"Error processing {file_path.name}: {exc}\n")
            return 2

    out_dir.mkdir(parents=True, exist_ok=True)
    for target_path, encoded in pending_writes:
        target_path.write_bytes(encoded)

    sys.stdout.write(f"Sanitised and wrote {len(pending_writes)} fixture files to {out_dir}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
