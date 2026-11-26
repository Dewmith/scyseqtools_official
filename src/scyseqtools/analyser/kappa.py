"""
Cohen kappa support for the analyser GUI.
"""

import csv
import itertools
import io
import pathlib
import tkinter
import tkinter.filedialog
import tkinter.messagebox
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from tkinter.simpledialog import Dialog

import numpy as np
import Pmw

from scyseqtools.analyser.timed_kappa import Timeline, parse_tolerance, time_agreement
from scyseqtools.analyser.charts import CountHeatmap, RecordingTracks
from scyseqtools.analyser.pairing import verify_common_media
from scyseqtools.analyser.reports import AnalysisResult, Detail
from scyseqtools.analyser.resultpanel import ResultPanel, scrollable_page
from scyseqtools.analyser.sample_alignment import (
    RecordingClock, SampleAlignment, match_sample_clocks, recording_overlap,
    require_matching_periods,
)


TABLE_EXT = ".csv"
SEP = ";"


def iter_file_pairs(files):
    """
    Return all unordered pairs from the selected files.
    """
    return list(itertools.combinations(files, 2))


def _sequence_values(sequence):
    return np.asarray(getattr(sequence, "ivals", sequence), dtype=int)


def _alphabet_labels(sequence):
    alphabet = getattr(sequence, "alphabet", None)
    if alphabet is None:
        return ()
    if hasattr(alphabet, "svals"):
        return tuple(alphabet.svals)
    return tuple(getattr(sym, "sval", getattr(sym, "strval", str(sym)))
                 for sym in alphabet)


def _validate_sequences(seq1, seq2):
    values1 = _sequence_values(seq1)
    values2 = _sequence_values(seq2)

    if len(values1) != len(values2):
        raise ValueError("Kappa sequences must have the same length.")
    if len(values1) == 0:
        raise ValueError("Kappa cannot be computed on empty sequences.")

    labels1 = _alphabet_labels(seq1)
    labels2 = _alphabet_labels(seq2)
    if labels1 and labels2 and labels1 != labels2:
        raise ValueError("Kappa sequences must have compatible alphabets.")

    return values1, values2, max(len(labels1), len(labels2))


def _sample_matrix(seq1, seq2):
    values1, values2, alphabet_len = _validate_sequences(seq1, seq2)
    max_value = int(max(values1.max(initial=0), values2.max(initial=0)))
    nb_labels = max(alphabet_len, max_value + 1)
    matrix = np.zeros((nb_labels, nb_labels), dtype=int)

    for true_value, pred_value in zip(values1, values2):
        matrix[int(true_value), int(pred_value)] += 1

    return matrix


def _sample_kappa(matrix):
    matrix = matrix.astype(float)
    nb_items = matrix.sum()
    observed = np.trace(matrix) / nb_items
    expected = np.dot(matrix.sum(axis=1), matrix.sum(axis=0)) / (nb_items ** 2)

    if expected == 1:
        return 1.0 if observed == 1 else 0.0

    return float((observed - expected) / (1 - expected))


def cohen_kappa(seq1, seq2):
    return _sample_kappa(_sample_matrix(seq1, seq2))


def format_kappa(value):
    """
    Format kappa values like the screenshot: 3 decimals, trimmed zeros.
    """
    rounded = round(float(value), 3)
    if abs(rounded) == 0:
        rounded = 0.0
    text = f"{rounded:.3f}".rstrip("0").rstrip(".")
    return "0" if text == "-0" else text


def common_codes_by_site(files, data):
    """
    Return site/code pairs present in every selected file, preserving order.
    """
    if not files:
        return {}

    first_file = files[0]
    first_data = data[first_file]
    codes_by_site = {}

    for site, first_codes in first_data.items():
        if not all(site in data[fname] for fname in files):
            continue

        common_codes = []
        for code in first_codes.keys():
            if all(code in data[fname][site] for fname in files):
                common_codes.append(code)

        if common_codes:
            codes_by_site[site] = common_codes

    return codes_by_site


