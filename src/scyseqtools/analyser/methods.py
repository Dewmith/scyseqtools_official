"""
Module to deal with the methods exposed by symbolix
"""
import tkinter
import tkinter.filedialog
from tkinter import messagebox, ttk

import pathlib

import copy
from datetime import datetime
from functools import partial
import json
# import inspect
import sys

from scyseqtools.analyser.parameters import Parameter
from scyseqtools.analyser.exports import SequenceExports, TableExport
from scyseqtools.analyser.output_files import output_path, write_lines, write_outputs
from scyseqtools.analyser.pairing import Track
from scyseqtools.analyser.save_dialog import resolve_destinations
from scyseqtools.analyser.visualizations import INDEPENDENCE, set_choices
# import utils as U
# import symbolix

# SEQ_EXT = '.json'
TABLE_EXT = '.csv'
SEP = ';'


def _as_codix_writer_sequences(dico_seqs):
    """
    Adapt analyser sequence mappings to the shape accepted by write_codix.
    """
    return {
        site: list(codes.items()) if hasattr(codes, 'items') else codes
        for site, codes in dico_seqs.items()
    }


def _sequence_values(sequence):
    return sequence.ivals.tolist()


def _sequence_alphabet(sequence):
    return list(sequence.alphabet.svals)


def _codix_container(source_metadata, dico_seqs):
    """
    Build a Codix record for analyser-generated sequence outputs.
    """
    container = copy.deepcopy(source_metadata) if source_metadata else {}
    container.setdefault('history', [])
    container.setdefault('media', '')
    container.setdefault('times', [])
    container.setdefault('comments', [])
    container.setdefault('version', '0.9')

    code = copy.deepcopy(container.get('code', {}))
    code['codes'] = {}
    code['sites'] = {}

    data = {}
    for site, code_sequences in _as_codix_writer_sequences(dico_seqs).items():
        data[site] = {}
        code['sites'][site] = []
        for codename, sequence in code_sequences:
            code['sites'][site].append(codename)
            code['codes'][codename] = _sequence_alphabet(sequence)
            data[site][codename] = _sequence_values(sequence)

    container['code'] = code
    container['data'] = data
    container['history'].append(
        (datetime.now().strftime('%c'), 'cdx-analyzer', '')
    )
    return container


def write_codix_export(fname, dico_seqs, source_metadata=None):
    """
    Write analyser-generated Codix data while preserving source metadata.
    """
    container = _codix_container(source_metadata, dico_seqs)
    with open(fname, 'w', encoding='utf-8') as datafile:
        json.dump(container, datafile)


class Method():
    """
    Main class to represent the methods exposed by symbolix
    """
    def __init__(self, name, meth, parent):
        """
        Define the method with its tab and own method
        """
        # Inputs
        self.gdata = {}
        self.metadata = {}
        self.selected_files = []
        self.parameters = []

        self.name = name
        self.tab = parent.notebook.add(self.name.replace('_', ' ').title())
        self.parent = parent
        doc_lines = meth.__doc__
        self.method = meth
        args = {k: v for k, v in meth.__annotations__.items() if k != "return"}

        # Documentation
        doc_frame = tkinter.LabelFrame(self.tab, text='Documentation')
        tkinter.Label(doc_frame, text=doc_lines).grid()
        doc_frame.grid(column=0, row=0)

        for param in args.items():
            par = Parameter(*param, self)
#            par.frame.grid(column=int(status['optional']),
#                           row=status['def_order']+2)
            par.frame.grid()
            self.parameters.append(par)

        launch_but = tkinter.Button(self.tab, text='Launch',
                                    command=self.launch)
        launch_but.grid(sticky=tkinter.W)

        if self.name == "mutual_information":
            graph_controls = ttk.Frame(self.tab, padding=(0, 8))
            graph_controls.grid(sticky="w")
            ttk.Label(graph_controls, text="Recording").pack(side="left")
            self.graph_recording = ttk.Combobox(graph_controls, state="readonly", width=28)
            self.graph_recording.pack(side="left", padx=6)
            self.graph_button = ttk.Button(graph_controls, text="View contributions",
                                           command=self.view_contributions, state="disabled")
            self.graph_button.pack(side="left")

    def view_contributions(self):
        filename = self.graph_recording.get()
        try:
            selections = [param.value.get() for param in self.parameters]
        except IndexError:
            messagebox.showerror("Could not view contributions",
                                 "Select a site and code for both inputs.", parent=self.tab)
            return
        first, second = (Track(filename, item["site"], item["code"]) for item in selections)
        self.parent.visualizations_tool.open_graph(INDEPENDENCE, first, second,
                                                   dialog_parent=self.tab)

    def launch(self):
        """
        Run the analysis and save its explicit table or sequence-export result.
        """
        in_params = {param.name: param.get() for param in self.parameters}

        print(in_params)
        # print(inspect.signature(self.method))
        output = self.method(self.method, **in_params)
        print(output)

#        output = self.client.call_method(method, **in_params)
#        try:
#            result = output.response_dict['result']
#        except KeyError:
#            print(output.response_body)

        if isinstance(output, TableExport):
            files = [(output.filename, partial(write_lines, lines=output.lines))]
        elif isinstance(output, SequenceExports):
            files = [(export.filename, partial(write_codix_export, dico_seqs=export.sequences_by_site,
                                               source_metadata=self._source_metadata(index)))
                     for index, export in enumerate(output.files)]
        else:
            raise TypeError(f'Unsupported analysis result type: {type(output).__name__}')

        try:
            initialdir = pathlib.Path(self.parent.cwd) / self.name
            initialdir.mkdir(exist_ok=True)
            outdir = tkinter.filedialog.askdirectory(parent=self.parent, initialdir=str(initialdir),
                                                     mustexist=True)
            if not outdir:
                return
            groups = [(output_path(outdir, name),) for name, _ in files]
            destinations = resolve_destinations(self.parent, groups)
            if destinations is not None:
                write_outputs(zip(destinations, (write for _, write in files)))
        except (OSError, ValueError) as exc:
            messagebox.showerror("Could not complete export", str(exc), parent=self.parent)

    def update_state(self, state):
        """
        Update the interface on the basis of application changes
        """
        # FIXME: this could certainly use self.parent.selected_files etc. but
        # need to change parameters
        self.selected_files = state['files']
        self.gdata = state['data']
        self.metadata = state.get('metadata', {})
        for param in self.parameters:
            param.update(state)
        if self.name == "mutual_information":
            set_choices(self.graph_recording, self.selected_files)
            self.graph_button.state(["!disabled"] if self.selected_files else ["disabled"])

    def _source_metadata(self, index):
        """
        Return metadata for the source file that produced an output row.
        """
        try:
            fname = self.selected_files[index]
        except (AttributeError, IndexError):
            return None
        return self.metadata.get(fname)
