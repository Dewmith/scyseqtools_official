from html import unescape
import json
import os
import sys
from unittest.mock import Mock
from xml.etree import ElementTree

import numpy as np
import pytest
from matplotlib import rc_context, rcParams
from matplotlib.backends.backend_agg import FigureCanvasAgg

from scyseq import Sequence, viz
from scyseqtools.analyser import graph_viewer, visualizations
from scyseqtools.analyser.analyser import Application, _load_codix_appstate
from scyseqtools.analyser.pairing import Track, validate_pair


SVG_NS = {"svg": "http://www.w3.org/2000/svg",
          "dc": "http://purl.org/dc/elements/1.1/"}


@pytest.fixture
def recordings(tmp_path):
    directory = tmp_path / "recordings"
    directory.mkdir()
    record = {
        "version": "0.9",
        "media": r"C:\Study\Recording.mp4",
        "times": [6000, 9000, 12000, 15000],
        "code": {
            "sites": {"Site one": ["Body motion"], "Site two": ["Look: direction"]},
            "codes": {
                "Body motion": ["Still", "Turn & reach"],
                "Look: direction": ["$centre$", "Away"],
            },
        },
        "data": {
            "Site one": {"Body motion": [0, 1, 1]},
            "Site two": {"Look: direction": [1, 0, 0]},
        },
    }
    for name in ("Recording 1.cdx", "Recording 2.cdx"):
        (directory / name).write_text(json.dumps(record), encoding="utf-8")
    return directory


def test_render_loaded_tracks_and_export_vector_svg(recordings, tmp_path):
    filename = "Recording 1.cdx"
    state = _load_codix_appstate(recordings, [filename])
    assert state["metadata"][filename]["times"] == [6000, 9000, 12000, 15000]
    expected = [
        ("Site one", "Body motion", ("Still", "Turn & reach"), [0, 1, 1]),
        ("Site two", "Look: direction", ("$centre$", "Away"), [1, 0, 0]),
    ]
    for site, code, labels, values in expected:
        sequence = state["data"][filename][site][code]
        assert isinstance(sequence, Sequence)
        title = f"{filename}\n{site} / {code}"
        figure = visualizations.sequence_figure(sequence, title)
        axes = figure.axes[0]
        FigureCanvasAgg(figure).draw()

        assert axes.get_title() == title
        assert axes.get_xlabel() == "Sample index (0-based)"
        assert tuple(label.get_text() for label in axes.get_yticklabels()) == labels
        assert all(not label.get_parse_math() for label in axes.get_yticklabels())
        np.testing.assert_array_equal(axes.collections[0].get_offsets(),
                                      list(enumerate(values)))

        path = tmp_path / visualizations.sequence_svg_filename(filename, site, code)
        assert ":" not in path.name
        axes.set_xlim(0.5, 2.5)
        with rc_context({"svg.fonttype": "none"}):
            graph_viewer.save_svg(figure, path, title=title, description="Sample index")
            assert rcParams["svg.fonttype"] == "none"

        assert axes.get_xlim() == (0.5, 2.5)
        svg = ElementTree.parse(path).getroot()
        assert svg.tag == "{http://www.w3.org/2000/svg}svg"
        assert svg.findtext("svg:title", namespaces=SVG_NS) == title
        assert svg.findtext(".//dc:description", namespaces=SVG_NS) == "Sample index"
        assert svg.findall(".//svg:path", SVG_NS)
        assert not svg.findall(".//svg:image", SVG_NS)
        exported_text = unescape(path.read_text(encoding="utf-8"))
        for label in labels:
            assert label in exported_text


@pytest.mark.parametrize(
    ("sequence", "message"),
    [(None, "unavailable"),
     (Sequence(np.array([], dtype=int), ["Only state"]), "no observations"),
     (Sequence([2], ["Only state"], check=False), "outside its state alphabet")],
)
def test_reject_unplottable_tracks(sequence, message):
    with pytest.raises(ValueError, match=message):
        visualizations.sequence_figure(sequence, "Unplottable")


def test_plot_one_observation():
    figure = visualizations.sequence_figure(Sequence([0], ["Only state"]), "One observation")
    assert figure.axes[0].get_xticks().tolist() == [0]
    FigureCanvasAgg(figure).draw()


