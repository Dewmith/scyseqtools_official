"""Explicit export results shared by analyser operations and the GUI writer."""

from dataclasses import dataclass

from scyseq.sequence import Sequence


@dataclass
class TableExport:
    """A CSV filename and serialized lines, including the header."""

    filename: str
    lines: list[str]


@dataclass
class SequenceExport:
    """One Codix file, with sequences indexed first by site, then by code."""

    filename: str
    sequences_by_site: dict[str, dict[str, Sequence]]


@dataclass
class SequenceExports:
    """Codix exports in source-file order, so source metadata stays aligned."""

    files: list[SequenceExport]
