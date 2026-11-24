"""Resolve analyser export filename conflicts before the files are written."""

from collections import Counter
from functools import partial
import stat
import tkinter as tk
from tkinter import font, simpledialog

from scyseqtools.analyser.output_files import SaveDestination, output_path


def _entry_mode(path):
    try:
        return path.lstat().st_mode
    except FileNotFoundError:
        return None


def _rename(paths, reserved, name):
    name = name.strip()
    if not name:
        raise ValueError("Enter a new file name.")
    first = output_path(paths[0].parent, name)
    extension = paths[0].suffix
    if not first.suffix:
        first = first.with_name(first.name + extension)
    elif first.suffix.lower() != extension.lower():
        raise ValueError(f"Use the {extension} file extension or leave it off.")
    new_paths = (first, *(path.with_name(first.stem + path.suffix) for path in paths[1:]))
    for path in new_paths:
        if path in reserved or _entry_mode(path) is not None:
            raise ValueError(f"{path.name} is already in use. Choose another name.")
    return tuple(SaveDestination(path) for path in new_paths)


def resolve_destinations(parent, groups):
    """Return destinations in input order. Related paths in a group share a new base name."""
    groups = tuple(groups)
    remaining = Counter(path for paths in groups for path in paths)
    resolved = []
    used = set()
    for paths in groups:
        remaining.subtract(paths)
        existing = {path: mode for path in paths if (mode := _entry_mode(path)) is not None}
        duplicate = used.intersection(paths)
        destinations = tuple(SaveDestination(path, replace=path in existing) for path in paths)
        if existing or duplicate:
            reserved = used.union(path for path, count in remaining.items() if count > 0)
            can_replace = not duplicate and all(map(stat.S_ISREG, existing.values()))
            replace = destinations if can_replace else None
            conflicts = tuple(path.name for path in paths if path in existing or path in duplicate)
            dialog = _SaveConflictDialog(parent, conflicts, bool(existing), replace,
                                         partial(_rename, paths, reserved))
            destinations = dialog.result
            if destinations is None:
                return None
        resolved.extend(destinations)
        used.update(destination.path for destination in destinations)
    return tuple(resolved)


class _SaveConflictDialog(simpledialog.Dialog):
    background = "#dedede"

    def __init__(self, parent, conflicts, existing, replace, rename):
        self.conflicts = conflicts
        self.existing = existing
        self.replacements = replace
        self.rename = rename
        super().__init__(parent, title="Save analysis file")

    def body(self, master):
        self.resizable(False, False)
        self.configure(background=self.background)
        master.configure(background=self.background, padx=11, pady=7)
        master.columnconfigure(1, weight=1, minsize=self.winfo_pixels("3.5i"))

        warning = tk.Canvas(master, width=50, height=44, background=self.background,
                            highlightthickness=0)
        warning.create_polygon(5, 37, 7, 32, 21, 6, 23, 3, 26, 6, 40, 32, 42, 37,
                               37, 38, 9, 38, smooth=True, fill="#ffdc16", outline="#302900", width=2)
        warning.create_line(23, 15, 23, 25, width=4, capstyle="round")
        warning.create_oval(21, 28, 25, 32, fill="black", outline="")
        warning.grid(row=0, column=0, rowspan=2, sticky="nw", padx=(2, 0))

        self.body_font = font.nametofont("TkDefaultFont", root=self).copy()
        self.body_font.configure(size=10)
        self.heading_font = self.body_font.copy()
        self.heading_font.configure(size=14, weight="bold")
        self.existing_font = self.body_font.copy()
        self.existing_font.configure(size=10, slant="italic")
        heading = "File already exists." if self.existing else "File name already in use."
        self._label(master, heading, font=self.heading_font).grid(row=0, column=1, sticky="w")
        if self.replacements:
            summary = ("A file with this name already exists in the selected folder. "
                       "Enter a new name below or replace the existing file.")
        else:
            summary = "This name is already in use. Enter a new name below."
        self._label(master, summary, wraplength="3.39i").grid(row=1, column=1, sticky="w", pady=(2, 9))

        name_row = tk.Frame(master, background=self.background)
        name_row.grid(row=2, column=0, columnspan=2, sticky="ew")
        self._label(name_row, "New file name:").pack(side="left", padx=(0, 8))
        self.entry = tk.Entry(name_row, width=32, background="white", font=self.body_font,
                              borderwidth=2, relief="sunken")
        self.entry.pack(side="left", fill="x", expand=True)
        self.bind("<Map>", self._focus_entry)

        label = "Existing file" if len(self.conflicts) == 1 else "Existing files"
        if not self.existing:
            label = "Name in use"
        self._label(master, f"{label}: {', '.join(self.conflicts)}", font=self.existing_font,
                    wraplength="4.1i").grid(row=3, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self.error = self._label(master, "", foreground="#9b1c1c", wraplength="4.1i")
        self.error.grid(row=4, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self.error.grid_remove()
        return self.entry

    def _focus_entry(self, event):
        if event.widget is self:
            self.after_idle(self.entry.focus_set)

    def _label(self, parent, text, **options):
        options.setdefault("font", self.body_font)
        return tk.Label(parent, text=text, background=self.background, justify="left", **options)

    def buttonbox(self):
        box = tk.Frame(self, background=self.background)
        box.pack(pady=(11, 18))
        replace = tk.Button(box, text="Replace", width=12, font=self.body_font, command=self._replace)
        if not self.replacements:
            replace.configure(state="disabled")
        replace.pack(side="left", padx=14)
        tk.Button(box, text="Save as new", width=16, font=self.body_font,
                  command=self.ok).pack(side="left", padx=14)
        tk.Button(box, text="Cancel", width=11, font=self.body_font,
                  command=self.cancel).pack(side="left", padx=14)
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)

    def _replace(self):
        self.result = self.replacements
        self.cancel()

    def validate(self):
        try:
            self.result = self.rename(self.entry.get())
        except (ValueError, OSError) as exc:
            self.error.configure(text=str(exc))
            self.error.grid()
            return False
        return True
