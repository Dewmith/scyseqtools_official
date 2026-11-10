import json
from types import SimpleNamespace

import pytest
from scyseq.sequence import Alphabet, Sequence

from scyseqtools.analyser.methods import Method
from scyseqtools.analyser.symbolix import Symbolix


def sequence_records(file_count, site, code, values):
    return [
        {
            "filename": f"recording-{index}.cdx",
            "sitename": site,
            "codename": code,
            "sequence": Sequence(values, Alphabet(["absent", "present"])),
        }
        for index in range(file_count)
    ]


def launch_export(result, name, records, tmp_path, monkeypatch):
    output_dir = tmp_path / "exports"
    output_dir.mkdir()
    monkeypatch.setattr(
        "scyseqtools.analyser.methods.tkinter.filedialog.askdirectory",
        lambda **kwargs: str(output_dir),
    )

    # Exercise the launch/save path without constructing the notebook widgets.
    method = Method.__new__(Method)
    method.name = name
    method.parent = SimpleNamespace(cwd=str(tmp_path))
    method.parameters = []
    method.method = lambda _: result
    method.selected_files = [record["filename"] for record in records]
    method.metadata = {
        record["filename"]: {
            "history": [["source date", f"observer {index}", "source note"]],
            "media": f"recording-{index}.mp4",
            "times": [0, 1000, 2000, 3000, 4000],
            "comments": [f"sample {index}", "", "", ""],
            "code": {"period": 1.0, "project": "export regression"},
        }
        for index, record in enumerate(records)
    }
    method.launch()
    return output_dir, method.metadata


@pytest.mark.parametrize("file_count", [1, 2, 3])
@pytest.mark.parametrize("operation", ["join", "change_code"])
def test_sequence_exports_write_every_file_with_source_metadata(
    operation, file_count, tmp_path, monkeypatch
):
    records = sequence_records(file_count, "Aidant", "gaze", [0, 1, 0, 1])
    analyser = Symbolix()
    if operation == "join":
        target_records = sequence_records(
            file_count, "Patient", "movement", [0, 0, 1, 1]
        )
        result = analyser.join(records, target_records)
        site, code = "Aidant+Patient", "gaze+movement"
    else:
        result = analyser.change_code(
            records, "recoded", [1, 0], ["present", "absent"]
        )
        site, code = "Aidant", "recoded"

    output_dir, metadata = launch_export(
        result, operation, records, tmp_path, monkeypatch
    )

    exported_files = sorted(output_dir.iterdir())
    assert len(exported_files) == file_count
    for index, path in enumerate(exported_files):
        assert path.suffix == ".cdx"
        assert path.name.startswith(f"recording-{index}_")
        record = json.loads(path.read_text(encoding="utf-8"))
        source = metadata[records[index]["filename"]]
        assert record["media"] == source["media"]
        assert record["times"] == source["times"]
        assert record["comments"] == source["comments"]
        assert record["history"][:-1] == source["history"]
        assert record["code"]["period"] == 1.0
        assert record["code"]["project"] == "export regression"
        assert record["code"]["sites"] == {site: [code]}
        values = record["data"][site][code]
        assert len(values) == 4
        if operation == "change_code":
            assert values == [1, 0, 1, 0]


@pytest.mark.parametrize(
    "operation",
    [
        "statistics",
        "mutual_information",
        "complexity",
        "transition_probability",
        "influence_probability",
    ],
)
def test_table_exports_still_write_one_csv(operation, tmp_path, monkeypatch):
    records = sequence_records(2, "Aidant", "gaze", [0, 1, 0, 1])
    parameters = {"lod": records}
    if operation in ("mutual_information", "influence_probability"):
        parameters = {
            "lod1": records,
            "lod2": sequence_records(2, "Patient", "movement", [0, 0, 1, 1]),
        }
    if operation in ("transition_probability", "influence_probability"):
        parameters["step"] = 1

    result = getattr(Symbolix(), operation)(**parameters)
    output_dir, _ = launch_export(
        result, operation, records, tmp_path, monkeypatch
    )

    exported_files = list(output_dir.iterdir())
    assert len(exported_files) == 1
    assert exported_files[0].suffix == ".csv"
    lines = exported_files[0].read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("Filename;")
    assert len(lines) == 3
    assert "recording-0.cdx" in lines[1]
    assert "recording-1.cdx" in lines[2]
