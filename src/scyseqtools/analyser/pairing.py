"""Validate the sample alignment of tracks selected for a paired graph."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import ntpath
from pathlib import PureWindowsPath
import posixpath


@dataclass(frozen=True)
class Track:
    filename: str
    site: str
    code: str

    @property
    def label(self):
        return f"{self.filename} · {self.site} / {self.code}"


def _media_reference(value):
    if not isinstance(value, str):
        return None
    if PureWindowsPath(value).is_absolute():
        return "windows", ntpath.normcase(ntpath.normpath(value))
    if posixpath.isabs(value):
        return "posix", posixpath.normpath(value)
    return None


def _timestamps(record, track, length):
    times = record.get("times")
    if times is None or (isinstance(times, (list, tuple)) and not times):
        return None
    if not isinstance(times, (list, tuple)) or len(times) not in (length, length + 1):
        raise ValueError(
            f"{track.filename} must have {length} sample timestamps "
            f"or {length + 1} timestamp boundaries."
        )
    try:
        grid = tuple(Decimal(str(value)) for value in times)
    except InvalidOperation as exc:
        raise ValueError(f"{track.filename} has invalid timestamps.") from exc
    if any(not value.is_finite() for value in grid) or any(
        later <= earlier for earlier, later in zip(grid, grid[1:])
    ):
        raise ValueError(f"{track.filename} timestamps must be finite and strictly increasing.")
    return grid


def validate_pair(first, seq1, second, seq2, metadata):
    if first == second:
        raise ValueError("Choose two different tracks.")
    if not len(seq1) or not len(seq2):
        raise ValueError("Both tracks must have observations.")
    if len(seq1) != len(seq2):
        raise ValueError("The two tracks must have the same number of observations.")

    first_record = metadata.get(first.filename, {})
    first_grid = _timestamps(first_record, first, len(seq1))
    if first.filename == second.filename:
        return

    second_record = metadata.get(second.filename, {})
    first_media = _media_reference(first_record.get("media"))
    second_media = _media_reference(second_record.get("media"))
    if first_media is None or second_media is None:
        raise ValueError("Both CDX files need an absolute media reference to verify the recording.")
    if first_media != second_media:
        raise ValueError("The CDX files refer to different media recordings.")

    second_grid = _timestamps(second_record, second, len(seq2))
    if first_grid is None or second_grid is None:
        raise ValueError("Both CDX files need timestamps to verify sample alignment.")
    if len(first_grid) != len(second_grid):
        raise ValueError("The CDX files use different timestamp conventions.")
    if first_grid[0] != second_grid[0]:
        raise ValueError("The CDX files have different recording start timestamps.")
    if first_grid != second_grid:
        raise ValueError("The CDX files have different sample spacing.")
    if first.code == second.code and seq1.alphabet.svals != seq2.alphabet.svals:
        raise ValueError("The same code must have matching state labels in the same order.")
