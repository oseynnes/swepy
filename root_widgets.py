import tkinter as tk
import tkinter.filedialog as fd
from pathlib import Path

import utils


class MenuBar(tk.Menu):
    """Adding menu bar"""

    def __init__(self, parent):
        super().__init__(parent)

        self.app = parent
        self.path = None

        self.file_menu = tk.Menu(self, tearoff=0)
        self.add_cascade(label='File', underline=0, menu=self.file_menu)
        self.file_menu.add_command(label='Open...', command=lambda: self.app.paths_handler())

        recent_paths = tk.Menu(self.file_menu, tearoff=0)
        paths_list = utils.load_settings('RECENT_PATHS')
        for path in paths_list:
            recent_paths.add_command(label=path, command=lambda x=Path(path): self.app.reset(x))
        self.file_menu.add_cascade(label='Open recent', menu=recent_paths)

        self.file_menu.add_separator()
        self.file_menu.add_command(label='Export to CSV',
                                   command=lambda: self.app.output.save_panel.export('csv'))
        self.file_menu.add_command(label='Export to Excel',
                                   command=lambda: self.app.output.save_panel.export('xlsx'))
        self.file_menu.add_separator()
        self.file_menu.add_command(label='Clear all results', command=lambda: self.app.output.clear_all())
        self.file_menu.add_command(label='Quit', command=quit)

        self.help_menu = tk.Menu(self, tearoff=0)
        self.add_cascade(label='Help', underline=0, menu=self.help_menu)
        self.help_menu.add_command(label='Swepy README', command=lambda: utils.callback('https://tinyurl.com/swepy'))

    def select_files(self):
        filetypes = (('dicom files', '*.dcm'), ('All files', '*.*'))
        temp_path = Path.cwd() / 'src' / 'cache' / 'settings.json'
        if temp_path.exists():
            temp = utils.load_json(temp_path)
            initialdir = Path(temp['RECENT_PATHS'][0]).parent
        else:
            initialdir = '/'
        paths = fd.askopenfilenames(initialdir=initialdir, title="Select dicom file(s)", filetypes=filetypes)
        if paths:
            self.paths = [Path(path) for path in paths]
            return self.paths
        else:
            return
