"""Select and preview symbolic tracks from loaded recordings."""

from inspect import signature
from pathlib import Path
import re
from tkinter import TclError, messagebox, ttk

from matplotlib.figure import Figure
from matplotlib.text import Text
from matplotlib.ticker import MaxNLocator

from scyseq import Sequence
from scyseq.information import mutual_information
from scyseqtools.analyser.graph_viewer import GraphViewer
from scyseqtools.analyser.pairing import Track, validate_pair


SCATTER = "Sequence scatter"
COLOR_STRIP = "Color strip"
BARCODE = "State barcode"
STATE_SPACE = "State-space grid"
INDEPENDENCE = "Mutual-information contributions"
GRAPH_TYPES = {
    SCATTER: ("plot", "sequence-plot"),
    COLOR_STRIP: ("plot_color", "color-strip"),
    BARCODE: ("plot_bar", "state-barcode"),
    STATE_SPACE: ("plot_grid", "state-space-grid"),
    INDEPENDENCE: ("plot_independence", "mutual-information"),
}
PAIRED_GRAPHS = (STATE_SPACE, INDEPENDENCE)


def _plotter(graph_type, required_options=()):
    from scyseq import viz

    name, _ = GRAPH_TYPES[graph_type]
    plotter = getattr(viz, name, None)
    required = {"ax", *required_options}
    if plotter is None or not required.issubset(signature(plotter).parameters):
        options = ", ".join(f"{option}=..." for option in sorted(required))
        raise ValueError(
            f"This viewer needs a ScySeq version with {name}({options}). "
            "Install the updated ScySeq checkout in the Analyser's Python environment."
        )
    return plotter


def _validate_sequence(sequence):
    if not isinstance(sequence, Sequence):
        raise ValueError("The selected track is unavailable.")
    if not len(sequence):
        raise ValueError("The selected track has no observations.")
    if sequence.ivals.max() >= len(sequence.alphabet):
        raise ValueError("The selected track has values outside its state alphabet.")


def _format_labels(axes):
    axes.tick_params(axis="y", labelrotation=0)
    for artist in axes.findobj(match=Text):
        artist.set_parse_math(False)


def sequence_figure(sequence, title, graph_type=SCATTER):
    """Draw one track against its zero-based observation index."""
    _validate_sequence(sequence)
    options = {"vector": True} if graph_type in (COLOR_STRIP, BARCODE) else {}
    plotter = _plotter(graph_type, options)
    if graph_type in (SCATTER, BARCODE):
        options["ylabel"] = "State"

    height = 3.2 if graph_type == COLOR_STRIP else 4.6
    figure = Figure(figsize=(8, height), layout="constrained")
    axes = figure.subplots()
    plotter(sequence, ax=axes, xlabel="Sample index (0-based)",
            title=title, labelsize=11, titlesize=13, **options)
    axes.set_xlim(-0.5, len(sequence) - 0.5)
    if len(sequence) == 1:
        axes.set_xticks([0])
    else:
        axes.xaxis.set_major_locator(MaxNLocator(integer=True))
    _format_labels(axes)
    return figure


def comparison_figure(graph_type, seq1, seq2, first, second, metadata):
    """Render a verified pair and label its source tracks."""
    _validate_sequence(seq1)
    _validate_sequence(seq2)
    validate_pair(first, seq1, second, seq2, metadata)

    title = graph_type
    if graph_type == STATE_SPACE:
        plotter = _plotter(graph_type, ("seed",))
        options = {"seed": 0}
        title += "\nMarker area scales with consecutive observations"
    else:
        plotter = _plotter(graph_type)
        options = {"scale": 1600}
        title += f"\nMutual information = {mutual_information(seq1, seq2):.6g} nats"

    figure = Figure(figsize=(8.5, 6.2), layout="constrained")
    axes = figure.subplots()
    plotter(seq1, seq2, ax=axes, xlabel=first.label, ylabel=second.label,
            title=title, labelsize=10, titlesize=13, **options)
    axes.tick_params(axis="x", labelrotation=35)
    for tick in axes.get_xticklabels():
        tick.set_ha("right")
    _format_labels(axes)
    return figure


def _graph_svg_filename(graph_type, tracks):
    _, prefix = GRAPH_TYPES[graph_type]
    # Reserve space for each track, including both recording names in a paired graph.
    part_length = 48 if len(tracks) == 1 else 24
    parts = (part for track in tracks for part in (Path(track.filename).stem,
                                                   track.site, track.code))
    safe_parts = [re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", part)[:part_length].rstrip(" .")
                  for part in parts]
    return prefix + "_" + "_".join(safe_parts) + ".svg"


def sequence_svg_filename(filename, site, code):
    return _graph_svg_filename(SCATTER, (Track(filename, site, code),))


def set_choices(selector, values):
    choices = tuple(values)
    selector.configure(values=choices)
    if selector.get() not in choices:
        selector.set(choices[0] if choices else "")


