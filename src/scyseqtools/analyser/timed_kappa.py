"""Duration-weighted agreement on the original Codix recording clock."""

from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional


def parse_tolerance(value):
    try:
        tolerance = Decimal(str(value))
        if tolerance.is_finite() and tolerance >= 0:
            return tolerance
    except InvalidOperation:
        pass
    raise ValueError("Timestamp tolerance must be a finite, nonnegative number in ms.")


@dataclass
class Timeline:
    times: list   # All original sample boundaries, including recording end.
    edges: list   # Boundaries of contiguous runs of the same label.
    states: list  # One label per run.

    @classmethod
    def from_samples(cls, times, labels, context):
        if not isinstance(times, (list, tuple)) or len(times) != len(labels) + 1:
            raise ValueError(f"{context}: expected {len(labels) + 1} timestamp boundaries.")
        if not len(labels):
            raise ValueError(f"{context}: empty observation sequence.")
        try:
            times = [Decimal(str(t)) for t in times]
        except InvalidOperation as exc:
            raise ValueError(f"{context}: invalid timestamp in ms.") from exc
        if (not all(t.is_finite() for t in times)
                or any(b <= a for a, b in zip(times, times[1:]))):
            raise ValueError(f"{context}: timestamps must be finite and strictly increasing.")

        edges, states = [], []
        for time, label in zip(times, labels):
            if not states or states[-1] != label:
                edges.append(time)
                states.append(label)
        return cls(times, edges + [times[-1]], states)

    def shortest_run(self, start, end):
        return min(b - a for a, b in zip(self.edges, self.edges[1:])
                   if b > start and a < end)


def _translated(a, b):
    if len(a) != len(b) or not a or a[0] == b[0]:
        return False
    offset = b[0] - a[0]
    return all(y - x == offset for x, y in zip(a, b))


def paired_intervals(a, b, start, end):
    """Walk both recordings on their common clock within the given overlap."""
    i = bisect_right(a.edges, start) - 1
    j = bisect_right(b.edges, start) - 1
    time = start
    while time < end:
        stop = min(a.edges[i + 1], b.edges[j + 1], end)
        yield time, stop, a.states[i], b.states[j]
        if a.edges[i + 1] == stop:
            i += 1
        if b.edges[j + 1] == stop:
            j += 1
        time = stop


def _kappa(matrix):
    row, column = Counter(), Counter()
    total = sum(matrix.values())
    disagreement = 0
    for (left, right), duration in matrix.items():
        row[left] += duration
        column[right] += duration
        if left != right:
            disagreement += duration
    chance = total * total - sum(row[k] * column[k] for k in row)
    return 1 - disagreement * total / chance if chance else None


def _local_matches(a, b, start, end, tolerance):
    """Yield isolated directed transitions. Candidate spans use the original clock."""
    partners = defaultdict(list)
    for j in range(1, len(b.states)):
        if start < b.edges[j] < end:
            partners[b.states[j - 1], b.states[j]].append(b.edges[j])

    spans = []
    for i in range(1, len(a.states)):
        time = a.edges[i]
        if not start < time < end:
            continue
        transition = a.states[i - 1], a.states[i]
        candidates = partners[transition]
        first = bisect_left(candidates, time - tolerance)
        stop = bisect_right(candidates, time + tolerance)
        if first < stop:
            # An ambiguous set reserves its entire span, so another match
            # cannot claim disagreement from inside that ambiguity.
            low = min(time, candidates[first])
            high = max(time, candidates[stop - 1])
            spans.append((low, high, stop - first, time, transition))

    spans.sort()
    previous_end = start
    for index, (low, high, count, time, transition) in enumerate(spans):
        touches_previous = low <= previous_end
        previous_end = max(previous_end, high)
        touches_next = index + 1 < len(spans) and spans[index + 1][0] <= high
        if low == high or count != 1 or touches_previous or touches_next:
            continue
        # The pair must be the only two actual transitions in this closed
        # interval, including simultaneous third-state changes at either end.
        changes = sum(bisect_right(stream.edges, high) - bisect_left(stream.edges, low)
                      for stream in (a, b))
        if changes == 2:
            before, after = transition
            cell = (after, before) if time == low else (before, after)
            yield cell, high - low


@dataclass
class Agreement:
    start: Optional[Decimal] = None
    end: Optional[Decimal] = None
    duration: Decimal = Decimal(0)
    strict: Optional[Decimal] = None
    adjusted: Optional[Decimal] = None
    disagreement: Decimal = Decimal(0)
    credited: Decimal = Decimal(0)
    warning: str = ""


def time_agreement(a, b, tolerance):
    """Calculate strict and optional boundary-adjusted kappa for two timelines."""
    start, end = max(a.times[0], b.times[0]), min(a.times[-1], b.times[-1])
    offset = (_translated(a.times, b.times)
              or (len(a.states) >= 3 and a.states == b.states
                  and _translated(a.edges[1:-1], b.edges[1:-1])))
    warnings = []
    if offset:
        warnings.append("Possible constant recording offset or later window. Verify clock synchronization.")
    if end <= start:
        return Agreement(warning=" ".join(["No overlapping recording time."] + warnings))

    matrix = Counter()
    for left, right, first, second in paired_intervals(a, b, start, end):
        matrix[first, second] += right - left
    result = Agreement(start, end, end - start, _kappa(matrix))
    result.disagreement = sum(d for (x, y), d in matrix.items() if x != y)
    if result.strict is None:
        warnings.append("Strict kappa undefined: expected agreement is one.")

    if tolerance > 0:
        shortest = min(a.shortest_run(start, end), b.shortest_run(start, end))
        if tolerance >= shortest / 2:
            warnings.append("Tolerance reaches half the shortest behavioural run.")
        if not offset:
            adjusted = matrix.copy()
            for (x, y), duration in _local_matches(a, b, start, end, min(tolerance, end - start)):
                adjusted[x, y] -= duration
                adjusted[x, x] += duration / 2
                adjusted[y, y] += duration / 2
                result.credited += duration
            result.adjusted = _kappa(adjusted)
            if result.adjusted is None:
                warnings.append("Adjusted kappa undefined: expected agreement is one.")
    result.warning = " ".join(warnings)
    return result
