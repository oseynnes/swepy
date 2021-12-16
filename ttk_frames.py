import tkinter as tk
from pathlib import Path
from tkinter import ttk
import tkinter.filedialog as fd

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
        self.file_menu.add_command(label='Export')  # TODO: Export results command
        self.file_menu.add_separator()
        self.file_menu.add_command(label='Clear all results')  # TODO: Export results command
        self.file_menu.add_command(label='Quit', command=quit)

        self.help_menu = tk.Menu(self, tearoff=0)
        self.add_cascade(label='Help', underline=0, menu=self.help_menu)
        self.help_menu.add_command(label='Swepy README')

    def select_file(self):
        filetypes = (('dicom files', '*.dcm'), ('All files', '*.*'))
        initialdir = self.path.parent if self.path else '/'
        path = fd.askopenfilename(initialdir=initialdir, title="Select dicom file", filetypes=filetypes)
        self.path = Path(path)
        # self.path = Path('data/C0000004.dcm')  # temporary skip file dialogue during devel
        return self.path


class ImgPanel(ttk.Frame):
    """Panel of GUI displaying images"""

    def __init__(self, parent):
        super().__init__(parent)

        self.roi_coords = None
        self.rect1 = self.rect2 = self.start_x = self.start_y = None
        self.x = self.y = 0

        self.canvas = tk.Canvas(self, width=720, height=540, bg='black', cursor="cross")
        self.canvas.grid(row=1, column=1, rowspan=3, sticky=tk.NSEW, padx=5, pady=5)
        self.grid(row=1, column=1, rowspan=3, sticky=tk.NSEW, padx=5, pady=5)
        self.fov_coords = {'x0': 0, 'y0': 0,
                           'x1': int(self.canvas['width']), 'y1': int(self.canvas['height']) / 2}

    def activate_draw(self):
        self.canvas.bind('<Button-1>', self.on_button_press)
        self.canvas.bind('<B1-Motion>', self.on_move_press)
        self.canvas.bind('<ButtonRelease-1>', self.on_button_release)

    def isin_fov(self):
        in_x_bounds = self.fov_coords['x0'] <= self.start_x <= self.fov_coords['x1']
        in_y_bounds = self.fov_coords['y0'] <= self.start_y <= self.fov_coords['y1']
        return in_x_bounds and in_y_bounds

    def set_rois(self):
        if self.roi_coords:
            self.draw_rois(self.roi_coords['x0'],
                           self.roi_coords['y0'],
                           self.roi_coords['x1'],
                           self.roi_coords['y1'])

    def draw_rois(self, x1, y1, x2, y2):
        if self.rect1:
            self.del_rois()
        self.rect1 = self.canvas.create_rectangle(x1, y1, x2, y2, outline='red')
        self.rect2 = self.canvas.create_rectangle(x1, y1 + 225, x2, y2 + 225, outline='red')

    def del_rois(self):
        self.canvas.delete(self.rect1, self.rect2)

    def on_button_press(self, event):
        # save mouse drag start position
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)
        if not self.rect1:
            self.draw_rois(self.x, self.y, 1, 1)

    def on_move_press(self, event):
        # expand rectangle as you drag the mouse
        if self.isin_fov():
            cur_x, cur_y = (event.x, event.y)
            self.canvas.coords(self.rect1, self.start_x, self.start_y, cur_x, cur_y)
            self.canvas.coords(self.rect2, self.start_x, self.start_y + 225, cur_x, cur_y + 225)

    def on_button_release(self, event):
        keys = ('x0', 'y0', 'x1', 'y1')
        self.roi_coords = dict(zip(keys, self.canvas.coords(self.rect1)))
        self.roi_coords = {k: int(v) for k, v in self.roi_coords.items()}


class TopPanel(ttk.Frame):
    """Panel of GUI displaying file name"""

    def __init__(self, parent):
        super().__init__(parent)
        options = {'fill': 'x', 'padx': 5, 'pady': 5}

        self.grid(row=0, column=1, sticky=tk.EW)

        self.img_name = ttk.Label(self, anchor=tk.CENTER, text='')
        self.img_name.pack(**options)


class LeftPanel(ttk.Frame):
    """Panel of GUI displaying widgets related to file opening and analysis"""

    def __init__(self, parent):
        super().__init__(parent)

        self.grid(row=1, column=0, rowspan=3, sticky=tk.NSEW)

        self.input_frame = ttk.LabelFrame(self, text='User input')
        self.input_frame.grid(row=0, column=0, sticky=tk.NSEW)

        fhz_label = ttk.Label(self.input_frame, text='SWE fhz:')
        fhz_label.grid(column=0, row=0, sticky=tk.W, padx=5)
        self.usr_fhz = tk.StringVar()
        self.fhz_entry = ttk.Entry(self.input_frame, width=4, textvariable=self.usr_fhz)
        self.fhz_entry.grid(column=1, row=0, sticky=tk.E, padx=5)

        scale_label = ttk.Label(self.input_frame, text='max. scale:')
        scale_label.grid(column=0, row=1, sticky=tk.W, padx=5)
        self.usr_scale = tk.StringVar()
        self.scale_entry = ttk.Entry(self.input_frame, width=4, textvariable=self.usr_scale)
        self.scale_entry.grid(column=1, row=1, sticky=tk.E, padx=5)

        self.usr_params = utils.load_settings('SWE_PARAM')
        if self.usr_params:
            self.usr_fhz.set(self.usr_params[0])
            self.usr_scale.set(self.usr_params[1])

        self.enter_btn = ttk.Button(self.input_frame, text='OK', width=2)
        self.enter_btn.grid(column=1, row=3, sticky=tk.E, padx=5, pady=5)

        self.space_frame = ttk.Frame(self)
        self.space_frame.grid(row=1, column=0, sticky=tk.NSEW)
        spacer = tk.Label(self.space_frame, text='')
        spacer.grid()

        self.tree_frame = ttk.Frame(self)
        self.tree_frame.grid(row=2, column=0, sticky=tk.NSEW)
        columns = ('dcm_property', 'value')
        self.variables = ('No. of frames', 'No. of rows', 'No. of columns', 'B mode Fhz')
        self.values = (None,)
        self.tv = ttk.Treeview(self.tree_frame, columns=columns, show='headings')
        self.tv.heading('dcm_property', text="DCM Property")
        self.tv.column('dcm_property', width=100)
        self.tv.heading("value", text="Value")
        self.tv.column('value', width=50)
        self.tv.grid(sticky=tk.NSEW)

        self.reset_roi_btn = ttk.Button(self.tree_frame, text="Reset ROI", width=8)
        self.reset_roi_btn.grid(sticky=tk.W)

        self.analyse_btn = ttk.Button(self.tree_frame, text="Analyse", width=8)
        self.analyse_btn.grid(sticky=tk.W)


class DisplayControls(ttk.Frame):
    """Panel of GUI displaying widgets to display images"""

    def __init__(self, parent):
        super().__init__(parent)

        self.grid(row=4, column=1, sticky=tk.EW)
        # self.columnconfigure(1, weight=4)
        # self.rowconfigure(4, weight=1)

        self.pause = False  # control video pause
        self.play_btn = ttk.Button(self, width=5, text="Play")
        self.play_btn.pack(side='left')

        self.current_value = tk.DoubleVar()
        self.slider = ttk.Scale(self, from_=0, to=0, variable=self.current_value)
        self.slider['state'] = 'disabled'
        self.slider.pack(side='left', padx=5, pady=5, expand=True, fill='both')

        self.frame_label = ttk.Label(self, width=10, text='')
        self.frame_label.pack(side='left')
