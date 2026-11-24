import json
import os
import sys
from threading import Event
from time import monotonic, sleep
from tkinter import filedialog, messagebox
from unittest.mock import Mock

import pytest

from scyseqtools.analyser import preview_data
from scyseqtools.analyser.analyser import Application
from scyseqtools.analyser.file_preview import PAGE_SIZE, PLACEHOLDER


def _write(path, record):
    path.write_text(json.dumps(record), encoding="utf-8")
    return path


def _record():
    return {
        "version": "0.9",
        "media": "unavailable-video.mp4",
        "history": [["2026-01-05", "Observer A", "Practice session"]],
        "code": {
            "project": "Matching task",
            "description": "Training document",
            "sites": {"Participant": ["Gaze", "Speech", "Movement"], "Témoin": ["Gaze"],
                      "Empty site": []},
            "codes": {"Gaze": ["Away", "Task", "Unused"], "Speech": ["Silent", "Speaking"],
                      "Movement": ["Idle"], "Unassigned": ["Other"]},
        },
        "times": [1200, 1500, None, 2500, 3000, 3500],
        "data": {
            "Participant": {"Gaze": [0, 1, 1, 0, 0], "Speech": [1, 0, 1, 1, 0]},
            "Témoin": {"Gaze": [1, 0]},
        },
    }


def test_extract_metadata_counts_and_chronological_pages(tmp_path):
    path = _write(tmp_path / "session.cdx", _record())
    preview = preview_data.read_preview(path)

    assert preview.filename == path.name
    assert (preview.steps, preview.total, preview.used_codes, preview.declared_codes) == (5, 12, 2, 4)
    assert list(preview.sites) == ["Participant", "Témoin", "Empty site"]
    assert preview.sites["Participant"]["Gaze"] == {"Away": 3, "Task": 2, "Unused": 0}
    assert preview.sites["Participant"]["Movement"] == {"Idle": 0}
    assert preview.sites["Témoin"]["Gaze"] == {"Away": 1, "Task": 1, "Unused": 0}
    assert preview.extent == (1200, 3500)
    assert preview.clock.duration == 2300
    for text in ("Matching task", "Observer A", "Training document", "unavailable-video.mp4", "0.9"):
        assert text in preview.metadata

    rows = list(preview.page(0, 12))
    assert [row.start for row in rows] == [1200] * 3 + [1500] * 3 + [2500] * 2 + [3000] * 2 + [None] * 2
    assert [(row.site, row.key) for row in rows[:3]] == [
        ("Participant", ("Gaze", "Away")), ("Participant", ("Speech", "Speaking")),
        ("Témoin", ("Gaze", "Task")),
    ]
    assert (rows[0].end, rows[0].duration) == (1500, 300)
    assert rows[3].end is rows[3].duration is None
    assert list(preview.page(2, 9)) == rows[2:11]
    assert list(preview.page(12, 1)) == []


def test_timeline_preserves_gaps_and_parallel_tracks(tmp_path):
    preview = preview_data.read_preview(_write(tmp_path / "session.cdx", _record()))
    gaze = list(preview.tracks["Participant", "Gaze"].spans.visible(1200, 3500, 300))
    speech = list(preview.tracks["Participant", "Speech"].spans.visible(1200, 3500, 300))
    shorter = list(preview.tracks["Témoin", "Gaze"].spans.visible(1200, 3500, 300))

    assert [(mark.start, mark.end, mark.value) for mark in gaze] == [
        (1200, 1500, 0), (1500, 1500, 1), (2500, 3500, 0),
    ]
    assert [(mark.start, mark.end, mark.value) for mark in speech] == [
        (1200, 1500, 1), (1500, 1500, 0), (2500, 3000, 1), (3000, 3500, 0),
    ]
    assert [(mark.start, mark.end) for mark in shorter] == [(1200, 1500), (1500, 1500)]
    assert (gaze[-1].first, gaze[-1].last) == (3, 4)


def test_timeline_keeps_the_recording_end_when_the_final_sample_is_untimed(tmp_path):
    record = _record()
    record["times"][-2] = None
    preview = preview_data.read_preview(_write(tmp_path / "session.cdx", record))
    assert preview.extent == (1200, 3500)
    assert preview.clock.duration == 2300
    gaze = preview.tracks["Participant", "Gaze"]
    assert [(mark.start, mark.end) for mark in gaze.spans.visible(2500, 3500, 300)] == [(2500, 2500)]
    assert gaze.observation(4, preview.clock).start is None


