"""Read-only CDX preview data and time geometry, independent of Tk."""

from collections import OrderedDict
from dataclasses import dataclass, field
from locale import getpreferredencoding
from pathlib import Path
from threading import Condition, Thread
from typing import Optional
import colorsys
import json
import math

import numpy as np
from matplotlib.colors import to_hex
from scyseq import Alphabet, Sequence, io
from scyseq.viz import get_state_colors


def _read_record(path):
    try:
        record = io.read_codix(path, data_only=False)
    except json.JSONDecodeError as error:
        if not error.doc.strip():
            raise ValueError("This file is empty.") from error
        if error.doc.startswith(("\ufeff", "ï»¿")):
            return _decode_tracks(json.loads(path.read_bytes()))
        raise ValueError(f"Invalid CDX JSON at line {error.lineno}, column {error.colno}.") from error
    except UnicodeDecodeError:
        return _decode_tracks(json.loads(path.read_bytes()))
    except (TypeError, KeyError) as error:
        # ScySeq's Sequence constructor rejects a JSON [] because NumPy gives
        # it a float dtype. Keep empty streams and use Sequence for the others.
        try:
            raw = json.loads(path.read_bytes())
        except UnicodeDecodeError:
            raw = json.loads(path.read_text())
        return _decode_tracks(raw, empty_fallback=error)

    # The upstream reader uses the OS text encoding. Check literal Unicode
    # on legacy Windows code pages, where UTF-8 can decode without an error.
    if getpreferredencoding(False).lower() != "utf-8" and _has_non_ascii_labels(record):
        try:
            source = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            return record  # A legacy CDX in the local text encoding.
        if not source.isascii():
            return _decode_tracks(json.loads(source))
    return record


def _has_non_ascii_labels(record):
    def has_non_ascii(value):
        if isinstance(value, str):
            return not value.isascii()
        if isinstance(value, dict):
            return any(has_non_ascii(key) or has_non_ascii(item) for key, item in value.items())
        if isinstance(value, (tuple, list)):
            return any(has_non_ascii(item) for item in value)
        return False

    if any(has_non_ascii(record.get(key)) for key in ("code", "history", "media", "version")):
        return True
    return any(not site.isascii() or any(
        not category.isascii() or has_non_ascii(sequence.alphabet.svals)
        for category, sequence in categories.items()
    ) for site, categories in record["data"].items())


def _decode_tracks(record, empty_fallback=None):
    data = record.get("data") if isinstance(record, dict) else None
    if not isinstance(data, dict) or any(not isinstance(site, dict) for site in data.values()):
        raise ValueError("Invalid CDX observation data.") from empty_fallback
    current = "version" in record
    entries = [(site, category, value if current else value["seq"], value)
               for site, categories in data.items() for category, value in categories.items()]
    if empty_fallback is not None and entries and not any(
            isinstance(values, list) and not values for _, _, values, _ in entries):
        raise empty_fallback

    code = record.get("code")
    declared = code.get("codes", {}) if isinstance(code, dict) else {}
    parsed = {site: {} for site in data}
    for site, category, values, value in entries:
        if current:
            alphabet = Alphabet(declared[category])
        else:
            labels = [""] * len(value["dico"])
            for index, label in value["dico"].items():
                labels[int(index)] = str(label)
            alphabet = Alphabet(labels)
        symbols = np.empty(0, dtype=np.uint8) if isinstance(values, list) and not values else values
        parsed[site][category] = Sequence(symbols, alphabet)
    record["data"] = parsed
    return record


def _code_colors(keys):
    palette, _ = get_state_colors(range(20), cmap_name="tab20")
    distinct = [to_hex(palette(index)) for index in range(0, 20, 2)]
    distinct.extend(to_hex(palette(index)) for index in range(1, 20, 2))
    colors = {}
    taken = set()
    for index, key in enumerate(sorted(keys)):
        if index < len(distinct):
            color = distinct[index]
        else:
            hue = (index * 0.618033988749895) % 1
            light = (0.34, 0.55, 0.68)[index % 3]
            color = to_hex(colorsys.hls_to_rgb(hue, light, 0.72))
            while color in taken:
                hue = (hue + 0.018) % 1
                color = to_hex(colorsys.hls_to_rgb(hue, light, 0.72))
                if color in taken:
                    light = (light + 0.031) % 0.54 + 0.22
        taken.add(color)
        colors[key] = color
    return colors


