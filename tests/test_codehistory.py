import json
import os
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from scyseqtools.encoder import encoder, playercontrol
from scyseqtools.encoder.codehistory import filter_choices, observations, site_colors


tk_window = pytest.mark.skipif(
    sys.platform.startswith("linux") and not os.environ.get("DISPLAY"),
    reason="Tk window tests require a display",
)


@pytest.fixture
def scheme():
    return {"period": 3, "sites": {"parent": ["movement", "sound"], "child": ["sound"]},
            "codes": {"sound": ["quiet", "loud"], "movement": ["still", "quiet"]}}


def test_dynamic_filters_and_colors(scheme):
    encoding = {site: {c: scheme["codes"][c] for c in codes}
                for site, codes in scheme["sites"].items()}
    encoding["visitor"] = {"gaze": ["quiet", "away"]}
    data = {"child": {"sound": [0]}, "parent": {"sound": [1], "movement": [1]},
            "visitor": {"gaze": [0]}}
    choices = filter_choices(encoding)
    assert list(choices).count("Value: quiet") == 1
    assert list(observations(encoding, data, 1, choices["Site: parent"])) == [
        ("parent", "movement: quiet, sound: loud")]
    assert list(observations(encoding, data, 1, choices["Category: sound"])) == [
        ("child", "sound: quiet"), ("parent", "sound: loud")]
    assert list(observations(encoding, data, 1, choices["Value: quiet"])) == [
        ("child", "sound: quiet"), ("parent", "movement: quiet"), ("visitor", "gaze: quiet")]
    assert len(list(observations(encoding, data, 1, choices["All"]))) == 3
    assert not list(observations(encoding, data, 1, choices["Value: away"]))
    colors = site_colors(encoding)
    assert len(set(colors.values())) == 3
    assert colors == site_colors(dict(reversed(list(encoding.items()))))


@pytest.fixture
def session_files(tmp_path, monkeypatch, scheme):
    player = Mock()
    player.get_length.return_value = 60_000
    player.get_time.return_value = 0
    monkeypatch.setattr(playercontrol, "create_player_backend", Mock(return_value=player))
    monkeypatch.setattr(encoder.U, "media_track_types", lambda path: {"Audio"})
    media = tmp_path / "media.wav"
    media.touch()
    code = tmp_path / "framework.jod"
    scheme["filename"] = str(code)
    code.write_text(json.dumps(scheme))
    return media, code, tmp_path / "session.cdx", player


def apply_filter(history, choice):
    history.filter.set(choice)
    history.filter.event_generate("<<ComboboxSelected>>")
    return history.body.get("1.0", "end-1c")


