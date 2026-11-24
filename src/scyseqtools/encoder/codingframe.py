"""
This module deals with all the encoding procedure:
- builds the interface according to the coding framework
- displays the codes
- records the codes and pass it to the application.
"""

import json
from pathlib import Path
from datetime import datetime

import tkinter
import tkinter.simpledialog
import tkinter.messagebox
from tkinter.colorchooser import askcolor

from scyseqtools.encoder.config import load_encoder_config
import scyseqtools.encoder.utils as U


class FrameworkFrame(tkinter.Frame):

    def __init__(self, parent, filename, application=None, definition=None):
        if definition is None:
            with open(filename, encoding="utf-8") as stream:
                definition = json.load(stream)
            definition["filename"] = Path(filename).absolute().as_posix()
        self.encoding = {
            site: {name: definition["codes"][name] for name in names}
            for site, names in definition["sites"].items()
        }
        self.application = application or parent

        config = load_encoder_config(
            self.application.cwd, required_sections=("codingframework",)
        )
        coding_config = config["codingframework"]
        border_width = coding_config.getint("borderwidth")
        coding_bg = coding_config["background"]
        relief = coding_config["relief"]
        self.disabled_bg = coding_config["disabled_bg"]
        self.panel_max = coding_config.getint("panel_max")

        tkinter.Frame.__init__(self, parent)
        self.configure(background=coding_bg,
                       borderwidth=border_width,
                       padx=20, pady=20,
                       relief=relief)

#FIXME: Not sure this is the best place...
        self.application.container['code'] = definition

        # variables related to player BUT ***taken from coding file***
        period = definition["period"]
        self.player_mode = tkinter.StringVar(value="continuous" if period is None else "regular")
        self.period_display = tkinter.StringVar(value=str(period))

        self.spec_frame = SpecificationFrame(self)
        self.spec_frame.grid(sticky=U.sticky_all)

        self.coding_frame = CodingFrame(
            parent=self,
            encoding=self.encoding,
            disabled_bg=self.disabled_bg,
            panel_max=self.panel_max,
        )
        self.coding_frame.grid(column=0, columnspan=2, sticky=U.sticky_all)
        self.config_processing_buttons('disabled')
        self.bind('<Button-3>', self.change_color)

        self.data = {}
        self.coding_comments = []
        self.elements = [self]
        self._displayed_values = self._editor_values()

    def _editor_values(self):
        return (self.coding_frame.comment.get(), *(
            widgets["var"].get() for panel in self.coding_frame.panels
            for widgets in panel.coding.values()
        ))

    def has_edits(self):
        return self._editor_values() != self._displayed_values

    def start_processing(self):
        """
        Start processing and fill the container with:
        - observer, date, comments
        - start time
        - code and media file names => INFOFRAME!!!
        - encoding specifications
        """

        self.spec_frame.start_but.config(state='disabled')
        # ----
        # Get and set specifications before disabling entries
        observer = self.spec_frame.person.get()
        while observer == '' or observer is None :
            name = tkinter.simpledialog.askstring('Please identify', 'Please identify yourself')
            observer = name
        self.spec_frame.person.set(observer)

        date = datetime.now().strftime('%c')
        self.spec_frame.timestamp.set(date)
        comment = self.spec_frame.comment.get()

        self.application.container['history'].append((date, observer, comment))

        self.config_specifications('disabled')
        # ----
        # Coding frame imposes the mode and period of player Control
        self.application.control.mode = self.player_mode.get()
        self.application.control.period = self.period_display.get()

        if self.application.state['data_loaded']: # resume session
            self.application.context = "resume"

        else: # starts a new session
            self.application.context = "initial"
            self.init_data()

    def init_data(self):
        panellist = self.coding_frame.panels
        for pan in panellist:
            self.data[pan.name] = {}
            #for cname, v in pan.coding.items():
            for cname in pan.coding.keys():
                self.data[pan.name][cname] = []
        print(self.data)

    def display_codes(self, time_step):
        """
        Displays the codes and comments
        """
        panellist = self.coding_frame.panels

        if time_step in self.application.recorded_steps:
            comment = self.coding_comments[time_step-1]
            self.coding_frame.comment.set(comment)

            for pan in panellist:
                # pan.name = recording site
                for cname, v in pan.coding.items():
                    idx = self.data[pan.name][cname][time_step-1]
                    local_str = self.encoding[pan.name][cname][idx]
                    v['var'].set(local_str)
        else:
            comment = ''
            self.coding_frame.comment.set(comment)

            for pan in panellist:
                # pan.name = recording site
                for cname, v in pan.coding.items():
                    local_str = '-'
                    v['var'].set(local_str)
        self._displayed_values = self._editor_values()

    def record_state(self):
        """
        Record a step
        """
        if self.application.control.mode != "regular":
            raise NotImplementedError

        panels = self.coding_frame.panels
        if any(v["var"].get() == "-" for pan in panels for v in pan.coding.values()):
            tkinter.messagebox.showinfo("Code missing", "A code is missing")
            return

        step = self.application.time_step

        def with_sample(sequence, value):
            updated = sequence.copy()
            if step <= len(updated):
                updated[step - 1] = value
            else:
                updated.append(value)
            return updated

        data = self.data.copy()
        for pan in panels:
            site_data = self.data.get(pan.name, {})
            data[pan.name] = site_data.copy()
            for name, widgets in pan.coding.items():
                symbol = widgets["var"].get()
                value = self.encoding[pan.name][name].index(symbol)
                data[pan.name][name] = with_sample(site_data.get(name, []), value)
        comments = with_sample(self.coding_comments, self.coding_frame.comment.get())
        record = dict(self.application.container, data=data, comments=comments)
        if not self.application.info.save_data(record, self.winfo_toplevel()):
            return

        self.data = data
        self.coding_comments = comments
        self.application.container.update(data=data, comments=comments)
        self.application.recorded_steps.add(step)
        self.config_processing_buttons("disabled")
        self.application.context = "processing"
        self.display_codes(step)
        self.application.code_history.recorded(data, step, self.application.step_time(step))
        self.application.code_history.select(step, reveal=True)

    def change_color(self, event):
        colortuple = askcolor()
        # print colortuple
        self.configure(background=colortuple[1])

    def config_processing_buttons(self,st):
        self.coding_frame.record_but.configure(state=st)
        self.coding_frame.comment_ent.configure(state=st)
        for panel in self.coding_frame.panels:
            # for k, v in panel.coding.items():
            for v in panel.coding.values():
                for button in v['buttons']:
                    button.configure(state=st)

    def config_specifications(self,st):
        self.spec_frame.person_ent.configure(state=st)
        self.spec_frame.comment_ent.configure(state=st)
        self.spec_frame.start_but.configure(state=st)