def _number(value):
    if isinstance(value, bool):
        return np.nan
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        return np.nan
    # Beyond this bound the recording clock can no longer resolve milliseconds.
    return value if math.isfinite(value) and abs(value) < 2 ** 53 else np.nan


@dataclass
class Clock:
    starts: np.ndarray
    ends: np.ndarray
    duration: Optional[float] = None
    notice: str = ""
    extent: Optional[tuple] = None

    @classmethod
    def from_times(cls, times, steps):
        starts = np.full(steps, np.nan)
        ends = starts.copy()
        if steps == 0:
            return cls(starts, ends)
        if not isinstance(times, (list, tuple)) or not times:
            return cls(starts, ends, notice="This file has no observation timestamps.")
        if len(times) not in (steps, steps + 1):
            return cls(starts, ends, notice="Timestamp count does not match the coding steps.")

        stamps = np.fromiter(map(_number, times), dtype=float, count=len(times))
        valid = stamps[np.isfinite(stamps)]
        if np.any(valid[1:] < valid[:-1]):
            return cls(starts, ends, notice="Timestamps go backwards. Observation times are unavailable.")

        starts = stamps[:steps]
        duration = None
        notices = []
        if len(stamps) > steps:
            following = stamps[1:]
            supported = following > starts
            ends[supported] = following[supported]
            if np.isfinite(stamps[[0, -1]]).all() and stamps[-1] > stamps[0]:
                duration = float(stamps[-1] - stamps[0])
            if np.any(following == starts):
                notices.append("Repeated boundaries are shown as points.")
        else:
            notices.append("Sample timestamps only. Recording duration is unavailable.")
        if len(valid) != len(stamps):
            notices.append("Some timestamps are missing or invalid.")
        extent = (float(valid[0]), float(valid[-1])) if np.isfinite(starts).any() else None
        return cls(starts, ends, duration, " ".join(notices), extent)


@dataclass(frozen=True)
class Observation:
    site: str
    category: str
    state: str
    start: Optional[float]
    end: Optional[float]

    @property
    def key(self):
        return self.category, self.state

    @property
    def duration(self):
        return self.end - self.start if self.end is not None else None


@dataclass(frozen=True)
class TimelineMark:
    start: float
    end: float
    value: Optional[int]  # None indicates multiple marks within one display bin.
    first: int
    last: int
    mixed: bool = False


