"""
Cohen kappa support for the analyser GUI.
"""

import csv
import itertools
import io
import os
import pathlib
import tkinter
import tkinter.filedialog
import tkinter.messagebox

import numpy as np
import Pmw


ALL_SITES_LABEL = "All"
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


def cohen_kappa(seq1, seq2):
    """
    Compute Cohen's kappa for two coded sequences.
    """
    values1, values2, alphabet_len = _validate_sequences(seq1, seq2)
    max_value = int(max(values1.max(initial=0), values2.max(initial=0)))
    nb_labels = max(alphabet_len, max_value + 1)
    matrix = np.zeros((nb_labels, nb_labels), dtype=float)

    for true_value, pred_value in zip(values1, values2):
        matrix[int(true_value), int(pred_value)] += 1

    nb_items = matrix.sum()
    observed = np.trace(matrix) / nb_items
    expected = np.dot(matrix.sum(axis=1), matrix.sum(axis=0)) / (nb_items ** 2)

    if expected == 1:
        return 1.0 if observed == 1 else 0.0

    return float((observed - expected) / (1 - expected))


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
    if ALL_SITES_LABEL in selected_sites:
        sites = list(codes_by_site.keys())
    else:
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
    if ALL_SITES_LABEL in selected_sites:
        return [
            (site, code)
            for site, codes in codes_by_site.items()
            for code in codes
        ]

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


def build_kappa_table(files, data, site_codes):
    """
    Build the wide kappa table shown by the analyser.
    """
    if len(files) < 2:
        raise ValueError("Select at least two files to compute kappa.")
    if not site_codes:
        raise ValueError("Select at least one site/code for kappa.")

    headers = ["comparison"]
    headers.extend([f"K {site}{code}" for site, code in site_codes])
    rows = []

    for file1, file2 in iter_file_pairs(files):
        stem1 = pathlib.Path(file1).stem
        stem2 = pathlib.Path(file2).stem
        row = [f"{stem1}-{stem2}"]

        for site, code in site_codes:
            seq1 = _get_sequence(data, file1, site, code)
            seq2 = _get_sequence(data, file2, site, code)
            row.append(format_kappa(cohen_kappa(seq1, seq2)))

        rows.append(row)

    return headers, rows


def to_csv_lines(headers, rows):
    """
    Convert a kappa table into semicolon-separated CSV lines.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=SEP, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return buffer.getvalue().splitlines(keepends=True)


class KappaTool:
    """
    Dedicated analyser tab for Cohen kappa exports.
    """

    def __init__(self, parent):
        self.parent = parent
        self.selected_files = []
        self.gdata = {}
        self.codes_by_site = {}

        self.tab = parent.notebook.add("Kappa")
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
        self.site_choice.configure(listbox_selectmode="multiple",
                                   listbox_exportselection=False)
        self.site_choice.grid(column=0, row=0)

        self.code_choice = Pmw.ScrolledListBox(
            select_frame,
            items=[],
            labelpos="nw",
            label_text="Codes",
        )
        self.code_choice.configure(listbox_selectmode="multiple",
                                   listbox_exportselection=False)
        self.code_choice.grid(column=1, row=0)

        update_but = tkinter.Button(select_frame, text="Update codes",
                                    command=self.update_code_choices)
        update_but.grid(column=0, row=1, sticky=tkinter.W)

        launch_but = tkinter.Button(self.tab, text="Compute kappa",
                                    command=self.launch)
        launch_but.grid(column=0, row=2, sticky=tkinter.W)

    def _select_all(self, scrolled_listbox):
        listbox = scrolled_listbox.component("listbox")
        listbox.selection_clear(0, tkinter.END)
        listbox.selection_set(0, tkinter.END)

    def _select_first(self, scrolled_listbox):
        listbox = scrolled_listbox.component("listbox")
        listbox.selection_clear(0, tkinter.END)
        listbox.selection_set(0)

    def update_state(self, state):
        """
        Update selectable sites and codes after files are loaded.
        """
        self.selected_files = state["files"]
        self.gdata = state["data"]
        self.codes_by_site = common_codes_by_site(self.selected_files,
                                                  self.gdata)

        self.site_choice.setlist([ALL_SITES_LABEL] +
                                 list(self.codes_by_site.keys()))
        self._select_first(self.site_choice)
        self.update_code_choices()

    def update_code_choices(self):
        """
        Refresh the code list from the currently selected sites.
        """
        selected_sites = self.site_choice.getcurselection()
        codes = code_names_for_sites(self.codes_by_site, selected_sites)
        self.code_choice.setlist(codes)
        if ALL_SITES_LABEL in selected_sites and codes:
            self._select_all(self.code_choice)

    def _selected_site_codes(self):
        selected_sites = self.site_choice.getcurselection()
        selected_codes = self.code_choice.getcurselection()
        return site_codes_from_selection(self.codes_by_site,
                                         selected_sites,
                                         selected_codes)

    def launch(self):
        """
        Compute kappa and write a CSV into the selected output directory.
        """
        try:
            site_codes = self._selected_site_codes()
            headers, rows = build_kappa_table(self.selected_files,
                                              self.gdata,
                                              site_codes)
        except Exception as exc:
            tkinter.messagebox.showerror(title="Could not compute kappa",
                                         message=str(exc))
            return

        initialdir = os.path.join(self.parent.cwd, "kappa")
        try:
            pathlib.Path(initialdir).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            tkinter.messagebox.showerror(title="Could not create output folder",
                                         message=str(exc))
            return

        outdir = tkinter.filedialog.askdirectory(initialdir=initialdir,
                                                 mustexist=True)
        if not outdir:
            return

        outfile = os.path.join(outdir, "kappa" + TABLE_EXT)
        try:
            with open(outfile, "w", encoding="utf-8", newline="") as datafile:
                datafile.writelines(to_csv_lines(headers, rows))
        except OSError as exc:
            tkinter.messagebox.showerror(title="Could not write kappa CSV",
                                         message=str(exc))
            return

        tkinter.messagebox.showinfo(title="Kappa CSV written",
                                    message=outfile)
