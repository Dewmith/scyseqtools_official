import configparser
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scyseqtools.encoder.playerbackends import (
    PlayerBackendError,
    VlcPlayerBackend,
    configured_backend_name,
    normalize_backend_name,
)


def playercontrol_section(backend=None):
    config = configparser.ConfigParser()
    config.add_section("playercontrol")
    if backend is not None:
        config["playercontrol"]["backend"] = backend
    return config["playercontrol"]


def test_configured_backend_name_defaults_to_vlc():
    assert configured_backend_name(playercontrol_section()) == "vlc"


def test_configured_backend_name_accepts_explicit_vlc():
    assert configured_backend_name(playercontrol_section("vlc")) == "vlc"


def test_configured_backend_name_accepts_explicit_mpv():
    assert configured_backend_name(playercontrol_section("mpv")) == "mpv"


def test_configured_backend_name_normalizes_case_and_spacing():
    assert configured_backend_name(playercontrol_section(" MPV ")) == "mpv"


def test_configured_backend_name_rejects_invalid_backend():
    with pytest.raises(PlayerBackendError, match="Unsupported media player backend"):
        configured_backend_name(playercontrol_section("bad-player"))


def test_normalize_backend_name_defaults_to_vlc_for_empty_value():
    assert normalize_backend_name("") == "vlc"


def test_vlc_waits_for_pause_before_exposing_seek(monkeypatch):
    states = SimpleNamespace(Playing=3, Paused=4, Ended=6, Error=7)
    monkeypatch.setitem(sys.modules, "vlc", SimpleNamespace(State=states))
    monkeypatch.setattr("scyseqtools.encoder.playerbackends.time.sleep", lambda delay: None)
    backend = object.__new__(VlcPlayerBackend)
    backend._player = Mock()
    backend._player.get_state.side_effect = [1, 2, states.Playing, states.Paused]
    backend.load("clip.wav")
    backend._player.set_pause.assert_called_once_with(do_pause=1)
    assert backend._player.get_state.call_count == 4
