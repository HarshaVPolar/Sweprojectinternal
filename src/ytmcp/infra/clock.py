"""Injectable clock and seedable random number generation."""

import abc
import random
import zoneinfo
from datetime import UTC, datetime, timedelta

DEFAULT_RESET_TZ: str = "America/Los_Angeles"


class Clock(abc.ABC):
    """Abstract base clock providing current time and reset boundary calculations."""

    def __init__(self, reset_tz: str = DEFAULT_RESET_TZ) -> None:
        if not reset_tz:
            raise ValueError("reset_tz cannot be empty")
        self._tz = zoneinfo.ZoneInfo(reset_tz)

    @abc.abstractmethod
    def now(self) -> datetime:
        """Return the current instant as a timezone-aware UTC datetime."""

    def reset_day(self) -> str:
        """Return the date of now() in the configured reset timezone formatted as YYYY-MM-DD."""
        current_utc = self.now()
        local_dt = current_utc.astimezone(self._tz)
        return local_dt.strftime("%Y-%m-%d")

    def next_reset(self) -> datetime:
        """Return the next local midnight in the reset timezone as an aware UTC datetime."""
        current_utc = self.now()
        local_dt = current_utc.astimezone(self._tz)
        next_date = local_dt.date() + timedelta(days=1)
        next_local = datetime(
            next_date.year,
            next_date.month,
            next_date.day,
            0,
            0,
            0,
            tzinfo=self._tz,
        )
        return next_local.astimezone(UTC)


class SystemClock(Clock):
    """Real-time clock reading the system wall clock."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class FakeClock(Clock):
    """Controllable clock for deterministic testing."""

    def __init__(
        self,
        start: datetime,
        reset_tz: str = DEFAULT_RESET_TZ,
    ) -> None:
        super().__init__(reset_tz=reset_tz)
        if start.tzinfo is None or start.utcoffset() is None:
            raise ValueError("start must be a timezone-aware datetime")
        self._current: datetime = start.astimezone(UTC)

    def now(self) -> datetime:
        return self._current

    def set(self, value: datetime) -> None:
        """Set the current clock instant."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("value must be a timezone-aware datetime")
        self._current = value.astimezone(UTC)

    def advance(self, seconds: float) -> None:
        """Advance the current clock instant by the given number of seconds."""
        self._current += timedelta(seconds=seconds)


def make_rng(seed: int | None = None) -> random.Random:
    """Create a new seeded random.Random generator."""
    return random.Random(seed)


__all__ = [
    "DEFAULT_RESET_TZ",
    "Clock",
    "FakeClock",
    "SystemClock",
    "make_rng",
]
