import tkinter as tk
import tkinter.filedialog as fd
from pathlib import Path
from tkinter import ttk

from swepy.processing import data_utils
from swepy.processing.io import json_io


class MenuBar(tk.Menu):
    """Adding menu bar"""

    def __init__(self, parent):
        super().__init__(parent)

        self.app = parent
        self.path = None

        self.file_menu = tk.Menu(self, tearoff=0)
        self.add_cascade(label='File', underline=0, menu=self.file_menu)
        self.file_menu.add_command(label='Open...', command=lambda: self.app.paths_handler())

        self.history_submenu = tk.Menu(self.file_menu, tearoff=0)
        paths_list = data_utils.get_settings('RECENT_PATHS')
        for path in paths_list:
            self.history_submenu.add_command(label=path, command=lambda x=Path(path): self.app.reset(x))
        self.file_menu.add_cascade(label='Open recent', menu=self.history_submenu)

        self.file_menu.add_separator()
        self.file_menu.add_command(label='Export to CSV',
                                   command=lambda: self.app.output.save_panel.export('csv'))
        self.file_menu.add_command(label='Export to Excel',
                                   command=lambda: self.app.output.save_panel.export('xlsx'))
        self.file_menu.add_separator()
        self.file_menu.add_command(label='Clear all results', command=lambda: self.app.output.clear_results())
        self.file_menu.add_command(label='Clear history', command=lambda: self.delete_history())
        self.file_menu.add_command(label='Quit', command=self.app.destroy)

        self.edit_menu = tk.Menu(self, tearoff=0)
        self.add_cascade(label='Edit', underline=0, menu=self.edit_menu)
        self.edit_menu.add_command(label='Settings', command=lambda: self.open_settings())

        self.help_menu = tk.Menu(self, tearoff=0)
        self.add_cascade(label='Help', underline=0, menu=self.help_menu)
        self.help_menu.add_command(label='Swepy README',
                                   command=lambda: data_utils.callback('https://tinyurl.com/swepy'))

    def delete_history(self):
        self.history_submenu.delete(0, 'end')
        data_utils.delete_settings('RECENT_PATHS')

    def select_files(self):
        filetypes = (('DICOM files', '*.dcm'), ('All files', '*.*'))
        temp_path = Path.cwd() / 'src' / 'cache' / 'settings.json'
        initialdir = '/'
        if temp_path.exists():
            temp = json_io.load_json(temp_path)
            if temp['RECENT_PATHS']:
                initialdir = Path(temp['RECENT_PATHS'][0]).parent
        paths = fd.askopenfilenames(initialdir=initialdir, title="Select DICOM file(s)", filetypes=filetypes)
        if paths:
            self.paths = [Path(path) for path in paths]
            return self.paths
        else:
            return

    def open_settings(self):
        """Instantiate Settings class"""
        settings = Settings(self)
        settings.grab_set()


class Settings(tk.Toplevel):
    """Set controls for app settings"""

    def __init__(self, parent):
        super().__init__(parent)

        self.menu = parent
        self.geometry('300x100')
        self.title('Settings')

        self.cmap_frame = ttk.LabelFrame(self, text='Source of colour map')
        self.cmap_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=5, pady=5)
        self.cmap_labels = {'local_cmap': 'From image',
                            'external_cmap': 'From standard reference'}
        grid_column = 0
        for key, label in self.cmap_labels.items():
            radio = ttk.Radiobutton(self.cmap_frame,
                                    text=label,
                                    value=key,
                                    variable=self.menu.app.view.cmap_loc_var,
                                    command=lambda: self.log_cmap_loc())

            radio.grid(column=grid_column, row=0, ipadx=5, ipady=5)
            grid_column += 1

        self.close_btn = ttk.Button(self, text='Close', command=self.destroy)
        self.close_btn.grid(column=0, row=1, sticky=tk.E, padx=5, pady=5)

    def log_cmap_loc(self):
        data_utils.save_cmap_source(self.menu.app.view.cmap_loc_var.get())
        print(self.menu.app.view.cmap_loc_var.get())
