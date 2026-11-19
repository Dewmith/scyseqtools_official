import os
import json

from pathlib import Path
from tempfile import NamedTemporaryFile

import tkinter
import tkinter.font
import tkinter.filedialog
import tkinter.messagebox
from tkinter.colorchooser import askcolor

from scyseqtools.encoder.config import load_encoder_config
import scyseqtools.encoder.utils as U

#### leomodif : on met ces variables dans config.ini directement

#bd = 2 # borderwidth
#info_bg = 'yellow' # information background
#disabled_bg = 'light grey' # disabled background
#relief = 'groove'
#filename_width = 30
# relief in ['flat', 'raised', 'sunken', 'solid', 'ridge', 'groove']


def coded_sample_lengths(data):
    """
    Return the lengths of all coded sequences in a ScySeqTools data container.
    """
    lengths = []
    for site_data in data.values():
        if not isinstance(site_data, dict):
            continue
        for sequence in site_data.values():
            if hasattr(sequence, "__len__"):
                lengths.append(len(sequence))
    return lengths


def resume_step_count(data, comments=None):
    """
    Infer how many regular-coding steps can safely be resumed.
    """
    lengths = coded_sample_lengths(data)
    if lengths:
        return min(lengths)
    if comments:
        return len(comments)
    return 0


def normalize_resume_data(record):
    """
    Normalize loaded session state without relying on the number of times.
    """
    data = record.get("data", {})
    comments = list(record.get("comments", []))
    times = list(record.get("times", []))
    count = resume_step_count(data, comments)

    if len(comments) < count:
        comments.extend([""] * (count - len(comments)))
    elif len(comments) > count:
        comments = comments[:count]

    if not times and count:
        period = record.get("code", {}).get("period")
        step = int(float(period) * 1000) if period else 0
        times = [step * index for index in range(count + 1)]

    return {
        "times": times,
        "comments": comments,
        "recorded_steps": set(range(1, count + 1)),
    }

class InfoFrame(tkinter.LabelFrame):

    def __init__(self, parent, states=[None, None, None]):
        tkinter.LabelFrame.__init__(self, parent)
        self.application = parent

        config = load_encoder_config(
            self.application.cwd, required_sections=("infoframe",)
        )

        bd = config['infoframe'].getint('borderwidth')
        info_bg = config['infoframe']['background']
        relief = config['infoframe']['relief']
        disabled_bg = config['infoframe']['disabled_bg']
        filename_width = config['infoframe'].getint('filename_width')
        self.configure(background=info_bg, borderwidth=bd, padx=20, pady=20,
                       relief=relief, text='Information: ', font=(tkinter.font.BOLD,))

        self.grid_columnconfigure(1, weight=1)

        self.code_file = tkinter.StringVar()
        self.media_file = tkinter.StringVar()
        self.data_file = tkinter.StringVar()
        self.session_path = None

        # Directory
        self.directory_label = tkinter.Label(self, text='Media directory: ', background = info_bg)
        self.directory_label.grid(row=1, column=0, sticky=tkinter.W)
        self.directory_msg = tkinter.Label(self, text= 'Please load file', background=info_bg)
        self.directory_msg.configure(anchor=tkinter.W)
        self.directory_msg.grid(row=1, column=1, sticky=U.sticky_all)

        # Media File
        self.media_label = tkinter.Label(self, text='Media file: ', background=info_bg)
        self.media_label.grid(row=2, column=0, sticky=tkinter.W)
        media_msg = tkinter.Entry(self, textvariable=self.media_file,
                                        state=tkinter.DISABLED,
                                        width=filename_width,
                                        disabledbackground=disabled_bg)
        media_msg.grid(row=2, column=1, sticky=U.sticky_all)
        self.media_load = tkinter.Button(self, text='Load', state=states[0],
                                         command=self.ask_media)
        self.media_load.grid(row=2, column=2, sticky=tkinter.W)

        # Code File
        self.code_label = tkinter.Label(self, text='Code file: ',
                                         background=info_bg)
        self.code_label.grid(row=3, column=0, sticky=tkinter.W)

        code_msg = tkinter.Entry(self, textvariable=self.code_file,
                                       state=tkinter.DISABLED,
                                       width=filename_width,
                                       disabledbackground=disabled_bg)
        code_msg.grid(row=3, column=1, sticky=U.sticky_all)
        self.code_load = tkinter.Button(self, text='Load',
                                        state=states[1],
                                        command=self.ask_code)
        self.code_load.grid(row=3, column=2, sticky=tkinter.W)

        # Data File
        self.data_label = tkinter.Label(self, text='Data file: ',
                                         background=info_bg)
        self.data_label.grid(row=4, column=0, sticky=tkinter.W)
        data_msg = tkinter.Entry(self, textvariable=self.data_file,
                                       state=tkinter.DISABLED,
                                       width=filename_width,
                                       disabledbackground=disabled_bg)
        data_msg.grid(row=4, column=1, sticky=U.sticky_all)
        self.data_load = tkinter.Button(self, text='Load',
                                        state=states[2],
                                        command=self.ask_data)
        self.data_load.grid(row=4, column=2, sticky=tkinter.W)

        self.detach_windows = tkinter.BooleanVar(self, value=parent.detached_layout)
        self.detach_check = tkinter.Checkbutton(
            self, text="Detach windows", variable=self.detach_windows,
            command=parent.switch_session_layout, background=info_bg,
        )
        self.detach_check.grid(row=5, column=0, columnspan=3, sticky="w")

