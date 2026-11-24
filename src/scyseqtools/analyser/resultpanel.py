"""Preview, navigation and export controls shared by graphical analysis tabs."""

from decimal import Decimal
from pathlib import Path
import os
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, font, messagebox, ttk
import webbrowser

import Pmw

from scyseqtools.analyser.charts import RecordingTracks
from scyseqtools.analyser.save_dialog import resolve_destinations


def scrollable_page(tab):
    page = Pmw.ScrolledFrame(tab, horizflex="elastic", vertflex="expand",
                             usehullsize=True, hull_width=790, hull_height=620)
    page.pack(fill="both", expand=True)
    return page.interior()


def release_results(panels, parent, action):
    pending = [p for p in panels if p.pending]
    if not pending:
        return True
    names = ", ".join(p.result.title for p in pending)
    decision = messagebox.askyesnocancel(
        "Unexported results", f"{names} have unexported results.\n\n"
        f"Yes: export and {action}.\nNo: discard and {action}.\nCancel: keep working.",
        default=messagebox.CANCEL, parent=parent)
    if decision is None:
        return False
    return not decision or all(p.export() for p in pending)


class ResultPanel(ttk.LabelFrame):
    def __init__(self, master):
        super().__init__(master, text="Latest result", padding=5)
        self.result = None
        self.folder = None
        self.report_path = None
        self.window = None
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)
        self.summary = ttk.Label(self, wraplength=710, justify="left")
        self.summary.grid(row=0, column=0, sticky="w")
        self.bind("<Configure>", lambda e: self.summary.configure(wraplength=max(200, e.width - 22)))
        self.stream = ttk.Combobox(self, state="readonly", width=35)
        self.stream.grid(row=1, column=0, sticky="w")
        self.stream.bind("<<ComboboxSelected>>", lambda e: self._select_detail())
        self.nav = ttk.Frame(self)
        self.nav.grid(row=2, column=0, sticky="w")
        for label, command in (("Earlier", lambda: self._navigate(1, -1)),
                               ("Zoom in", lambda: self._navigate(Decimal("0.5"), 0)),
                               ("Zoom out", lambda: self._navigate(2, 0)),
                               ("Later", lambda: self._navigate(1, 1))):
            ttk.Button(self.nav, text=label, command=command).pack(side="left")

        self.canvas = tk.Canvas(self, width=520, height=165, background="white",
                                highlightthickness=0, takefocus=True)
        self.canvas.grid(row=3, column=0, sticky="nsew")
        self._scrollbars(self.canvas, 3)
        self.readout = ttk.Label(self.nav)
        self.readout.pack(side="left", padx=5)
        self.canvas.bind("<Motion>", self._inspect_point)
        self.canvas.bind("<Leave>", lambda e: self.readout.configure(text=""))
        for key, direction in (("<Left>", -1), ("<Right>", 1)):
            self.canvas.bind(key, lambda e, d=direction: self._navigate(1, d) if self.window else None)
        self.tree = ttk.Treeview(self, show="headings", selectmode="browse", height=3)
        self.tree.grid(row=5, column=0, sticky="ew")
        self._scrollbars(self.tree, 5)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._select_row())
        actions = ttk.Frame(self)
        actions.grid(row=7, column=0, sticky="w")
        self.status = ttk.Label(actions)
        self.status.pack(side="left", padx=4)
        self.export_button = ttk.Button(actions, text="Export", command=self.export)
        self.export_button.pack(side="left")
        self.open_report = ttk.Button(actions, text="Open report", command=lambda: self._open(False))
        self.open_folder = ttk.Button(actions, text="Open output folder", command=lambda: self._open(True))
        for button in (self.open_report, self.open_folder):
            button.pack(side="left")

    def _scrollbars(self, widget, row):
        horizontal = ttk.Scrollbar(self, orient="horizontal", command=widget.xview)
        vertical = ttk.Scrollbar(self, orient="vertical", command=widget.yview)
        horizontal.grid(row=row + 1, column=0, sticky="ew")
        vertical.grid(row=row, column=1, sticky="ns")
        widget.configure(xscrollcommand=horizontal.set, yscrollcommand=vertical.set)

    @property
    def pending(self):
        return self.result is not None and self.folder is None

    def present(self, result, initialdir):
        if not release_results([self], self.winfo_toplevel(), "replace"):
            return
        self.result = result
        self.initialdir = Path(initialdir)
        self.folder = None
        self.report_path = None
        self.tree.delete(*self.tree.get_children())
        # Tk column identifiers must be unique, even when source labels repeat.
        columns = result.headers
        if len(set(columns)) != len(columns) or any(h.startswith("#") or not h for h in columns):
            columns = [f"col{i}" for i in range(len(columns))]
        self.tree.configure(columns=columns)
        default_font = font.nametofont("TkDefaultFont")
        for i, (column, heading) in enumerate(zip(columns, result.headers)):
            values = {str(row[i]) for row in result.rows}
            width = max(default_font.measure(v) for v in values | {heading})
            self.tree.heading(column, text=heading)
            self.tree.column(column, width=max(70, width + 16), stretch=False)
        for i, row in enumerate(result.rows):
            self.tree.insert("", "end", iid=str(i), values=row)
        self.tree.selection_set("0")
        self.tree.focus("0")
        self.tree.xview_moveto(0)
        self.tree.yview_moveto(0)
        self._select_row()
        self.status.configure(text="Not exported")
        self.export_button.configure(text="Export")
        self.open_report.state(["disabled"])
        self.open_folder.state(["disabled"])
        self.grid()
        self.update_idletasks()
        self.export()

    def _group(self):
        return self.result.details[int(self.tree.selection()[0])]

    def _select_row(self):
        if not self.tree.selection():
            return
        group = self._group()
        selected = self.stream.current()
        self.stream.configure(values=[detail.stream for detail in group])
        self.stream.current(selected if 0 <= selected < len(group) else 0)
        if len(group) > 1:
            self.stream.grid()
        else:
            self.stream.grid_remove()
        self._select_detail()

    def _select_detail(self):
        detail = self._group()[self.stream.current()]
        self.summary.configure(text=f"{detail.title}\n{detail.summary}")
        self.chart = detail.chart
        self.window = None
        if isinstance(self.chart, RecordingTracks) and self.chart.bounds[0] < self.chart.bounds[1]:
            self.window = self.chart.bounds
            self.nav.grid()
        else:
            self.nav.grid_remove()
        self.readout.configure(text="")
        self.descriptions = self.chart.draw().on_canvas(self.canvas)
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)

    def _navigate(self, scale, direction):
        start, end = self.chart.bounds
        a, b = self.window
        span = min(end - start, (b - a) * scale)
        left = max(start, min(end - span, (a + b - span + direction * span) / 2))
        if left + span > left:
            self.window = (left, left + span)
            self.descriptions = self.chart.draw(self.window).on_canvas(self.canvas)
            self.readout.configure(text="")

    def _inspect_point(self, event):
        if self.window:
            x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
            items = self.canvas.find_overlapping(x, y, x, y)
            self.readout.configure(text=next((self.descriptions[i] for i in reversed(items)
                                              if i in self.descriptions), ""))

    def export(self):
        parent = self.winfo_toplevel()
        folder = None
        try:
            initial = self.folder or self.initialdir
            initial.mkdir(exist_ok=True, parents=True)
            chosen = filedialog.askdirectory(parent=parent, initialdir=str(initial), mustexist=True)
            if not chosen:
                return False
            folder = Path(chosen)
            destinations = resolve_destinations(parent, [self.result.paths(folder)])
            if destinations is None:
                return False
            self.result.write(folder, destinations=destinations)
        except (OSError, ValueError) as exc:
            if self.folder is None or self.folder == folder:
                self.folder = None
                self.report_path = None
                self.status.configure(text="Export incomplete")
                self.open_report.state(["disabled"])
                self.open_folder.state(["disabled"])
            messagebox.showerror("Could not complete export", str(exc), parent=parent)
            return False
        self.folder = folder
        self.report_path = destinations[1].path
        self.status.configure(text="Exported")
        self.export_button.configure(text="Export again")
        self.open_report.state(["!disabled"])
        self.open_folder.state(["!disabled"])
        return True

    def _open(self, directory):
        path = self.folder if directory else self.report_path
        if path is None:
            return
        try:
            if not path.exists():
                raise FileNotFoundError(path)
            if not directory:
                if not webbrowser.open(path.resolve().as_uri()):
                    raise OSError("Could not start your web browser.")
            elif sys.platform == "win32":
                os.startfile(path)
            else:
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])
        except OSError as exc:
            messagebox.showerror("Could not open output", str(exc), parent=self.winfo_toplevel())