class CodingFrame(tkinter.LabelFrame):

    def __init__(self, parent, encoding, disabled_bg, panel_max): # coding is a dict
        tkinter.LabelFrame.__init__(self, parent)
        self.configure(text='Codes', padx=10, pady=10)
        self.parent = parent
        self.disabled_bg = disabled_bg
        self.panel_max = panel_max

        sites = list(encoding.keys())
        sites.sort()
        self.panels = [
            Panel(
                parent=self,
                name=site,
                codes=encoding[site],
                disabled_bg=self.disabled_bg,
            )
            for site in sites
        ]

        # Set the panels on several rows and columns according to panel_max
        # panels per row. Better ergonomy when there is a lot of recording sites.
        for no_col, panel in enumerate(self.panels):
            col = no_col % self.panel_max
            row = no_col // self.panel_max
            panel.rowconfigure(row, weight=3)
            panel.columnconfigure(col, weight=1)
            panel.grid(row=row, column=col, sticky=U.sticky_all)

        comment_frame = tkinter.LabelFrame(self, text='Comment: ')
        comment_row = (len(self.panels) - 1) // self.panel_max + 1
        comment_frame.grid(row=comment_row, column=0, columnspan=max(1, len(self.panels)),
                                            sticky=U.sticky_all)
        self.comment = tkinter.StringVar()
        self.comment_ent = tkinter.Entry(comment_frame,
                                         textvariable=self.comment,
                                         disabledbackground=self.disabled_bg,
                                         width=60)
        self.comment_ent.grid(sticky=U.sticky_all)

        self.record_but = tkinter.Button(self, text="Record",
                                               height=2,
                                               command=parent.record_state)
        self.record_but.grid(column=self.panel_max+1, row=0, rowspan=2, sticky=U.sticky_all)

