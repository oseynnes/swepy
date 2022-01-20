import tkinter as tk
import tkinter.filedialog as fd
from pathlib import Path
import webbrowser

import utils


class MenuBar(tk.Menu):
    """Adding menu bar"""

    def __init__(self, parent):
        super().__init__(parent)

        self.app = parent
        self.path = None

        self.file_menu = tk.Menu(self, tearoff=0)
        self.add_cascade(label='File', underline=0, menu=self.file_menu)
        self.file_menu.add_command(label='Open...', command=lambda: self.app.reset())

        recent_paths = tk.Menu(self.file_menu, tearoff=0)
        paths_list = utils.load_settings('RECENT_PATHS')
        for path in paths_list:
            recent_paths.add_command(label=path, command=lambda x=Path(path): self.app.reset(x))
        self.file_menu.add_cascade(label='Open recent', menu=recent_paths)

        self.file_menu.add_separator()
        self.file_menu.add_command(label='Export to CSV',
                                   command=lambda: self.app.output.save_frame.export_to('csv'))
        self.file_menu.add_command(label='Export to Excel',
                                   command=lambda: self.app.output.save_frame.export_to('xlsx'))
        self.file_menu.add_separator()
        self.file_menu.add_command(label='Clear all results', command=self.clear_all)
        self.file_menu.add_command(label='Quit', command=quit)

        self.help_menu = tk.Menu(self, tearoff=0)
        self.add_cascade(label='Help', underline=0, menu=self.help_menu)
        self.help_menu.add_command(label='Swepy README', command=lambda: self.callback('https://tinyurl.com/swepy'))

    def select_file(self):
        filetypes = (('dicom files', '*.dcm'), ('All files', '*.*'))
        temp_path = Path.cwd() / 'src' / 'cache' / 'settings.json'
        if temp_path.exists():
            temp = utils.load_json(temp_path)
            initialdir = Path(temp['RECENT_PATHS'][0]).parent
        else:
            initialdir = '/'
        path = fd.askopenfilename(initialdir=initialdir, title="Select dicom file", filetypes=filetypes)
        if path:
            self.path = Path(path)
            utils.save_path(str(self.path.resolve()))
            return self.path
        else:
            return

    def callback(self, url):  #TODO: change to static (don't need self)
        webbrowser.open_new(url)

    def clear_all(self):
        self.clear_treeview()
        self.clear_figure()
        self.clear_pickle()

    def clear_treeview(self):
        tree = self.app.output.files_panel.tv
        tree.delete(*tree.get_children())

    def clear_figure(self):
        fig_lf = self.app.output.fig_frame.lf0
        for widget in fig_lf.winfo_children():
            widget.destroy()

    @staticmethod
    def clear_pickle():
        src_path = Path.cwd() / 'src'
        paths = list(Path(src_path).rglob('*.pickle'))
        for path in paths:
            path.unlink()

