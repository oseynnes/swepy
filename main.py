import tkinter as tk
from tkinter import ttk

import numpy as np
from PIL import ImageTk, Image

import utils
from processing import Data


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

        self.swe_fhz = 1

        options = {'fill': 'x', 'padx': 5, 'pady': 5}

        self.grid(row=1, column=0, rowspan=2, sticky=tk.NSEW)

        self.btn_open = ttk.Button(self, text='Open dicom file')
        self.btn_open.pack(fill='x', expand=True)

        self.fhz_frame = ttk.Frame(self)
        self.fhz_frame.pack()
        self.fhz_label = ttk.Label(self.fhz_frame, text='SWE fhz:')
        self.fhz_label.pack(side='left', **options)
        self.usr_value = tk.StringVar()
        self.usr_entry = ttk.Entry(self.fhz_frame, width=3, textvariable=self.usr_value)
        self.usr_entry.pack(side='left', **options)
        self.usr_entry.focus()

        # Left menu info table
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


class View(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        self.ds = None
        self.img_array = None
        self.img = None
        self.img_name = None

        self.controller = None

        self.img_panel = ImgPanel(self)
        self.canvas = self.img_panel.canvas
        self.roi_coords = None
        self.n_frame = 0
        self.current_frame = 0

        self.top = TopPanel(self)

        self.left_panel = LeftPanel(self)
        self.left_panel.btn_open['command'] = self.load_file
        self.swe_fhz = self.left_panel.swe_fhz
        self.left_panel.usr_entry.bind('<Return>', self.save_fhz)
        self.left_panel.btn_analyse['command'] = self.analyse

        self.controls = DisplayControls(self)
        self.controls.slider['command'] = self.update_slider
        self.controls.play_btn['command'] = self.toggle_play_pause

    def set_controller(self, controller):
        self.controller = controller

    def analyse(self):
        self.roi_coords = self.img_panel.roi_coords
        # TODO: continue function:
        #                   - move function to controller
        #                   - select roi in each frame
        #                   - filter voids
        #                   - get relevant variables of SWE from RGB values in ROI and scale bar
        pass

    def save_fhz(self, event):
        try:
            float(self.left_panel.usr_value.get())
        except ValueError:
            utils.warn_no_number()
            return
        self.swe_fhz = self.left_panel.usr_value.get()
        if 'swe_row' in self.left_panel.tv.get_children():
            self.left_panel.tv.delete('swe_row')
        self.left_panel.tv.insert(parent='',
                                  index=tk.END,
                                  iid='swe_row',
                                  values=('SWE Fhz',self.swe_fhz))

    def update_slider(self, event):
        if int(self.controls.current_value.get()) < self.n_frame:
            self.current_frame = int(self.controls.current_value.get())
            self.update_frame(self.current_frame)

    def toggle_play_pause(self):
        if self.controls.pause:
            self.controls.pause = False
            self.controls.play_btn.config(text='Play')
            self.after_cancel(self.after_id)
        else:
            self.controls.pause = True
            self.controls.play_btn.config(text='Pause')
            self.play_video()

    def play_video(self):
        if self.ds:
            self.controls.current_value.set(self.current_frame)
            self.update_frame(self.current_frame)
            self.current_frame += 1
            if self.current_frame < self.n_frame:
                self.after_id = self.after(50, self.play_video)  # 50ms
            else:
                self.controls.pause = False
                self.controls.play_btn.config(text='Play')
                self.current_frame = 0
        else:
            utils.warn_no_video()
            return

    def update_dcm_info(self):
        self.left_panel.values = (self.ds.NumberOfFrames,
                                  self.ds.Rows,
                                  self.ds.Columns,
                                  self.ds.RecommendedDisplayFrameRate)  # get dcm info
        rows = (zip(self.left_panel.variables, self.left_panel.values))
        for row in rows:
            self.left_panel.tv.insert(parent='', index=tk.END, values=row)

    def activate_slider(self):
        # set max number of frames
        self.n_frame = self.ds.NumberOfFrames
        self.controls.slider.config(to=self.n_frame)
        self.controls.slider.config(state='normal')  # activate slider

    def set_img_name(self):
        self.top.img_name.config(text=self.img_name)

    def update_frame(self, frame_idx):
        self.img = ImageTk.PhotoImage(image=Image.fromarray(self.img_array[frame_idx]))
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.img)

    def load_file(self):
        self.ds, self.img_array, self.img_name = self.controller.get_dicom()
        self.update_frame(self.current_frame)
        self.activate_slider()
        self.update_dcm_info()
        self.set_img_name()


class Controller:
    def __init__(self, data, view):
        self.data = data
        self.view = view

    def save_roi_coords(self, coords):
        self.data.roi_coords = coords

    def get_dicom(self):
        # TODO: link to a ttk.Progressbar widget (dicom loading is a few seconds)
        self.data.load_dicom()
        return self.data.ds, self.data.img_array, self.data.img_name


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        options = {'fill': 'x', 'padx': 5, 'pady': 5}

        self.title('SwePy')
        window_width = 960
        window_height = 650
        utils.set_win_geometry(self, window_width, window_height)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=4)

        # create a model
        data = Data()

        # create a view and place it on the root window
        view = View(self)
        view.grid(row=0, column=0, rowspan=4, sticky=tk.NSEW)

        # # create a controller
        controller = Controller(data, view)

        # # set the controller to view
        view.set_controller(controller)


if __name__ == '__main__':
    app = App()
    app.mainloop()

    # TODO: - move frames and canvas to subclasses
    #       - add doctrings to class(es) and functions