class Panel(tkinter.LabelFrame):

    def __init__(self, parent, name, codes, disabled_bg):
        tkinter.LabelFrame.__init__(self, parent)
        self.name = name
        self.disabled_bg = disabled_bg
        self.configure(text=name, padx=10, pady=10, labelanchor='n')

        max_symbols = max([len(codes[k]) for k in codes.keys()])
        # nb_code = len(codes)
        code_names = list(codes.keys())
        code_names.sort()

        local_col = 0
        self.coding = {}

        for code_name in code_names:
            self.coding[code_name] = {}
            self.coding[code_name]['var'] = tkinter.StringVar()

            label = tkinter.Label(self, text=code_name, padx=10, pady=10)
            label.grid(row=0, column=local_col, sticky=U.sticky_all)

            symbols = codes[code_name]
            self.coding[code_name]['buttons'] = [tkinter.Button(self, text=symbol,
                   command=lambda s=self, n=code_name, kk=symbol: s.set_msg(kk,n))
                                                 for symbol in symbols]
            for nb_symbols, sbut in enumerate(self.coding[code_name]['buttons']):
                sbut.grid(row=nb_symbols+1, column=local_col, sticky=U.sticky_all)


            msg = tkinter.Entry(self, state=tkinter.DISABLED,
                                      width=10,
                                      disabledbackground=self.disabled_bg,
                                      disabledforeground='black',
                                      textvariable=self.coding[code_name]['var'])
            msg.grid(row=max_symbols+1, column=local_col, sticky=U.sticky_all)
            local_col += 1

    def set_msg(self, symbol, code_name):
        """Show the selected code in the message box
        """
        self.coding[code_name]['var'].set(symbol)

class SpecificationFrame(tkinter.LabelFrame):

    def __init__(self, parent):

        # self.parent = parent
        tkinter.LabelFrame.__init__(self, parent)
        disabled_bg = parent.disabled_bg

        self.configure(text='Specifications', padx=10, pady=10)


        # date in local format
        self.timestamp = tkinter.StringVar()
        self.timestamp.set(datetime.now().strftime('%c'))

        date_lab = tkinter.Label(self, text='Date: ')
        date_lab.grid(column=0, row=0, sticky=tkinter.W)
        self.date_ent = tkinter.Entry(self,
                                      textvariable=self.timestamp,
                                      state=tkinter.DISABLED,
                                      disabledbackground=disabled_bg,
                                      width=21)
        self.date_ent.grid(column=1, row=0, sticky=tkinter.W)

        # observer name
        self.person = tkinter.StringVar()

        person_lab = tkinter.Label(self, text='Observer: ')
        person_lab.grid(row=0, column=2, sticky=tkinter.E)
        self.person_ent = tkinter.Entry(self,
                                        textvariable=self.person,
                                        disabledbackground=disabled_bg,
                                        width=15)
        self.person_ent.grid(row=0, column=3, sticky=tkinter.W, columnspan=4)

        # coding / player  mode
        mode_lab = tkinter.Label(self, text='Coding mode: ')
        mode_lab.grid(column=0, row=1, sticky=tkinter.W)

        mode_ent = tkinter.Entry(self,
                                      textvariable=parent.player_mode,
                                      disabledbackground=disabled_bg,
                                      state=tkinter.DISABLED,
                                      width=21)
        mode_ent.grid(column=1, row=1, sticky=tkinter.W)

        period_lab = tkinter.Label(self, text='Step: ')
        period_lab.grid(column=2, row=1)
        period_ent = tkinter.Entry(self,
                                      textvariable=parent.period_display,
                                      disabledbackground=disabled_bg,
                                      state=tkinter.DISABLED,
                                      width=5)
        period_ent.grid(column=3, row=1, sticky=tkinter.W)
        # time units is given in seconds - mandatory
        unit_lab = tkinter.Label(self, text='second(s)')
        unit_lab.grid(column=4, row=1, sticky=tkinter.W)

        # Comments for the coding session
        self.comment = tkinter.StringVar()
        comment_lab = tkinter.Label(self, text='Comment: ')
        comment_lab.grid(row=3, column=0, sticky=tkinter.W)
        self.comment_ent = tkinter.Entry(self, textvariable=self.comment,
                                         disabledbackground=disabled_bg,
                                         width=45)
        self.comment_ent.grid(row=3, column=1, columnspan=4, sticky=tkinter.W)

        # Start processing / coding / recording button...
# FIXME: place this button in a better way.
        self.start_but = tkinter.Button(self, text='Start\nprocessing',
                                         # command=self.parent.start_processing)
                                         command=parent.start_processing)
        self.start_but.grid(row=0, column=5, rowspan=4, sticky=U.sticky_all)
