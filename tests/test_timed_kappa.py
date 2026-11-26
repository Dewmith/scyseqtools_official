import csv
from decimal import Decimal
import os
import sys
import tkinter
from types import SimpleNamespace
from unittest.mock import Mock

import Pmw
import pytest
from scyseq.sequence import Alphabet, Sequence

from scyseqtools.analyser.kappa import KappaTool, build_time_kappa_table
from scyseqtools.analyser.timed_kappa import Timeline, parse_tolerance, time_agreement


def timeline(times, states):
    return Timeline.from_samples(times, states, "recording.cdx, Caregiver/speech")


def compare(a, b, tolerance):
    tolerance = parse_tolerance(tolerance)
    result = time_agreement(a, b, tolerance)
    assert result == time_agreement(b, a, tolerance)
    assert 0 <= result.credited <= result.disagreement <= result.duration
    return result


@pytest.mark.parametrize("delay,tolerance,strict,adjusted,credit", [
    (0, 0, "1", None, 0),
    (80, 100, ".960", "1", 80),
    (120, 100, ".940", ".940", 0),
    (100, 100, ".950", "1", 100),
    (0.5, ".5", ".99975", "1", Decimal(".5")),
])
def test_local_boundary(delay, tolerance, strict, adjusted, credit):
    a = timeline([0, 2000, 4000], [0, 1])
    b = timeline([0, 2000 + delay, 4000], [0, 1])
    result = compare(a, b, tolerance)
    assert result.strict == Decimal(strict)
    assert result.adjusted == (Decimal(adjusted) if adjusted else None)
    assert (result.duration, result.disagreement, result.credited) == (4000, delay, credit)


def test_multiple_local_transfers_use_adjusted_marginals():
    a = timeline([0, 800, 1400, 2000, 3000], [0, 0, 1, 2])
    b = timeline([0, 1470, 1980, 3000], [0, 1, 2])
    assert compare(a, b, 100).credited == 90
    result = compare(a, b, 50)
    # Only the 20 ms transition is credited. Adjusted diagonal durations
    # are 1400, 520 and 1010; 70 ms remains in cell (1, 0).
    chance_numerator = 1400*1470 + 590*520 + 1010*1010
    assert result.adjusted == 1 - Decimal(70*3000) / (3000**2 - chance_numerator)
    assert result.credited == 20
    assert a.times == [0, 800, 1400, 2000, 3000]
    assert b.states == [0, 1, 2]


@pytest.mark.parametrize("a,b", [
    (([0, 100, 300], [0, 1]), ([0, 90, 105, 115, 300], [0, 1, 0, 1])),
    (([0, 100, 300], [0, 1]), ([0, 110, 300], [1, 0])),
    (([0, 100, 300], [0, 1]), ([0, 110, 300], [0, 2])),
    (([0, 100, 105, 300], [0, 1, 2]), ([0, 110, 120, 300], [0, 1, 2])),
    (([0, 100, 115, 125, 300], [0, 1, 2, 3]),
     ([0, 105, 110, 120, 300], [2, 3, 0, 1])),
])
def test_ambiguous_overlapping_crossing_or_incompatible_transitions(a, b):
    result = compare(timeline(*a), timeline(*b), 50)
    assert result.credited == 0
    assert result.strict == result.adjusted


def test_reject_global_shift_in_grids_or_transition_train():
    a = timeline([0, 1000, 2000, 3000], [0, 1, 0])
    for b in (timeline([80, 1080, 2080, 3080], [0, 1, 0]),
              timeline([0, 200, 1080, 2080, 3000], [0, 0, 1, 0])):
        result = compare(a, b, 100)
        assert result.strict < 1 and result.credited == 0
        assert result.adjusted is None and "offset" in result.warning


def test_original_run_length_warning_and_unequal_partial_overlap():
    a = timeline([10, 110, 210, 310], [0, 0, 1])
    b = timeline([205, 235, 300], [0, 1])
    result = compare(a, b, 15)
    assert (result.start, result.end, result.duration, result.disagreement) == (205, 300, 95, 25)
    assert "shortest" in result.warning
    assert "shortest" not in compare(a, b, 14).warning


