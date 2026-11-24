"""Display and export application-owned Matplotlib figures in Tkinter."""

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from matplotlib import rc_context
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

from scyseqtools.analyser.output_files import SaveDestination, output_path, write_outputs
from scyseqtools.analyser.save_dialog import resolve_destinations


def _svg_path(destination):
    path = Path(destination)
    if path.suffix.lower() != ".svg":
        raise ValueError("Choose a filename ending in .svg.")
    return path


def save_svg(figure, destination, *, title, description, replace=True):
    """Save the displayed limits as a standalone SVG."""
    path = _svg_path(destination)

    def write(source):
        with source.open("wb") as stream, rc_context({"svg.fonttype": "path"}):
            figure.savefig(
                stream, format="svg", bbox_inches="tight",
                metadata={"Title": title, "Description": description,
                          "Creator": "ScySeqTools Analyser"},
            )

    write_outputs([(SaveDestination(path, replace=replace), write)])


class _GraphToolbar(NavigationToolbar2Tk):
    toolitems = tuple(
        item for item in NavigationToolbar2Tk.toolitems
        if item[0] in ("Home", "Back", "Forward", "Pan", "Zoom")
    )


class GraphViewer(tk.Toplevel):
    def __init__(self, parent, figure, *, title, description, filename, directory):
        super().__init__(parent)
        self.withdraw()
        self.title(title.replace("\n", " · "))
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.graph_title = title
        self.description = description
        self.filename = filename
        self.directory = directory
        self.canvas = None

        try:
            controls = ttk.Frame(self, padding=(4, 0))
            controls.pack(side="bottom", fill="x")
            self.canvas = FigureCanvasTkAgg(figure, master=self)
            toolbar = _GraphToolbar(self.canvas, controls, pack_toolbar=False)
            toolbar.pack(side="left", fill="x", expand=True)
            ttk.Button(controls, text="Export SVG", command=self.export).pack(side="right")
            self.canvas.get_tk_widget().pack(fill="both", expand=True)
            self.canvas.draw()
        except Exception:
            self.destroy()
            raise
        self.deiconify()

    def export(self):
        chosen = filedialog.asksaveasfilename(
            parent=self, title="Export graph as SVG", initialdir=self.directory,
            initialfile=self.filename, defaultextension=".svg",
            filetypes=[("SVG vector graphic", "*.svg")], confirmoverwrite=False,
        )
        if not chosen:
            return
        try:
            path = _svg_path(chosen)
            destinations = resolve_destinations(self, [(output_path(path.parent, path.name),)])
            if destinations is None:
                return
            destination, = destinations
            save_svg(self.canvas.figure, destination.path, title=self.graph_title,
                     description=self.description, replace=destination.replace)
        except (OSError, RuntimeError, ValueError) as exc:
            messagebox.showerror("Could not export SVG", str(exc), parent=self)
        else:
            self.directory = str(destination.path.parent)

    def destroy(self):
        if self.canvas is not None:
            # As with Matplotlib's Tk manager, cancel a resize redraw before destroying its canvas.
            idle_draw = getattr(self.canvas, "_idle_draw_id", None)
            if idle_draw is not None:
                self.canvas.get_tk_widget().after_cancel(idle_draw)
        super().destroy()
        self.canvas = None
