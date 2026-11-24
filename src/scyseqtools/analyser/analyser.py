"""
A Tk client for symbolic analysis
"""

from scyseqtools.analyser.file_preview import FilePreview
from scyseqtools.analyser.kappa import KappaTool
from scyseqtools.analyser.methods import Method
from scyseqtools.analyser.synchronization import SynchronizationTool
from scyseqtools.analyser.symbolix import Symbolix
from scyseqtools.analyser.statistics import StatisticsTool
from scyseqtools.analyser.resultpanel import release_results
from scyseqtools.analyser.visualizations import VisualizationsTool
from scyseqtools.applicationmenu import ApplicationMenu

import os
import sys
import inspect
import pathlib
import copy

import tkinter
import tkinter.filedialog
import tkinter.messagebox
from tkinter import ttk

import Pmw

# sys.path.append('/home/zarpe/scikits-symbolic/symbolic')
from scyseq import io as IO

__version__ = '0.1'
__author__ = 'L. Pezard'
__licence__ = 'GPL'

# PLATFORM = sys.platform
ANALYZERDIR = 'analyzer_files'


def _analyzer_dir_for(data_dir):
    """
    Return the analyser working directory for a selected data directory.
    """
    parent_dir = os.path.split(data_dir)[0]
    return os.path.join(parent_dir, ANALYZERDIR)


def _key_difference(expected, actual, kind):
    missing = sorted(expected.keys() - actual.keys())
    unexpected = sorted(actual.keys() - expected.keys())
    return ', '.join(
        f'{description} {kind} {names[0]!r}'
        for description, names in (('missing', missing), ('unexpected', unexpected))
        if names
    )


def _validate_coding_framework(filename, candidates, reference_name, reference):
    message = f'{filename!r} is incompatible with {reference_name!r}.'
    if difference := _key_difference(reference, candidates, 'site'):
        raise ValueError(f'{message}\nSite mismatch ({difference}).')

    for site, categories in reference.items():
        if difference := _key_difference(categories, candidates[site], 'category'):
            raise ValueError(f'{message}\nSite {site!r} has a category mismatch ({difference}).')
        for category, sequence in categories.items():
            expected = sequence.alphabet.svals
            actual = candidates[site][category].alphabet.svals
            if expected != actual:
                raise ValueError(
                    f'{message}\nState labels differ at site {site!r}, category {category!r}.'
                    f'\nExpected {expected!r}.\nFound {actual!r}.'
                )


def _load_codix_appstate(data_dir, file_tuple):
    """
    Load selected Codix files and build the application state.
    """
    data = {}
    metadata = {}
    sites = []
    codes = {}

    for fname in file_tuple:
        fid = os.path.join(data_dir, fname)
        record = IO.read_codix(fid, data_only=False)
        candidates = record['data']
        if data:
            reference_name, reference = next(iter(data.items()))
            _validate_coding_framework(fname, candidates, reference_name, reference)
        else:
            sites = list(candidates)
            codes = {site: list(categories) for site, categories in candidates.items()}

        data[fname] = candidates
        metadata[fname] = {
            key: copy.deepcopy(value)
            for key, value in record.items()
            if key != 'data'
        }

    return {'files': list(file_tuple), 'sites': sites, 'codes': codes,
            'data': data, 'metadata': metadata}


def _empty_appstate():
    """
    Return an empty application state for unloaded data.
    """
    return {'files': [], 'sites': [], 'codes': {}, 'data': {},
            'metadata': {}}


def _append_unique(current, additions):
    """
    Return current plus additions while preserving first-seen order.
    """
    outfiles = []
    seen = set()
    for fname in list(current) + list(additions):
        if fname not in seen:
            outfiles.append(fname)
            seen.add(fname)
    return outfiles