@dataclass
class TimelineSpans:
    starts: np.ndarray
    stops: np.ndarray
    indexes: np.ndarray
    lasts: np.ndarray
    values: np.ndarray
    exclusive_stops: np.ndarray = field(init=False)

    def __post_init__(self):
        points = self.stops == self.starts
        self.exclusive_stops = self.stops
        if np.any(points):
            self.exclusive_stops = self.stops.copy()
            self.exclusive_stops[points] = np.nextafter(self.stops[points], np.inf)

    @classmethod
    def build(cls, clock, values):
        indexes = np.flatnonzero(np.isfinite(clock.starts[:len(values)]))
        starts = clock.starts[indexes]
        ends = clock.ends[indexes]
        stops = np.where(np.isfinite(ends), ends, starts)
        symbols = values[indexes]
        split = np.ones(len(indexes), dtype=bool)
        split[1:] = ((stops[:-1] != starts[1:]) | (symbols[:-1] != symbols[1:])
                     | (indexes[1:] != indexes[:-1] + 1)
                     | (starts[:-1] == stops[:-1]) | (starts[1:] == stops[1:]))
        first = np.flatnonzero(split)
        last = np.r_[first[1:] - 1, len(indexes) - 1] if len(first) else first
        index_type = np.int32 if len(values) <= np.iinfo(np.int32).max else np.int64
        return cls(starts[first], stops[last], indexes[first].astype(index_type, copy=False),
                   indexes[last].astype(index_type, copy=False), symbols[first])

    def _mark(self, index):
        return TimelineMark(float(self.starts[index]), float(self.stops[index]),
                            int(self.values[index]), int(self.indexes[index]), int(self.lasts[index]))

    def visible(self, left, right, width):
        """Yield exact marks or occupied bins within the current viewport."""
        first = self.exclusive_stops.searchsorted(left, side="right")
        last = self.starts.searchsorted(right, side="right")
        if last and self.starts[last - 1] == right and self.stops[last - 1] > right:
            last -= 1
        budget = max(1, width // 5)
        if last - first <= budget:
            index = first
            while index < last:
                if self.starts[index] == self.stops[index]:
                    following = min(last, self.starts.searchsorted(self.starts[index], side="right"))
                    if following - index > 1 and self.stops[following - 1] > self.starts[index]:
                        following -= 1  # An interval can start at the same time as the points.
                    if following - index > 1:
                        start = float(self.starts[index])
                        yield TimelineMark(start, start, None, int(self.indexes[index]),
                                           int(self.indexes[following - 1]), mixed=True)
                        index = following
                        continue
                yield self._mark(index)
                index += 1
            return

        edges = np.linspace(left, right, budget + 1)
        firsts = self.exclusive_stops.searchsorted(edges[:-1], side="right")
        lasts = self.starts.searchsorted(edges[1:], side="left")
        lasts[-1] = last
        for column in np.flatnonzero(lasts > firsts):
            first, last = firsts[column], lasts[column]
            if last == first + 1:
                mark = self._mark(first)
                if mark.start == mark.end or (
                    mark.start >= edges[column] and mark.end <= edges[column + 1]
                ):
                    yield mark
                else:
                    yield TimelineMark(max(mark.start, edges[column]),
                                       min(mark.end, edges[column + 1]),
                                       mark.value, mark.first, mark.last)
            else:
                yield TimelineMark(float(edges[column]), float(edges[column + 1]), None,
                                   int(self.indexes[first]), int(self.lasts[last - 1]), mixed=True)


@dataclass
class PreviewTrack:
    site: str
    category: str
    labels: tuple
    values: np.ndarray
    spans: TimelineSpans

    def observation(self, sample, clock):
        start, end = clock.starts[sample], clock.ends[sample]
        return Observation(self.site, self.category, self.labels[self.values[sample]],
                           float(start) if np.isfinite(start) else None,
                           float(end) if np.isfinite(end) else None)


def _session_metadata(record, code):
    metadata = []
    for label, value in (("Project", code.get("project")), ("Code date", code.get("date")),
                         ("Description", code.get("description")), ("Media", record.get("media")),
                         ("CDX version", record.get("version"))):
        if isinstance(value, (str, int, float)) and value != "":
            metadata.append(f"{label}: {value}")
    history = record.get("history", ())
    if isinstance(history, list):
        for entry in history:
            if isinstance(entry, (list, tuple)):
                details = " · ".join(str(value) for value in entry if value)
                if details:
                    metadata.append(f"Session: {details}")
    return "\n\n".join(metadata)


@dataclass
class PreviewData:
    filename: str
    sites: dict
    tracks: dict
    colors: dict
    used_keys: tuple
    declared_codes: int
    used_codes: int
    clock: Clock
    extent: Optional[tuple]
    metadata: str
    ordered_samples: np.ndarray
    row_offsets: np.ndarray

    @property
    def steps(self):
        return len(self.ordered_samples)

    @property
    def total(self):
        return int(self.row_offsets[-1])

    def page(self, offset, limit):
        """Read a page without materializing all event rows."""
        if offset >= self.total:
            return
        tracks = tuple(self.tracks.values())
        order = self.row_offsets.searchsorted(offset, side="right") - 1
        stop = min(offset + limit, self.total)
        while offset < stop:
            sample = self.ordered_samples[order]
            active = [track for track in tracks if len(track.values) > sample]
            first = offset - self.row_offsets[order]
            last = min(len(active), first + stop - offset)
            for track in active[first:last]:
                yield track.observation(sample, self.clock)
            offset += last - first
            order += 1


def read_preview(path):
    path = Path(path)
    record = _read_record(path)
    data = record["data"]
    code = record.get("code")
    code = code if isinstance(code, dict) else {}
    declared = code.get("codes")
    declared = declared if isinstance(declared, dict) else {}
    associations = code.get("sites")
    associations = associations if isinstance(associations, dict) else {}
    lengths = [len(sequence) for categories in data.values() for sequence in categories.values()]
    steps = max(lengths, default=0)
    clock = Clock.from_times(record.get("times"), steps)
    sites, tracks = {}, {}
    keys, used_keys, used_categories = set(), set(), set()
    for site in dict.fromkeys((*data, *associations)):
        actual = data.get(site, {})
        assigned = associations.get(site)
        assigned = assigned if isinstance(assigned, (list, tuple)) else ()
        sites[site] = {}
        for category in dict.fromkeys((*actual, *(name for name in assigned if isinstance(name, str)))):
            sequence = actual.get(category)
            values = sequence.ivals if sequence is not None else np.empty(0, dtype=np.uint8)
            alphabet = (sequence.alphabet.svals if sequence is not None
                        else Alphabet(declared[category]).svals if category in declared else ())
            labels = tuple(alphabet)
            if len(values):
                counts = np.bincount(values.astype(np.intp, copy=False), minlength=len(labels))
                used_categories.add(category)
                used_keys.update((category, label) for label, count in zip(labels, counts) if count)
                tracks[site, category] = PreviewTrack(site, category, labels, values,
                                                       TimelineSpans.build(clock, values))
            else:
                counts = [0] * len(labels)
            keys.update((category, label) for label in labels)
            sites[site][category] = dict(zip(labels, map(int, counts)))

    # Legacy files declare their code alphabets inside each track.
    declared_names = set(declared) | {
        category for site in sites.values() for category in site
    }
    timed = np.isfinite(clock.starts)
    ordered = np.r_[np.flatnonzero(timed), np.flatnonzero(~timed)]
    active = np.cumsum(np.bincount(lengths, minlength=steps + 1)[::-1])[::-1][1:]
    offsets = np.r_[0, np.cumsum(active[ordered])]
    return PreviewData(path.name, sites, tracks, _code_colors(keys), tuple(sorted(used_keys)),
                       len(declared_names), len(used_categories), clock, clock.extent,
                       _session_metadata(record, code), ordered, offsets)


class PreviewReader:
    """A single worker with one replaceable pending read and no Tk references."""

    def __init__(self):
        self._condition = Condition()
        self._pending = self._result = self._current = None
        self._closed = False
        self._thread = None

    def request(self, token, path):
        with self._condition:
            self._current = token
            self._pending = (token, path) if path is not None else None
            self._result = None
            if self._pending is not None and self._thread is None:
                self._thread = Thread(target=self._work, name="CDX preview", daemon=True)
                self._thread.start()
            self._condition.notify()

    def take(self):
        with self._condition:
            result, self._result = self._result, None
            return result

    def close(self):
        with self._condition:
            self._closed = True
            self._current = self._pending = self._result = None
            self._condition.notify()

    def _work(self):
        cache = OrderedDict()
        while True:
            with self._condition:
                self._condition.wait_for(lambda: self._pending is not None or self._closed)
                if self._closed:
                    return
                (token, path), self._pending = self._pending, None
            try:
                path = path.resolve()
                info = path.stat()
                key = path, info.st_size, info.st_mtime_ns
                result = cache.get(key)
                if result is None:
                    result = read_preview(path)
                    current = path.stat()
                    if (current.st_size, current.st_mtime_ns) != key[1:]:
                        raise ValueError("The file changed while it was being read. Select it again.")
                    for outdated in tuple(cache):
                        if outdated[0] == path:
                            del cache[outdated]
                    if info.st_size <= 8 * 1024 * 1024:
                        cache[key] = result
                        if len(cache) > 4:
                            cache.popitem(last=False)
                else:
                    cache.move_to_end(key)
                error = None
            except Exception as exc:
                result, error = None, str(exc) or type(exc).__name__
            with self._condition:
                if token == self._current and not self._closed:
                    self._result = token, result, error
            del result  # Release uncached previews while the worker is idle.
