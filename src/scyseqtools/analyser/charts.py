"""Geometry shared by the Tk preview and the offline SVG report."""

from bisect import bisect_right
from dataclasses import dataclass
from decimal import Decimal
from html import escape
from math import isfinite
from unicodedata import east_asian_width

from scyseqtools.analyser.timed_kappa import Timeline, paired_intervals


INK = "#233748"
PALETTE = ("#276c86", "#e6af48", "#745a98", "#419885", "#8da6cb", "#ad7168")


def label_width(value):
    units = sum(2 if east_asian_width(c) in ("W", "F") else 1 for c in str(value))
    return 10 * units + 20


class Drawing:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.items = []

    def label(self, x, y, text, color=INK):
        self.items.append(("text", x, y, str(text), color))

    def rect(self, x, y, width, height, color, description=""):
        self.items.append(("rect", x, y, width, height, color, description))

    def on_canvas(self, canvas):
        canvas.delete("all")
        descriptions = {}
        for kind, x, y, *args in self.items:
            if kind == "text":
                text, color = args
                canvas.create_text(x, y, text=text, fill=color, anchor="w",
                                   font=("TkDefaultFont", -13))
            else:
                width, height, color, description = args
                item = canvas.create_rectangle(x, y, x + width, y + height, outline="", fill=color)
                if description:
                    descriptions[item] = description
        canvas.configure(scrollregion=(0, 0, self.width, self.height))
        return descriptions

    def svg(self, title):
        out = [f'<svg xmlns="http://www.w3.org/2000/svg" role="img" '
               f'viewBox="0 0 {self.width} {self.height}" width="{self.width}" '
               f'height="{self.height}"><title>{escape(title)}</title>']
        for kind, x, y, *args in self.items:
            if kind == "text":
                text, color = args
                out.append(f'<text x="{x:.3f}" y="{y + 4:.3f}" fill="{color}" '
                           f'font-family="sans-serif" font-size="13">{escape(text)}</text>')
            else:
                width, height, color, desc = args
                out.append(f'<rect x="{x:.3f}" y="{y:.3f}" width="{width:.3f}" '
                           f'height="{height}" fill="{color}"><title>{escape(desc)}</title></rect>')
        return "".join(out) + "</svg>"


@dataclass
class FrequencyBars:
    labels: tuple
    values: tuple

    def draw(self):
        left = max(map(label_width, self.labels), default=50)
        drawing = Drawing(left + 384, 34 + len(self.labels) * 26)
        drawing.label(8, 13, "Share of observations")
        for index, (label, value) in enumerate(zip(self.labels, self.values)):
            y = 31 + index * 26
            drawing.label(8, y + 7, label)
            drawing.rect(left, y, 285, 15, "#e6eef1")
            if isfinite(value):
                drawing.rect(left, y, 285 * value, 15, PALETTE[0])
            drawing.label(left + 295, y + 7, "Undefined" if not isfinite(value)
                          else f"{value * 100:.4g}%")
        return drawing


@dataclass
class CountHeatmap:
    labels: tuple
    counts: object
    first: str
    second: str

    def draw(self):
        left = max(map(label_width, self.labels), default=60)
        cell = max(left, 52)
        axes = f"Rows: {self.first}   ·   Columns: {self.second}   ·   Samples"
        drawing = Drawing(max(label_width(axes), left + len(self.labels) * cell + 12),
                          62 + len(self.labels) * 28)
        drawing.label(8, 14, axes)
        maximum = max(1, self.counts.max())
        shades = ("#edf4f5", "#c9e2e5", "#91c3cc", "#5596a6", "#276c86")
        for j, label in enumerate(self.labels):
            drawing.label(left + j * cell + 4, 40, label)
        for i, row in enumerate(self.counts):
            y = 55 + i * 28
            drawing.label(8, y + 13, self.labels[i])
            for j, count in enumerate(row):
                x = left + j * cell
                shade = round(4 * count / maximum)
                drawing.rect(x, y, cell - 2, 26, shades[shade])
                drawing.label(x + 6, y + 13, int(count), "white" if shade >= 3 else INK)
        return drawing


@dataclass
class RecordingTracks:
    first: str
    second: str
    a: Timeline
    b: Timeline
    labels: tuple

    @property
    def bounds(self):
        return max(self.a.edges[0], self.b.edges[0]), min(self.a.edges[-1], self.b.edges[-1])

    def draw(self, window=None):
        start, end = window or self.bounds
        left = max(label_width(s) for s in (self.first, self.second, "Recording clock (ms)"))
        drawing = Drawing(max(left + 550, max(map(label_width, self.labels), default=0) + 35),
                          145 + 22 * len(self.labels))
        if end <= start:
            drawing.label(8, 20, "No overlapping recording time.")
            return drawing
        drawing.label(8, 16, "Recording clock (ms)")
        drawing.label(left, 16, str(start))
        drawing.label(left + 460, 16, str(end))
        drawing.width = max(drawing.width, left + 460 + label_width(end))
        for y, name in ((45, self.first), (73, self.second), (104, "Disagreement")):
            drawing.label(8, y, name)
        drawing.rect(left, 98, 480, 14, "#e6eef1")
        scale = Decimal(480) / (end - start)
        for track, recording in enumerate((self.a, self.b)):
            i = bisect_right(recording.edges, start) - 1
            position = start
            while position < end:
                state = recording.states[i]
                stop = min(end, recording.edges[i + 1])
                x = left + float((position - start) * scale)
                width = float((stop - position) * scale)
                label = self.labels[state]
                y = 35 + 28 * track
                description = f"{label} · {recording.edges[i]}–{recording.edges[i + 1]} ms"
                drawing.rect(x, y, max(1, width), 20, PALETTE[state % len(PALETTE)], description)
                if width >= label_width(label):
                    drawing.label(x + 6, y + 10, label, "white" if state % len(PALETTE) in (0, 2) else INK)
                # Move at least one display pixel on dense tracks; zoom uses the original runs.
                position = max(stop, min(end, position + 1 / scale))
                i = bisect_right(recording.edges, position) - 1
        previous_pixel = -1
        for lo, hi, a, b in paired_intervals(self.a, self.b, start, end):
            if a != b:
                x = float((lo - start) * scale)
                stop = float((hi - start) * scale)
                if int(stop) > previous_pixel or stop - x >= 1:
                    drawing.rect(left + x, 98, max(1, stop - x), 14, "#af402e",
                                 f"Disagreement · {lo}–{hi} ms ({hi - lo} ms)")
                    previous_pixel = int(stop)
        drawing.label(8, 132, "Behaviour labels")
        for i, label in enumerate(self.labels):
            y = 149 + 22 * i
            drawing.rect(8, y - 6, 14, 13, PALETTE[i % len(PALETTE)])
            drawing.label(31, y, label)
        return drawing