class TrackSelector(ttk.LabelFrame):
    def __init__(self, parent, text, on_change):
        super().__init__(parent, text=text, padding=6)
        self.data = {}
        self.on_change = on_change
        self.columnconfigure(0, weight=1)
        self.file = self._selector("Recording", 0, self._update_sites)
        self.site = self._selector("Site", 1, self._update_codes)
        self.code = self._selector("Code", 2, self.on_change)

    def _selector(self, label, column, refresh):
        ttk.Label(self, text=label).grid(row=0, column=column, sticky="w", padx=(0, 6))
        selector = ttk.Combobox(self, state="readonly", width=22)
        selector.grid(row=1, column=column, sticky="ew", padx=(0, 6))
        selector.bind("<<ComboboxSelected>>", lambda event: refresh())
        return selector

    def update_state(self, state):
        self.data = state["data"]
        set_choices(self.file, state["files"])
        self._update_sites()

    def _update_sites(self):
        set_choices(self.site, self.data.get(self.file.get(), {}))
        self._update_codes()

    def _update_codes(self):
        set_choices(self.code, self.data.get(self.file.get(), {}).get(self.site.get(), {}))
        self.on_change()

    def get(self):
        filename, site, code = self.file.get(), self.site.get(), self.code.get()
        if filename and site and code:
            return Track(filename, site, code)
        return None


class VisualizationsTool:
    def __init__(self, parent):
        self.parent = parent
        self.data = {}
        self.metadata = {}
        self.viewer = None
        self.viewed_files = set()
        self.tab = parent.notebook.add("Visualizations")
        controls = ttk.Frame(self.tab, padding=10)
        controls.pack(fill="x")
        controls.columnconfigure(0, weight=1)
        ttk.Label(controls, text="Graph type").grid(row=0, column=0, sticky="w")
        self.graph_type = ttk.Combobox(controls, values=tuple(GRAPH_TYPES), state="readonly",
                                       width=35)
        self.graph_type.current(0)
        self.graph_type.grid(row=1, column=0, pady=(0, 8), sticky="w")
        self.graph_type.bind("<<ComboboxSelected>>", self._update_graph_type)
        self.first = TrackSelector(controls, "Track", self._update_button)
        self.first.grid(row=2, column=0, sticky="ew")
        self.second = TrackSelector(controls, "Track 2", self._update_button)
        self.second.grid(row=3, column=0, sticky="ew", pady=(5, 0))
        self.view_button = ttk.Button(controls, text="View graph", command=self.show_graph)
        self.view_button.grid(row=4, column=0, pady=(8, 0), sticky="w")
        self._update_graph_type()

    def update_state(self, state):
        self.data = state["data"]
        self.metadata = state.get("metadata", {})
        self.first.update_state(state)
        self.second.update_state(state)
        if self.viewer is not None and not self.viewed_files.issubset(self.data):
            self.viewer.destroy()

    def _update_graph_type(self, event=None):
        paired = self.graph_type.get() in PAIRED_GRAPHS
        self.first.configure(text="Track 1" if paired else "Track")
        if paired:
            self.second.grid()
        else:
            self.second.grid_remove()
        self._update_button()

    def _update_button(self):
        ready = self.first.get() is not None
        if self.graph_type.get() in PAIRED_GRAPHS:
            ready = ready and self.second.get() is not None
        self.view_button.state(["!disabled"] if ready else ["disabled"])

    def _sequence(self, track):
        if track is None:
            raise ValueError("Select a recording, site, and code for each track.")
        return self.data.get(track.filename, {}).get(track.site, {}).get(track.code)

    def show_graph(self):
        graph_type = self.graph_type.get()
        second = self.second.get() if graph_type in PAIRED_GRAPHS else None
        self.open_graph(graph_type, self.first.get(), second)

    def open_graph(self, graph_type, first, second=None, *, dialog_parent=None):
        try:
            sequence = self._sequence(first)
            if graph_type in PAIRED_GRAPHS:
                other = self._sequence(second)
                figure = comparison_figure(graph_type, sequence, other, first, second,
                                           self.metadata)
                title = f"{graph_type}\n{first.label}\n{second.label}"
                description = f"{figure.axes[0].get_title()}. {len(sequence)} paired observations."
                tracks = (first, second)
            else:
                title = f"{first.filename}\n{first.site} / {first.code}"
                figure = sequence_figure(sequence, title, graph_type)
                states = ", ".join(sequence.alphabet.svals)
                description = f"{graph_type} by zero-based sample index. State labels are {states}."
                tracks = (first,)

            viewer = GraphViewer(
                self.parent, figure, title=title, description=description,
                filename=_graph_svg_filename(graph_type, tracks), directory=self.parent.ddir.get(),
            )
        except (RuntimeError, TclError, ValueError) as exc:
            messagebox.showerror("Could not view graph", str(exc), parent=dialog_parent or self.tab)
            return

        if self.viewer is not None:
            self.viewer.destroy()
        self.viewer = viewer
        self.viewed_files = {track.filename for track in tracks}
        viewer.bind("<Destroy>", self._viewer_destroyed, add="+")

    def _viewer_destroyed(self, event):
        if event.widget is self.viewer:
            self.viewer = None
            self.viewed_files.clear()
