import json
import os
import sys
from unittest.mock import Mock

import pytest

from scyseqtools.encoder import config, encoder, playercontrol


pytestmark = pytest.mark.skipif(
    sys.platform.startswith("linux") and not os.environ.get("DISPLAY"),
    reason="Tk window tests require a display",
)


@pytest.fixture
def launch(tmp_path, monkeypatch, capsys):
    settings = tmp_path / "settings"
    monkeypatch.setattr(config, "get_user_config_dir", lambda _: settings)
    monkeypatch.setattr(config, "get_user_state_dir", lambda _: settings)
    apps = []

    def open_encoder(layout="embedded", dpi=96):
        (tmp_path / "config.ini").write_text(f"[application]\nencoder_layout = {layout}\n")

        def choose_directory(parent, **kwargs):
            parent.tk.call("tk", "scaling", dpi / 72)
            return str(tmp_path)

        monkeypatch.setattr(encoder.filedialog, "askdirectory", choose_directory)
        # Tcl caches Windows standard handles for the interpreter's lifetime.
        with capsys.disabled():
            app = encoder.Application()
        apps.append(app)
        app.update()
        return app

    yield open_encoder
    for app in apps:
        if app.tk.call("info", "commands", "."):
            app.quit_session()


@pytest.mark.parametrize("dpi", [96, 144], ids=["100-percent", "150-percent"])
def test_home_layout_and_keyboard_order(launch, dpi):
    app = launch(dpi=dpi)
    assert app.title() == "scyseqtools"
    assert app.menu.index("end") == 0
    assert app.menu.entrycget(0, "label") == "Help"

    heading, *buttons = app.home.winfo_children()
    assert heading.cget("text") == "scyseqtools"
    assert [button.cget("text") for button in buttons] == [
        "Define a new code", "Start a new session", "Retrieve a session", "Quit",
    ]
    assert len({button.winfo_width() for button in buttons}) == 1
    for widget in (heading, *buttons):
        x = widget.winfo_rootx() - app.winfo_rootx()
        y = widget.winfo_rooty() - app.winfo_rooty()
        assert widget.winfo_viewable()
        assert 0 <= x <= app.winfo_width() - widget.winfo_width()
        assert 0 <= y <= app.winfo_height() - widget.winfo_height()
    for current, following in zip(buttons, buttons[1:] + buttons[:1]):
        assert current.tk_focusNext() == following

    buttons[-1].invoke()
    assert not app.tk.call("info", "commands", ".")


def test_saving_code_returns_to_home(launch, tmp_path, monkeypatch):
    app = launch()
    app.home.buttons[0].invoke()
    app.update()
    assert not app.home.winfo_ismapped()
    form = app.newcode
    form.project_name.set("Observation")
    form.description_text.insert("1.0", "Example")
    form.tmpcode.set("movement")
    form.tmpitems.set("still,moving")
    form.record_code()
    form.tmpsite.set("Participant")
    form.codelist.selection_set(0)
    form.record_site()
    code_file = tmp_path / "data" / "observation.jod"
    monkeypatch.setattr(encoder.filedialog, "asksaveasfilename", lambda **kw: str(code_file))
    confirm = Mock(return_value=False)
    monkeypatch.setattr(encoder.tkinter.messagebox, "askokcancel", confirm)
    form.record_all()
    app.update()

    assert code_file.is_file()
    assert not form.winfo_exists()
    assert app.home.winfo_viewable()
    assert app.focus_lastfor() == app.home.buttons[0]
    confirm.assert_not_called()


def back_button(window):
    button, = window.grid_slaves(row=0, column=0)
    assert button.cget("text") == "Back to main menu"
    assert button.winfo_viewable()
    return button


@pytest.mark.parametrize("layout", ["embedded", "detached"])
def test_back_from_unstarted_workflows(launch, layout, monkeypatch):
    app = launch(layout)
    directory = app.cwd
    confirm = Mock(return_value=False)
    choose_directory = Mock()
    monkeypatch.setattr(encoder.tkinter.messagebox, "askokcancel", confirm)
    monkeypatch.setattr(encoder.filedialog, "askdirectory", choose_directory)
    for action in app.home.buttons:
        action.invoke()
        app.update()
        back_button(app).invoke()
        app.update()
        assert app.home.winfo_viewable()
        assert app.cwd == directory
        assert app.title() == "scyseqtools"
        assert app.focus_lastfor() == app.home.buttons[0]
    confirm.assert_not_called()
    choose_directory.assert_not_called()


def test_back_with_unsaved_code(launch, monkeypatch):
    app = launch()
    app.new_code()
    app.update()
    app.newcode.tmpitems.set("draft")
    confirm = Mock(side_effect=[False, True])
    monkeypatch.setattr(encoder.tkinter.messagebox, "askokcancel", confirm)
    back_button(app).invoke()
    assert app.newcode.tmpitems.get() == "draft"
    back_button(app).invoke()
    app.update()
    assert confirm.call_count == 2
    assert app.home.winfo_viewable()
    app.new_code()
    assert not app.newcode.has_input()


