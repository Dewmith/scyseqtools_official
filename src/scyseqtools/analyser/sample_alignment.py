"""Match complete coded observations by their original media boundaries."""

from bisect import bisect_left, bisect_right
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional


@dataclass(frozen=True)
class RecordingClock:
    times: tuple
    period_ms: Optional[Decimal]
    notice: str = ""

    @classmethod
    def from_metadata(cls, metadata, count, context):
        if not isinstance(metadata, Mapping):
            raise ValueError(f"{context} has invalid timing metadata.")
        code = metadata.get("code")
        period = metadata.get("period")
        if isinstance(code, Mapping):
            period = code.get("period", period)
        if period is not None:
            try:
                period = Decimal(str(period))
            except InvalidOperation as exc:
                raise ValueError(f"{context} has an invalid sampling period.") from exc
            if not period.is_finite() or period <= 0:
                raise ValueError(f"{context} needs a finite, positive sampling period.")
            period *= 1000

        if metadata.get("timestamps_estimated") is True:
            return cls((), period, "timestamps were estimated for Encoder Resume")
        times = metadata.get("times")
        if times is None or (isinstance(times, (list, tuple)) and not times):
            return cls((), period, "missing observation timestamps")
        if not isinstance(times, (list, tuple)) or len(times) not in (count, count + 1):
            raise ValueError(f"{context} has invalid timestamp metadata. Expected {count + 1} "
                             f"interval boundaries for {count} coded observations.")
        try:
            grid = tuple(Decimal(str(value)) for value in times)
        except InvalidOperation as exc:
            raise ValueError(f"{context} has an invalid timestamp in milliseconds.") from exc
        if (any(not value.is_finite() or value < 0 for value in grid)
                or any(b <= a for a, b in zip(grid, grid[1:]))):
            raise ValueError(f"{context} timestamps must be finite, nonnegative and strictly increasing.")
        if len(grid) == count:
            return cls(grid, period, "legacy timestamps lack complete interval boundaries")
        return cls(grid, period)


@dataclass(frozen=True)
class Overlap:
    first: tuple
    second: tuple
    common: tuple


def recording_overlap(first, second):
    for clock in (first, second):
        if clock.notice:
            raise ValueError(f"Complete media timestamps are required ({clock.notice}).")
    a, b = (first.times[0], first.times[-1]), (second.times[0], second.times[-1])
    start, end = max(a[0], b[0]), min(a[1], b[1])
    if end <= start:
        raise ValueError("The selected recordings have no common observation interval. "
                         "Select recordings with overlapping coding times.")
    return Overlap(a, b, (start, end))


def require_matching_periods(first, second):
    a, b = first.period_ms, second.period_ms
    if a is not None and b is not None and a != b:
        raise ValueError(f"Different sampling periods cannot be aligned ({a} ms and {b} ms).")


@dataclass(frozen=True)
class SampleAlignment:
    overlap: Overlap
    compared: tuple
    first_slice: slice
    second_slice: slice

    def sequences(self, first, second):
        return first[self.first_slice], second[self.second_slice]


def match_sample_clocks(first, second):
    overlap = recording_overlap(first, second)
    require_matching_periods(first, second)
    a, b = first.times, second.times
    start, end = overlap.common

    # If an edge cuts an observation, both grids must agree at the next
    # interior boundary. This can discard one observation per edge, never an
    # interior stretch of mismatched observations.
    i, j = bisect_left(a, start), bisect_left(b, start)
    if a[i] != start or b[j] != start:
        i, j = bisect_right(a, start), bisect_right(b, start)
    stop_i, stop_j = bisect_right(a, end) - 1, bisect_right(b, end) - 1
    if a[stop_i] != end or b[stop_j] != end:
        stop_i, stop_j = bisect_left(a, end) - 1, bisect_left(b, end) - 1
    if i >= stop_i or j >= stop_j:
        raise ValueError("There are no comparable complete coded observations in the overlap.")
    if a[i:stop_i + 1] != b[j:stop_j + 1]:
        raise ValueError("The recordings have incompatible sampling grids. Observations inside the "
                         "overlap must have matching start and end boundaries.")
    return SampleAlignment(overlap, (a[i], a[stop_i]), slice(i, stop_i), slice(j, stop_j))


def align_samples(first, first_metadata, second, second_metadata):
    """Return two aligned slices and their comparison window on a shared media clock."""
    if not len(first) or not len(second):
        raise ValueError("There are no comparable coded observations in an empty sequence.")
    first_clock = RecordingClock.from_metadata(first_metadata, len(first), "First recording")
    second_clock = RecordingClock.from_metadata(second_metadata, len(second), "Second recording")
    alignment = match_sample_clocks(first_clock, second_clock)
    return (*alignment.sequences(first, second), alignment)
