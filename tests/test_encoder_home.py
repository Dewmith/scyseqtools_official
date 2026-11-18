import os
import sys
from unittest.mock import Mock

import pytest

from scyseqtools.encoder import config, encoder


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
    form.record_all()
    app.update()

    assert code_file.is_file()
    assert not form.winfo_exists()
    assert app.home.winfo_viewable()
    assert app.focus_lastfor() == app.home.buttons[0]


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