@pytest.mark.parametrize("times,notice", [
    ([], "no observation timestamps"),
    ([10, 20], "count does not match"),
    ([10, 20, 15, 30, 35], "go backwards"),
])
def test_ambiguous_clocks_leave_observations_untimed(tmp_path, times, notice):
    record = _record()
    record["times"] = times
    preview = preview_data.read_preview(_write(tmp_path / "session.cdx", record))
    assert preview.extent is preview.clock.duration is None
    assert notice in preview.clock.notice
    assert all(row.start is row.end is None for row in preview.page(0, 12))
    assert all(not len(track.spans.starts) for track in preview.tracks.values())


def test_legacy_points_and_empty_track(tmp_path):
    path = _write(tmp_path / "legacy.cdx", {
        "times": [900, 900, 1250],
        "data": {"Room": {
            "Position": {"seq": [0, 1, 0], "dico": {"1": "Standing", "0": "Seated"}},
            "Speech": {"seq": [], "dico": {"0": "Silent"}},
        }},
    })
    preview = preview_data.read_preview(path)
    assert (preview.steps, preview.total, preview.used_codes, preview.declared_codes) == (3, 3, 1, 2)
    assert preview.sites["Room"]["Speech"] == {"Silent": 0}
    assert preview.clock.duration is None
    rows = list(preview.page(0, 3))
    assert [row.state for row in rows] == ["Seated", "Standing", "Seated"]
    assert [row.start for row in rows] == [900, 900, 1250]
    assert all(row.end is None for row in rows)
    marks = list(preview.tracks["Room", "Position"].spans.visible(900, 1250, 300))
    assert [(mark.start, mark.end, mark.mixed) for mark in marks] == [
        (900, 900, True), (1250, 1250, False),
    ]


def test_empty_current_session_and_mixed_empty_tracks(tmp_path):
    path = _write(tmp_path / "empty.cdx", {"version": "0.9", "data": {}})
    preview = preview_data.read_preview(path)
    assert preview.total == preview.steps == 0
    assert preview.extent is preview.clock.duration is None
    assert not list(preview.page(0, 5))

    record = _record()
    record["data"]["Participant"]["Movement"] = []
    preview = preview_data.read_preview(_write(path, record))
    assert preview.total == 12 and preview.sites["Participant"]["Movement"] == {"Idle": 0}


def test_preview_keeps_literal_utf8_labels_on_a_legacy_windows_code_page(tmp_path, monkeypatch):
    record = _record()
    record["code"]["codes"]["Gaze"][1] = "Visée"
    path = tmp_path / "unicode.cdx"
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    def upstream_read(path, data_only):
        return preview_data._decode_tracks(json.loads(path.read_text(encoding="cp1252")))

    monkeypatch.setattr(preview_data, "getpreferredencoding", lambda _: "cp1252")
    monkeypatch.setattr(preview_data.io, "read_codix", upstream_read)
    preview = preview_data.read_preview(path)
    assert preview.sites["Témoin"]["Gaze"]["Visée"] == 1


@pytest.mark.parametrize("content,message", [
    (" \n ", "This file is empty"),
    ("{broken", "Invalid CDX JSON"),
    ("{}", "Invalid CDX observation data"),
    ('{"data": {"Room":{"Speech":{"seq":[]}}}}', "dico"),
])
def test_invalid_files(tmp_path, content, message):
    path = tmp_path / "invalid.cdx"
    path.write_text(content, encoding="utf-8")
    with pytest.raises((ValueError, KeyError), match=message):
        preview_data.read_preview(path)


def test_colours_are_deterministic_and_distinguishable_for_large_alphabets():
    keys = [("Position", f"Label {index}") for index in range(80)]
    colors = preview_data._code_colors(keys)
    assert colors == preview_data._code_colors(reversed(keys))
    assert len(set(colors.values())) == len(keys)


@pytest.fixture
def app(capsys):
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        pytest.skip("Tk window tests require a display")
    with capsys.disabled():
        window = Application()
    window.geometry("1250x830")
    window.update()
    try:
        yield window
    finally:
        window.destroy()


def _wait(app, condition, seconds=8):
    deadline = monotonic() + seconds
    while monotonic() < deadline:
        app.update()
        if condition():
            return
        sleep(0.01)
    pytest.fail("The preview did not reach the expected state")


def _click(app, source, filename):
    app.update()
    source.names[filename].event_generate("<Button-1>", x=5, y=5)
    app.update()


def _choose(monkeypatch, app, *paths):
    monkeypatch.setattr(filedialog, "askdirectory", Mock(side_effect=[str(path) for path in paths]))
    app.get_directory()
    app.update()


