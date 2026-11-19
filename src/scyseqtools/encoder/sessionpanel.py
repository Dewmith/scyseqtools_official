"""A session panel that can move between the main grid and its own window."""

import tkinter


class SessionPanel(tkinter.Frame):
    def __init__(self, application, title, **grid_position):
        super().__init__(application)
        self.window_title = title
        self.grid_position = grid_position
        self.back_button = application._add_back_button(self)
        self.back_button.grid_remove()
        self.close_command = self.register(application.focus_information)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

    def place_panel(self, detached, visible=True):
        # Query Tk itself so this also restores a partially applied transition.
        floating = self.winfo_toplevel() is self
        if detached and visible:
            if not floating:
                self.grid_forget()
                self.master.wm_manage(self)
            self.tk.call("wm", "title", self, self.window_title)
            self.tk.call("wm", "protocol", self, "WM_DELETE_WINDOW", self.close_command)
            self.back_button.grid()
        else:
            if floating:
                self.master.wm_forget(self)
            self.back_button.grid_remove()
            if visible:
                self.grid(sticky="nsew", **self.grid_position)
            else:
                self.grid_remove()