def code_names_for_sites(codes_by_site, selected_sites):
    """
    Return code names available for the selected sites.
    """
    sites = [site for site in codes_by_site if site in selected_sites]

    codes = []
    for site in sites:
        for code in codes_by_site[site]:
            if code not in codes:
                codes.append(code)

    return codes


def site_codes_from_selection(codes_by_site, selected_sites, selected_codes):
    """
    Convert GUI site/code selections into ordered site/code pairs.
    """
    selected_code_set = set(selected_codes)
    return [
        (site, code)
        for site in codes_by_site
        if site in selected_sites
        for code in codes_by_site[site]
        if code in selected_code_set
    ]


def _get_sequence(data, filename, site, code):
    try:
        return data[filename][site][code]
    except KeyError:
        raise ValueError(
            f"Missing site/code {site}/{code} in {filename}."
        ) from None


def _validate_selection(files, site_codes):
    if len(files) < 2:
        raise ValueError("Select at least two files to compute kappa.")
    if not site_codes:
        raise ValueError("Select at least one site/code for kappa.")


def _prepare_comparisons(files, data, metadata, site_codes, *, duration_weighted=False):
    """Check the entire selection before seeking confirmation or computing scores."""
    _validate_selection(files, site_codes)
    sequences, clocks, alphabets = {}, {}, {}
    for filename in files:
        for site, code in site_codes:
            seq = _get_sequence(data, filename, site, code)
            context = f"{filename}, {site}/{code}"
            if not len(seq):
                raise ValueError(f"{context} has no coded observations.")
            labels = _alphabet_labels(seq)
            if labels and alphabets.setdefault((site, code), labels) != labels:
                raise ValueError(f"{context} has an incompatible coding alphabet.")
            sequences[filename, site, code] = seq
            if filename not in clocks:
                clocks[filename] = RecordingClock.from_metadata(
                    metadata.get(filename, {}), len(seq), context)
            clock = clocks[filename]
            expected_count = len(clock.times) if clock.notice else len(clock.times) - 1
            if clock.times and len(seq) != expected_count:
                raise ValueError(f"{context} has invalid timestamp metadata. Its observation count "
                                 "does not match the recording clock.")

    legacy = [f"{name} — {clock.notice}" for name, clock in clocks.items() if clock.notice]
    if legacy and (duration_weighted or len(legacy) != len(files)):
        raise ValueError("Complete media timestamps are required for this selection.\n\n"
                         + "\n".join(legacy))

    comparisons, digests = {}, {}
    for first, second in iter_file_pairs(files):
        a, b = clocks[first], clocks[second]
        try:
            verify_common_media(metadata.get(first, {}).get("media"),
                                metadata.get(second, {}).get("media"), digests)
            if legacy:
                require_matching_periods(a, b)
                if a.times and b.times and a.times != b.times:
                    raise ValueError("The available legacy timestamps differ. "
                                     "They do not support index-based comparison.")
                for site, code in site_codes:
                    size_a = len(sequences[first, site, code])
                    size_b = len(sequences[second, site, code])
                    if size_a != size_b:
                        raise ValueError(f"{site}/{code} sequences must have the same length "
                                         "for index-based comparison.")
                comparisons[first, second] = None
            elif duration_weighted:
                comparisons[first, second] = recording_overlap(a, b)
            else:
                comparisons[first, second] = match_sample_clocks(a, b)
        except ValueError as exc:
            raise ValueError(f"{first} and {second}\n\n{exc}") from exc
    return comparisons, legacy


def _interval_text(bounds, *, seconds=False):
    start, end = bounds
    if seconds:
        return f"{start / 1000:.3f}–{end / 1000:.3f} seconds"
    return f"{start}–{end} ms"


def _window_text(first, second, overlap, compared, *, seconds=False):
    return "\n".join([
        f"{first} · {_interval_text(overlap.first, seconds=seconds)}",
        f"{second} · {_interval_text(overlap.second, seconds=seconds)}",
        f"Common interval · {_interval_text(overlap.common, seconds=seconds)}",
        f"Compared interval · {_interval_text(compared, seconds=seconds)}",
    ])


