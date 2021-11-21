import tkinter as tk
from tkinter import ttk

import numpy as np


class ImgPanel(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        self.roi_coords = np.empty([4, ])
        self.rect = self.start_x = self.start_y = None
        self.x = self.y = 0

        self.canvas = tk.Canvas(self, width=720,
                                height=540, bg='black', cursor="cross")
        self.canvas.grid(row=1, column=1, rowspan=3,
                         sticky=tk.NSEW, padx=5, pady=5)
        self.grid(row=1, column=1, rowspan=3,
                  sticky=tk.NSEW, padx=5, pady=5)

        self.canvas.bind('<Button-1>', self.on_button_press)
        self.canvas.bind('<B1-Motion>', self.on_move_press)
        self.canvas.bind('<ButtonRelease-1>', self.on_button_release)

    def on_button_press(self, event):
        # save mouse drag start position
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)
        # create rectangle if not yet exist
        if not self.rect:
            self.rect = self.canvas.create_rectangle(self.x, self.y, 1, 1, outline='red')

    def on_move_press(self, event):
        cur_x, cur_y = (event.x, event.y)
        # expand rectangle as you drag the mouse
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_button_release(self, event):
        self.roi_coords = np.array(self.canvas.coords(self.rect))


class TopPanel(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        options = {'fill': 'x', 'padx': 5, 'pady': 5}

        self.grid(row=0, column=1, sticky=tk.EW)

        self.img_name = ttk.Label(self, anchor=tk.CENTER, text=None)
        self.img_name.pack(**options)


class LeftPanel(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        options = {'fill': 'x', 'padx': 5, 'pady': 5}

        self.grid(row=1, column=0, rowspan=2, sticky=tk.NSEW)

        self.btn_open = ttk.Button(self, text='Open dicom file')
        self.btn_open.pack(**options)

        self.fhz_frame = ttk.Frame(self)
        self.fhz_frame.pack()
        self.fhz_label = ttk.Label(self.fhz_frame, text='SWE fhz:')
        self.fhz_label.pack(side='left', **options)
        self.swe_fhz = ''
        self.usr_value = tk.StringVar()
        self.usr_entry = ttk.Entry(self.fhz_frame, width=3, textvariable=self.usr_value)
        self.usr_entry.pack(side='left', **options)

        columns = ('dcm_property', 'value')
        self.variables = ('No. of frames', 'No. of rows', 'No. of columns', 'B mode Fhz')
        self.values = (None,)
        self.tv = ttk.Treeview(self, columns=columns, show='headings')
        self.tv.heading('dcm_property', text="DCM Property")
        self.tv.column('dcm_property', width=100)
        self.tv.heading("value", text="Value")
        self.tv.column('value', width=100)
        self.tv.pack(**options)

        self.btn_analyse = ttk.Button(self, text="Analyse")
        self.btn_analyse.pack(**options)  # TODO: link to methods (class?)


class DisplayControls(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        self.grid(row=4, column=1, sticky=tk.EW)

        self.pause = False  # control video pause
        self.play_btn = ttk.Button(self, width=5, text="Play")
        self.play_btn.pack(side='left')

        self.current_value = tk.DoubleVar()
        self.slider = ttk.Scale(self, from_=0, to=0, variable=self.current_value)
        self.slider['state'] = 'disabled'
        self.slider.pack(side='left', padx=5, pady=5, expand=True, fill='both')

        self.frame_label = ttk.Label(self, width=10, text='')
        self.frame_label.pack(side='left')
