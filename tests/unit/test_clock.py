import random
from datetime import UTC, datetime, timedelta, timezone

import pytest

from ytmcp.infra.clock import (
    DEFAULT_RESET_TZ,
    Clock,
    FakeClock,
    SystemClock,
    make_rng,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("instant", "expected_day"),
    [
        (datetime(2026, 1, 15, 7, 59, 59, tzinfo=UTC), "2026-01-14"),
        (datetime(2026, 1, 15, 8, 0, 0, tzinfo=UTC), "2026-01-15"),
        (datetime(2026, 7, 1, 6, 59, 59, tzinfo=UTC), "2026-06-30"),
        (datetime(2026, 7, 1, 7, 0, 0, tzinfo=UTC), "2026-07-01"),
        (datetime(2026, 3, 8, 7, 59, 59, tzinfo=UTC), "2026-03-07"),
        (datetime(2026, 3, 8, 8, 0, 0, tzinfo=UTC), "2026-03-08"),
        (datetime(2026, 3, 9, 6, 59, 59, tzinfo=UTC), "2026-03-08"),
        (datetime(2026, 3, 9, 7, 0, 0, tzinfo=UTC), "2026-03-09"),
        (datetime(2026, 11, 1, 6, 59, 59, tzinfo=UTC), "2026-10-31"),
        (datetime(2026, 11, 1, 7, 0, 0, tzinfo=UTC), "2026-11-01"),
        (datetime(2026, 11, 2, 7, 59, 59, tzinfo=UTC), "2026-11-01"),
        (datetime(2026, 11, 2, 8, 0, 0, tzinfo=UTC), "2026-11-02"),
    ],
)
def test_reset_day_boundaries(instant: datetime, expected_day: str) -> None:
    clock = FakeClock(instant)
    assert clock.reset_day() == expected_day


@pytest.mark.unit
@pytest.mark.parametrize(
    ("instant", "expected_reset"),
    [
        (
            datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC),
            datetime(2026, 1, 16, 8, 0, 0, tzinfo=UTC),
        ),
        (
            datetime(2026, 7, 1, 12, 0, 0, tzinfo=UTC),
            datetime(2026, 7, 2, 7, 0, 0, tzinfo=UTC),
        ),
        (
            datetime(2026, 3, 8, 12, 0, 0, tzinfo=UTC),
            datetime(2026, 3, 9, 7, 0, 0, tzinfo=UTC),
        ),
        (
            datetime(2026, 11, 1, 12, 0, 0, tzinfo=UTC),
            datetime(2026, 11, 2, 8, 0, 0, tzinfo=UTC),
        ),
        (
            datetime(2026, 1, 15, 7, 59, 59, tzinfo=UTC),
            datetime(2026, 1, 15, 8, 0, 0, tzinfo=UTC),
        ),
        (
            datetime(2026, 1, 15, 8, 0, 0, tzinfo=UTC),
            datetime(2026, 1, 16, 8, 0, 0, tzinfo=UTC),
        ),
    ],
)
def test_next_reset(instant: datetime, expected_reset: datetime) -> None:
    clock = FakeClock(instant)
    res = clock.next_reset()
    assert res == expected_reset
    assert res.tzinfo is not None
    assert res.utcoffset() == timedelta(0)


@pytest.mark.unit
def test_fake_clock_converts_offsets() -> None:
    offset_tz = timezone(timedelta(hours=5, minutes=30))
    dt = datetime(2026, 1, 15, 12, 0, 0, tzinfo=offset_tz)
    clock = FakeClock(dt)

    assert clock.now() == datetime(2026, 1, 15, 6, 30, 0, tzinfo=UTC)
    assert clock.now().utcoffset() == timedelta(0)
    assert clock.reset_day() == "2026-01-14"


@pytest.mark.unit
def test_fake_clock_rejects_naive() -> None:
    naive_dt = datetime(2026, 1, 15, 12, 0, 0)
    with pytest.raises(ValueError):
        FakeClock(naive_dt)

    clock = FakeClock(datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC))
    with pytest.raises(ValueError):
        clock.set(naive_dt)


@pytest.mark.unit
def test_fake_clock_advance_and_set() -> None:
    clock = FakeClock(datetime(2026, 1, 15, 7, 59, 59, tzinfo=UTC))
    assert clock.reset_day() == "2026-01-14"

    clock.advance(1)
    assert clock.reset_day() == "2026-01-15"

    clock.advance(86400)
    assert clock.reset_day() == "2026-01-16"

    new_instant = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    clock.set(new_instant)
    assert clock.now() == new_instant

    clock.advance(0.5)
    assert clock.now() == new_instant + timedelta(seconds=0.5)


@pytest.mark.unit
def test_custom_reset_zone() -> None:
    clock1 = FakeClock(
        datetime(2026, 1, 15, 18, 29, 59, tzinfo=UTC),
        reset_tz="Asia/Kolkata",
    )
    assert clock1.reset_day() == "2026-01-15"

    clock2 = FakeClock(
        datetime(2026, 1, 15, 18, 30, 0, tzinfo=UTC),
        reset_tz="Asia/Kolkata",
    )
    assert clock2.reset_day() == "2026-01-16"


@pytest.mark.unit
def test_invalid_zone() -> None:
    with pytest.raises((KeyError, ValueError)):
        FakeClock(datetime.now(UTC), reset_tz="Not/AZone")

    with pytest.raises((KeyError, ValueError)):
        SystemClock(reset_tz="Not/AZone")

    with pytest.raises(ValueError):
        FakeClock(datetime.now(UTC), reset_tz="")

    with pytest.raises(ValueError):
        SystemClock(reset_tz="")


@pytest.mark.unit
def test_system_clock() -> None:
    clock = SystemClock()
    before = datetime.now(UTC)
    now = clock.now()
    after = datetime.now(UTC)

    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)
    assert before <= now <= after

    day = clock.reset_day()
    assert isinstance(day, str)
    assert len(day) == 10
    assert day[4] == "-" and day[7] == "-"
    int(day[:4])
    int(day[5:7])
    int(day[8:10])

    reset_time = clock.next_reset()
    assert reset_time.tzinfo is not None
    assert reset_time.utcoffset() == timedelta(0)
    assert reset_time > now


@pytest.mark.unit
def test_abstract_clock() -> None:
    with pytest.raises(TypeError):
        Clock(DEFAULT_RESET_TZ)  # type: ignore[abstract]


@pytest.mark.unit
def test_rng() -> None:
    rng1 = make_rng(42)
    rng2 = make_rng(42)
    vals1 = [rng1.random() for _ in range(5)]
    vals2 = [rng2.random() for _ in range(5)]
    assert vals1 == vals2

    rng_diff1 = make_rng(1)
    rng_diff2 = make_rng(2)
    assert [rng_diff1.random() for _ in range(5)] != [rng_diff2.random() for _ in range(5)]

    rng_default = make_rng()
    assert isinstance(rng_default, random.Random)