@pytest.mark.parametrize("layout,origin", [
    ("embedded", "Information"), ("detached", "Information"),
    ("detached", "Control"), ("detached", "Coding framework"),
])
@pytest.mark.parametrize("resume", [False, True], ids=["new", "retrieved"])
def test_back_during_playback(launch, tmp_path, monkeypatch, layout, origin, resume):
    app = launch(layout)
    player = Mock()
    player.get_length.return_value = 60000
    player.get_time.return_value = 0
    monkeypatch.setattr(playercontrol, "create_player_backend", lambda *args: player)
    media = tmp_path / "clip.wav"
    media.touch()
    code = tmp_path / "scheme.jod"
    scheme = {"filename": code.as_posix(), "codes": {"gaze": ["away"]},
              "sites": {"Observer": ["gaze"]}, "period": 1}
    code.write_text(json.dumps(scheme))
    data = tmp_path / "session.cdx"
    saved = json.dumps({"code": scheme, "media": media.as_posix(), "times": [0, 1000],
                        "data": {"Observer": {"gaze": [0]}}, "comments": ["first"]})
    data.write_text(saved)
    if resume:
        app.retrieve_session()
        monkeypatch.setattr(encoder.U, "is_valid_media", lambda path: True)
        app.info.read_data(str(data))
        assert app.recorded_steps == {1}
    else:
        app.start_session()
        app.make_media_player(str(media))
        app.make_coding_frame(str(code))
    app.update()
    window = {"Information": app, "Control": app._control_window,
              "Coding framework": app._coding_window}[origin]
    windows = [w for w in (app._control_window, app._coding_window) if w]
    control = app.control
    control.step_play(30)
    job = control._step_after_id
    control.step_play(30)
    assert control._step_after_id == job
    confirm = Mock(side_effect=[False, True])
    monkeypatch.setattr(encoder.tkinter.messagebox, "askokcancel", confirm)
    button = back_button(window)
    button.invoke()
    assert confirm.call_args.kwargs["parent"] is window
    assert control.state == "s_playing"
    player.close.assert_not_called()
    button.invoke()
    app.update()
    player.close.assert_called_once_with()
    assert job not in app.tk.call("after", "info")
    assert all(not w.winfo_exists() for w in windows)
    assert app.home.winfo_viewable()
    assert app.focus_lastfor() == app.home.buttons[0]
    assert data.read_text() == saved
    assert json.loads(code.read_text()) == scheme
    app.start_session()
    assert not any(app.state.values())
    assert app.container["data"] == {} and app.container["times"] == []
    assert not app.recorded_steps
    assert app.context == "standard" and app.time_step is None


@pytest.mark.parametrize("layout", ["embedded", "detached"])
@pytest.mark.parametrize("action,states", [
    ("Start a new session", ("normal", "disabled", "disabled")),
    ("Retrieve a session", ("disabled", "disabled", "normal")),
])
def test_session_buttons_open_the_selected_workflow(launch, layout, action, states):
    app = launch(layout)
    button = next(b for b in app.home.buttons if b.cget("text") == action)
    button.invoke()
    app.update()
    assert not app.home.winfo_ismapped()
    assert app.info.winfo_viewable()
    assert tuple(b.cget("state") for b in
                 (app.info.media_load, app.info.code_load, app.info.data_load)) == states
    if layout == "embedded":
        assert app.coding_workspace.winfo_viewable()
    else:
        assert app.coding_workspace is None
    app.tk.call(app.protocol("WM_DELETE_WINDOW"))
    assert not app.tk.call("info", "commands", ".")


def test_cancel_directory_exits_before_home(launch, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(encoder.filedialog, "askdirectory", lambda **kwargs: "")
    monkeypatch.setattr(encoder, "EncoderHome", lambda app: pytest.fail("Home opened on cancel"))
    with capsys.disabled():
        encoder._run_application()
    assert not (tmp_path / "settings" / config.CWD_FILENAME).exists()
    assert not (tmp_path / "data").exists()


def test_help_menu_on_home_screen_and_in_session(launch, monkeypatch):
    app = launch()
    open_tab = Mock(return_value=True)
    monkeypatch.setattr(encoder.webbrowser, "open_new_tab", open_tab)
    destinations = [
        ("Report issue", "https://github.com/scyseq-tools/scyseqtools/issues/new"),
        ("About", "https://github.com/scyseq-tools/scyseqtools#readme"),
    ]

    def check_menu():
        menu_bar = app.nametowidget(app.cget("menu"))
        menu = app.nametowidget(menu_bar.entrycget("Help", "menu"))
        assert menu.index("end") == len(destinations) - 1
        for index, (label, url) in enumerate(destinations):
            assert menu.entrycget(index, "label") == label
            menu.invoke(index)
            open_tab.assert_called_once_with(url)
            open_tab.reset_mock()

    assert app.home.winfo_viewable()
    check_menu()
    app.start_session()
    app.update()
    assert app.info.winfo_viewable()
    check_menu()


@pytest.mark.parametrize("error,copy_link", [
    (None, True),
    (encoder.webbrowser.Error("No browser available"), False),
    (OSError("Browser launch failed"), True),
])
def test_help_link_browser_failure(monkeypatch, error, copy_link):
    app = Mock()
    open_tab = Mock(return_value=False, side_effect=error)
    ask_copy = Mock(return_value=copy_link)
    monkeypatch.setattr(encoder.webbrowser, "open_new_tab", open_tab)
    monkeypatch.setattr(encoder.tkinter.messagebox, "askyesno", ask_copy)

    encoder.Application._open_project_page(app, "/issues/new")

    url = "https://github.com/scyseq-tools/scyseqtools/issues/new"
    open_tab.assert_called_once_with(url)
    ask_copy.assert_called_once()
    assert url in ask_copy.call_args.args[1]
    assert ask_copy.call_args.kwargs["parent"] is app
    if copy_link:
        app.clipboard_clear.assert_called_once_with()
        app.clipboard_append.assert_called_once_with(url)
    else:
        app.clipboard_clear.assert_not_called()
        app.clipboard_append.assert_not_called()
