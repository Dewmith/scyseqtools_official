"""
Main application module

.. todo:: All the "print" should be moved to some logging process...

We need doc
"""

from pathlib import Path
import webbrowser
# import json
#import time

import tkinter
from tkinter import filedialog, ttk
import tkinter.messagebox
import tkinter.simpledialog

# tk colors : https://www.tcl.tk/man/tcl/TkCmd/colors.html

# from datetime import datetime # datetime.now().strftime('%c')

import scyseqtools.encoder.utils as U
from scyseqtools.encoder.infoframe import InfoFrame
from scyseqtools.encoder.playercontrol import PlayerControl
from scyseqtools.encoder.playerbackends import prepare_video_display
from scyseqtools.encoder.sessionpanel import SessionPanel
from scyseqtools.encoder.applicationmenu import ApplicationMenu, EncoderHome
from scyseqtools.encoder.codingframe import FrameworkFrame
from scyseqtools.encoder.config import (
    get_cwd_file_path,
    get_encoder_layout,
    remember_encoder_layout,
    load_encoder_config,
)
from scyseqtools.encoder.newcode import NewCode

__version__ = '0.9'
__author__ = 'L. Pezard'
__licence__ = 'GPL'


class Application(tkinter.Tk):
    """
    Main ScySeqTools application class
    """
    def __init__(self):
        prepare_video_display()
        tkinter.Tk.__init__(self)
        self.title("scyseqtools")
        self.resizable(tkinter.TRUE, tkinter.TRUE)
        # Menu
        self.menu = ApplicationMenu(master=self)
        self['menu'] = self.menu
        self._reset_workflow()
        config = load_encoder_config(required_sections=("application",))
        self._cwd_file = get_cwd_file_path(config)
        self._default_folder = Path(config["application"]["default_cwd"]).expanduser()
        self._last_project = None
        if self._cwd_file.is_file():
            saved = self._cwd_file.read_text(encoding="utf-8").rstrip("\r\n")
            if saved and Path(saved).expanduser().is_dir():
                self._last_project = Path(saved).expanduser()
        self._save_project = None
        self.protocol("WM_DELETE_WINDOW", self.quit_session)
        self.home = EncoderHome(self)
        self._back_button = self._add_back_button(self, columnspan=2)
        self._back_button.grid_remove()
        self.home.show()

    def _reset_workflow(self):
        """Start with fresh editor, playback, and observation state."""
        self.state = {'media_loaded': False,
                      'code_loaded': False,
                      'data_loaded': False}

        self.__time_step = None

        self.container = {'history': [], # [(date, observer, comment), ...]
                          'media': '', # path for the media file
                          'code': {}, # dictionary taken from the code file
                          'times': [], # sample times (in ms) taken from the player
                          'comments': [], # sample comments taken from codingframe
                          'data': {},
                          'version': __version__} # data

        self._context = "standard"
        self.newcode = None
        self._editor_focus_job = None
        self.info = None
        self.control = None
        self.framework = None
        self._control_window = None
        self._coding_window = None
        self._video_window = None
        self.video_surface = None
        self.recorded_steps = set()
        self.coding_workspace = None

# Working directory

    def browse_folder(self, subfolder=None):
        """Suggest an existing directory without creating project folders."""
        root = self._save_project or self._last_project
        if root is None or not root.is_dir():
            root = self._default_folder if self._default_folder.is_dir() else Path.home()
        if subfolder and (root / subfolder).is_dir():
            return root / subfolder
        return root

    def choose_save_folder(self, parent):
        """Choose the project once per launch and prepare its data directory."""
        project = self._save_project
        if project is None:
            selected = filedialog.askdirectory(
                parent=parent, title="Choose working directory",
                initialdir=self.browse_folder(), mustexist=True,
            )
            if not selected:
                return None
            project = Path(selected)
        try:
            folder = project / "data"
            folder.mkdir(exist_ok=True)
            if self._save_project is None:
                self._cwd_file.write_text(str(project), encoding="utf-8")
        except OSError as error:
            self._save_project = None
            tkinter.messagebox.showerror("Cannot prepare save folder", str(error), parent=parent)
            return None
        self._save_project = project
        return folder