def test_overlap_edge_cannot_match_a_transition():
    a = timeline([0, 100, 200], [0, 1])
    b = timeline([100, 110, 200], [0, 1])
    assert compare(a, b, 20).credited == 0


def test_empty_overlap_and_constant_states():
    a = timeline([0, 100], [0])
    for times in ([100, 200], [101, 150]):
        result = compare(a, timeline(times, [0]), 10)
        assert result.strict is result.adjusted is result.start is result.end is None
        assert result.duration == 0 and "No overlapping" in result.warning
    result = compare(a, a, 1)
    assert result.strict is result.adjusted is None
    assert "expected agreement is one" in result.warning


@pytest.mark.parametrize("value", ["", "abc", "-1", "NaN", "inf", "-Infinity", None])
def test_invalid_tolerance(value):
    with pytest.raises(ValueError, match="finite, nonnegative"):
        parse_tolerance(value)


@pytest.mark.parametrize("times", [None, [], [0, 2], [0, 1, 1], [0, 3, 2],
                                    [0, "NaN", 2], [0, None, 2], [0, 1, "Infinity"]])
def test_timestamp_validation_names_stream(times):
    with pytest.raises(ValueError, match="recording.cdx, Caregiver/speech"):
        timeline(times, [0, 1])


def test_incompatible_alphabets():
    data = {f: {"S": {"C": Sequence([0, 1], Alphabet(labels))}}
            for f, labels in [("A", ["x", "y"]), ("B", ["y", "x"])]}
    metadata = {f: {"times": [0, 1, 2]} for f in data}
    with pytest.raises(ValueError, match="B, S/C: incompatible"):
        build_time_kappa_table(list(data), data, metadata, [("S", "C")], 0)


@pytest.mark.skipif(sys.platform.startswith("linux") and not os.environ.get("DISPLAY"),
                    reason="Tk window tests require a display")
def test_kappa_controls_and_export(tmp_path, monkeypatch, capsys):
    from tkinter import filedialog, messagebox
    monkeypatch.setattr(filedialog, "askdirectory", lambda **kwargs: str(tmp_path))
    monkeypatch.setattr(messagebox, "showinfo", Mock())
    error = Mock()
    monkeypatch.setattr(messagebox, "showerror", error)
    with capsys.disabled():
        app = tkinter.Tk()
    try:
        app.withdraw()
        Pmw.initialise(app)
        tab = KappaTool(SimpleNamespace(notebook=Pmw.NoteBook(app), cwd=str(tmp_path)))
        data = {name: {"S": {"C": [0, 1]}} for name in ("A", "B")}
        metadata = {name: {"times": [0, 2000, 4000], "media": "/study/session.mp4"}
                    for name in data}
        tab.update_state({"data": data, "files": list(data), "metadata": metadata})
        assert not tab.time_aligned.get() and tab.tolerance.get() == "0"
        assert tab.tolerance_entry.instate(["disabled"])
        tab.tolerance.set("invalid")
        tab.launch()
        assert (tmp_path / "S_C_kappa.csv").read_text().splitlines() == ["comparison;K S-C", "A-B;1"]
        data["B"]["S"]["C"] = [0]
        tab.launch()
        assert "invalid timestamp metadata" in error.call_args.kwargs["message"]
        data["B"]["S"]["C"] = [0, 1]
        metadata["B"]["times"] = [0, 2080, 4000]
        tab.time_checkbox.invoke()
        assert not tab.tolerance_entry.instate(["disabled"])
        tab.launch()
        assert "tolerance" in error.call_args.kwargs["message"]
        for tolerance in ("0", "100"):
            tab.tolerance.set(tolerance)
            tab.launch()
            with (tmp_path / f"S_C_kappa_time_aligned_{tolerance}ms.csv").open() as file:
                headers, row = csv.reader(file, delimiter=";")
            assert list(tab.results["columns"]) == headers
            item, = tab.results.get_children()
            assert [tab.results.set(item, col) for col in headers] == row
            assert row[headers.index("Strict kappa")] == "0.96"
            assert ("Adjusted kappa" in headers) == (tolerance != "0")
        del metadata["A"]["times"]
        tab.launch()
        assert "A — missing observation timestamps" in error.call_args.kwargs["message"]
    finally:
        app.destroy()
