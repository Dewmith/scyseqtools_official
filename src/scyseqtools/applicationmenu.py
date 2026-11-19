"""Shared Help menu for the Encoder and Analyser."""

import tkinter
from tkinter import messagebox
import webbrowser


class ApplicationMenu(tkinter.Menu):
    """Keep project help and issue reporting available from the main window."""

    def __init__(self, master):
        super().__init__(master, tearoff=0)
        help_menu = tkinter.Menu(self, tearoff=0)
        self.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(
            label="Report issue", command=lambda: _open_project_page(master, "/issues/new")
        )
        help_menu.add_command(
            label="About", command=lambda: _open_project_page(master, "#readme")
        )


def _open_project_page(parent, destination):
    url = "https://github.com/scyseq-tools/scyseqtools" + destination
    try:
        if webbrowser.open_new_tab(url):
            return
    except (OSError, webbrowser.Error):
        pass

    if messagebox.askyesno(
        "Could not open browser",
        f"Copy this link to the clipboard so you can open it yourself?\n\n{url}",
        parent=parent,
    ):
        parent.clipboard_clear()
        parent.clipboard_append(url)