# Home screen and menu commands
#-----------------------

    def _add_back_button(self, window, columnspan=1):
        button = ttk.Button(window, text="Back to main menu",
                            command=lambda: self._request_home(window))
        button.grid(row=0, column=0, columnspan=columnspan, sticky="w",
                    padx="6p", pady="4p")
        return button

    def _enter_workflow(self):
        self.cwd = self._save_project or self._last_project
        self.home.hide()
        self._back_button.grid()

    def _request_home(self, window):
        has_work = any(self.state.values()) or (
            self.newcode is not None and self.newcode.has_input()
        )
        if has_work and not tkinter.messagebox.askokcancel(
            "Back to main menu",
            "Return to the main menu? Any unsaved edits will be discarded. "
            "Files you already saved will be kept.",
            parent=window, default="cancel",
        ):
            return
        self._return_home()

    def _return_home(self):
        self._close_workflow()
        self._reset_workflow()
        self._back_button.grid_remove()
        for column in (0, 1):
            self.grid_columnconfigure(column, weight=0)
        for row in (1, 2, 3):
            self.grid_rowconfigure(row, weight=0)
        self.title("scyseqtools")
        self.deiconify()
        self.lift()
        self.home.show()

    def new_code(self):
        """Application for defining a new coding framework.
        """
        self._enter_workflow()
        self.newcode = NewCode(parent=self)
        self.newcode.grid(row=1, column=1, sticky=U.sticky_all)
        self._editor_focus_job = self.after_idle(self.newcode.focus_first_field)

    def finish_new_code(self):
        """Return to the home screen after saving a code."""
        self._return_home()

    def start_session(self):
        self._open_session((tkinter.NORMAL, tkinter.DISABLED, tkinter.DISABLED))

    def retrieve_session(self):
        self._open_session((tkinter.DISABLED, tkinter.DISABLED, tkinter.NORMAL))

    def _open_session(self, states):
        self._enter_workflow()
        self.encoder_layout = get_encoder_layout(self.cwd)
        self.info = InfoFrame(self, states=states)
        self._place_session(self.detached_layout)

    def report_issue(self):
        self._open_project_page("/issues/new")

    def about_handler(self):
        self._open_project_page("#readme")

    def _open_project_page(self, destination):
        url = "https://github.com/scyseq-tools/scyseqtools" + destination
        try:
            if webbrowser.open_new_tab(url):
                return
        except (OSError, webbrowser.Error):
            pass

        if tkinter.messagebox.askyesno(
            "Could not open browser",
            f"Copy this link to the clipboard so you can open it yourself?\n\n{url}",
            parent=self,
        ):
            self.clipboard_clear()
            self.clipboard_append(url)

    @property
    def detached_layout(self):
        """Whether encoder content should be split into separate windows."""
        return self.encoder_layout == "detached"

    def switch_session_layout(self):
        detached = self.info.detach_windows.get()
        if detached == self.detached_layout:
            return
        try:
            self._place_session(detached)
            # A user-sized Information window may be too small for the full grid.
            self.geometry("")
        except tkinter.TclError as error:
            self.info.detach_windows.set(self.detached_layout)
            self._place_session(self.detached_layout)
            tkinter.messagebox.showerror("Cannot switch layout", str(error), parent=self)
            return
        self.encoder_layout = "detached" if detached else "embedded"
        try:
            remember_encoder_layout(self.encoder_layout)
        except OSError as error:
            tkinter.messagebox.showwarning("Cannot remember layout", str(error), parent=self)

    def _place_session(self, detached):
        if not detached and self.coding_workspace is None:
            self.__make_coding_workspace()
        has_video = self._video_window is not None
        side_column = 1 if has_video and not detached else 0
        title = "Information" if detached else "Encoder"
        self.title(f"ScySeqTools - {title} - version: {__version__}")
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)
        self.rowconfigure(1, weight=1)
        self.rowconfigure(3, weight=int(not detached))
        self.info.grid(row=1, column=side_column, sticky="nsew")
        if has_video:
            self._video_window.place_panel(detached)
        if self._control_window is not None:
            self._control_window.grid_position["column"] = side_column
            self._control_window.place_panel(detached)
        if self._coding_window is not None:
            self._coding_window.place_panel(detached, visible=not detached or self.framework is not None)

    def _session_panel(self, title, **position):
        return SessionPanel(self, f"ScySeqTools - {title} - version: {__version__}", **position)

    def focus_information(self):
        self.deiconify()
        self.lift()
        self.info.detach_check.focus_force()

    def _close_workflow(self):
        if self._editor_focus_job is not None:
            self.after_cancel(self._editor_focus_job)
        if self.control is not None and self.control.winfo_exists():
            self.control.shutdown()

        for widget in (self._control_window, self._coding_window, self._video_window,
                       self.info, self.newcode):
            if widget is not None and widget.winfo_exists():
                widget.destroy()

    def quit_session(self):
        """Close the current workflow and exit the encoder."""
        self._close_workflow()
        self.destroy()