class CheckboxFileList(tkinter.LabelFrame):
    """
    A scrollable list of filenames with one checkbox per row.
    """

    def __init__(self, master, label_text, width=320, height=200, on_preview=None):
        tkinter.LabelFrame.__init__(self, master, text=label_text)

        self.items = []
        self.variables = {}
        self.names = {}
        self.checkboxes = {}
        self.on_preview = on_preview
        self.highlighted = None
        style = ttk.Style(self)
        self._highlight_bg = style.lookup('Treeview', 'background', ('selected',)) or '#d6e6fa'
        self._highlight_fg = style.lookup('Treeview', 'foreground', ('selected',)) or '#202020'

        self.canvas = tkinter.Canvas(self, width=width, height=height,
                                     borderwidth=0, highlightthickness=0)
        self.frame = tkinter.Frame(self.canvas)
        self.frame.grid_columnconfigure(0, weight=1)
        self.yscroll = tkinter.Scrollbar(self, orient=tkinter.VERTICAL,
                                         command=self.canvas.yview)
        self.xscroll = tkinter.Scrollbar(self, orient=tkinter.HORIZONTAL,
                                         command=self.canvas.xview)

        self.canvas.configure(yscrollcommand=self.yscroll.set,
                              xscrollcommand=self.xscroll.set)
        self.window = self.canvas.create_window((0, 0), window=self.frame,
                                                anchor='nw')

        self.canvas.grid(row=0, column=0, sticky='nsew')
        self.yscroll.grid(row=0, column=1, sticky='ns')
        self.xscroll.grid(row=1, column=0, sticky='ew')
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.frame.bind('<Configure>', self._update_scrollregion)
        self.canvas.bind('<Configure>', self._update_scrollregion)
        for widget in (self.canvas, self.frame):
            self._bind_wheel(widget)

    def _update_scrollregion(self, event=None):
        width = max(self.canvas.winfo_width(), self.frame.winfo_reqwidth())
        if int(float(self.canvas.itemcget(self.window, 'width'))) != width:
            self.canvas.itemconfigure(self.window, width=width)
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def _bind_wheel(self, widget):
        widget.bind('<MouseWheel>', lambda event: self._scroll(-1 if event.delta > 0 else 1))
        widget.bind('<Button-4>', lambda event: self._scroll(-1))
        widget.bind('<Button-5>', lambda event: self._scroll(1))

    def _scroll(self, direction):
        self.canvas.yview_scroll(direction, 'units')
        return 'break'

    def setlist(self, items):
        """
        Replace the visible filenames and clear checkbox selection.
        """
        for child in self.frame.winfo_children():
            child.destroy()

        self.items = list(items)
        self.variables = {}
        self.names = {}
        self.checkboxes = {}

        for row, item in enumerate(self.items):
            line = tkinter.Frame(self.frame)
            line.grid(row=row, column=0, sticky='ew')
            line.grid_columnconfigure(1, weight=1)
            variable = tkinter.BooleanVar(master=self, value=False)
            checkbutton = tkinter.Checkbutton(line, variable=variable, padx=1)
            checkbutton.grid(row=0, column=0, sticky='w')
            name = tkinter.Label(line, text=item, anchor='w', takefocus=True, cursor='hand2',
                                 highlightthickness=1, padx=2)
            name.grid(row=0, column=1, sticky='ew')
            name.bind('<Button-1>', lambda event, filename=item: self._activate(event, filename))
            name.bind('<Return>', lambda event, filename=item: self._activate(event, filename))
            name.bind('<space>', lambda event, filename=item: self._activate(event, filename))
            for widget in (line, name, checkbutton):
                self._bind_wheel(widget)
            for widget in (name, checkbutton):
                widget.bind('<FocusIn>', lambda event, row=line: self._reveal_row(row))
            self.variables[item] = variable
            self.names[item] = name
            self.checkboxes[item] = checkbutton

        self.highlight(self.highlighted)
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)
        self.frame.update_idletasks()
        self._update_scrollregion()

    def _activate(self, event, filename):
        event.widget.focus_set()
        if self.on_preview is not None:
            self.on_preview(self, filename)
        return 'break'

    def _reveal_row(self, row):
        top = self.canvas.canvasy(0)
        height = self.canvas.winfo_height()
        first, last = row.winfo_y(), row.winfo_y() + row.winfo_height()
        if first < top:
            self.canvas.yview_moveto(first / self.frame.winfo_height())
        elif last > top + height:
            self.canvas.yview_moveto((last - height) / self.frame.winfo_height())

    def highlight(self, filename):
        previous = self.names.get(self.highlighted)
        if previous is not None:
            previous.configure(background=self.frame.cget('background'), foreground='black')
        self.highlighted = filename if filename in self.names else None
        if self.highlighted is not None:
            self.names[filename].configure(background=self._highlight_bg, foreground=self._highlight_fg)

    def getcurselection(self):
        """
        Return filenames with checked boxes in visible order.
        """
        return tuple(
            item for item in self.items
            if self.variables[item].get()
        )

    def clear_selection(self):
        """
        Clear all checked boxes.
        """
        for variable in self.variables.values():
            variable.set(False)


class Application(tkinter.Tk):
    """
    The main frame for the analyzer application
    """

    def __init__(self):
