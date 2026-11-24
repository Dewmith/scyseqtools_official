import os
import sys
from time import monotonic
import tkinter as tk

import pytest

from scyseqtools.analyser.output_files import SaveDestination, write_outputs
from scyseqtools.analyser.save_dialog import resolve_destinations


@pytest.fixture
def root(capsys):
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        pytest.skip("Tk window tests require a display")
    with capsys.disabled():
        window = tk.Tk()
        try:
            window.update()
            yield window
        finally:
            window.destroy()


def use_dialog(root, groups, action):
    errors = []
    deadline = monotonic() + 2

    def interact():
        dialog, = root.winfo_children()
        if monotonic() < deadline and (dialog.grab_current() != dialog or dialog.focus_lastfor() != dialog.entry):
            root.after(30, interact)
            return
        try:
            assert dialog.title() == "Save analysis file"
            assert dialog.grab_current() == dialog
            assert dialog.focus_lastfor() == dialog.entry
            assert dialog.entry.get() == ""
            buttons = {button.cget("text"): button for frame in dialog.winfo_children()
                       for button in frame.winfo_children() if isinstance(button, tk.Button)}
            action(dialog, buttons)
        except Exception as exc:
            errors.append(exc)
        finally:
            if dialog.winfo_exists():
                dialog.cancel()

    root.after(30, interact)
    destinations = resolve_destinations(root, groups)
    if errors:
        raise errors[0]
    return destinations


@pytest.mark.parametrize("action", ["Replace", "Cancel", "Escape", "Close"])
def test_conflict_modal_actions(root, tmp_path, action):
    path = tmp_path / "analysis_results.csv"
    path.write_text("existing CSV")

    def choose(dialog, buttons):
        if action == "Escape":
            dialog.entry.focus_force()
            dialog.entry.event_generate("<Escape>")
            assert not dialog.winfo_exists()
        elif action == "Close":
            dialog.tk.call(dialog.protocol("WM_DELETE_WINDOW"))
            assert not dialog.winfo_exists()
        else:
            buttons[action].invoke()

    resolution = use_dialog(root, [(path,)], choose)
    assert resolution == ((SaveDestination(path, replace=True),) if action == "Replace" else None)
    assert path.read_text() == "existing CSV"


@pytest.mark.parametrize("new_name", ["new results", "new results.csv"])
def test_save_as_new_validates_in_the_dialog(root, tmp_path, new_name):
    path = tmp_path / "analysis_results.csv"
    path.mkdir()
    (tmp_path / "taken.csv").touch()

    def choose(dialog, buttons):
        assert buttons["Replace"].cget("state") == "disabled"
        for name, error in [("", "Enter a new file name"), ("../outside", "selected folder"),
                            ("other.svg", ".csv"), ("taken", "taken.csv is already in use")]:
            dialog.entry.delete(0, "end")
            dialog.entry.insert(0, name)
            buttons["Save as new"].invoke()
            assert error in dialog.error.cget("text")
        dialog.entry.delete(0, "end")
        dialog.entry.insert(0, new_name)
        buttons["Save as new"].invoke()

    destinations = use_dialog(root, [(path,)], choose)
    assert destinations == (SaveDestination(tmp_path / "new results.csv"),)
    assert path.is_dir()


def test_save_preserves_file_created_during_staging(tmp_path):
    path = tmp_path / "new.csv"
    destination, = resolve_destinations(None, [(path,)])

    def serialize(staged):
        staged.write_text("export")
        path.write_text("created by another program")

    with pytest.raises(FileExistsError):
        write_outputs([(destination, serialize)])
    assert path.read_text() == "created by another program"
    assert list(tmp_path.iterdir()) == [path]
