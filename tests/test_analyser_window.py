import os
import sys
from tkinter import filedialog
from unittest.mock import Mock, call

import pytest

from scyseqtools import applicationmenu
from scyseqtools.analyser.analyser import Application


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
    app = Mock(spec=["ddir", "available", "_clear_loaded_files"])

    Application.get_directory(app)
    (visible_files,), _ = app.available.setlist.call_args
    assert sorted(visible_files) == ["first.cdx", "second.CDX"]

    Application.get_directory(app)
    app.available.setlist.assert_called_with([])


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