def test_export_filename_keeps_site_and_code_for_long_recording_name():
    filename = visualizations.sequence_svg_filename("a" * 190 + ".cdx", "Site", "Code")
    assert filename == "sequence-plot_" + "a" * 48 + "_Site_Code.svg"


@pytest.mark.parametrize(
    "graph_type", [visualizations.COLOR_STRIP, visualizations.BARCODE,
                   visualizations.STATE_SPACE, visualizations.INDEPENDENCE],
)
def test_additional_graphs_from_loaded_tracks(graph_type, recordings, tmp_path):
    first = Track("Recording 1.cdx", "Site one", "Body motion")
    second = Track("Recording 2.cdx", "Site two", "Look: direction")
    state = _load_codix_appstate(recordings, [first.filename, second.filename])
    seq1 = state["data"][first.filename][first.site][first.code]
    seq2 = state["data"][second.filename][second.site][second.code]
    if graph_type in visualizations.PAIRED_GRAPHS:
        figure = visualizations.comparison_figure(
            graph_type, seq1, seq2, first, second, state["metadata"]
        )
        tracks = (first, second)
        axes = figure.axes[0]
        assert (axes.get_xlabel(), axes.get_ylabel()) == (first.label, second.label)
        assert tuple(tick.get_text() for tick in axes.get_xticklabels()) == seq1.alphabet.svals
        assert tuple(tick.get_text() for tick in axes.get_yticklabels()) == seq2.alphabet.svals
        if graph_type == visualizations.INDEPENDENCE:
            assert "Mutual information = 0.636514 nats" in axes.get_title()
    else:
        figure = visualizations.sequence_figure(seq1, first.label, graph_type)
        tracks = (first,)
        assert figure.axes[0].get_xlim() == (-0.5, 2.5)
        assert figure.axes[0].get_xlabel() == "Sample index (0-based)"

    FigureCanvasAgg(figure).draw()
    filename = visualizations._graph_svg_filename(graph_type, tracks)
    for track in tracks:
        assert track.filename.removesuffix(".cdx") in filename
        assert track.site in filename
    assert ":" not in filename
    path = tmp_path / filename
    graph_viewer.save_svg(figure, path, title=graph_type, description="Test graph")
    svg = ElementTree.parse(path).getroot()
    assert svg.findtext("svg:title", namespaces=SVG_NS) == graph_type
    assert svg.findtext(".//dc:description", namespaces=SVG_NS) == "Test graph"
    assert not svg.findall(".//svg:image", SVG_NS)


def test_same_file_pair_uses_shared_indices_with_or_without_timestamps():
    first = Track("local.cdx", "Site one", "Body motion")
    second = Track("local.cdx", "Site two", "Look")
    sequence = Sequence([0, 0], ["State"])
    validate_pair(first, sequence, second, sequence, {})
    validate_pair(first, sequence, second, sequence, {"local.cdx": {"times": [0, 100]}})
    with pytest.raises(ValueError, match="different tracks"):
        validate_pair(first, sequence, first, sequence, {})
    with pytest.raises(ValueError, match="same number of observations"):
        validate_pair(first, sequence, second, Sequence([0], ["State"]), {})
    with pytest.raises(ValueError, match="strictly increasing"):
        validate_pair(first, sequence, second, sequence, {"local.cdx": {"times": [0, 0]}})


@pytest.mark.parametrize(
    ("media", "times", "error"),
    [
        ("recording.mp4", [0, 100, 200], "absolute media reference"),
        (r"C:\study\other.mp4", [0, 100, 200], "different media recordings"),
        ("c:/study/recording.mp4", [], "need timestamps"),
        ("c:/study/recording.mp4", [100, 200], "different timestamp conventions"),
        ("c:/study/recording.mp4", [0, 100, 100], "strictly increasing"),
        ("c:/study/recording.mp4", [0, "NaN", 200], "finite"),
        ("c:/study/recording.mp4", [0, "invalid", 200], "invalid timestamps"),
        ("c:/study/recording.mp4", [0, 100, 200, 300], "sample timestamps"),
        ("c:/study/recording.mp4", [10, 110, 210], "different recording start"),
        ("c:/study/recording.mp4", [0, 101, 200], "different sample spacing"),
        ("c:/study/subfolder/../Recording.MP4", [0, "100.0", 200], None),
    ],
)
def test_cross_file_pair_requires_verified_media_and_clock(media, times, error):
    first = Track("first.cdx", "Site", "Code")
    second = Track("second.cdx", "Site", "Code")
    sequence = Sequence([0, 1], ["First", "Second"])
    records = {first.filename: {"media": r"C:\Study\Recording.mp4", "times": [0, 100, 200]},
               second.filename: {"media": media, "times": times}}
    if error:
        with pytest.raises(ValueError, match=error):
            validate_pair(first, sequence, second, sequence, records)
    else:
        validate_pair(first, sequence, second, sequence, records)


