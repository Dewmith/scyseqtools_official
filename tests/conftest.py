import pytest


@pytest.fixture
def launch(tmp_path, monkeypatch, capsys):
    from scyseqtools.encoder import config, encoder

    settings = tmp_path / "settings"
    monkeypatch.setattr(config, "get_user_config_dir", lambda config_dir=None: settings)
    monkeypatch.setattr(config, "get_user_state_dir", lambda config_dir=None: settings)
    settings.mkdir()
    apps = []

    def open_encoder(layout="embedded"):
        (settings / config.CONFIG_FILENAME).write_text(
            f"[application]\nencoder_layout = {layout}\ndefault_cwd = {tmp_path}\n",
            encoding="utf-8",
        )
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