def test_file_preview_is_independent_of_loading_and_removal(app, tmp_path, monkeypatch):
    directory = tmp_path / "inputs"
    directory.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    first = _write(directory / "first.cdx", _record())
    second = _write(directory / "second.CDX", _record())
    original = first.read_bytes(), first.stat().st_mtime_ns
    _choose(monkeypatch, app, directory, elsewhere)
    panel = app.file_preview
    assert panel.status.cget("text") == PLACEHOLDER

    _click(app, app.available, first.name)
    _wait(app, lambda: panel.data is not None)
    assert app.available.highlighted == first.name
    assert app.available.getcurselection() == ()
    assert app.selected_files == [] and app.data == {} and app.metadata == {}
    assert not (tmp_path / "analyzer_files").exists()

    app.available.checkboxes[second.name].invoke()
    assert app.available.getcurselection() == (second.name,)
    assert panel.status.cget("text") == first.name
    app.file_but.invoke()
    assert app.selected_files == [second.name]
    assert panel.status.cget("text") == first.name

    _click(app, app.selected, second.name)
    _wait(app, lambda: panel.status.cget("text") == second.name)
    assert app.selected.highlighted == second.name and app.available.highlighted is None
    assert app.selected.getcurselection() == ()
    app.selected.checkboxes[second.name].invoke()
    app.remove_but.invoke()
    assert app.selected_files == [] and app.data == {}
    assert app.available.highlighted == second.name
    assert panel.status.cget("text") == second.name

    app.get_directory()
    assert panel.status.cget("text") == PLACEHOLDER
    assert app.available.highlighted is None and panel.data is None
    assert (first.read_bytes(), first.stat().st_mtime_ns) == original


def test_incompatible_file_can_be_previewed_and_load_rejection_is_atomic(app, tmp_path, monkeypatch):
    directory = tmp_path / "inputs"
    directory.mkdir()
    baseline = _write(directory / "baseline.cdx", _record()).name
    compatible = _write(directory / "compatible.cdx", _record()).name
    different = _record()
    different["code"]["codes"]["Gaze"] = ["Elsewhere", "Task", "Unused"]
    incompatible = _write(directory / "incompatible.cdx", different).name
    _choose(monkeypatch, app, directory)

    app.available.checkboxes[baseline].invoke()
    app.file_but.invoke()
    assert app.selected_files == [baseline]
    loaded_data, metadata, working_directory = app.data, app.metadata, app.cwd
    update_methods = Mock(wraps=app._update_methods)
    monkeypatch.setattr(app, "_update_methods", update_methods)
    show_error = Mock()
    monkeypatch.setattr(messagebox, "showerror", show_error)

    _click(app, app.available, incompatible)
    _wait(app, lambda: app.file_preview.data is not None)
    preview = app.file_preview.data
    assert preview.sites["Participant"]["Gaze"]["Elsewhere"] == 3
    app.available.checkboxes[compatible].invoke()
    app.available.checkboxes[incompatible].invoke()
    app.selected.checkboxes[baseline].invoke()
    app.file_but.invoke()

    show_error.assert_called_once()
    message = show_error.call_args.kwargs["message"]
    assert baseline in message and incompatible in message
    assert "State labels differ at site 'Participant', category 'Gaze'" in message
    assert app.selected_files == [baseline] and app.selected.items == [baseline]
    assert app.selected.getcurselection() == (baseline,)
    assert set(app.available.getcurselection()) == {compatible, incompatible}
    assert app.data is loaded_data and app.metadata is metadata and app.cwd == working_directory
    assert app.file_preview.data is preview and app.available.highlighted == incompatible
    update_methods.assert_not_called()

    app.available.checkboxes[incompatible].invoke()
    app.file_but.invoke()
    assert app.selected_files == [baseline, compatible]
    assert app.file_preview.data is preview
    app.selected.checkboxes[compatible].invoke()
    app.remove_but.invoke()
    assert app.selected_files == [baseline]
    show_error.assert_called_once()


def test_switching_files_uses_latest_request_and_recovers_after_error(app, tmp_path, monkeypatch):
    started, release = Event(), Event()
    paths = [_write(tmp_path / f"{name}.cdx", _record()) for name in ("first", "skipped", "last")]
    bad = tmp_path / "broken.cdx"
    bad.write_text("invalid", encoding="utf-8")
    read = preview_data.read_preview

    def delayed(path):
        if path.name == "first.cdx":
            started.set()
            release.wait(10)
        return read(path)

    mock_read = Mock(side_effect=delayed)
    monkeypatch.setattr(preview_data, "read_preview", mock_read)
    _choose(monkeypatch, app, tmp_path)
    try:
        for index, path in enumerate(paths):
            _click(app, app.available, path.name)
            if index == 0:
                _wait(app, started.is_set)
        assert app.file_preview.data is None
    finally:
        release.set()
    _wait(app, lambda: app.file_preview.data is not None)
    assert app.file_preview.status.cget("text") == paths[-1].name
    assert [call.args[0].name for call in mock_read.call_args_list] == ["first.cdx", "last.cdx"]

    _click(app, app.available, bad.name)
    _wait(app, lambda: "Could not preview" in app.file_preview.status.cget("text"))
    assert app.file_preview.data is None
    _click(app, app.available, paths[-1].name)
    _wait(app, lambda: app.file_preview.data is not None)
    assert app.file_preview.status.cget("text") == paths[-1].name
    assert mock_read.call_count == 3

    edited = _record()
    edited["code"]["project"] = "Changed project on disk"
    _write(paths[-1], edited)
    _click(app, app.available, paths[-1].name)
    _wait(app, lambda: app.file_preview.data is not None)
    assert "Changed project on disk" in app.file_preview.data.metadata
    assert mock_read.call_count == 4