def test_cross_file_sample_timestamps_and_ordered_labels():
    first = Track("first.cdx", "Site", "Code")
    second = Track("second.cdx", "Site", "Code")
    sequence = Sequence([0, 1], ["First", "Second"])
    records = {name: {"media": "/study/recording.mp4", "times": [100, 200]}
               for name in (first.filename, second.filename)}
    validate_pair(first, sequence, second, sequence, records)
    reordered = Sequence([0, 1], ["Second", "First"])
    with pytest.raises(ValueError, match="same order"):
        validate_pair(first, sequence, second, reordered, records)


def test_old_scyseq_is_reported_before_calling_its_plotter(monkeypatch):
    def old_plot(sequence, **kwargs):
        pytest.fail("The legacy plotter would allocate a pyplot figure")

    monkeypatch.setattr(viz, "plot", old_plot)
    with pytest.raises(ValueError, match=r"ScySeq version with plot\(ax="):
        visualizations.sequence_figure(Sequence([0], ["State"]), "Old ScySeq")


def test_failed_svg_save_preserves_destination(monkeypatch, tmp_path):
    destination = tmp_path / "existing.svg"
    destination.write_bytes(b"original")
    figure = visualizations.sequence_figure(Sequence([0], ["State"]), "Graph")

    def fail_during_save(stream, **kwargs):
        stream.write(b"partial export")
        raise OSError("Write failed")

    monkeypatch.setattr(figure, "savefig", fail_during_save)
    with pytest.raises(OSError, match="Write failed"):
        graph_viewer.save_svg(figure, destination, title="Graph", description="Example")
    assert destination.read_bytes() == b"original"
    assert list(tmp_path.iterdir()) == [destination]


@pytest.mark.skipif(sys.platform.startswith("linux") and not os.environ.get("DISPLAY"),
                    reason="Tk window tests require a display")