def _range_confirmation(comparisons):
    ranges = []
    for (first, second), window in comparisons.items():
        overlap = window.overlap if isinstance(window, SampleAlignment) else window
        if overlap.first != overlap.second:
            compared = window.compared if isinstance(window, SampleAlignment) else overlap.common
            ranges.append(_window_text(first, second, overlap, compared, seconds=True))
    return "\n\n".join(ranges)


def sequence_kappa_result(files, data, site_codes, *, comparisons=None):
    """Build the wide kappa table, applying prepared sample comparisons if supplied."""
    _validate_selection(files, site_codes)
    headers = ["comparison"]
    headers.extend([f"K {site}-{code}" for site, code in site_codes])
    rows, details = [], []

    legacy = comparisons is not None and all(window is None for window in comparisons.values())
    title = "Sequence-based Kappa" if comparisons is None else "Sample-based Kappa"
    filename = kappa_filename(site_codes)
    if legacy:
        title = "Legacy index-based Kappa"
        filename = f"{pathlib.Path(filename).stem}_index_based.csv"

    for file1, file2 in iter_file_pairs(files):
        stem1 = pathlib.Path(file1).stem
        stem2 = pathlib.Path(file2).stem
        row = [f"{stem1}-{stem2}"]
        group = []
        alignment = comparisons[file1, file2] if comparisons is not None else None
        timing = ""
        if alignment is not None:
            timing = "\n" + _window_text(file1, file2, alignment.overlap, alignment.compared)
        elif legacy:
            timing = "\nCompared by sequence position using the confirmed legacy observation schedule."

        for site, code in site_codes:
            seq1 = _get_sequence(data, file1, site, code)
            seq2 = _get_sequence(data, file2, site, code)
            if alignment is not None:
                seq1, seq2 = alignment.sequences(seq1, seq2)
            matrix = _sample_matrix(seq1, seq2)
            score = format_kappa(_sample_kappa(matrix))
            row.append(score)
            labels = _alphabet_labels(seq1) or tuple(map(str, range(len(matrix))))
            stream = f"{site} / {code}"
            group.append(Detail(stream, f"{file1} and {file2} · {stream}",
                                f"{title.replace('Kappa', 'κ')} = {score}. Compared {matrix.sum()} samples. "
                                f"Diagonal cells count matching labels.{timing}",
                                CountHeatmap(labels, matrix, file1, file2)))

        rows.append(row)
        details.append(group)

    return AnalysisResult(title, filename, headers, rows, details)


def time_kappa_result(files, data, metadata, site_codes, tolerance):
    """Build one duration-weighted result per pair and selected stream."""
    _validate_selection(files, site_codes)
    tolerance = parse_tolerance(tolerance)
    headers = ["File A", "File B", "Site", "Code", "Tolerance (ms)", "Start (ms)",
               "End (ms)", "Compared (ms)", "Strict kappa"]
    if tolerance:
        headers.append("Adjusted kappa")
    headers.extend(["Strict disagreement (ms)", "Credited disagreement (ms)", "Warning"])

    timelines = {}
    alphabets = {}
    for site, code in site_codes:
        for filename in files:
            seq = _get_sequence(data, filename, site, code)
            alphabet = _alphabet_labels(seq)
            if alphabet and alphabets.setdefault((site, code), alphabet) != alphabet:
                raise ValueError(f"{filename}, {site}/{code}: incompatible coding alphabet.")
            timelines[filename, site, code] = Timeline.from_samples(
                metadata.get(filename, {}).get("times"), _sequence_values(seq),
                f"{filename}, {site}/{code}")

    rows, details = [], []
    for first, second in iter_file_pairs(files):
        for site, code in site_codes:
            a, b = timelines[first, site, code], timelines[second, site, code]
            result = time_agreement(a, b, tolerance)
            row = [first, second, site, code, str(tolerance),
                   str(result.start) if result.start is not None else "N/A",
                   str(result.end) if result.end is not None else "N/A",
                   str(result.duration),
                   format_kappa(result.strict) if result.strict is not None else "N/A"]
            if tolerance:
                row.append(format_kappa(result.adjusted) if result.adjusted is not None else "N/A")
            rows.append(row + [str(result.disagreement), str(result.credited), result.warning])
            stream = f"{site} / {code}"
            labels = alphabets.get((site, code))
            if not labels:
                labels = tuple(map(str, range(1 + max(max(a.states), max(b.states)))))
            summary = f"Strict κ = {row[8]}. "
            if tolerance:
                summary += f"Adjusted κ = {row[9]}. "
            summary += (f"Compared {result.duration} ms · disagreement {result.disagreement} ms · "
                        f"credited {result.credited} ms · tolerance {tolerance} ms. "
                        f"{first}: {len(a.times) - 1} samples, {_interval_text((a.times[0], a.times[-1]))}. "
                        f"{second}: {len(b.times) - 1} samples, {_interval_text((b.times[0], b.times[-1]))}.")
            if result.start is not None:
                summary += f" Compared interval · {_interval_text((result.start, result.end))}."
            details.append([Detail(stream, f"{first} and {second} · {stream}",
                                   (summary + " " + result.warning).strip(),
                                   RecordingTracks(first, second, a, b, labels))])
    stem = pathlib.Path(kappa_filename(site_codes)).stem
    return AnalysisResult("Time-aligned Kappa", f"{stem}_time_aligned_{tolerance}ms.csv",
                          headers, rows, details)


