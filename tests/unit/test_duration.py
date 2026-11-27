from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ytmcp.domain.duration import format_mmss, parse_iso8601_duration


@pytest.mark.unit
@pytest.mark.parametrize(
    ("raw", "expected_seconds"),
    [
        ("PT0S", 0),
        ("P0D", 0),
        ("PT0M0S", 0),
        ("P0DT0S", 0),
        ("PT59S", 59),
        ("PT1M", 60),
        ("PT1H", 3600),
        ("PT1H2M3S", 3723),
        ("PT15M33S", 933),
        ("PT2H", 7200),
        ("PT100H", 360000),
        ("P1D", 86400),
        ("P1DT1H", 90000),
        ("P1DT2H3M4S", 93784),
    ],
)
def test_parse_valid(raw: str, expected_seconds: int) -> None:
    assert parse_iso8601_duration(raw) == expected_seconds


@pytest.mark.unit
@pytest.mark.parametrize(
    "raw",
    [
        "",
        "P",
        "PT",
        "P1DT",
        "pt1h",
        "PT1.5S",
        "PT-5S",
        "PT1M1H",
        "PT1S1S",
        " PT1S",
        "PT1S ",
        "PT1S\n",
        "\nPT1S",
        "P1W",
        "P1Y",
        "PT1H2",
        "1H",
        "PT1",
        "PT1,5S",
        "P-1D",
        "P1DT\n",
        "PT\u0661S",
    ],
)
def test_parse_invalid(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_iso8601_duration(raw)


@pytest.mark.unit
def test_parse_rejects_non_string() -> None:
    with pytest.raises(ValueError):
        parse_iso8601_duration(123)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        parse_iso8601_duration(None)  # type: ignore[arg-type]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("seconds", "expected_text"),
    [
        (0, "00:00"),
        (5, "00:05"),
        (59, "00:59"),
        (60, "01:00"),
        (125, "02:05"),
        (3599, "59:59"),
        (3600, "1:00:00"),
        (3723, "1:02:03"),
        (36000, "10:00:00"),
        (86399, "23:59:59"),
        (90000, "25:00:00"),
    ],
)
def test_format_valid(seconds: int, expected_text: str) -> None:
    assert format_mmss(seconds) == expected_text


@pytest.mark.unit
@pytest.mark.parametrize("invalid_input", [-1, "5", True, False])
def test_format_invalid(invalid_input: Any) -> None:
    with pytest.raises(ValueError):
        format_mmss(invalid_input)


def _build_duration_text(seconds: int) -> str:
    if seconds == 0:
        return "PT0S"
    days = seconds // 86400
    rem = seconds % 86400
    hours = rem // 3600
    rem %= 3600
    minutes = rem // 60
    secs = rem % 60

    parts: list[str] = ["P"]
    if days > 0:
        parts.append(f"{days}D")
    if hours > 0 or minutes > 0 or secs > 0:
        parts.append("T")
        if hours > 0:
            parts.append(f"{hours}H")
        if minutes > 0:
            parts.append(f"{minutes}M")
        if secs > 0:
            parts.append(f"{secs}S")
    return "".join(parts)


@pytest.mark.unit
@given(st.integers(min_value=0, max_value=100_000_000))
def test_property_round_trip(seconds: int) -> None:
    duration_str = _build_duration_text(seconds)
    assert parse_iso8601_duration(duration_str) == seconds


@pytest.mark.unit
@given(st.integers(min_value=0, max_value=100_000_000))
def test_property_format(seconds: int) -> None:
    formatted = format_mmss(seconds)
    parts = formatted.split(":")
    if seconds < 3600:
        assert len(parts) == 2
        m = int(parts[0])
        s = int(parts[1])
        assert m * 60 + s == seconds
    else:
        assert len(parts) == 3
        h = int(parts[0])
        m = int(parts[1])
        s = int(parts[2])
        assert h * 3600 + m * 60 + s == seconds

    assert len(parts[-2]) == 2
    assert len(parts[-1]) == 2


@pytest.mark.unit
@given(st.text())
def test_property_never_other_error(raw: str) -> None:
    try:
        val = parse_iso8601_duration(raw)
        assert isinstance(val, int)
        assert val >= 0
    except ValueError:
        pass
