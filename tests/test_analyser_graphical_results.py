import csv
import os
from decimal import Decimal
import sys
from types import SimpleNamespace
from tkinter import TclError, filedialog, messagebox
from unittest.mock import Mock

import pytest
from scyseq.sequence import Alphabet, Sequence

from scyseqtools.analyser import output_files, resultpanel, save_dialog
from scyseqtools.analyser.analyser import Application
from scyseqtools.analyser.kappa import sequence_kappa_result, time_kappa_result
from scyseqtools.analyser.methods import write_codix_export
from scyseqtools.analyser.resultpanel import release_results
from scyseqtools.analyser.symbolix import statistics_result


def test_frequency_snapshot_and_offline_report(tmp_path):
    labels = ["a;b", "Parlé <&>"]
    seq = Sequence([0, 0, 0, 1], Alphabet(labels))
    record = dict(filename="a&b.cdx", sitename="Room", codename="Activity", sequence=seq)
    result = statistics_result([record])
    record["filename"] = "new file"
    result.write(tmp_path)
    csvfile, report = result.paths(tmp_path)
    with csvfile.open(encoding="utf-8", newline="") as stream:
        assert list(csv.reader(stream, delimiter=";")) == [
            ["Filename", "N", *labels], ["a&b.cdx", "4", "0.75", "0.25"]]
    html = report.read_text(encoding="utf-8")
    assert all(value in html for value in (
        "a&amp;b.cdx", "Parlé &lt;&amp;&gt;", "75%", "25%", "N = 4", "<svg", "@media print"))
    assert "<script" not in html
    reversed_seq = Sequence([0, 0, 0, 1], Alphabet(labels[::-1]))
    with pytest.raises(ValueError, match="order"):
        statistics_result([record, dict(record, sequence=reversed_seq)])


def test_kappa_charts_share_original_values(tmp_path):
    names = ["A.cdx", "B.cdx"]
    data = {name: {"Site": {"Code": Sequence([0, 1], Alphabet(["Silent", "Speaking"]))}}
            for name in names}
    streams = [("Site", "Code")]
    seq = sequence_kappa_result(names, data, streams)
    assert seq.details[0][0].chart.counts.tolist() == [[1, 0], [0, 1]]
    assert seq.rows == [["A-B", "1"]]
    metadata = {name: {"times": [0, t, 4000]} for name, t in zip(names, (2000, 2080))}
    result = time_kappa_result(names, data, metadata, streams, 100)
    result.write(tmp_path)
    csvfile, report = result.paths(tmp_path)
    with csvfile.open(encoding="utf-8") as stream:
        row, = csv.DictReader(stream, delimiter=";")
    assert [row[k] for k in ("Strict kappa", "Adjusted kappa", "Credited disagreement (ms)")] == [
        "0.96", "1", "80"]
    assert "2000–2080 ms (80 ms)" in report.read_text(encoding="utf-8")
    chart = result.details[0][0].chart
    assert "2000–2080 ms" in chart.draw((1950, 2100)).svg("detail")
    metadata["B.cdx"]["times"] = [5000, 5100, 5200]
    disjoint = time_kappa_result(names, data, metadata, streams, 100)
    assert "No overlapping recording time" in "".join(disjoint.html())
    assert chart.bounds == (0, 4000)