def click_text(body, index):
    x, y, width, height = body.bbox(index)
    body.event_generate("<Button-1>", x=x + width // 2, y=y + height // 2)


def enter_sample(framework, sound, comment):
    for panel in framework.coding_frame.panels:
        panel.coding["sound"]["var"].set(sound)
        if "movement" in panel.coding:
            panel.coding["movement"]["var"].set("still")
    framework.coding_frame.comment.set(comment)


@tk_window
def test_record_filter_edit_and_reopen(launch, session_files, monkeypatch):
    media, code, path, player = session_files
    app = launch()
    app.start_session()
    history = app.code_history
    assert history.goto_button.instate(["disabled"])
    assert history.body.get("1.0", "end-1c") == ""
    assert app.info._load_media(str(media))
    app.make_coding_frame(code)
    frame = app.framework
    frame.spec_frame.person.set("Observer")
    frame.spec_frame.start_but.invoke()

    app.control.step_play(0, 3123)
    app.update()
    enter_sample(frame, "quiet", "first")
    monkeypatch.setattr(app, "choose_save_folder", Mock(side_effect=[None, path.parent]))
    monkeypatch.setattr(encoder.filedialog, "asksaveasfilename", lambda **kw: str(path))
    frame.coding_frame.record_but.invoke()
    assert not path.exists() and not history.step_lines
    assert frame.coding_frame.comment.get() == "first"
    frame.coding_frame.record_but.invoke()
    assert list(history.step_lines) == [1]

    app.control.step_play(0, 6123)
    app.update()
    enter_sample(frame, "loud", "second")
    frame.coding_frame.record_but.invoke()
    saved = path.read_bytes()
    assert json.loads(saved)["times"] == [0, 3123, 6123]
    shown = apply_filter(history, "Category: sound")
    assert shown.count("3.123") == shown.count("6.123") == 1
    assert shown.count("sound: quiet") == shown.count("sound: loud") == 2
    assert "movement" not in shown
    shown = apply_filter(history, "Value: quiet")
    assert "6.123" not in shown and history.goto_button.instate(["disabled"])
    assert app.time_step == 2
    app.update()
    click_text(history.body, "1.end-1c")
    assert history.selected_step == 1 and app.time_step == 2
    app.control.step_play(30)
    job = app.control._step_after_id
    history.goto_button.invoke()
    assert app.time_step == 1 and app.control.state == "paused"
    player.set_time.assert_called_with(3123)
    assert job not in app.tk.call("after", "info")
    assert frame.coding_frame.comment.get() == "first"
    parent = next(p for p in frame.coding_frame.panels if p.name == "parent")
    assert parent.coding["movement"]["var"].get() == "still"
    assert path.read_bytes() == saved

    apply_filter(history, "All")
    frame.coding_frame.comment.set("corrected")
    confirm = Mock(side_effect=[False, True])
    monkeypatch.setattr(encoder.tkinter.messagebox, "askokcancel", confirm)
    click_text(history.body, "3.0")
    assert app.time_step == history.selected_step == 1
    assert frame.coding_frame.comment.get() == "corrected"
    with monkeypatch.context() as fail:
        fail.setattr(Path, "replace", Mock(side_effect=OSError("write failed")))
        fail.setattr(encoder.tkinter.messagebox, "showerror", Mock())
        frame.coding_frame.record_but.invoke()
    assert path.read_bytes() == saved and frame.has_edits()
    enter_sample(frame, "loud", "corrected")
    frame.coding_frame.record_but.invoke()
    assert not frame.has_edits()
    assert history.body.get("1.0", "end").count("3.123") == 1
    click_text(history.body, "3.0")
    assert frame.coding_frame.comment.get() == "second"
    app.control.step_play(0, 9123)
    app.update()
    enter_sample(frame, "quiet", "discard me")
    click_text(history.body, "1.0")
    assert app.time_step == 1 and app.control.times == [0, 3123, 6123]
    assert confirm.call_count == 2
    click_text(history.body, "3.0")
    app.control.step_play(0, 9123)
    app.update()
    enter_sample(frame, "quiet", "third")
    frame.coding_frame.record_but.invoke()
    record = json.loads(path.read_bytes())
    assert record["times"] == [0, 3123, 6123, 9123]
    assert record["comments"] == ["corrected", "second", "third"]
    assert record["data"]["child"]["sound"] == [1, 1, 0]

    apply_filter(history, "Site: parent")
    history.select(2)
    for detached in (True, False, True):
        app.info.detach_check.invoke()
        app.update()
        assert (history.winfo_toplevel() == app._history_window) == detached
        assert history.filter.get() == "Site: parent" and history.selected_step == 2
    monkeypatch.setattr(encoder.tkinter.messagebox, "askokcancel", Mock(return_value=True))
    app._history_window.back_button.invoke()
    assert not history.winfo_exists()
    code.unlink()
    app.retrieve_session()
    saved = path.read_bytes()
    assert app.info.read_data(path)
    assert app.code_history.step_lines == {1: (1, 2), 2: (3, 4), 3: (5, 6)}
    assert app.goto_recorded_step(1) and app.context == "standard"
    assert app.framework.coding_frame.comment.get() == "corrected"
    assert str(app.framework.coding_frame.record_but["state"]) == "disabled"
    assert path.read_bytes() == saved


@tk_window
@pytest.mark.parametrize("times,expected", [
    ([0, 3127], [0, 3127]), ([127, 3127, 6127], [3127, 6127]), ([], [3000, 6000])
])
def test_resume_time_formats(launch, session_files, scheme, times, expected):
    media, code, path, player = session_files
    path.write_text(json.dumps({
        "code": scheme, "media": str(media), "times": times, "comments": ["first"],
        "data": {"parent": {"sound": [1, 0], "movement": [0, 1]}, "child": {"sound": [0, 1]}},
    }))
    code.write_text("{}")  # The on-disk definition has changed since recording.
    app = launch("detached")
    app.retrieve_session()
    original = path.read_bytes()
    assert app.info.read_data(path)
    assert path.read_bytes() == original
    assert list(app.code_history.times.values()) == expected
    assert app.goto_recorded_step(1)
    player.set_time.assert_called_with(expected[0])
    app.framework.spec_frame.person.set("Observer")
    app.framework.spec_frame.start_but.invoke()
    app.control.forward_but.invoke()
    player.set_time.assert_called_with(expected[1])
    assert app.framework.coding_frame.comment.get() == ""
    app.control.step_play(0, expected[1] + 3000)
    app.update()
    enter_sample(app.framework, "quiet", "continued")
    app.framework.coding_frame.record_but.invoke()
    saved = json.loads(path.read_bytes())
    assert saved["times"] == (times or [0, *expected]) + [expected[1] + 3000]
    assert saved["comments"] == ["first", "", "continued"]
    assert saved.get("timestamps_estimated", False) == (not times)


@tk_window
def test_long_history_keeps_scroll_position_across_layouts(launch, session_files, scheme):
    media, _, path, _ = session_files
    count = 80
    times = [345 + 500 * i for i in range(count)]
    path.write_text(json.dumps({
        "code": scheme, "media": str(media), "times": times,
        "data": {"child": {"sound": [0] * count},
                 "parent": {"movement": [1] * count, "sound": [0] * count}},
    }))
    app = launch()
    app.retrieve_session()
    assert app.info.read_data(path)
    history = app.code_history
    apply_filter(history, "Site: parent")
    app.geometry("1024x650")
    app.update()
    history.select(45, reveal=True)
    history.body.yview("40.0")
    app.update()
    first_line = history.body.index("@0,0").split(".")[0]
    assert first_line == "40"
    for _ in range(2):
        app.info.detach_check.invoke()
        app.update()
        assert history.selected_step == 45
        assert history.body.index("@0,0").split(".")[0] == first_line
        assert history.goto_button.winfo_viewable()


@tk_window
def test_resume_empty_history_and_record_first_step(launch, session_files, scheme):
    media, _, path, _ = session_files
    path.write_text(json.dumps({"code": scheme, "media": str(media), "data": {}}))
    app = launch()
    app.retrieve_session()
    assert app.info.read_data(path)
    history = app.code_history
    assert not history.times and history.goto_button.instate(["disabled"])
    assert "Site: child" in history.filter["values"]
    app.framework.spec_frame.person.set("Observer")
    app.framework.spec_frame.start_but.invoke()
    app.control.step_play(0, 3000)
    app.update()
    enter_sample(app.framework, "quiet", "first")
    app.framework.coding_frame.record_but.invoke()
    assert list(history.times.values()) == [3000]
    assert json.loads(path.read_bytes())["times"] == [0, 3000]


@tk_window
def test_legacy_samples_sharing_a_timestamp(launch, session_files, scheme):
    media, _, path, _ = session_files
    path.write_text(json.dumps({
        "code": scheme, "media": str(media), "times": [3000, 0, 3000],
        "comments": ["first at three", "at zero", "second at three"],
        "data": {"child": {"sound": [0, 1, 1]},
                 "parent": {"movement": [0, 1, 1], "sound": [1, 1, 0]}},
    }))
    app = launch()
    app.retrieve_session()
    assert app.info.read_data(path)
    history = app.code_history
    shown = history.body.get("1.0", "end")
    assert shown.index("0.000") < shown.index("3.000")
    assert shown.count("3.000") == 1
    history.select(3)
    assert tuple(map(str, history.body.tag_ranges("selected"))) == ("3.0", history.body.index("6.end"))
    history.goto_button.invoke()
    assert app.time_step == 3 and app.control.time == 3000
    assert app.framework.coding_frame.comment.get() == "second at three"