def test_viewer_opens_exports_replaces_and_closes(recordings, tmp_path, monkeypatch, capsys):
    with capsys.disabled():
        app = Application()
    try:
        tool = app.visualizations_tool
        assert tool.view_button.instate(["disabled"])
        monkeypatch.setattr("tkinter.filedialog.askdirectory", lambda **kw: str(recordings))
        app.get_directory()
        for variable in app.available.variables.values():
            variable.set(True)
        app.load_file()
        app.notebook.selectpage("Visualizations")
        app.update()
        assert tool.first.file.get() == "Recording 1.cdx"
        assert tool.first.site.get() == "Site one"
        assert tool.first.code.get() == "Body motion"

        figure_numbers = viz.plt.get_fignums()
        tool.view_button.invoke()
        first = tool.viewer
        assert first.winfo_exists()
        assert first.canvas.toolbar.mode == ""

        tool.first.site.current(1)
        tool.first.site.event_generate("<<ComboboxSelected>>")
        tool.view_button.invoke()
        app.update()
        assert not first.winfo_exists()
        assert first.canvas is None
        viewer = tool.viewer
        figure = viewer.canvas.figure
        axes = figure.axes[0]
        toolbar = viewer.canvas.toolbar
        assert tool.first.code.get() == "Look: direction"
        assert "Site two" in axes.get_title()
        initial_limits = axes.get_xlim()
        toolbar.push_current()
        toolbar.pan()
        assert toolbar.mode == "pan/zoom"
        toolbar.pan()
        toolbar.zoom()
        assert toolbar.mode == "zoom rect"
        axes.set_xlim(0.5, 2.5)
        toolbar.push_current()
        toolbar.home()
        assert axes.get_xlim() == initial_limits

        destination = tmp_path / "export.svg"
        ask = Mock(side_effect=["", str(tmp_path / "missing folder" / "export.svg"),
                               str(destination)])
        error = Mock()
        monkeypatch.setattr(graph_viewer.filedialog, "asksaveasfilename", ask)
        monkeypatch.setattr(graph_viewer.messagebox, "showerror", error)
        viewer.export()
        assert viewer.winfo_exists()
        error.assert_not_called()
        viewer.export()
        error.assert_called_once()
        assert viewer.winfo_exists()
        viewer.export()
        assert ElementTree.parse(destination).findtext(
            "svg:title", namespaces=SVG_NS) == axes.get_title()
        assert ask.call_args.kwargs["initialfile"] == (
            "sequence-plot_Recording 1_Site two_Look_ direction.svg"
        )

        app.tk.call(viewer.protocol("WM_DELETE_WINDOW"))
        app.update()
        assert tool.viewer is None
        assert app.winfo_exists()
        assert viz.plt.get_fignums() == figure_numbers

        tool.view_button.invoke()
        app.selected.variables["Recording 1.cdx"].set(True)
        app.remove_selected_files()
        app.update()
        assert tool.viewer is None
        assert tool.first.file.get() == "Recording 2.cdx"
        assert tool.first.site.get() == "Site two"
        assert tool.first.code.get() == "Look: direction"
        tool.view_button.invoke()
        assert tool.viewer.winfo_exists()
    finally:
        app.destroy()


@pytest.mark.skipif(sys.platform.startswith("linux") and not os.environ.get("DISPLAY"),
                    reason="Tk window tests require a display")
def test_pair_selection_and_mutual_information_shortcut_share_viewer(
    recordings, monkeypatch, capsys
):
    with capsys.disabled():
        app = Application()
    try:
        monkeypatch.setattr("tkinter.filedialog.askdirectory", lambda **kw: str(recordings))
        app.get_directory()
        for variable in app.available.variables.values():
            variable.set(True)
        app.load_file()
        tool = app.visualizations_tool
        app.notebook.selectpage("Visualizations")
        app.update()
        assert not tool.second.winfo_ismapped()
        tool.graph_type.set(visualizations.STATE_SPACE)
        tool.graph_type.event_generate("<<ComboboxSelected>>")
        app.update()
        assert tool.second.winfo_ismapped()
        tool.second.file.current(1)
        tool.second.file.event_generate("<<ComboboxSelected>>")
        tool.second.site.current(1)
        tool.second.site.event_generate("<<ComboboxSelected>>")
        tool.view_button.invoke()
        assert tool.viewed_files == {"Recording 1.cdx", "Recording 2.cdx"}
        grid = tool.viewer
        app.selected.variables["Recording 2.cdx"].set(True)
        app.remove_selected_files()
        assert not grid.winfo_exists()

        method = next(item for item in app.methods if getattr(item, "name", "") == "mutual_information")
        app.notebook.selectpage("Mutual Information")
        for index, param in enumerate(method.parameters):
            param.value.sget.selection_set(index)
            select = next(widget for widget in param.tk.winfo_children()
                          if widget.winfo_class() == "Button" and widget.cget("text") == "Select")
            select.invoke()
            param.value.cget.selection_set(0)
        assert method.graph_recording.get() == "Recording 1.cdx"
        method.graph_button.invoke()
        viewer = tool.viewer
        axes = viewer.canvas.figure.axes[0]
        assert "Mutual information = 0.636514 nats" in axes.get_title()
        assert axes.get_xlabel() == "Recording 1.cdx · Site one / Body motion"
        assert axes.get_ylabel() == "Recording 1.cdx · Site two / Look: direction"

        tool.graph_type.set(visualizations.BARCODE)
        tool.graph_type.event_generate("<<ComboboxSelected>>")
        tool.view_button.invoke()
        assert not viewer.winfo_exists()
        assert tool.viewer.filename.startswith("state-barcode_")
        assert not tool.second.winfo_ismapped()
    finally:
        app.destroy()
