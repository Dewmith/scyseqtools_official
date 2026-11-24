"""The Configuration tab's independent, read-only CDX preview."""

from bisect import bisect_right
from pathlib import Path
import tkinter as tk
from tkinter import font, ttk

from matplotlib.ticker import MaxNLocator

from scyseqtools.analyser.preview_data import PreviewReader


PLACEHOLDER = "Select a file to preview its contents."
PAGE_SIZE = 200


def _seconds(milliseconds):
    if milliseconds is None:
        return "—"
    return f"{milliseconds / 1000:.6f}".rstrip("0").rstrip(".")


def _duration(milliseconds):
    if milliseconds is None:
        return "Unavailable"
    total_seconds, fraction = divmod(round(milliseconds), 1000)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    result = f"{hours:02}:{minutes:02}:{seconds:02}"
    return f"{result}.{fraction:03}" if fraction else result


def _scrollable_tree(parent, **options):
    frame = ttk.Frame(parent)
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(0, weight=1)
    tree = ttk.Treeview(frame, **options)
    vertical = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    horizontal = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
    tree.grid(row=0, column=0, sticky="nsew")
    vertical.grid(row=0, column=1, sticky="ns")
    horizontal.grid(row=1, column=0, sticky="ew")
    return frame, tree


class PreviewTimeline(ttk.LabelFrame):
    """Display only the lanes and time marks within the canvas viewport."""

    HEADER = 19
    LANE = 17

    def __init__(self, parent):
        super().__init__(parent, text="Timeline", padding=3)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.data = None
        self._layout = []
        self._site_ends = []
        self._bounds = self._view = (0.0, 1.0)
        self._draw_job = self._hover_job = None
        self._hover_target = None
        self._hits = {}
        self._font = font.nametofont("TkDefaultFont", root=self)

        controls = ttk.Frame(self)
        controls.grid(row=0, column=0, columnspan=2, sticky="ew")
        self._zoom_buttons = []
        for text, command in (("Zoom in", lambda: self._zoom(0.5)),
                              ("Zoom out", lambda: self._zoom(2)),
                              ("Fit", self._fit)):
            button = ttk.Button(controls, text=text, command=command, width=8)
            button.pack(side="left")
            self._zoom_buttons.append(button)

        self.body = tk.Canvas(self, width=200, height=98, highlightthickness=0,
                              background="white")
        self.body.grid(row=1, column=0, sticky="nsew")
        self._vertical = ttk.Scrollbar(self, orient="vertical", command=self.body.yview)
        self._vertical.grid(row=1, column=1, sticky="ns")
        self.body.configure(yscrollcommand=self._scrolled)
        self.axis = tk.Canvas(self, width=1, height=22, highlightthickness=0, background="white")
        self.axis.grid(row=2, column=0, sticky="ew")
        self._horizontal = ttk.Scrollbar(self, orient="horizontal", command=self._pan)
        self._horizontal.grid(row=3, column=0, sticky="ew")
        self._tooltip = tk.Label(self.body, background="#fffbd6", foreground="#202020",
                                 relief="solid", borderwidth=1, padx=5, pady=3,
                                 justify="left", wraplength=255)
        self.body.bind("<Configure>", self._schedule_draw)
        self.body.bind("<Motion>", self._motion)
        self.body.bind("<Leave>", self._hide_tooltip)
        self.body.bind("<MouseWheel>", self._wheel)
        self.body.bind("<Button-4>", lambda event: self._wheel(event, -1))
        self.body.bind("<Button-5>", lambda event: self._wheel(event, 1))
        self.set_data(None)

    def set_data(self, data):
        self.data = data
        self._layout = []
        self._site_ends = []
        position = 0
        if data is not None and data.extent is not None:
            for site, categories in data.sites.items():
                tracks = [data.tracks[site, category] for category in categories
                          if (site, category) in data.tracks]
                self._layout.append((position, site, tracks))
                position += self.HEADER + self.LANE * max(len(tracks), 1)
                self._site_ends.append(position)
            start, end = data.extent
            self._bounds = (start, end) if end > start else (start - 500, end + 500)
        for button in self._zoom_buttons:
            button.state(["!disabled"] if self._layout else ["disabled"])
        self.body.configure(height=max(55, min(145, position)), scrollregion=(0, 0, 1, position))
        self.body.yview_moveto(0)
        self._fit()

    def _fit(self):
        self._view = self._bounds
        self._schedule_draw()

    def _set_view(self, left, span):
        start, end = self._bounds
        span = min(end - start, span)
        left = max(start, min(left, end - span))
        self._view = (left, left + span)
        self._schedule_draw()

    def _zoom(self, factor):
        left, right = self._view
        span = max(0.001, (right - left) * factor)
        self._set_view(left + ((right - left) - span) / 2, span)

    def _pan(self, operation, argument, units=None):
        start, end = self._bounds
        left, right = self._view
        span = right - left
        if operation == "moveto":
            left = start + float(argument) * (end - start)
        else:
            left += int(argument) * span * (0.85 if units == "pages" else 0.1)
        self._set_view(left, span)

    def _wheel(self, event, direction=None):
        if direction is None:
            direction = -1 if event.delta > 0 else 1
        self.body.yview_scroll(direction, "units")
        return "break"

    def _scrolled(self, first, last):
        self._vertical.set(first, last)
        self._schedule_draw()

    def _schedule_draw(self, event=None):
        if self._draw_job is None:
            self._draw_job = self.after_idle(self._draw)

    def _clip_label(self, label, width):
        if self._font.measure(label) <= width:
            return label
        while label and self._font.measure(label + "…") > width:
            label = label[:len(label) // 2] if len(label) > 120 else label[:-1]
        return label + "…"

    def _draw(self):
        self._draw_job = None
        self._hide_tooltip()
        self.body.delete("all")
        self.axis.delete("all")
        self._hits.clear()
        if not self._layout:
            if self.data is not None:
                message = "No timed observations." if self.data.total else "No observations recorded."
                self.body.create_text(8, 10, text=message, anchor="nw", fill="#363636")
            self._horizontal.set(0, 1)
            return

        width = self.body.winfo_width()
        if width < 110:
            return
        label_width = min(145, max(68, width // 4))
        plot_end = width - 8
        plot_width = plot_end - label_width
        left, right = self._view
        start, end = self._bounds
        self._horizontal.set((left - start) / (end - start), (right - start) / (end - start))
        self._time_origin, self._label_width, self._scale = left, label_width, plot_width / (right - left)

        self.axis.create_line(label_width, 1, plot_end, 1, fill="#626262")
        ticks = MaxNLocator(nbins=max(2, plot_width // 85)).tick_values(left, right)
        for time in ticks:
            if left <= time <= right:
                x = self._x(time)
                self.axis.create_line(x, 1, x, 5, fill="#626262")
                self.axis.create_text(x, 7, text=_seconds(time), anchor="n", font=self._font)
        self.axis.create_text(5, 7, text="Time (s)", anchor="nw", font=self._font)

        top = max(0, self.body.canvasy(0))
        bottom = top + self.body.winfo_height()
        first = bisect_right(self._site_ends, top)
        for site_index in range(first, len(self._layout)):
            y, name, tracks = self._layout[site_index]
            if y >= bottom:
                break
            self.body.create_rectangle(0, y, width, y + self.HEADER,
                                       fill="#edf0f3", outline="")
            self.body.create_text(5, y + self.HEADER / 2, anchor="w", font=self._font,
                                  text=self._clip_label(name, width - 12))
            lane_top = y + self.HEADER
            if not tracks:
                self.body.create_text(10, lane_top + self.LANE / 2, text="No observations",
                                      anchor="w", fill="#454545", font=self._font)
            first_lane = max(0, int((top - lane_top) // self.LANE))
            last_lane = min(len(tracks), int((bottom - lane_top) // self.LANE) + 1)
            for index in range(first_lane, last_lane):
                track = tracks[index]
                y = lane_top + index * self.LANE
                self.body.create_text(12, y + self.LANE / 2, anchor="w", font=self._font,
                                      text=self._clip_label(track.category, label_width - 18))
                self.body.create_line(label_width, y + self.LANE - 1, plot_end, y + self.LANE - 1,
                                      fill="#e8e8e8")
                self._draw_lane(track, y, plot_width, plot_end)

    def _x(self, time):
        return self._label_width + (time - self._time_origin) * self._scale

    def _draw_lane(self, track, y, plot_width, plot_end):
        points = []
        for mark in track.spans.visible(*self._view, plot_width):
            x = max(self._label_width, self._x(mark.start))
            end = min(plot_end, self._x(mark.end))
            color = "#6a6a6a" if mark.mixed else self.data.colors[track.category, track.labels[mark.value]]
            if mark.start == mark.end:
                points.append((x, color, mark))
                continue
            item = self.body.create_rectangle(
                min(x, plot_end - 1), y + 2, min(plot_end, max(x + 1, end)), y + self.LANE - 3,
                outline="", fill=color, stipple="gray50" if mark.mixed else "")
            self._hits[item] = track, mark
        for x, color, mark in points:
            mid = y + self.LANE / 2 - 1
            item = self.body.create_polygon(x, mid - 5, x + 4, mid, x, mid + 5, x - 4, mid,
                                            fill=color, outline="#444444")
            self._hits[item] = track, mark

    def _motion(self, event):
        x, y = event.x, self.body.canvasy(event.y)
        items = self.body.find_overlapping(x - 1, y - 1, x + 1, y + 1)
        item = next((number for number in reversed(items) if number in self._hits), None)
        if self._hover_target == (item, x):
            return
        self._hide_tooltip()
        if item is not None:
            self._hover_target = item, x
            self._hover_job = self.after(250, self._show_tooltip, item, x, event.y)

    def _show_tooltip(self, item, x, y):
        self._hover_job = None
        track, mark = self._hits[item]
        if mark.mixed:
            if mark.start == mark.end:
                detail = f"{_seconds(mark.start)} s · Coincident observations. See the event table."
            else:
                detail = f"{_seconds(mark.start)}–{_seconds(mark.end)} s · Zoom in for individual observations."
            message = f"{track.site} / {track.category}\n{detail}"
        else:
            time = self._time_origin + (x - self._label_width) / self._scale
            starts = self.data.clock.starts[mark.first:mark.last + 1]
            index = min(len(starts) - 1, max(0, starts.searchsorted(time, side="right") - 1))
            observation = track.observation(mark.first + index, self.data.clock)
            message = (f"{track.site} / {track.category} · {observation.state}"
                       f"\nTimestamp {_seconds(observation.start)} s")
            if observation.duration is not None:
                message += f" · Duration {_seconds(observation.duration)} s"
        self._tooltip.configure(text=message)
        width = self._tooltip.winfo_reqwidth()
        height = self._tooltip.winfo_reqheight()
        left = max(0, min(x + 12, self.body.winfo_width() - width))
        top = y + 12 if y + 12 + height <= self.body.winfo_height() else max(0, y - height - 6)
        self._tooltip.place(x=left, y=top)

    def _hide_tooltip(self, event=None):
        if self._hover_job is not None:
            self.after_cancel(self._hover_job)
            self._hover_job = None
        self._hover_target = None
        self._tooltip.place_forget()

    def destroy(self):
        self._hide_tooltip()
        if self._draw_job is not None:
            self.after_cancel(self._draw_job)
        super().destroy()


class FilePreview(ttk.LabelFrame):
    def __init__(self, parent):
        super().__init__(parent, text="File preview", padding=3)
        self._reader = PreviewReader()
        self._token = 0
        self._poll_job = self._fit_job = None
        self._inserts = set()
        self._swatches = {}
        self._branches = {}
        self._offset = 0
        self.data = None
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self._viewport = tk.Canvas(self, highlightthickness=0, width=470, height=350)
        background = ttk.Style(self).lookup("TFrame", "background") or self._viewport.cget("background")
        self._viewport.configure(background=background)
        self._viewport.grid(row=0, column=0, sticky="nsew")
        outer_scroll = ttk.Scrollbar(self, orient="vertical", command=self._viewport.yview)
        outer_scroll.grid(row=0, column=1, sticky="ns")
        self._viewport.configure(yscrollcommand=outer_scroll.set)
        self._content = ttk.Frame(self._viewport, padding=3)
        self._window = self._viewport.create_window(0, 0, window=self._content, anchor="nw")
        self._viewport.bind("<Configure>", self._schedule_fit)
        self._content.columnconfigure(0, weight=1)
        self._content.bind("<Configure>", self._schedule_fit)
        self._content.rowconfigure(4, weight=2)
        self._content.rowconfigure(5, weight=1)

        self.status = ttk.Label(self._content, text=PLACEHOLDER, wraplength=360, justify="left")
        self.status.grid(row=0, column=0, sticky="ew")
        self._filename_font = font.nametofont("TkDefaultFont", root=self).copy()
        self._filename_font.configure(weight="bold")
        self._summary = ttk.Label(self._content, wraplength=360, justify="left")
        self._summary.grid(row=1, column=0, sticky="ew", pady=(3, 2))
        self._details = ttk.Button(self._content, text="Session details", command=self._toggle_details)
        self._details.grid(row=2, column=0, sticky="w", pady=(0, 3))
        self._metadata_box = ttk.Frame(self._content)
        self._metadata_box.grid(row=3, column=0, sticky="nsew")
        self._metadata_box.columnconfigure(0, weight=1)
        self._metadata_box.rowconfigure(0, weight=1)
        self._metadata = tk.Text(self._metadata_box, width=1, height=4, wrap="word",
                                 font="TkDefaultFont", state="disabled")
        self._metadata.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(self._metadata_box, orient="vertical", command=self._metadata.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._metadata.configure(yscrollcommand=scrollbar.set)

        self._sites_box = ttk.LabelFrame(self._content, text="Sites and codes", padding=3)
        self._sites_box.grid(row=4, column=0, sticky="nsew", pady=2)
        frame, self.sites = _scrollable_tree(self._sites_box, columns=("count",), height=3)
        frame.pack(expand=True, fill="both")
        self.sites.heading("#0", text="Site, category, or state")
        self.sites.heading("count", text="Count")
        self.sites.column("#0", width=220)
        self.sites.column("count", width=65, stretch=False, anchor="e")
        self.sites.bind("<<TreeviewOpen>>", self._expand_site)

        self._timeline_box = ttk.Frame(self._content)
        self._timeline_box.grid(row=5, column=0, sticky="nsew", pady=2)
        self._timeline_box.columnconfigure(0, weight=1)
        self._timeline_box.rowconfigure(0, weight=1)
        self.timeline = PreviewTimeline(self._timeline_box)
        self.timeline.grid(row=0, column=0, sticky="nsew")
        self._legend_box = ttk.Frame(self._timeline_box, padding=(3, 4, 3, 0))
        self._legend_box.grid(row=1, column=0, sticky="ew")
        self._legend_box.columnconfigure(1, weight=1)
        ttk.Label(self._legend_box, text="Codes").grid(row=0, column=0, sticky="nw", padx=(0, 5))
        self.legend = tk.Text(self._legend_box, height=2, width=1, wrap="word", relief="flat",
                              background=background, borderwidth=0, highlightthickness=0,
                              font="TkDefaultFont", state="disabled")
        self.legend.grid(row=0, column=1, sticky="ew")
        legend_scroll = ttk.Scrollbar(self._legend_box, orient="vertical", command=self.legend.yview)
        legend_scroll.grid(row=0, column=2, sticky="ns")
        self.legend.configure(yscrollcommand=legend_scroll.set)

        self._events_box = ttk.LabelFrame(self._content, text="Recorded observations", padding=3)
        self._events_box.grid(row=6, column=0, sticky="nsew", pady=2)
        self._content.rowconfigure(6, weight=2)
        self._events_box.columnconfigure(0, weight=1)
        self._events_box.rowconfigure(0, weight=1)
        frame, self.events = _scrollable_tree(
            self._events_box, columns=("time", "end", "duration", "site"), height=4)
        frame.grid(row=0, column=0, columnspan=3, sticky="nsew")
        headings = (("#0", "Category / state", 140), ("time", "Time (s)", 72),
                    ("end", "End (s)", 72), ("duration", "Duration (s)", 80), ("site", "Site", 100))
        for name, label, width in headings:
            self.events.heading(name, text=label)
            self.events.column(name, width=width, minwidth=min(width, 65),
                               anchor="w" if name in ("#0", "site") else "e",
                               stretch=name in ("#0", "site"))
        self._row_count = ttk.Label(self._events_box)
        self._row_count.grid(row=1, column=0, sticky="w")
        self._prev = ttk.Button(self._events_box, text="Previous", command=lambda: self._page(-1))
        self._prev.grid(row=1, column=1)
        self._next = ttk.Button(self._events_box, text="Next", command=lambda: self._page(1))
        self._next.grid(row=1, column=2)
        self._panels = (self._summary, self._details, self._metadata_box, self._sites_box,
                        self._timeline_box, self._events_box)
        self._reset()

    def _schedule_fit(self, event=None):
        if self._fit_job is None:
            self._fit_job = self.after_idle(self._fit_viewport)

    def _fit_viewport(self):
        self._fit_job = None
        width = self._viewport.winfo_width()
        wrap = max(80, width - 10)
        if int(self.status.cget("wraplength")) != wrap:
            self.status.configure(wraplength=wrap)
            self._summary.configure(wraplength=wrap)
            self._schedule_fit()
        height = max(self._viewport.winfo_height(), self._content.winfo_reqheight())
        self._viewport.itemconfigure(self._window, width=width, height=height)
        self._viewport.configure(scrollregion=(0, 0, width, height))

    def _toggle_details(self):
        visible = bool(self._metadata_box.winfo_manager())
        if visible:
            self._metadata_box.grid_remove()
        else:
            self._metadata_box.grid()
        self._details.configure(text="Session details" if visible else "Hide session details")
        self._schedule_fit()

    def _reset(self):
        if self._poll_job is not None:
            self.after_cancel(self._poll_job)
            self._poll_job = None
        for job in self._inserts:
            self.after_cancel(job)
        self._inserts.clear()
        for panel in self._panels:
            panel.grid_remove()
        for tree in (self.sites, self.events):
            tree.delete(*tree.get_children())
            tree.xview_moveto(0)
            tree.yview_moveto(0)
        self._branches.clear()
        self._swatches.clear()
        for text in (self._metadata, self.legend):
            text.configure(state="normal")
            text.delete("1.0", "end")
            text.configure(state="disabled")
        self.data = None
        self.timeline.set_data(None)
        self._offset = 0
        self._viewport.yview_moveto(0)
        self._schedule_fit()

    def clear(self):
        self._token += 1
        self._reader.request(self._token, None)
        self._reset()
        self.status.configure(text=PLACEHOLDER, font="TkDefaultFont")

    def show(self, path):
        path = Path(path)
        self._reset()
        self._token += 1
        self.status.configure(text=f"Reading {path.name}…", font="TkDefaultFont")
        self._reader.request(self._token, path)
        self._poll_job = self.after(30, self._poll, self._token, path.name)

    def _poll(self, token, filename):
        self._poll_job = None
        if token != self._token:
            return
        result = self._reader.take()
        if result is None or result[0] != token:
            self._poll_job = self.after(30, self._poll, token, filename)
            return
        _, data, error = result
        if error is not None:
            self.status.configure(text=f"{filename}\nCould not preview this file. {error[:400]}")
            self._schedule_fit()
        else:
            # Keep the actual selected name even when a symlink resolves to another filename.
            self._display(data, filename)

    def _display(self, data, filename):
        self.data = data
        self.status.configure(text=filename, font=self._filename_font)
        categories = f"{data.used_codes:,} used / {data.declared_codes:,} declared"
        overview = (f"Duration  {_duration(data.clock.duration)}    Sites  {len(data.sites):,}"
                    f"    Codes  {categories}\n"
                    f"Coding steps  {data.steps:,}    Observations  {data.total:,}")
        if data.clock.notice:
            overview += f"\n{data.clock.notice}"
        self._summary.configure(text=overview)
        for panel in (self._summary, self._sites_box, self._timeline_box, self._events_box):
            panel.grid()
        if data.metadata:
            self._metadata.configure(state="normal")
            self._metadata.insert("1.0", data.metadata)
            self._metadata.configure(state="disabled")
            self._metadata.yview_moveto(0)
            self._details.configure(text="Session details")
            self._details.grid()
        self._queue_inserts((self._site_row(site, categories) for site, categories in data.sites.items()))
        self._queue_inserts((self._legend_row(key) for key in data.used_keys))
        if data.used_keys:
            self._legend_box.grid()
        else:
            self._legend_box.grid_remove()
        self.timeline.set_data(data)
        self._show_page()
        self._schedule_fit()

    def _queue_inserts(self, rows):
        def insert():
            self._inserts.discard(job)
            for _ in range(80):
                if not next(rows, False):
                    return
            self._queue_inserts(rows)

        job = self.after(1, insert)
        self._inserts.add(job)

    def _swatch(self, key):
        if key not in self._swatches:
            image = tk.PhotoImage(master=self, width=12, height=12)
            image.put("#575757", to=(1, 1, 11, 11))
            image.put(self.data.colors[key], to=(2, 2, 10, 10))
            self._swatches[key] = image
        return self._swatches[key]

    def _site_row(self, site, categories):
        item = self.sites.insert("", "end", text=site)
        if categories:
            self._branches[item] = (self._category_row(item, category, counts)
                                    for category, counts in categories.items())
            self.sites.insert(item, "end")
        return item

    def _category_row(self, site, category, counts):
        item = self.sites.insert(site, "end", text=category, values=(f"{sum(counts.values()):,}",))
        if counts:
            self._branches[item] = (self.sites.insert(item, "end", text=state, values=(f"{count:,}",),
                                                     image=self._swatch((category, state)))
                                    for state, count in counts.items())
            self.sites.insert(item, "end")
        return item

    def _expand_site(self, event):
        item = self.sites.focus()
        rows = self._branches.pop(item, None)
        if rows is not None:
            self.sites.delete(*self.sites.get_children(item))
            self._queue_inserts(rows)

    def _legend_row(self, key):
        self.legend.configure(state="normal")
        name = self.legend.image_create("end", image=self._swatch(key), padx=3)
        self.legend.insert("end", f"{key[0]} / {key[1]}   ")
        self.legend.configure(state="disabled")
        return name

    def _show_page(self):
        self.events.delete(*self.events.get_children())
        self.events.yview_moveto(0)
        for item in self.data.page(self._offset, PAGE_SIZE):
            self.events.insert("", "end", text=f"{item.category} / {item.state}", image=self._swatch(item.key),
                               values=(_seconds(item.start), _seconds(item.end),
                                       _seconds(item.duration), item.site))
        total = self.data.total
        stop = min(total, self._offset + PAGE_SIZE)
        text = f"{self._offset + 1:,}–{stop:,} of {total:,}" if total else "No recorded observations"
        self._row_count.configure(text=text)
        self._prev.state(["!disabled"] if self._offset else ["disabled"])
        self._next.state(["!disabled"] if stop < total else ["disabled"])

    def _page(self, direction):
        offset = self._offset + direction * PAGE_SIZE
        if self.data is not None and 0 <= offset < self.data.total:
            self._offset = offset
            self._show_page()

    def destroy(self):
        self._reader.close()
        self._reset()
        if self._fit_job is not None:
            self.after_cancel(self._fit_job)
        super().destroy()
