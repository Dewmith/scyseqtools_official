import csv
from decimal import Decimal
import json
import os
import sys
import tkinter
from tkinter import filedialog, messagebox
from types import SimpleNamespace
from unittest.mock import Mock

import Pmw
import pytest
from scyseq.sequence import Alphabet, Sequence

from scyseqtools.analyser import kappa
from scyseqtools.analyser.analyser import _load_codix_appstate
from scyseqtools.analyser.sample_alignment import align_samples


MEDIA = "/study/session.mp4"
LABELS = ["Silent", "Speaking"]
STATES = [0, 0, 1, 0, 1, 1, 1, 0, 1, 0, 0, 1]
STREAMS = [("Room", "Speech"), ("Room", "Gaze"), ("Observer", "Speech")]


def record(start, end):
    times = list(range(start * 1000, end * 1000 + 1, 3000))
    values = STATES[start // 3:end // 3]
    return {
        "version": "0.9",
        "media": MEDIA,
        "times": times,
        "code": {"period": 3, "codes": {"Speech": LABELS, "Gaze": ["Away", "Task"]}},
        "data": {"Room": {"Speech": values, "Gaze": values[::-1]},
                 "Observer": {"Speech": values}},
    }


def pair(first, second, first_times, second_times, **timing):
    data = {"A.cdx": {"Room": {"Speech": first}}, "B.cdx": {"Room": {"Speech": second}}}
    metadata = {name: {"media": MEDIA, "times": times, **timing}
                for name, times in zip(data, (first_times, second_times))}
    return list(data), data, metadata


def table(files, data, metadata, **options):
    return kappa.build_kappa_table(files, data, STREAMS[:1], metadata=metadata, **options)


@pytest.mark.parametrize("a,b,shared", [
    ((0, 30), (0, 30), (0, 30)),
    ((0, 30), (6, 30), (6, 30)),
    ((0, 24), (0, 30), (0, 24)),
    ((0, 30), (6, 36), (6, 30)),
])
def test_complete_intervals_align_at_absolute_times(a, b, shared):
    meta_a, meta_b = record(*a), record(*b)
    alphabet = Alphabet(LABELS)
    first = Sequence(meta_a["data"]["Room"]["Speech"], alphabet)
    second = Sequence(meta_b["data"]["Room"]["Speech"], alphabet)
    before = (first.ivals.tolist(), second.ivals.tolist())
    x, y, match = align_samples(first, meta_a, second, meta_b)
    assert match.overlap.first == tuple(t * 1000 for t in a)
    assert match.overlap.second == tuple(t * 1000 for t in b)
    assert match.compared == match.overlap.common == tuple(t * 1000 for t in shared)
    assert x.ivals.tolist() == y.ivals.tolist() == STATES[shared[0] // 3:shared[1] // 3]
    assert x.alphabet.svals == y.alphabet.svals == tuple(LABELS)
    assert (first.ivals.tolist(), second.ivals.tolist()) == before
    files, data, metadata = pair(first, second, meta_a["times"], meta_b["times"], code={"period": 3})
    assert table(files, data, metadata) == (["comparison", "K Room-Speech"], [["A-B", "1"]])
    if a == b:
        assert table(files, data, metadata) == kappa.build_kappa_table(files, data, STREAMS[:1])
    elif a[1] - a[0] == b[1] - b[0]:
        assert kappa.cohen_kappa(first, second) != 1


@pytest.mark.parametrize("first,second,message", [
    ([0, 3000, 6000, 9000, 12000], [18000, 21000, 24000, 27000, 30000], "no common"),
    ([0, 3000, 6000], [6000, 9000, 12000], "no common"),
    ([0, 3000, 6000], [4500, 7500, 10500], "no comparable complete"),
    ([0, 3000, 6000, 9000, 12000], [0, 3000, 6300, 9000, 12000], "incompatible sampling grids"),
    ([0, 3000, 6000, 9000, 12000], [1000, 2000, 3000, 6000, 9000, 12000],
     "incompatible sampling grids"),
])
def test_comparison_rejects_unusable_grids(first, second, message):
    with pytest.raises(ValueError, match=message):
        table(*pair([0] * (len(first) - 1), [0] * (len(second) - 1), first, second))


def test_distinct_sampling_periods_are_rejected():
    files, data, metadata = pair([0, 1, 0, 1, 0], [0, 1, 0],
                                 [0, 3000, 6000, 9000, 12000, 15000], [0, 5000, 10000, 15000])
    metadata["A.cdx"]["code"] = {"period": 3}
    metadata["B.cdx"]["code"] = {"period": 5}
    with pytest.raises(ValueError, match="Different sampling periods"):
        table(files, data, metadata)


def test_partial_edges_and_decimal_milliseconds():
    x, y, match = align_samples([0, 1, 0, 0], {"times": [0, "3000.125", 6000, 9000, 12000]},
                                [0, 1, 0, 1], {"times": [1200, 3000.125, 6000, 9000, 10500]})
    assert (x, y) == ([1, 0], [1, 0])
    assert match.overlap.common == (1200, 10500)
    assert match.compared == (Decimal("3000.125"), 9000)


@pytest.mark.parametrize("times,message", [
    ("[0,3000,6000]", "invalid timestamp metadata"),
    ([0], "invalid timestamp metadata"),
    ([0, 3000, 6000, 9000], "invalid timestamp metadata"),
    ([0, None, 6000], "invalid timestamp"),
    ([0, False, 6000], "invalid timestamp"),
    ([0, "NaN", 6000], "finite"),
    ([0, "Infinity", 6000], "finite"),
    ([-1, 3000, 6000], "nonnegative"),
    ([0, 3000, 3000], "strictly increasing"),
    ([3000, 0, 6000], "strictly increasing"),
])
def test_malformed_metadata_cannot_fall_back(times, message):
    with pytest.raises(ValueError, match=message):
        table(*pair([0, 1], [0, 1], times, []), allow_legacy_index=True)


def test_missing_timing_cannot_be_mixed_with_a_complete_clock():
    with pytest.raises(ValueError, match="missing observation timestamps"):
        table(*pair([0, 1], [0, 1], [0, 3000, 6000], []), allow_legacy_index=True)


def test_incompatible_alphabets_and_empty_streams():
    a = Sequence([0, 1], Alphabet(LABELS))
    b = Sequence([0, 1], Alphabet(LABELS[::-1]))
    with pytest.raises(ValueError, match="B.cdx, Room/Speech has an incompatible coding alphabet"):
        table(*pair(a, b, [0, 3000, 6000], [0, 3000, 6000]))
    with pytest.raises(ValueError, match="no coded observations"):
        table(*pair(a, [], [0, 3000, 6000], [0]))


@pytest.mark.parametrize("first,second,message", [
    ([3000, 6000], [6000, 9000], "available legacy timestamps differ"),
    ([3000, 6000], [], "same length"),
])
def test_legacy_timing_must_not_contradict_index_comparisons(first, second, message):
    other = [0, 1] if second else [0]
    with pytest.raises(ValueError, match=message):
        table(*pair([0, 1], other, first, second), allow_legacy_index=True)


def test_unversioned_codix_and_estimated_timing_require_legacy_opt_in(tmp_path):
    legacy_record = {
        "media": MEDIA,
        "period": 3,
        "data": {"Room": {"Speech": {"seq": [0, 1], "dico": {"0": "Silent", "1": "Speaking"}}}},
        "times": [3000, 6000],
    }
    estimated = record(0, 6)
    estimated["timestamps_estimated"] = True
    estimated["data"] = {"Room": {"Speech": [0, 1]}}
    for name, source in zip(("A.cdx", "B.cdx"), (legacy_record, estimated)):
        (tmp_path / name).write_text(json.dumps(source), encoding="utf-8")
    state = _load_codix_appstate(tmp_path, ["A.cdx", "B.cdx"])
    args = (state["files"], state["data"], state["metadata"])
    with pytest.raises(ValueError, match="explicitly enabled") as exc:
        table(*args)
    assert "legacy timestamps" in str(exc.value) and "timestamps were estimated" in str(exc.value)
    assert table(*args, allow_legacy_index=True)[1] == [["A-B", "1"]]


def test_media_requires_a_shared_reference_or_identical_file(tmp_path):
    times = [0, 3000, 6000]
    files, data, metadata = pair([0, 1], [0, 1], times, times)
    first, second = metadata.values()
    first["media"] = r"C:\Study\Media\SESSION.mp4"
    second["media"] = "c:/study/media/subfolder/../session.mp4"
    assert table(files, data, metadata)[1] == [["A-B", "1"]]
    second["media"] = "session.mp4"
    with pytest.raises(ValueError, match="absolute media reference"):
        table(files, data, metadata)
    a, b = tmp_path / "a.mp4", tmp_path / "b.mp4"
    first["media"], second["media"] = str(a), str(b)
    a.write_bytes(b"test media")
    with pytest.raises(ValueError, match="common media timeline"):
        table(files, data, metadata)
    b.write_bytes(a.read_bytes())
    assert table(files, data, metadata)[1] == [["A-B", "1"]]
    b.write_bytes(b"other file")
    with pytest.raises(ValueError, match="common media timeline"):
        table(files, data, metadata)


@pytest.mark.skipif(sys.platform.startswith("linux") and not os.environ.get("DISPLAY"),
                    reason="Tk window tests require a display")
def test_load_confirm_and_export_distinct_pairwise_overlaps(tmp_path, monkeypatch, capsys):
    data_dir, output = tmp_path / "data", tmp_path / "output"
    data_dir.mkdir()
    output.mkdir()
    files = ["A.cdx", "B.cdx", "C.cdx"]
    paths = [data_dir / name for name in files]
    for path, bounds in zip(paths, [(0, 24), (6, 30), (12, 36)]):
        path.write_text(json.dumps(record(*bounds)), encoding="utf-8")
    original = [path.read_bytes() for path in paths]

    state = _load_codix_appstate(data_dir, files)
    confirm = Mock(return_value=SimpleNamespace(result=False))
    choose = Mock(return_value=str(output))
    errors = Mock()
    engine = Mock(wraps=kappa._sample_kappa)
    monkeypatch.setattr(kappa, "_ConfirmKappa", confirm)
    monkeypatch.setattr(kappa, "_sample_kappa", engine)
    monkeypatch.setattr(filedialog, "askdirectory", choose)
    monkeypatch.setattr(messagebox, "showerror", errors)
    with capsys.disabled():
        app = tkinter.Tk()
    try:
        app.withdraw()
        Pmw.initialise(app)
        tool = kappa.KappaTool(SimpleNamespace(notebook=Pmw.NoteBook(app), cwd=str(tmp_path)))
        tool.update_state(state)
        tool.launch()
        confirm.assert_called_once()
        assert confirm.call_args.args[1] == "Different recording time ranges detected"
        for span in ("6.000–24.000", "12.000–24.000", "12.000–30.000"):
            assert f"Common interval · {span} seconds" in confirm.call_args.args[-1]
        assert not engine.called and not choose.called and tool.panel.result is None

        confirm.return_value.result = True
        tool.launch()
        errors.assert_not_called()
        assert engine.call_count == 9
        result = tool.panel.result
        csv_path, html_path = result.paths(output)
        with csv_path.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.reader(stream, delimiter=";"))
        assert rows[0] == ["comparison", "K Room-Speech", "K Room-Gaze", "K Observer-Speech"]
        expected = []
        for first, second, left, right in [("A", "B", slice(2, 8), slice(0, 6)),
                                            ("A", "C", slice(4, 8), slice(0, 4)),
                                            ("B", "C", slice(2, 8), slice(0, 6))]:
            a = state["data"][f"{first}.cdx"]["Room"]["Gaze"][left]
            b = state["data"][f"{second}.cdx"]["Room"]["Gaze"][right]
            expected.append([f"{first}-{second}", "1", kappa.format_kappa(kappa.cohen_kappa(a, b)), "1"])
        assert rows[1:] == expected
        assert [path.read_bytes() for path in paths] == original
        assert [len(group) for group in result.details] == [3, 3, 3]
        report = html_path.read_text(encoding="utf-8")
        for text in ("A.cdx · 0–24000 ms", "B.cdx · 6000–30000 ms", "C.cdx · 12000–36000 ms",
                     "Common interval · 12000–30000 ms", "Compared interval · 12000–24000 ms",
                     "Compared 4 samples.", "Compared 6 samples."):
            assert text in report

        engine.reset_mock()
        confirm.return_value.result = False
        tool.launch()
        assert not engine.called and choose.call_count == 1 and tool.panel.result is result

        state["metadata"]["C.cdx"]["times"] = list(range(24000, 48001, 3000))
        confirm.reset_mock()
        tool.launch()
        assert "A.cdx and C.cdx" in errors.call_args.kwargs["message"]
        assert "no common observation interval" in errors.call_args.kwargs["message"]
        assert not confirm.called and not engine.called and choose.call_count == 1
        assert tool.panel.result is result

        tool.time_checkbox.invoke()
        tool.launch()
        assert "no common observation interval" in errors.call_args.kwargs["message"]
        assert not confirm.called and tool.panel.result is result
    finally:
        app.destroy()


def test_legacy_gui_confirms_and_labels_exports(monkeypatch, tmp_path):
    files, data, metadata = pair([0, 1], [0, 1], None, [])
    dialog = Mock(return_value=SimpleNamespace(result=False))
    monkeypatch.setattr(kappa, "_ConfirmKappa", dialog)
    tool = object.__new__(kappa.KappaTool)
    tool.selected_files, tool.gdata, tool.metadata = files, data, metadata
    tool.parent = SimpleNamespace(cwd=tmp_path)
    tool.tab, tool.panel = Mock(), Mock()
    tool.time_aligned = Mock(get=Mock(return_value=False))
    tool._selected_site_codes = Mock(return_value=STREAMS[:1])
    tool.launch()
    tool.panel.present.assert_not_called()
    assert "same intervals in the same order" in dialog.call_args.args[2]
    dialog.return_value.result = True
    tool.launch()
    result = tool.panel.present.call_args.args[0]
    assert result.filename == "Room_Speech_kappa_index_based.csv"
    assert "Legacy index-based Kappa" in "".join(result.html())