def test_dense_timeline_and_short_disagreement():
    samples = 12000
    times = list(range(0, (samples + 1) * 1000, 1000))
    later = times.copy()
    later[samples // 2] += 1
    labels = Alphabet(["Silent", "Speaking"])
    sequence = Sequence([i % 2 for i in range(samples)], labels)
    data = {name: {"S": {"C": sequence}} for name in ("A", "B")}
    result = time_kappa_result(list(data), data, {"A": {"times": times}, "B": {"times": later}},
                               [("S", "C")], 0)
    chart = result.details[0][0].chart
    overview = chart.draw()
    assert len(overview.items) < 1100
    assert "6000000–6000001 ms (1 ms)" in overview.svg("Full recording")
    assert "6000000–6000001 ms (1 ms)" in chart.draw((5999999, 6000002)).svg("Zoom")


def test_quit_with_multiple_pending_results(monkeypatch):
    panels = [SimpleNamespace(result=SimpleNamespace(title=title), pending=True, export=Mock())
              for title in ("Time-aligned Kappa", "Statistics")]
    decision = Mock(return_value=False)
    monkeypatch.setattr(messagebox, "askyesnocancel", decision)
    assert release_results(panels, None, "exit")
    assert all(not panel.export.called for panel in panels)
    decision.return_value = True
    panels[1].export.return_value = False
    assert not release_results(panels, None, "exit")
    for panel in panels:
        panel.export.assert_called_once()


@pytest.mark.skipif(sys.platform.startswith("linux") and not os.environ.get("DISPLAY"),
                    reason="Tk window tests require a display")
def test_graphical_workflow_from_cdx_to_exit(tmp_path, monkeypatch, capsys):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    out = tmp_path / "exports"
    out.mkdir()
    for name in ("A.cdx", "B.cdx"):
        sequence = Sequence([0, 0, 0, 1], Alphabet(["Absent", "Present"]))
        write_codix_export(data_dir / name, {"Room": {"Activity": sequence}},
                           {"times": [0, 1000, 2000, 3000, 4000]})
    choose = Mock(return_value=str(data_dir))
    monkeypatch.setattr(filedialog, "askdirectory", choose)
    decision = Mock(return_value=None)
    monkeypatch.setattr(messagebox, "askyesnocancel", decision)
    conflict = Mock(return_value=SimpleNamespace(result=None))
    monkeypatch.setattr(save_dialog, "_SaveConflictDialog", conflict)
    errors = Mock()
    monkeypatch.setattr(messagebox, "showerror", errors)
    with capsys.disabled():
        app = Application()
    try:
        app.geometry("720x480")
        app.update()
        assert (app.remove_but.winfo_rootx() + app.remove_but.winfo_width()
                <= app.winfo_rootx() + app.winfo_width())
        app.get_directory()
        for check in app.available.variables.values():
            check.set(True)
        app.load_file()
        assert app.selected.cget("text") == "Loaded files (2)"
        choose.return_value = ""
        app.notebook.selectpage("Statistics")
        app.statistics_tool.launch()
        stats = app.statistics_tool.panel
        old = stats.result
        choose.assert_called()
        assert stats.pending and stats.status.cget("text") == "Not exported"
        stats.tree.selection_set("1")
        app.update()
        assert old.rows[1][0] in stats.summary.cget("text")
        app.statistics_tool.launch()
        assert stats.result is old
        decision.return_value = False
        app.statistics_tool.launch()
        assert stats.result is not old and stats.pending
        old = stats.result
        decision.return_value = None
        app.notebook.selectpage("Kappa")
        app.kappa_tool.time_checkbox.invoke()
        app.kappa_tool.launch()
        kappa = app.kappa_tool.panel
        kappa._navigate(Decimal("0.5"), 0)
        assert kappa.window == (1000, 3000)
        kappa._navigate(1, 1)
        assert kappa.window == (2000, 4000)
        app._clear_loaded_files()
        assert stats.result is old and kappa.pending
        app.request_exit()
        assert "Statistics" in decision.call_args.args[1] and "Kappa" in decision.call_args.args[1]
        assert app.winfo_exists()

        # A failure publishing the HTML leaves the CSV and a retryable result.
        choose.return_value = str(out)
        csvpath, htmlpath = old.paths(out)
        publish = output_files._publish_new

        def fail_html(source, target):
            if target == htmlpath:
                raise OSError("Could not publish HTML")
            publish(source, target)

        with monkeypatch.context() as scoped:
            scoped.setattr(output_files, "_publish_new", fail_html)
            assert not stats.export()
        errors.assert_called_once()
        assert stats.pending and csvpath.is_file()
        assert not stats.export() and not htmlpath.exists()
        conflict.side_effect = lambda parent, names, existing, replace, rename: SimpleNamespace(result=replace)
        csvpath.write_text("previous CSV")
        assert stats.export() and htmlpath.is_file()
        assert csvpath.read_text() != "previous CSV"
        assert not stats.pending

        # The HTML file alone can trigger a rename of both outputs.
        renamed_folder = tmp_path / "renamed"
        renamed_folder.mkdir()
        original_csv, original_html = old.paths(renamed_folder)
        original_html.write_text("previous HTML")
        choose.return_value = str(renamed_folder)
        conflict.side_effect = lambda parent, names, existing, replace, rename: SimpleNamespace(result=rename("new"))
        assert stats.export()
        assert conflict.call_args.args[1] == (original_html.name,)
        assert original_html.read_text() == "previous HTML" and not original_csv.exists()
        assert (renamed_folder / "new.csv").is_file()
        renamed_html = renamed_folder / "new.html"
        assert renamed_html.is_file()
        browser = Mock(return_value=True)
        monkeypatch.setattr(resultpanel.webbrowser, "open", browser)
        stats.open_report.invoke()
        browser.assert_called_once_with(renamed_html.resolve().as_uri())

        decision.return_value = True
        choose.return_value = ""
        app.request_exit()
        assert app.winfo_exists() and kappa.pending
        choose.return_value = str(out)
        app.request_exit()
        assert len(list(out.glob("*.html"))) == 2
    finally:
        try:
            app.destroy()
        except TclError:
            pass  # Successful export-and-exit already destroyed this Tcl application.