# Interface elements
        self.elements = [self, self.directory_label, self.media_label, self.data_label, self.code_label, self.directory_msg]

        self.bind('<Button-3>', self.change_color)

    def _load_media(self, filename):
        tracks = U.media_track_types(filename)
        if not tracks.intersection({"Video", "Audio"}):
            tkinter.messagebox.showinfo("Cannot load media file", filename, parent=self)
            return False
        if not self.application.make_media_player(filename, has_video="Video" in tracks):
            return False
        path = Path(filename)
        self.directory_msg.config(text=str(path.parent))
        self.media_file.set(path.name)
        return True

    def ask_media(self):
        filename = tkinter.filedialog.askopenfilename(
            parent=self, initialdir=self.application.browse_folder("media")
        )
        if not filename:
            return
        if not self._load_media(filename):
            return
        self.media_load.config(state="disabled")
        self.code_load.config(state="normal")

    def ask_code(self):
        if self.application.control.state in ["c_playing", "s_playing"]:
            self.application.control.dopause()

        filename = tkinter.filedialog.askopenfilename(
            parent=self, initialdir=self.application.browse_folder("data"),
            filetypes=[("Code definition", "*.jod"), ("Legacy code file", "*.cod")],
        )
        if not filename:
            return
        if Path(filename).suffix.lower() != ".jod":
            tkinter.messagebox.showinfo("Cannot load code file", filename, parent=self)
            return
        self.application.make_coding_frame(filename)
        self.code_file.set(filename)
        self.code_load.config(state="disabled")

    def ask_data(self):
        filename = tkinter.filedialog.askopenfilename(
            parent=self, initialdir=self.application.browse_folder("data"),
            filetypes=[("ScySeqTools data file", "*.cdx"), ("All files", "*.*")],
        )
        if filename and self.read_data(filename):
            self.data_load.config(state="disabled")

    def read_data(self, fname):
        with open(fname, "r") as datafile:
            data = json.load(datafile)

        code = data["code"]["filename"]
        media = data["media"]
        if not os.path.exists(media):
            tkinter.messagebox.showinfo("Cannot load media file", media, parent=self)
            return False
        if not self._load_media(media):
            return False
        self.application.state["data_loaded"] = True
        if os.path.exists(code):
            self.application.make_coding_frame(code)
            self.code_file.set(code)
        else:
            tkinter.messagebox.showinfo("Cannot load code file", code, parent=self)

        resume_state = normalize_resume_data(data)
        data["times"] = resume_state["times"]
        data["comments"] = resume_state["comments"]
        self.application.container.update(data)
        self.application.recorded_steps = resume_state["recorded_steps"]
        self.session_path = Path(fname)
        self.data_file.set(str(self.session_path))
        return True

    def save_data(self, record, parent):
        """Write the proposed record before committing the sample in the UI."""
        path = self.session_path
        if path is None:
            folder = self.application.choose_save_folder(parent)
            if folder is None:
                return False
            filename = tkinter.filedialog.asksaveasfilename(
                parent=parent, initialdir=folder, defaultextension=".cdx",
                filetypes=[("ScySeqTools data file", "*.cdx")],
            )
            if not filename:
                return False
            path = Path(filename if filename.lower().endswith(".cdx") else filename + ".cdx")

        # Replace only after the whole record has been written.
        pending = None
        try:
            with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                    delete=False) as datafile:
                pending = Path(datafile.name)
                json.dump(record, datafile)
            pending.replace(path)
        except OSError as error:
            tkinter.messagebox.showerror("Cannot save session", str(error), parent=parent)
            return False
        finally:
            if pending is not None:
                pending.unlink(missing_ok=True)
        self.session_path = path
        self.data_file.set(str(path))
        return True

    def change_color(self, event):
        colortuple = askcolor()
        # print colortuple
        self.configure(background=colortuple[1])
        self.code_label.configure(background=colortuple[1])
        self.media_label.configure(background=colortuple[1])
        self.data_label.configure(background=colortuple[1])
        self.directory_label.configure(background=colortuple[1])
        self.directory_msg.configure(background=colortuple[1])
        self.detach_check.configure(background=colortuple[1])
