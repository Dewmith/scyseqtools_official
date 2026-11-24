"""Media-player backends for the encoder player control."""

import sys
import time


DEFAULT_BACKEND = "vlc"
SUPPORTED_BACKENDS = ("vlc", "mpv")


class PlayerBackendError(RuntimeError):
    """Raised when a configured media-player backend cannot be used."""


def prepare_video_display():
    """Initialize Xlib threading before Tk opens the display used by LibVLC."""
    if sys.platform.startswith("linux"):
        from ctypes import CDLL

        if not CDLL("libX11.so.6").XInitThreads():
            raise PlayerBackendError("Could not initialize X11 threading for video playback.")


def normalize_backend_name(name):
    """Return a supported backend name from config/user input."""
    backend_name = (name or DEFAULT_BACKEND).strip().lower()
    if backend_name not in SUPPORTED_BACKENDS:
        names = ", ".join(SUPPORTED_BACKENDS)
        raise PlayerBackendError(
            f"Unsupported media player backend '{backend_name}'. "
            f"Use one of: {names}."
        )
    return backend_name


def configured_backend_name(playercontrol_config):
    """Return the configured backend name from the playercontrol section."""
    return normalize_backend_name(playercontrol_config.get("backend", DEFAULT_BACKEND))


def create_player_backend(name, file_name, window_id=None):
    """Create the configured media-player backend."""
    backend_name = normalize_backend_name(name)
    if backend_name == "vlc":
        return VlcPlayerBackend(file_name, window_id)
    if backend_name == "mpv":
        return MpvPlayerBackend(file_name, window_id)
    raise AssertionError(f"Unhandled media player backend: {backend_name}")


class VlcPlayerBackend:
    """VLC implementation of the media-player backend API."""

    def __init__(self, file_name, window_id=None):
        try:
            import vlc
        except ImportError as exc:
            raise PlayerBackendError(
                "The VLC backend requires the python-vlc package and VLC 64-bit."
            ) from exc

        args = ["--no-xlib"]
        self._instance = vlc.Instance(args)
        self._player = self._instance.media_player_new()
        try:
            if window_id is not None:
                if sys.platform == "win32":
                    self._player.set_hwnd(window_id)
                else:
                    self._player.set_xwindow(window_id)
            self.load(file_name)
        except Exception:
            self.close()
            raise

    def load(self, file_name):
        import vlc

        media = self._player.set_mrl(file_name)
        media.release()  # The player retains its own reference.
        # VLC accepts play asynchronously and ignores seeks while still opening.
        # Expose the player to the encoder only once a paused seek can take effect.
        if self._player.play() == -1:
            raise PlayerBackendError("VLC could not start the selected media.")
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            state = self._player.get_state()
            if state == vlc.State.Paused:
                return
            if state == vlc.State.Playing:
                self.pause()
            elif state in (vlc.State.Error, vlc.State.Ended):
                raise PlayerBackendError(f"VLC could not prepare the selected media ({state}).")
            time.sleep(0.025)
        raise PlayerBackendError("VLC did not finish opening the selected media in time.")

    def play(self):
        self._player.play()

    def pause(self):
        self._player.set_pause(do_pause=1)

    def close(self):
        try:
            self._player.stop()
        finally:
            self._player.release()
            self._instance.release()

    def get_time(self):
        return self._player.get_time()

    def set_time(self, value):
        self._player.set_time(value)

    def get_length(self):
        return self._player.get_length()


class MpvPlayerBackend:
    """MPV implementation of the media-player backend API."""

    def __init__(self, file_name, window_id=None):
        try:
            import mpv
        except ImportError as exc:
            raise PlayerBackendError(
                "The MPV backend requires the optional 'mpv' Python package "
                "and system libmpv. Install with 'pip install scyseqtools[mpv]' "
                "or 'pip install mpv', and make sure libmpv is available."
            ) from exc

        player_factory = getattr(mpv, "MPV", None) or getattr(mpv, "Mpv", None)
        if player_factory is None:
            raise PlayerBackendError(
                "The MPV backend could not find python-mpv's MPV class."
            )

        try:
            options = {"wid": str(window_id)} if window_id is not None else {}
            if window_id is not None and sys.platform.startswith("linux"):
                # Tk supplies an XID even on a Wayland desktop using XWayland.
                options.update(gpu_context="x11egl", vo="gpu,x11")
            self._player = player_factory(**options)
            initialize = getattr(self._player, "initialize", None)
            if callable(initialize):
                initialize()
        except Exception as exc:
            raise PlayerBackendError(
                "The MPV backend could not start. Make sure system libmpv is "
                "installed and visible in PATH."
            ) from exc

        try:
            self.load(file_name)
        except Exception:
            self.close()
            raise

    def load(self, file_name):
        self._player.pause = True
        self._player.play(file_name)
        self._wait_for_duration()

    def play(self):
        self._player.pause = False

    def pause(self):
        self._player.pause = True

    def close(self):
        terminate = getattr(self._player, "terminate", None)
        if callable(terminate):
            terminate()
        else:
            self._player.command("quit")

    def get_time(self):
        time_pos = getattr(self._player, "time_pos", None)
        if time_pos is None:
            time_pos = getattr(self._player, "playback_time", None)
        if time_pos is None:
            return -1
        return int(round(time_pos * 1000))

    def set_time(self, value):
        self._player.command("seek", value / 1000.0, "absolute+exact")

    def get_length(self):
        duration = getattr(self._player, "duration", None)
        if duration is None:
            return -1
        return int(round(duration * 1000))

    def _wait_for_duration(self, attempts=10, delay=0.1):
        for _ in range(attempts):
            if self.get_length() > 0:
                break
            time.sleep(delay)