def build_kappa_table(files, data, site_codes, *, metadata=None, allow_legacy_index=False):
    """Build a wide kappa table, using recording clocks when metadata is supplied."""
    comparisons = None
    if metadata is not None:
        comparisons, legacy = _prepare_comparisons(files, data, metadata, site_codes)
        if legacy and not allow_legacy_index:
            raise ValueError("Complete media timestamps are required unless legacy index comparison "
                             "is explicitly enabled.\n\n" + "\n".join(legacy))
    result = sequence_kappa_result(files, data, site_codes, comparisons=comparisons)
    return result.headers, result.rows


def build_time_kappa_table(files, data, metadata, site_codes, tolerance):
    result = time_kappa_result(files, data, metadata, site_codes, tolerance)
    return result.headers, result.rows


def kappa_filename(site_codes):
    """
    Return the kappa CSV filename for the selected site/code pairs.
    """
    parts = [
        part
        for site, code in site_codes
        for part in (str(site), str(code))
    ]
    parts.append("kappa")
    return "_".join(parts) + TABLE_EXT


def to_csv_lines(headers, rows):
    """
    Convert a kappa table into semicolon-separated CSV lines.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=SEP, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return buffer.getvalue().splitlines(keepends=True)


class _ConfirmKappa(Dialog):
    def __init__(self, parent, title, message, details):
        self.message = message
        self.details = details
        super().__init__(parent, title=title)

    def body(self, master):
        ttk.Label(master, text=self.message, wraplength=475, justify="left").pack(
            anchor="w", padx=8, pady=(6, 8))
        text = ScrolledText(master, width=63, height=10, wrap="word",
                            font="TkDefaultFont")
        text.pack(fill="both", expand=True, padx=8)
        text.insert("1.0", self.details)
        text.configure(state="disabled")
        return text

    def buttonbox(self):
        buttons = ttk.Frame(self)
        buttons.pack(pady=8)
        ttk.Button(buttons, text="Proceed", command=self.ok).pack(side="left", padx=4)
        ttk.Button(buttons, text="Cancel", command=self.cancel).pack(side="left", padx=4)
        self.bind("<Escape>", self.cancel)

    def apply(self):
        self.result = True


class KappaTool:
    """
    Dedicated analyser tab for Cohen kappa exports.
    """

    def __init__(self, parent):
        self.parent = parent
        self.selected_files = []
        self.gdata = {}
        self.metadata = {}
        self.codes_by_site = {}
        self.select_all_sites_var = tkinter.BooleanVar(value=False)
        self.select_all_codes_var = tkinter.BooleanVar(value=False)

        self.tab = scrollable_page(parent.notebook.add("Kappa"))
        doc_frame = tkinter.LabelFrame(self.tab, text="Kappa")
        tkinter.Label(
            doc_frame,
            text="Compute Cohen kappa between all selected file pairs.",
        ).grid(sticky=tkinter.W)
        doc_frame.grid(column=0, row=0, sticky=tkinter.W)

        select_frame = tkinter.LabelFrame(self.tab, text="Site and code")
        select_frame.grid(column=0, row=1, sticky=tkinter.W)

        self.site_choice = Pmw.ScrolledListBox(
            select_frame,
            items=[],
            labelpos="nw",
            label_text="Sites",
        )
        self.site_choice.configure(listbox_height=3, listbox_selectmode="multiple",
                                   listbox_exportselection=False)
        self.site_choice.grid(column=0, row=0)
        self.site_choice.component("listbox").bind(
            "<<ListboxSelect>>",
            self._on_site_selection_change,
        )

        self.code_choice = Pmw.ScrolledListBox(
            select_frame,
            items=[],
            labelpos="nw",
            label_text="Codes",
        )
        self.code_choice.configure(listbox_height=3, listbox_selectmode="multiple",
                                   listbox_exportselection=False)
        self.code_choice.grid(column=1, row=0)
        self.code_choice.component("listbox").bind(
            "<<ListboxSelect>>",
            self._on_code_selection_change,
        )

        site_all = tkinter.Checkbutton(
            select_frame,
            text="Select all sites",
            variable=self.select_all_sites_var,
            command=self.toggle_all_sites,
        )
        site_all.grid(column=0, row=1, sticky=tkinter.W)

        code_all = tkinter.Checkbutton(
            select_frame,
            text="Select all codes",
            variable=self.select_all_codes_var,
            command=self.toggle_all_codes,
        )
        code_all.grid(column=1, row=1, sticky=tkinter.W)

        options = tkinter.Frame(self.tab)
        options.grid(column=0, row=2, sticky="w")
        self.time_aligned = tkinter.BooleanVar(value=False)
        self.tolerance = tkinter.StringVar(value="0")
        self.time_checkbox = tkinter.Checkbutton(
            options, text="Use duration-weighted Kappa", variable=self.time_aligned,
            command=self._toggle_alignment)
        self.time_checkbox.grid(row=0, column=0, sticky="w")
        tkinter.Label(options, text="Timestamp tolerance (ms)").grid(row=0, column=1)
        self.tolerance_entry = ttk.Entry(options, width=9, textvariable=self.tolerance,
                                         state="disabled")
        self.tolerance_entry.grid(row=0, column=2)
        tkinter.Label(options, justify="left", wraplength=620,
                      text="By default, Kappa counts observations with matching media intervals. "
                           "Duration weighting compares shared recording time. Its tolerance "
                           "can credit small differences between matching behaviour changes.").grid(
                               row=1, column=0, columnspan=3, sticky="w")

        launch_but = tkinter.Button(self.tab, text="Compute kappa",
                                    command=self.launch)
        launch_but.grid(column=0, row=3, sticky=tkinter.W)

        self.tab.columnconfigure(0, weight=1)
        self.tab.rowconfigure(4, weight=1)
        self.panel = ResultPanel(self.tab)
        self.panel.grid(column=0, row=4, sticky="nsew")
        self.panel.grid_remove()
        self.results = self.panel.tree

    def _toggle_alignment(self):
        self.tolerance_entry.configure(state="normal" if self.time_aligned.get() else "disabled")

    def _set_all_selection(self, scrolled_listbox, selected):
        listbox = scrolled_listbox.component("listbox")
        listbox.selection_clear(0, tkinter.END)
        if selected and listbox.size():
            listbox.selection_set(0, tkinter.END)

    def _select_items(self, scrolled_listbox, items, selected_items):
        listbox = scrolled_listbox.component("listbox")
        listbox.selection_clear(0, tkinter.END)
        selected_item_set = set(selected_items)
        for index, item in enumerate(items):
            if item in selected_item_set:
                listbox.selection_set(index)

    def _sync_select_all_sites(self):
        selected_sites = self.site_choice.getcurselection()
        all_selected = bool(self.codes_by_site) and (
            len(selected_sites) == len(self.codes_by_site)
        )
        self.select_all_sites_var.set(all_selected)

    def _sync_select_all_codes(self, codes):
        selected_codes = self.code_choice.getcurselection()
        all_selected = bool(codes) and len(selected_codes) == len(codes)
        self.select_all_codes_var.set(all_selected)

    def _on_site_selection_change(self, event=None):
        self._sync_select_all_sites()
        self.update_code_choices()

    def _on_code_selection_change(self, event=None):
        codes = code_names_for_sites(self.codes_by_site,
                                     self.site_choice.getcurselection())
        self._sync_select_all_codes(codes)

    def toggle_all_sites(self):
        """
        Select or clear all sites, then refresh the relevant code list.
        """
        self._set_all_selection(self.site_choice,
                                self.select_all_sites_var.get())
        self.update_code_choices()

    def toggle_all_codes(self):
        """
        Select or clear all currently visible codes.
        """
        self._set_all_selection(self.code_choice,
                                self.select_all_codes_var.get())

    def update_state(self, state):
        """
        Update selectable sites and codes after files are loaded.
        """
        self.selected_files = state["files"]
        self.gdata = state["data"]
        self.metadata = state.get("metadata", {})
        self.codes_by_site = common_codes_by_site(self.selected_files,
                                                  self.gdata)

        self.site_choice.setlist(list(self.codes_by_site.keys()))
        self.select_all_sites_var.set(bool(self.codes_by_site))
        self.select_all_codes_var.set(bool(self.codes_by_site))
        self._set_all_selection(self.site_choice, bool(self.codes_by_site))
        self.update_code_choices()

    def update_code_choices(self):
        """
        Refresh the code list from the currently selected sites.
        """
        previously_selected_codes = self.code_choice.getcurselection()
        selected_sites = self.site_choice.getcurselection()
        codes = code_names_for_sites(self.codes_by_site, selected_sites)
        self.code_choice.setlist(codes)
        if self.select_all_codes_var.get():
            self._set_all_selection(self.code_choice, bool(codes))
        else:
            self._select_items(self.code_choice, codes,
                               previously_selected_codes)
        self._sync_select_all_codes(codes)

    def _selected_site_codes(self):
        selected_sites = self.site_choice.getcurselection()
        selected_codes = self.code_choice.getcurselection()
        return site_codes_from_selection(self.codes_by_site,
                                         selected_sites,
                                         selected_codes)

    def launch(self):
        try:
            site_codes = self._selected_site_codes()
            duration_weighted = self.time_aligned.get()
            tolerance = parse_tolerance(self.tolerance.get()) if duration_weighted else None
            comparisons, legacy = _prepare_comparisons(
                self.selected_files, self.gdata, self.metadata, site_codes,
                duration_weighted=duration_weighted)
            if legacy:
                dialog = _ConfirmKappa(
                    self.tab, "Legacy index-based Kappa",
                    "These files lack complete media timestamps. Proceed only if you can confirm "
                    "that the observers coded the same intervals in the same order. "
                    "Kappa will compare by sequence position.", "\n".join(legacy))
                if not dialog.result:
                    return
            elif ranges := _range_confirmation(comparisons):
                dialog = _ConfirmKappa(
                    self.tab, "Different recording time ranges detected",
                    "Only observations within each pair’s compared interval will contribute to Kappa.",
                    ranges)
                if not dialog.result:
                    return

            if duration_weighted:
                result = time_kappa_result(self.selected_files, self.gdata, self.metadata,
                                           site_codes, tolerance)
            else:
                result = sequence_kappa_result(self.selected_files, self.gdata, site_codes,
                                               comparisons=comparisons)
        except (ValueError, IndexError, KeyError) as exc:
            tkinter.messagebox.showerror(title="Could not compute kappa",
                                         message=str(exc), parent=self.tab)
            return
        self.panel.present(result, pathlib.Path(self.parent.cwd) / "kappa")
