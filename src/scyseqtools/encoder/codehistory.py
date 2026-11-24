"""Scrollable view of the encoder's committed coding steps."""

import colorsys
import tkinter as tk
from tkinter import font, ttk


def site_colors(encoding):
    colors = {}
    for index, site in enumerate(sorted(encoding)):
        if index < 2:
            color = ("#dfd3fa", "#d5f2c6")[index]
        else:
            hue = (0.07 + (index - 2) * 0.61803398875) % 1
            rgb = colorsys.hls_to_rgb(hue, 0.83, 0.72)
            color = "#{:02x}{:02x}{:02x}".format(*(round(v * 255) for v in rgb))
        colors[site] = color
    return colors


def filter_choices(encoding):
    categories = {name for codes in encoding.values() for name in codes}
    values = {v for codes in encoding.values() for alphabet in codes.values() for v in alphabet}
    choices = {"All": (None, None)}
    for kind, names in (("Site", encoding), ("Category", categories), ("Value", values)):
        for name in sorted(names):
            choices[f"{kind}: {name}"] = (kind, name)
    return choices


def observations(encoding, data, step, selection):
    """Decode one 1-based sample, retaining the matching categories within each site."""
    kind, target = selection
    for site in sorted(encoding):
        if kind == "Site" and site != target:
            continue
        matches = []
        for category, alphabet in encoding[site].items():
            if kind == "Category" and category != target:
                continue
            symbol = alphabet[data[site][category][step - 1]]
            if kind != "Value" or symbol == target:
                matches.append(f"{category}: {symbol}")
        if matches:
            yield site, ", ".join(matches)


