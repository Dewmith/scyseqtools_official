"""Label frequencies for one site and code across the loaded recordings."""

from pathlib import Path
from tkinter import messagebox, ttk

from scyseqtools.analyser.kappa import common_codes_by_site
from scyseqtools.analyser.symbolix import statistics_result
from scyseqtools.analyser.resultpanel import ResultPanel, scrollable_page


class StatisticsTool:
    def __init__(self, parent):
        self.parent = parent
        self.files = []
        self.tab = parent.notebook.add("Statistics")
        body = scrollable_page(self.tab)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(1, weight=1)
        controls = ttk.Frame(body, padding=5)
        controls.grid(row=0, column=0, sticky="w")
        ttk.Label(controls, text="Site").grid(row=0, column=0, sticky="w")
        ttk.Label(controls, text="Code").grid(row=0, column=1, sticky="w")
        self.site = ttk.Combobox(controls, state="readonly")
        self.code = ttk.Combobox(controls, state="readonly")
        self.site.grid(row=1, column=0)
        self.code.grid(row=1, column=1)
        self.site.bind("<<ComboboxSelected>>", lambda e: self._update_codes())
        ttk.Button(controls, text="Compute statistics", command=self.launch).grid(row=1, column=2)
        self.panel = ResultPanel(body)
        self.panel.grid(row=1, column=0, sticky="nsew")
        self.panel.grid_remove()

    def update_state(self, state):
        self.files = state["files"]
        self.data = state["data"]
        self.sites = common_codes_by_site(self.files, self.data)
        self.site.configure(values=list(self.sites))
        if self.site.get() not in self.sites:
            self.site.set(next(iter(self.sites), ""))
        self._update_codes()

    def _update_codes(self):
        codes = self.sites.get(self.site.get(), [])
        self.code.configure(values=codes)
        if self.code.get() not in codes:
            self.code.set(codes[0] if codes else "")

    def launch(self):
        site, code = self.site.get(), self.code.get()
        if not site or not code:
            messagebox.showerror("Could not compute statistics",
                                 "Load files with a shared site and code.", parent=self.tab)
            return
        try:
            records = [dict(filename=name, sitename=site, codename=code,
                            sequence=self.data[name][site][code]) for name in self.files]
            result = statistics_result(records)
        except (KeyError, ValueError) as exc:
            messagebox.showerror("Could not compute statistics", str(exc), parent=self.tab)
            return
        self.panel.present(result, Path(self.parent.cwd) / "statistics")