def test_preview_widgets_use_same_swatch_and_tooltip_shows_original_time(app, tmp_path, monkeypatch):
    path = _write(tmp_path / "preview.cdx", _record())
    _choose(monkeypatch, app, tmp_path)
    filename = app.available.names[path.name]
    filename.focus_force()
    app.update()
    filename.event_generate("<KeyPress-Return>")
    panel = app.file_preview
    _wait(app, lambda: panel.data is not None and bool(panel.sites.get_children()))

    tree = panel.sites
    site = tree.get_children()[0]
    tree.focus(site)
    tree.event_generate("<<TreeviewOpen>>")
    tree.item(site, open=True)
    _wait(app, lambda: bool(tree.get_children(site)) and tree.item(tree.get_children(site)[0], "text") == "Gaze")
    code = tree.get_children(site)[0]
    tree.focus(code)
    tree.event_generate("<<TreeviewOpen>>")
    tree.item(code, open=True)
    _wait(app, lambda: bool(tree.get_children(code)) and tree.item(tree.get_children(code)[0], "text") == "Away")
    leaf = tree.get_children(code)[0]
    first_event = panel.events.get_children()[0]
    assert tree.item(leaf, "image") == panel.events.item(first_event, "image")
    assert tree.item(leaf, "image")[0] == panel.legend.image_cget("1.0", "image")
    panel._details.invoke()
    assert "Practice session" in panel._metadata.get("1.0", "end")
    panel._details.invoke()
    app.update()

    timeline = panel.timeline
    _wait(app, lambda: bool(timeline._hits))
    for item, (track, mark) in timeline._hits.items():
        if track.site == "Participant" and track.category == "Gaze" and mark.start == 1200:
            left, top, right, bottom = timeline.body.coords(item)
            timeline.body.event_generate("<Motion>", x=round((left + right) / 2),
                                         y=round((top + bottom) / 2))
            break
    else:
        pytest.fail("The first interval was not rendered")
    _wait(app, timeline._tooltip.winfo_ismapped)
    assert timeline._tooltip.cget("text") == "Participant / Gaze · Away\nTimestamp 1.2 s · Duration 0.3 s"


def test_large_preview_bounds_rendering_and_supports_navigation(app, tmp_path, monkeypatch):
    steps = 100_000
    record = _record()
    record["times"] = list(range(0, steps * 100 + 1, 100))
    record["data"] = {"Participant": {"Gaze": [0, 1] * (steps // 2)}}
    record["code"]["sites"].update({f"Site {index:02}": [] for index in range(60)})
    path = _write(tmp_path / "large.cdx", record)
    _choose(monkeypatch, app, tmp_path)
    _click(app, app.available, path.name)
    panel = app.file_preview
    _wait(app, lambda: panel.data is not None)
    assert panel.data.total == steps
    assert len(panel.events.get_children()) == PAGE_SIZE
    assert panel._row_count.cget("text") == "1–200 of 100,000"
    panel._next.invoke()
    assert len(panel.events.get_children()) == PAGE_SIZE
    assert panel._row_count.cget("text") == "201–400 of 100,000"
    panel._prev.invoke()
    assert panel._row_count.cget("text") == "1–200 of 100,000"

    timeline = panel.timeline
    _wait(app, lambda: bool(timeline._hits))
    assert any(mark.mixed for _, mark in timeline._hits.values())
    assert len(timeline.body.find_all()) < 300
    full_start, full_end = timeline._view
    timeline._zoom(0.5)
    assert timeline._view[1] - timeline._view[0] == (full_end - full_start) / 2
    timeline._pan("moveto", "1.0")
    assert timeline._view[1] == full_end
    timeline.body.yview_moveto(1)
    app.update()
    assert not timeline._hits and len(timeline.body.find_all()) < 40

    before = panel.winfo_width()
    sash_x, sash_y = app.file_panes.sash_coord(0)
    app.file_panes.sash_place(0, sash_x - 100, sash_y)
    app.update()
    assert panel.winfo_width() > before
    app.geometry("645x425")
    app.update()
    assert panel.winfo_width() >= 275
    panel._viewport.yview_moveto(1)
    app.update()
    assert panel._viewport.yview()[1] == 1
