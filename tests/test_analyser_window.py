import json
import os
import sys
from tkinter import filedialog
from unittest.mock import Mock, call

import pytest

from scyseqtools import applicationmenu
from scyseqtools.analyser.analyser import Application, _load_codix_appstate


@pytest.fixture
def framework_files(tmp_path):
    reference = {
        "version": "0.9",
        "media": "reference.mp4",
        "times": [0, 1000],
        "code": {"codes": {"Gaze": ["Away", "Task"], "Speech": ["Silent", "Speaking"]}},
        "data": {"Room": {"Gaze": [1], "Speech": [0]}, "Observer": {"Gaze": [0]}},
    }
    (tmp_path / "reference.cdx").write_text(json.dumps(reference), encoding="utf-8")

    def load_pair(**changes):
        candidate = {**reference, **changes}
        (tmp_path / "candidate.cdx").write_text(json.dumps(candidate), encoding="utf-8")
        return _load_codix_appstate(tmp_path, ("reference.cdx", "candidate.cdx"))

    return reference, load_pair


@pytest.mark.parametrize(("sites", "difference"), [
    (("Room",), "missing site 'Observer'"),
    (("Room", "Observer", "Outside"), "unexpected site 'Outside'"),
    (("room", "Observer"), "missing site 'Room', unexpected site 'room'"),
])
def test_load_rejects_different_sites(framework_files, sites, difference):
    reference, load_pair = framework_files
    data = {site: reference["data"].get(site, reference["data"]["Room"]) for site in sites}
    with pytest.raises(ValueError) as error:
        load_pair(data=data)
    assert "candidate.cdx" in str(error.value) and "reference.cdx" in str(error.value)
    assert difference in str(error.value)


@pytest.mark.parametrize(("categories", "difference"), [
    (("Gaze",), "missing category 'Speech'"),
    (("Gaze", "Speech", "Movement"), "unexpected category 'Movement'"),
    (("gaze", "Speech"), "missing category 'Gaze', unexpected category 'gaze'"),
])
def test_load_rejects_different_categories_at_a_site(framework_files, categories, difference):
    reference, load_pair = framework_files
    data = {**reference["data"], "Room": {category: [0] for category in categories}}
    codes = {**reference["code"]["codes"], "Movement": ["Still"], "gaze": ["Away", "Task"]}
    with pytest.raises(ValueError) as error:
        load_pair(data=data, code={"codes": codes})
    assert "Site 'Room'" in str(error.value)
    assert difference in str(error.value)


@pytest.mark.parametrize("labels", [["Away", "Elsewhere"], ["Task", "Away"], ["Away", "Task", "Other"]])
def test_load_rejects_different_state_labels(framework_files, labels):
    reference, load_pair = framework_files
    codes = {**reference["code"]["codes"], "Gaze": labels}
    with pytest.raises(ValueError, match="State labels differ at site 'Room', category 'Gaze'") as error:
        load_pair(code={"codes": codes})
    assert "Expected ('Away', 'Task')" in str(error.value)
    assert f"Found {tuple(labels)!r}" in str(error.value)


def test_load_accepts_the_same_framework_in_a_different_order(framework_files):
    _, load_pair = framework_files
    state = load_pair(
        media="different.mp4", times=[500, 700, 1500],
        data={"Observer": {"Gaze": [0, 1]}, "Room": {"Speech": [0, 1], "Gaze": [1, 0]}},
    )
    assert state["files"] == ["reference.cdx", "candidate.cdx"]
    assert state["sites"] == ["Room", "Observer"]
    assert state["codes"] == {"Room": ["Gaze", "Speech"], "Observer": ["Gaze"]}
    assert state["metadata"]["candidate.cdx"]["times"] == [500, 700, 1500]
    assert len(state["data"]["candidate.cdx"]["Room"]["Gaze"]) == 2


def test_load_checks_a_framework_with_no_sites(tmp_path, framework_files):
    empty = {"version": "0.9", "code": {"codes": {}}, "data": {}}
    (tmp_path / "empty.cdx").write_text(json.dumps(empty), encoding="utf-8")
    assert _load_codix_appstate(tmp_path, ("empty.cdx",))["data"] == {"empty.cdx": {}}
    with pytest.raises(ValueError, match="unexpected site"):
        _load_codix_appstate(tmp_path, ("empty.cdx", "reference.cdx"))


def test_get_directory_lists_only_cdx_files(monkeypatch, tmp_path):
    mixed_dir = tmp_path / "mixed"
    mixed_dir.mkdir()
    for name in ("first.cdx", "second.CDX", "report.html", "original.jod"):
        (mixed_dir / name).touch()
    nested_dir = mixed_dir / "folder.cdx"
    nested_dir.mkdir()
    (nested_dir / "nested.cdx").touch()

    no_cdx_dir = tmp_path / "no_cdx"
    no_cdx_dir.mkdir()
    (no_cdx_dir / "report.html").touch()

    choose_directory = Mock(side_effect=[str(mixed_dir), str(no_cdx_dir)])
    monkeypatch.setattr(filedialog, "askdirectory", choose_directory)
    app = Mock(spec=["ddir", "available", "_clear_file_preview", "_clear_loaded_files"])

    Application.get_directory(app)
    (visible_files,), _ = app.available.setlist.call_args
    assert sorted(visible_files) == ["first.cdx", "second.CDX"]

    Application.get_directory(app)
    app.available.setlist.assert_called_with([])
    assert app._clear_file_preview.call_count == 2


@pytest.mark.skipif(
    sys.platform.startswith("linux") and not os.environ.get("DISPLAY"),
    reason="Tk window tests require a display",
)
def test_window_title_and_help_menu(monkeypatch, capsys):
    open_tab = Mock(return_value=True)
    monkeypatch.setattr(applicationmenu.webbrowser, "open_new_tab", open_tab)
    # Tcl caches Windows standard handles for the interpreter's lifetime.
    with capsys.disabled():
        app = Application()
    try:
        assert app.title() == "scyseqtools"
        assert app.notebook.getcurselection() == "Configuration"
        menu_bar = app.nametowidget(app.cget("menu"))
        assert menu_bar.entrycget(0, "label") == "Help"

        app.notebook.selectpage("Kappa")
        app.update_idletasks()
        assert app.notebook.getcurselection() == "Kappa"
        assert app.nametowidget(app.cget("menu")) is menu_bar

        help_menu = app.nametowidget(menu_bar.entrycget("Help", "menu"))
        assert help_menu.index("end") == 1
        assert help_menu.entrycget(0, "label") == "Report issue"
        assert help_menu.entrycget(1, "label") == "About"
        help_menu.invoke(0)
        help_menu.invoke(1)
        assert open_tab.call_args_list == [
            call("https://github.com/scyseq-tools/scyseqtools/issues/new"),
            call("https://github.com/scyseq-tools/scyseqtools#readme"),
        ]
    finally:
        app.destroy()
