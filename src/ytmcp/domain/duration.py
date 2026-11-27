"""ISO 8601 duration parser and formatter."""

import re

_PATTERN = re.compile(
    r"P"
    r"(?:(?P<days>[0-9]+)D)?"
    r"(?:"
    r"T(?=[0-9])"
    r"(?:(?P<hours>[0-9]+)H)?"
    r"(?:(?P<minutes>[0-9]+)M)?"
    r"(?:(?P<seconds>[0-9]+)S)?"
    r")?"
)


def parse_iso8601_duration(s: str) -> int:
    """Parse an ISO 8601 duration string into seconds."""
    if not isinstance(s, str):
        raise ValueError(f"Expected str, got {type(s).__name__}")

    match = _PATTERN.fullmatch(s)
    if match is None:
        raise ValueError(f"Invalid ISO 8601 duration: {s}")

    days_str = match.group("days")
    hours_str = match.group("hours")
    minutes_str = match.group("minutes")
    seconds_str = match.group("seconds")

    if days_str is None and hours_str is None and minutes_str is None and seconds_str is None:
        raise ValueError(f"Invalid ISO 8601 duration: {s}")

    days = int(days_str) if days_str is not None else 0
    hours = int(hours_str) if hours_str is not None else 0
    minutes = int(minutes_str) if minutes_str is not None else 0
    seconds = int(seconds_str) if seconds_str is not None else 0

    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def format_mmss(seconds: int) -> str:
    """Format total seconds into MM:SS or H:MM:SS."""
    if isinstance(seconds, bool) or not isinstance(seconds, int):
        raise ValueError(f"Expected integer seconds, got {type(seconds).__name__}")
    if seconds < 0:
        raise ValueError(f"Seconds cannot be negative: {seconds}")

    if seconds < 3600:
        m = seconds // 60
        s = seconds % 60
        return f"{m:02d}:{s:02d}"

    h = seconds // 3600
    rem = seconds % 3600
    m = rem // 60
    s = rem % 60
    return f"{h}:{m:02d}:{s:02d}"


__all__ = ["format_mmss", "parse_iso8601_duration"]