# Functions related to infoframe
#-------------------------------

    def make_media_player(self, fname, has_video=None):
        """Map the drawing surface before the backend starts playback."""
        if has_video is None:
            has_video = "Video" in U.media_track_types(fname)
        self._control_window = self._session_panel("Control", row=2, column=0)
        try:
            window_id = None
            if has_video:
                self._video_window = self._session_panel("Video", row=1, column=0, rowspan=2)
                self.video_surface = tkinter.Frame(self._video_window, background="black",
                                                   width=480, height=270)
                self.video_surface.grid(row=1, column=0, sticky="nsew")
            self._place_session(self.detached_layout)
            if has_video:
                self.update_idletasks()
                window_id = self.video_surface.winfo_id()
            self.control = PlayerControl(self._control_window, fname, application=self,
                                         window_id=window_id)
            self.control.grid(row=1, column=0, sticky="nsew")
        except Exception as error:
            if self.control is not None:
                self.control.shutdown()
            self._control_window.destroy()
            if self._video_window is not None:
                self._video_window.destroy()
            self.control = self._control_window = None
            self.video_surface = self._video_window = None
            self._place_session(self.detached_layout)
            tkinter.messagebox.showerror("Cannot open media player", str(error), parent=self)
            return False
        self.state['media_loaded'] = True
        self.container['media'] = Path(fname).absolute().as_posix()
        return True

    def make_coding_frame(self, fname):
        """
        creates the coding frame
        """
        self.__make_coding_workspace()
        self.framework = FrameworkFrame(
            parent=self.coding_workspace,
            filename=fname,
            application=self,
        )
        self.framework.grid(row=0, column=0, sticky=U.sticky_all,
                            padx=20, pady=20)
        self.state['code_loaded'] = True
        self._place_session(self.detached_layout)

    def __make_coding_workspace(self):
        """
        Create the lower yellow area that holds coding widgets.
        """
        if self.coding_workspace is not None and self.coding_workspace.winfo_exists():
            return

        config = load_encoder_config(
            self.cwd, required_sections=("codingframework",)
        )
        coding_config = config["codingframework"]
        self._coding_window = self._session_panel("Coding framework", row=3, column=0, columnspan=2)
        self.coding_workspace = tkinter.LabelFrame(self._coding_window)
        self.coding_workspace.configure(
            background=coding_config["background"],
            borderwidth=coding_config.getint("borderwidth"),
            padx=20,
            pady=20,
            relief=coding_config["relief"],
            text='Coding framework: ',
            font=('bold',),
        )
        self.coding_workspace.grid(row=1, column=0, sticky="nsew")
        self.coding_workspace.grid_columnconfigure(0, weight=1)
        self.coding_workspace.grid_columnconfigure(1, weight=1)
        self.coding_workspace.grid_rowconfigure(0, weight=1)

    @property
    def context(self):
        return self._context

    @context.setter
    def context(self, value):
        if value == "initial":
            self._context = "processing"
            print('Context Initial')
            self.control.config_buttons({self.control.play_but : 'normal',
                                    self.control.back_but : 'disabled',
                                    self.control.forward_but : 'disabled',
                                    self.control.mode_check : 'disabled',
                                    self.control.period_ent : 'disabled',
                                    self.control.time_ent: 'disabled'})
            assert len(self.control.times) == 0
            self.control.times.append(self.control.time)

            self.container['times'] = self.control.times
            self.container['data'] = self.framework.data

            self.__time_step = 0
            print('TIME_STEP: ', self.time_step)

        elif value == "resume":
            self._context = "processing"
            print('Context Resume session')
            #### leomodif : j'ai commenté le premier bouton et
            #### je l'ai réactivé quand on clique sur record
            self.control.config_buttons({#self.control.play_but : 'normal',
                                    self.control.back_but : 'disabled',
                                    self.control.forward_but : 'disabled',
                                    self.control.mode_check : 'disabled',
                                    self.control.period_ent : 'disabled',
                                    self.control.time_ent: 'disabled'})

            # assert(len(self.control.times) == 0)
            # self.control.times.append(self.control.time)
            # self.container['times'] = self.control.times
            # self.container['data'] = self.framework.data
            # self.container['media'] = self.info.media_file.get()

            self.control.times = self.container['times']
            self.framework.data = self.container['data']
            self.framework.coding_comments = self.container['comments']
            # self.container['media'] = self.info.media_file.get()

            self.time_step = 'last_recorded'
            print('TIME_STEP: ', self.time_step)

        elif value == "processing":
            print('Context Processing')
            print("Recorded steps : ", self.recorded_steps)
            self.control.play_but.config(state='normal')
            # if self.time_step == self.times_length - 1 :
            #     self.control.forward_but.config(state='disabled')
            #     self.control.back_but.config(state='normal')
            # elif self.time_step == 0 :
            #     self.control.back_but.config(state='disabled')
            # else:
            #     self.control.back_but.config(state='normal')

            # if len(self.recorded_steps) > self.time_step :
            #     self.control.forward_but.config(state='normal')

            if self.time_step == 0 :
                self.control.back_but.config(state='disabled')
            else:
                self.control.back_but.config(state='normal')

            if len(self.recorded_steps) > self.time_step :
                self.control.forward_but.config(state='normal')
            else :
                self.control.forward_but.config(state='disabled')

            self.framework.display_codes(self.time_step)

        elif value == 'not_recorded':
            self.control.config_buttons({self.control.play_but : 'disabled',
                                         self.control.back_but : 'disabled',
                                         self.control.forward_but : 'disabled',
                                         self.control.mode_check : 'disabled',
                                         self.control.period_ent : 'disabled',
                                         self.control.time_ent: 'disabled'})
            self.framework.config_processing_buttons('normal')
            # self.info.save_data()

        elif value == 'standard':
            if self.state['code_loaded'] :
                if self.control.state == 'paused' :
                    self.framework.spec_frame.start_but.config(state='normal')

                elif self.control.state in ['s_playing', 'c_playing']:
                    self.framework.spec_frame.start_but.config(state='disabled')

        else: # FIXME: raise error?
            pass

    @property
    def times_length(self):
        return len(self.control.times)

    @property
    def time_step(self):
        return self.__time_step

    @time_step.setter
    def time_step(self, value):

        if value == '1p':
            if self.control.time > self.control.times[-1]:
                self.control.times.append(self.control.time)
                self.__time_step += 1
            else:
                self.__time_step = min(self.__time_step + 1, self.times_length-1)
                self.control.time = self.control.times[self.time_step]
            self.framework.config_processing_buttons('normal')

        elif value == 1:
            self.__time_step = min(self.__time_step + 1, self.times_length-1)
            self.control.time = self.control.times[self.time_step]
            self.framework.config_processing_buttons('disabled')

        elif value == -1:
            self.__time_step = max(0, self.__time_step - 1)
            self.control.time = self.control.times[self.time_step]
            self.framework.config_processing_buttons('disabled')

        elif value == 'last':
            self.__time_step = self.times_length - 1
            if self.control.times:
                self.control.time = self.control.times[-1]
        elif value == 'last_recorded':
            if self.recorded_steps:
                self.__time_step = max(self.recorded_steps)
            else:
                self.__time_step = max(0, self.times_length - 1)
            if self.control.times:
                time_index = min(self.__time_step, self.times_length - 1)
                self.control.time = self.control.times[time_index]
        else:
            # raise error ?
            pass

        self.container['times'] = self.control.times
        self.context = "processing"

        print('TIME_STEP: ', self.time_step)
        print(self.control.times)