class CodeHistoryPanel(ttk.Frame):
    def __init__(self, parent, navigate):
        super().__init__(parent, padding=6)
        self.navigate = navigate
        self.selected_step = None
        self.encoding = {}
        self.data = {}
        self.times = {}
        self.line_steps = {}
        self.step_lines = {}
        self.last_time = None
        self.columnconfigure(1, weight=1)
        self.rowconfigure(3, weight=1)

        ttk.Label(self, text="Code History", font="TkHeadingFont").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))
        ttk.Label(self, text="Filter").grid(row=1, column=0, sticky="w")
        self.filter = ttk.Combobox(self, state="readonly", width=18)
        self.filter.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(4, 0))
        self.filter.bind("<<ComboboxSelected>>", lambda event: self.redraw())

        header = ttk.Frame(self)
        header.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 2))
        column_width = font.nametofont("TkDefaultFont").measure("00000.000  ")
        header.columnconfigure(0, minsize=column_width)
        ttk.Label(header, text="Time (s)").grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="Observations").grid(row=0, column=1, sticky="w")

        self.body = tk.Text(self, font="TkDefaultFont", width=37, height=12,
                            wrap="word", tabs=(column_width,), padx=3, cursor="arrow",
                            state="disabled", takefocus=True)
        self.body.grid(row=3, column=0, columnspan=2, sticky="nsew")
        scroll = ttk.Scrollbar(self, command=self.body.yview)
        scroll.grid(row=3, column=2, sticky="ns")
        self.body.configure(yscrollcommand=scroll.set)
        self.body.tag_configure("observation", lmargin2=column_width, spacing3=2)
        self.body.tag_configure("timestamp", foreground="#244969", underline=True)
        self.body.tag_configure("selected", background="#c9e4fa")
        self.body.bind("<Button-1>", self._click)
        self.body.bind("<Up>", lambda event: self._move(-1))
        self.body.bind("<Down>", lambda event: self._move(1))
        self.body.bind("<Return>", lambda event: self.goto())
        self.goto_button = ttk.Button(self, text="Goto", command=self.goto, state="disabled")
        self.goto_button.grid(row=4, column=0, columnspan=3, sticky="w", pady=4)

        legend = ttk.LabelFrame(self, text="Site Legend", padding=3)
        legend.grid(row=5, column=0, columnspan=3, sticky="ew")
        legend.columnconfigure(0, weight=1)
        self.legend = tk.Text(legend, width=1, height=1, wrap="word", font="TkDefaultFont",
                              relief="flat", state="disabled", takefocus=False)
        self.legend.grid(row=0, column=0, sticky="ew")
        self.legend_scroll = ttk.Scrollbar(legend, command=self.legend.yview)
        self.legend.configure(yscrollcommand=self.legend_scroll.set)
        self.set_framework({})

    def set_framework(self, encoding):
        self.encoding = encoding
        self.choices = filter_choices(encoding)
        self.filter.configure(values=list(self.choices))
        self.filter.current(0)
        colors = site_colors(encoding)
        self.site_tags = {}
        self.legend.configure(state="normal", height=max(1, min(4, len(colors))))
        self.legend.delete("1.0", "end")
        for index, (site, color) in enumerate(colors.items()):
            tag = f"site_{index}"
            self.site_tags[site] = tag
            self.legend.tag_configure(tag, background=color)
            self.body.tag_configure(tag, background=color)
            if index:
                self.legend.insert("end", "\n")
            self.legend.insert("end", "    ", tag)
            self.legend.insert("end", f"  {site}")
        self.legend.configure(state="disabled")
        if len(colors) > 4:
            self.legend_scroll.grid(row=0, column=1, sticky="ns")
        else:
            self.legend_scroll.grid_remove()

    def load(self, data, times):
        self.data = data
        self.times = times
        self.redraw()

    def recorded(self, data, step, timestamp):
        self.data = data
        append = step not in self.times and (self.last_time is None or timestamp >= self.last_time)
        self.times[step] = timestamp
        if append:
            at_end = self.body.yview()[1] >= 0.999
            self.body.configure(state="normal")
            self._insert(step)
            self.body.configure(state="disabled")
            if at_end:
                self.body.see("end")
        else:
            self.redraw()

    def _insert(self, step):
        timestamp = self.times[step]
        selection = self.choices[self.filter.get()]
        first = len(self.line_steps) + 1
        for site, description in observations(self.encoding, self.data, step, selection):
            line = len(self.line_steps) + 1
            if line > 1:
                self.body.insert("end", "\n", ())
            if line == first and timestamp != self.last_time:
                self.body.insert("end", f"{timestamp / 1000:.3f}", "timestamp")
            self.body.insert("end", "\t", ())
            self.body.insert("end", site, self.site_tags[site])
            self.body.insert("end", f"  {description}", ())
            self.line_steps[line] = step
        last = len(self.line_steps)
        if last >= first:
            self.step_lines[step] = (first, last)
            self.body.tag_add("observation", f"{first}.0", f"{last}.end")
            self.last_time = timestamp

    def redraw(self):
        position = self.body.yview()[0]
        self.body.configure(state="normal")
        self.body.delete("1.0", "end")
        self.step_lines.clear()
        self.line_steps.clear()
        self.last_time = None
        for step in sorted(self.times, key=self.times.get):
            self._insert(step)
        self.body.configure(state="disabled")
        self.body.yview_moveto(position)
        self.select(self.selected_step)

    def select(self, step, reveal=False):
        self.body.tag_remove("selected", "1.0", "end")
        self.selected_step = step if step in self.step_lines else None
        self.goto_button.state(["disabled"] if self.selected_step is None else ["!disabled"])
        if self.selected_step is not None:
            first, last = self.step_lines[step]
            # Distinct legacy samples can share a timestamp and have separate comments.
            timestamp = self.times[step]
            while first > 1 and self.times[self.line_steps[first - 1]] == timestamp:
                first -= 1
            while last < len(self.line_steps) and self.times[self.line_steps[last + 1]] == timestamp:
                last += 1
            self.body.tag_add("selected", f"{first}.0", f"{last}.end")
            if reveal:
                self.body.see(f"{self.step_lines[step][0]}.0")

    def _click(self, event):
        index = self.body.index(f"@{event.x},{event.y}")
        line = int(index.split(".")[0])
        bounds = self.body.dlineinfo(index)
        if bounds and bounds[1] <= event.y < bounds[1] + bounds[3]:
            step = self.line_steps.get(line)
            self.body.focus_set()
            if "timestamp" in self.body.tag_names(index):
                if self.navigate(step):
                    self.select(step)
            else:
                self.select(step)
        return "break"

    def _move(self, direction):
        steps = list(self.step_lines)
        if steps:
            index = steps.index(self.selected_step) + direction if self.selected_step in steps else 0
            self.select(steps[max(0, min(index, len(steps) - 1))], reveal=True)
        return "break"

    def goto(self):
        if self.selected_step is not None:
            self.navigate(self.selected_step)
        return "break"
