"""A completed analysis and its portable CSV and HTML representations."""

import csv
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial
from html import escape
from importlib.metadata import PackageNotFoundError, version
import io

from scyseqtools.analyser.output_files import SaveDestination, output_path, write_lines, write_outputs


def _version(package):
    try:
        return version(package)
    except PackageNotFoundError:
        return "unavailable"


@dataclass
class Detail:
    stream: str
    title: str
    summary: str
    chart: object


@dataclass
class AnalysisResult:
    title: str
    filename: str
    headers: list
    rows: list
    details: list  # One group per table row, one detail per selectable stream.
    generated: str = field(default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds"))
    versions: str = field(default_factory=lambda: f"ScySeqTools {_version('scyseqtools')} · ScySeq {_version('scyseq')}")

    def csv_lines(self):
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
        writer.writerow(self.headers)
        writer.writerows(self.rows)
        return buffer.getvalue().splitlines(keepends=True)

    def html(self):
        title = escape(self.title)
        yield f'<!doctype html><html lang="en"><meta charset="utf-8"><title>{title}</title>'
        yield """<style>
body{font:16px/1.45 system-ui,sans-serif;color:#233748;margin:2rem auto;padding:0 1rem;max-width:76rem}
h1,h2{line-height:1.2}section{margin:2rem 0}svg{display:block;background:white}
.scroll{overflow:auto}table{border-collapse:collapse;font-variant-numeric:tabular-nums}
td,th{padding:.35rem .65rem;border:1px solid #b6c9cd;text-align:left}th{background:#edf4f5}
@media print{body{margin:0;font-size:9pt}.scroll{overflow:visible}svg{max-width:100%;height:auto}
table{width:100%;font-size:8pt;overflow-wrap:anywhere}th,td{padding:2pt}tr,svg{break-inside:avoid}
h2{break-after:avoid}*{print-color-adjust:exact}
table.wide,table.wide tbody{display:block}.wide thead{display:none}
.wide caption{display:block;text-align:left;font-weight:bold;margin-bottom:4pt}
.wide tr{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));margin-bottom:6pt}
.wide td{padding:3pt 5pt}.wide td::before{content:attr(data-heading);display:block;font-weight:bold}}
</style>"""
        yield f'<main><h1>{title}</h1><p>{escape(self.generated)} · {escape(self.versions)}</p>'
        style = ' class="wide"' if len(self.headers) > 8 else ''
        yield f'<div class="scroll"><table{style}><caption>Result values</caption><thead><tr>'
        yield from (f'<th scope="col">{escape(str(h))}</th>' for h in self.headers)
        yield '</tr></thead><tbody>'
        for row in self.rows:
            yield '<tr>'
            for heading, value in zip(self.headers, row):
                yield f'<td data-heading="{escape(str(heading))}">{escape(str(value))}</td>'
            yield '</tr>'
        yield '</tbody></table></div>'
        for group in self.details:
            for detail in group:
                yield f'<section><h2>{escape(detail.title)}</h2><p>{escape(detail.summary)}</p>'
                yield '<div class="scroll">' + detail.chart.draw().svg(detail.title) + '</div></section>'
        yield '</main></html>'

    def paths(self, folder):
        csv_path = output_path(folder, self.filename)
        return csv_path, csv_path.with_suffix(".html")

    def write(self, folder, *, destinations=None):
        """Stage both documents before publishing either. Each replacement is atomic."""
        if destinations is None:
            destinations = tuple(SaveDestination(path, replace=True) for path in self.paths(folder))
        csv_destination, html_destination = destinations
        write_outputs([
            (csv_destination, partial(write_lines, lines=self.csv_lines(), newline="")),
            (html_destination, partial(write_lines, lines=self.html(), newline="")),
        ])