#       Create and pack the NoteBook.
        tkinter.Tk.__init__(self)
        self.protocol("WM_DELETE_WINDOW", self.request_exit)
        Pmw.initialise(self)
        self.title("scyseqtools")
        self.menu = ApplicationMenu(master=self)
        self.configure(menu=self.menu)

        self.data = {} # data[file][...]
        self.metadata = {}
        self.ddir = tkinter.StringVar()
        self.ddir.set('')
        self.cwd = None
        self.selected_files = []
        self._loaded_directory = None
        self._preview_source = None
        self._preview_path = None

        self.notebook = Pmw.NoteBook(self)
        self.notebook.pack(fill = 'both', expand = 1, padx = 10, pady = 10)
        # Add the "Configuration" page to the notebook.
        config_frame = self.notebook.add('Configuration')
        config_frame.grid_columnconfigure(1, weight=1)
        config_frame.grid_rowconfigure(2, weight=1)
        self.notebook.tab('Configuration').focus_set()

        dir_lab = tkinter.Label(config_frame, text='Directory')
        dir_ent = tkinter.Entry(config_frame, textvariable=self.ddir,
                                    state=tkinter.NORMAL,
                                    disabledbackground='white',
                                    width=50)
        self.dir_but = tkinter.Button(config_frame, text='Choose data directory',
                                     command=self.get_directory)
        dir_lab.grid(column=0, row=1)
        dir_ent.grid(column=1, row=1, sticky='ew')
        self.dir_but.grid(column=2, row=1)

        self.file_panes = tkinter.PanedWindow(config_frame, orient='horizontal', borderwidth=0,
                                              sashwidth=8, showhandle=True, sashrelief='raised')
        self.file_panes.grid(row=2, column=0, columnspan=3, sticky='nsew')
        grp = Pmw.Group(self.file_panes, tag_text='Files')
        lists = grp.interior()
        lists.grid_columnconfigure(0, weight=1, uniform='file_lists')
        lists.grid_columnconfigure(1, weight=1, uniform='file_lists')
        lists.grid_rowconfigure(0, weight=1)

        self.available = CheckboxFileList(lists,
                                          label_text='Available files',
                                          width=260, height=300, on_preview=self._preview_file)
        self.available.grid(row=0, column=0, sticky='nsew', padx=(0, 3))

        self.file_but = tkinter.Button(lists, text="Load checked files",
                                       command=self.load_file)
        self.file_but.grid(row=1, column=0, sticky='w', pady=(4, 0))

        self.selected = CheckboxFileList(lists,
                                         label_text='Loaded files (0)',
                                         width=230, height=300, on_preview=self._preview_file)
        self.selected.grid(row=0, column=1, sticky='nsew', padx=(3, 0))

        self.remove_but = tkinter.Button(lists, text='Remove selected',
                                         command=self.remove_selected_files)
        self.remove_but.grid(row=1, column=1, sticky='w', pady=(4, 0))

        self.file_preview = FilePreview(self.file_panes)
        self.file_panes.add(grp, minsize=260, stretch='always')
        self.file_panes.add(self.file_preview, minsize=275, stretch='always')
        self.ddir.trace_add('write', self._preview_directory_changed)

        quit_but = tkinter.Button(config_frame, text='Quit', command=self.request_exit)
        quit_but.grid(column=0, row=4)

        self.visualizations_tool = VisualizationsTool(self)
        self.kappa_tool = KappaTool(self)
        self.synchronization_tool = SynchronizationTool(self)
        available_meth = inspect.getmembers(Symbolix, predicate=inspect.isfunction)
        self.methods = [self.visualizations_tool, self.kappa_tool, self.synchronization_tool]
        for name, method in available_meth:
            if name == "statistics":
                self.statistics_tool = StatisticsTool(self)
                self.methods.append(self.statistics_tool)
            else:
                self.methods.append(Method(name, method, self))
        self._set_startup_window_size()

    def request_exit(self):
        panels = [self.kappa_tool.panel, self.statistics_tool.panel]
        if release_results(panels, self, "exit"):
            self.destroy()

    def _update_methods(self, appstate):
        """
        Push loaded-file state to every analysis tab.
        """
        for method in self.methods:
            method.update_state(appstate)

    def _preview_file(self, source, filename):
        directory = self._loaded_directory if source is self.selected else self.ddir.get()
        if not directory:
            self._clear_file_preview()
            return
        self._preview_source = source
        self._preview_path = pathlib.Path(directory) / filename
        self.available.highlight(filename if source is self.available else None)
        self.selected.highlight(filename if source is self.selected else None)
        self.file_preview.show(self._preview_path)

    def _clear_file_preview(self):
        self._preview_source = self._preview_path = None
        self.available.highlight(None)
        self.selected.highlight(None)
        self.file_preview.clear()

    def _preview_directory_changed(self, *args):
        if self._preview_source is self.available:
            self._clear_file_preview()

    def _apply_appstate(self, appstate, data_dir):
        """
        Store loaded data and refresh file widgets and analysis tabs.
        """
        self.selected_files = appstate['files']
        self._loaded_directory = data_dir
        self.data = appstate['data']
        self.metadata = appstate['metadata']
        self.selected.setlist(self.selected_files)
        self.selected.configure(text=f"Loaded files ({len(self.selected_files)})")
        self.selected.clear_selection()
        self.available.clear_selection()
        self._update_methods(appstate)
        if self._preview_source is self.selected:
            filename = self._preview_path.name
            if filename in self.selected_files:
                if pathlib.Path(data_dir) / filename != self._preview_path:
                    self._preview_file(self.selected, filename)
            elif (filename in self.available.items and self.ddir.get()
                  and pathlib.Path(self.ddir.get()) / filename == self._preview_path):
                self._preview_source = self.available
                self.available.highlight(filename)
            else:
                self._clear_file_preview()

    def _clear_loaded_files(self):
        """
        Clear selected files, loaded data, and dependent analysis tabs.
        """
        self.cwd = None
        self._apply_appstate(_empty_appstate(), None)

    def _set_startup_window_size(self):
        """
        Size the startup window from the largest fully-built notebook page.
        """
        self.notebook.setnaturalsize()
        self.update_idletasks()

        width = min(self.winfo_reqwidth(), self.winfo_screenwidth())
        height = min(self.winfo_reqheight(), self.winfo_screenheight())

        self.geometry(f'{width}x{height}')
        self.minsize(min(width, 640), min(height, 420))

    def get_directory(self):
        """
        Choose a data directory and list its CDX files.
        """
        initialdir = self.ddir.get() or str(pathlib.Path.home())

        outdir = tkinter.filedialog.askdirectory(parent=self,
                                                initialdir=initialdir)
        if not outdir:
            return

        try:
            with os.scandir(outdir) as entries:
                filelist = [
                    entry.name for entry in entries
                    if entry.name.lower().endswith('.cdx') and entry.is_file()
                ]
        except OSError as exc:
            tkinter.messagebox.showerror(title='Could not list directory',
                                         message=str(exc))
            return

        self._clear_file_preview()
        self.ddir.set(outdir)
        self.available.setlist(filelist)
        self._clear_loaded_files()

    def load_file(self):
        """
        Loads the data file

        Puts all the data in memory maybe this is not a good idea...
        """
        data_dir = self.ddir.get()
        if not data_dir:
            tkinter.messagebox.showwarning(title='No directory selected',
                    message='Choose a data directory before selecting files.')
            return

        selected_available = self.available.getcurselection()
        if not selected_available:
            tkinter.messagebox.showwarning(title='No file selected',
                    message='Select at least one data file to load.')
            return

        file_tuple = tuple(_append_unique(self.selected_files,
                                          selected_available))
        try:
            appstate = _load_codix_appstate(data_dir, file_tuple)
        except Exception as exc:
            tkinter.messagebox.showerror(title='Could not load data file',
                                         message=str(exc))
            return

        cwd = _analyzer_dir_for(data_dir)
        try:
            pathlib.Path(cwd).mkdir(exist_ok=True)
        except OSError as exc:
            tkinter.messagebox.showerror(title='Could not create working directory',
                                         message=str(exc))
            return

        self.cwd = cwd
        self._apply_appstate(appstate, data_dir)

    def remove_selected_files(self):
        """
        Remove checked files from the loaded selection.
        """
        selected_for_removal = self.selected.getcurselection()
        if not selected_for_removal:
            tkinter.messagebox.showwarning(title='No selected file checked',
                    message='Check at least one selected file to remove.')
            return

        removal_set = set(selected_for_removal)
        remaining_files = [
            fname for fname in self.selected_files
            if fname not in removal_set
        ]

        if not remaining_files:
            self._clear_loaded_files()
            return

        data_dir = self.ddir.get()
        try:
            appstate = _load_codix_appstate(data_dir, tuple(remaining_files))
        except Exception as exc:
            tkinter.messagebox.showerror(title='Could not load data file',
                                         message=str(exc))
            return

        self._apply_appstate(appstate, data_dir)

######################################################################

if __name__ == '__main__':
    application = Application()
    application.mainloop()
