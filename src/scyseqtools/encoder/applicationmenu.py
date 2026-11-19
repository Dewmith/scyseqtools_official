"""Home screen for the encoder."""

from tkinter import font, ttk


class EncoderHome(ttk.Frame):
    """Choose an encoder task from the home screen."""

    def __init__(self, master):
        super().__init__(master, padding=("28p", "20p"))
        family = font.nametofont("TkDefaultFont", root=master).actual("family")
        heading = ttk.Label(self, text="scyseqtools", font=(family, 25, "bold"))
        heading.grid(row=0, column=0, pady=(0, "10p"))

        style = ttk.Style(self)
        style.configure("EncoderHome.TButton", font=(family, 14), padding=("12p", "6p"))
        actions = (
            ("Define a new code", master.new_code, "5p"),
            ("Start a new session", master.start_session, "5p"),
            ("Retrieve a session", master.retrieve_session, "5p"),
        )
        self.buttons = []
        for row, (label, command, top_gap) in enumerate(actions, start=1):
            button = ttk.Button(self, text=label, command=command, width=22,
                                style="EncoderHome.TButton")
            button.grid(row=row, column=0, sticky="ew", pady=(top_gap, 0))
            self.buttons.append(button)

    def show(self):
        self.master.grid_anchor("center")
        self.grid(row=0, column=0)
        self.buttons[0].focus_set()

    def hide(self):
        self.grid_remove()
        self.master.grid_anchor("nw")
