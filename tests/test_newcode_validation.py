import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scyseqtools.encoder import newcode


@pytest.fixture
def save_form(tmp_path, monkeypatch):
    # Call the real save handler with widget values, without opening a Tk window.
    form = SimpleNamespace(
        project_name=Mock(get=Mock(return_value="  Observation study  ")),
        description_text=Mock(
            get=Mock(return_value="  Observations with accents: é.\nSecond line.  ")
        ),
        regular=Mock(get=Mock(return_value=True)),
        period=Mock(get=Mock(return_value="2.5")),
        codes_container={"gaze": ["absent", "present"]},
        sites_container={"Participant": ["gaze"]},
        application=SimpleNamespace(cwd=str(tmp_path), finish_new_code=Mock()),
        destroy=Mock(),
        saved=False,
    )
    dialogs = SimpleNamespace(
        error=Mock(),
        info=Mock(),
        save=Mock(return_value=str(tmp_path / "framework")),
        create_directory=Mock(wraps=newcode.U.ensure_subdirectory),
    )
    monkeypatch.setattr(newcode.tkinter.messagebox, "showerror", dialogs.error)
    monkeypatch.setattr(newcode.tkinter.messagebox, "showinfo", dialogs.info)
    monkeypatch.setattr(newcode.tkinter.filedialog, "asksaveasfilename", dialogs.save)
    monkeypatch.setattr(newcode.U, "ensure_subdirectory", dialogs.create_directory)
    return form, dialogs


def assert_invalid_submission(form, dialogs, tmp_path):
    newcode.NewCode.record_all(form)

    dialogs.error.assert_called_once()
    title, message = dialogs.error.call_args.args
    assert title == "Invalid coding framework"
    dialogs.save.assert_not_called()
    dialogs.create_directory.assert_not_called()
    dialogs.info.assert_not_called()
    form.application.finish_new_code.assert_not_called()
    form.destroy.assert_not_called()
    assert not form.saved
    assert not list(tmp_path.iterdir())
    return message


@pytest.mark.parametrize("field", ["project_name", "description_text"])
@pytest.mark.parametrize("value", ["", " \t\n "])
def test_blank_required_text_prevents_saving(field, value, save_form, tmp_path):
    form, dialogs = save_form
    getattr(form, field).get.return_value = value

    message = assert_invalid_submission(form, dialogs, tmp_path)

    expected = "name of the project" if field == "project_name" else "description"
    assert expected in message
    assert getattr(form, field).get.return_value == value


@pytest.mark.parametrize(
    "field, expected",
    [("codes_container", "at least one code"),
     ("sites_container", "at least one recording site")],
)
def test_missing_recorded_definitions_prevent_saving(
    field, expected, save_form, tmp_path
):
    form, dialogs = save_form
    setattr(form, field, {})

    message = assert_invalid_submission(form, dialogs, tmp_path)

    assert expected in message


@pytest.mark.parametrize(
    "period", ["", " \t ", "not a number", "0", "-1", "inf", "-inf", "NaN", "1e999"]
)
def test_invalid_regular_period_prevents_saving(period, save_form, tmp_path):
    form, dialogs = save_form
    form.period.get.return_value = period

    message = assert_invalid_submission(form, dialogs, tmp_path)

    assert "period" in message


def test_all_validation_errors_appear_in_one_dialog(save_form, tmp_path):
    form, dialogs = save_form
    form.project_name.get.return_value = ""
    form.description_text.get.return_value = ""
    form.period.get.return_value = "invalid"
    form.codes_container = {}
    form.sites_container = {}

    message = assert_invalid_submission(form, dialogs, tmp_path)

    assert len(message.splitlines()) == 5
    for expected in (
        "name of the project", "description", "period", "at least one code",
        "at least one recording site",
    ):
        assert expected in message


@pytest.mark.parametrize("regular", [True, False])
def test_valid_framework_saves_json_and_html(regular, save_form, tmp_path):
    form, dialogs = save_form
    form.regular.get.return_value = regular
    if not regular:
        form.period.get.return_value = "ignored for continuous sampling"

    newcode.NewCode.record_all(form)

    dialogs.error.assert_not_called()
    dialogs.info.assert_not_called()
    dialogs.save.assert_called_once()
    dialogs.create_directory.assert_called_once_with(str(tmp_path), "data")
    saved_path = tmp_path / "framework.jod"
    specs = json.loads(saved_path.read_text(encoding="utf-8"))
    assert set(specs) == {
        "date", "version", "project", "description", "period", "codes", "sites",
        "filename",
    }
    assert specs["date"]
    assert specs["version"] == newcode.VERSION
    assert specs["project"] == form.project_name.get.return_value
    assert specs["description"] == form.description_text.get.return_value
    assert specs["period"] == (2.5 if regular else None)
    assert specs["codes"] == form.codes_container
    assert specs["sites"] == form.sites_container
    assert specs["filename"] == str(saved_path)
    html = (tmp_path / "framework.html").read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html
    assert specs["project"] in html
    assert specs["description"] in html
    assert ("Regular coding" if regular else "Continuous coding") in html
    if regular:
        assert "2.5 seconds" in html
    form.application.finish_new_code.assert_called_once_with()
    form.destroy.assert_called_once_with()
    assert form.saved


def test_cancel_save_keeps_form_open_without_writing_files(save_form, tmp_path):
    form, dialogs = save_form
    dialogs.save.return_value = ""

    newcode.NewCode.record_all(form)

    dialogs.error.assert_not_called()
    dialogs.save.assert_called_once()
    assert not any(path.is_file() for path in tmp_path.rglob("*"))
    form.application.finish_new_code.assert_not_called()
    form.destroy.assert_not_called()
    assert not form.saved
