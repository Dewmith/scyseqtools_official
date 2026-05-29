import textwrap

import pytest

from scyseqtools.encoder.config import (
    APP_COMPONENT_NAME,
    APP_NAME,
    CONFIG_FILENAME,
    CWD_FILENAME,
    get_cwd_file_path,
    get_user_config_path,
    load_encoder_config,
)


@pytest.fixture(autouse=True)
def isolated_appdata(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))


def test_load_encoder_config_uses_bundled_defaults():
    config = load_encoder_config(
        required_sections=(
            "application",
            "infoframe",
            "playercontrol",
            "codingframework",
        )
    )

    assert config["application"]["cwd_file"] == "cwdfile.ini"
    assert config["application"]["default_cwd"] == "~"
    assert config["application"]["required_subfolders"] == "media,data"
    assert config["infoframe"]["background"] == "lightsteelblue"
    assert config["playercontrol"]["backend"] == "vlc"
    assert config["playercontrol"]["relief"] == "groove"
    assert config["codingframework"]["background"] == "palegoldenrod"


def test_load_encoder_config_creates_user_config_from_defaults():
    load_encoder_config(required_sections=("application",))

    user_config = get_user_config_path()
    assert user_config.exists()
    assert user_config.name == CONFIG_FILENAME
    assert user_config.parent.name == APP_COMPONENT_NAME
    assert user_config.parent.parent.name == APP_NAME
    assert user_config.read_text(encoding="utf-8").startswith("[application]")


def test_load_encoder_config_reads_user_config_before_cwd_override(tmp_path):
    user_config = get_user_config_path()
    user_config.parent.mkdir(parents=True, exist_ok=True)
    user_config.write_text(
        textwrap.dedent(
            """
            [infoframe]
            background = lavender

            [playercontrol]
            backend = mpv
            """
        ),
        encoding="utf-8",
    )

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "config.ini").write_text(
        textwrap.dedent(
            """
            [infoframe]
            background = plum
            """
        ),
        encoding="utf-8",
    )

    config = load_encoder_config(
        project_dir,
        required_sections=("infoframe", "playercontrol"),
    )

    assert config["infoframe"]["background"] == "plum"
    assert config["playercontrol"]["backend"] == "mpv"


def test_get_cwd_file_path_stores_relative_file_in_user_config_dir():
    config = load_encoder_config(required_sections=("application",))
    cwd_file = get_cwd_file_path(config)

    assert cwd_file.name == CWD_FILENAME
    assert cwd_file.parent == get_user_config_path().parent


def test_load_encoder_config_allows_cwd_override(tmp_path):
    (tmp_path / "config.ini").write_text(
        textwrap.dedent(
            """
            [infoframe]
            background = plum
            """
        ),
        encoding="utf-8",
    )

    config = load_encoder_config(tmp_path, required_sections=("infoframe",))

    assert config["infoframe"]["background"] == "plum"
    assert config["infoframe"]["relief"] == "groove"


def test_load_encoder_config_allows_application_cwd_override(tmp_path):
    (tmp_path / "config.ini").write_text(
        textwrap.dedent(
            """
            [application]
            required_subfolders = media,data,exports
            """
        ),
        encoding="utf-8",
    )

    config = load_encoder_config(tmp_path, required_sections=("application",))

    assert config["application"]["required_subfolders"] == "media,data,exports"
    assert config["application"]["cwd_file"] == "cwdfile.ini"


def test_load_encoder_config_integer_options_are_available_as_ints():
    config = load_encoder_config(
        required_sections=("infoframe", "playercontrol", "codingframework")
    )

    assert config["infoframe"].getint("borderwidth") == 2
    assert config["infoframe"].getint("filename_width") == 30
    assert config["playercontrol"].getint("borderwidth") == 2
    assert config["codingframework"].getint("panel_max") == 5


def test_load_encoder_config_reports_missing_required_section():
    with pytest.raises(ValueError, match="Missing encoder config section: missing"):
        load_encoder_config(required_sections=("missing",))