# FIXME: Not sure this is still needed
#    def disable_load_data(self):
#        self.menu.fileMenu.entryconfig(4, state=tkinter.DISABLED)
#        self.info.data_load.config(state=tkinter.DISABLED)
#
#    def disable_load_media(self):
#        self.menu.fileMenu.entryconfig(3, state=tkinter.DISABLED)
#        self.info.media_load.config(state=tkinter.DISABLED)
#
#    def disable_load_code(self):
#        self.menu.fileMenu.entryconfig(2, state=tkinter.DISABLED)
#        self.info.code_load.config(state=tkinter.DISABLED)
#
#    def enable_load_data(self):
#        self.menu.fileMenu.entryconfig(4, state=tkinter.NORMAL)
#        self.info.data_load.config(state=tkinter.NORMAL)
#
#    def freeze(self):
#        """ cannot change step
#        """
#        self.control.mode_check.configure(state=tkinter.DISABLED)
#        self.control.period_ent.configure(state=tkinter.DISABLED)
#        self.control.time_ent.configure(state=tkinter.DISABLED)

#    def get_mode_and_period(self, encoding):
#        period = encoding['period']
#
#        if period is None:
#            # self.player_mode.set("continuous")
## FIXME: est que player ne serait pa mieux que control?
#            self.control.mode = "continuous"
#            tkinter.messagebox.showinfo('Continuous not implemented',
#                                   'Irregular sampling not implemented')
#            raise NotImplementedError()
#        else:
#            #self.player_mode.set("regular")
#            self.control.mode = "regular"
#            # self.period_display.set(str(period))

def _run_application():
    """Launch the encoder home screen."""
    Application().mainloop()


if __name__ == "__main__":
    _run_application()
